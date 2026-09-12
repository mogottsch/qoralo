package dev.vibevoice.podcast.generation

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import dev.vibevoice.podcast.data.ArtifactStore
import dev.vibevoice.podcast.data.EpisodePhase
import dev.vibevoice.podcast.data.JobKind
import dev.vibevoice.podcast.data.PodcastDatabase
import dev.vibevoice.podcast.data.PodcastRepository
import dev.vibevoice.podcast.model.GemmaModelContract
import dev.vibevoice.podcast.model.ModelRoute
import dev.vibevoice.podcast.model.SupertonicModelContract
import dev.vibevoice.podcast.model.VerifiedModelPack
import dev.vibevoice.podcast.runtime.AudioMetadata
import dev.vibevoice.podcast.runtime.EpisodeOutline
import dev.vibevoice.podcast.runtime.FrozenChapter
import dev.vibevoice.podcast.runtime.LlmEngine
import dev.vibevoice.podcast.runtime.OutlineChapter
import dev.vibevoice.podcast.runtime.RuntimeProvenance
import dev.vibevoice.podcast.runtime.SourceMaterial
import dev.vibevoice.podcast.runtime.TtsEngine
import dev.vibevoice.podcast.runtime.WavInspector
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.json.JSONObject
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.io.File
import java.io.RandomAccessFile

@RunWith(RobolectricTestRunner::class)
class GenerationCoordinatorTest {
    @get:Rule val temporary = TemporaryFolder()
    private lateinit var database: PodcastDatabase
    private lateinit var repository: PodcastRepository
    private lateinit var artifacts: ArtifactStore

    @Before fun setUp() {
        database = Room.inMemoryDatabaseBuilder(ApplicationProvider.getApplicationContext<Context>(), PodcastDatabase::class.java).allowMainThreadQueries().build()
        artifacts = ArtifactStore(temporary.newFolder("episodes"), temporary.newFolder("models"))
        repository = PodcastRepository(database, artifacts, providerAdmission = false)
    }
    @After fun close() = database.close()

    @Test fun gemmaProducesOutlineThenOneCompleteRequestPerChapter() = runTest {
        val (episode, job) = queuedScript(review = true)
        val llm = FakeLlm()
        coordinator(llm = llm).generateScript(episode, job) {}
        assertEquals(EpisodePhase.SCRIPT_DRAFT, repository.episode(episode).phase)
        assertEquals(listOf("chapter-1", "chapter-2"), llm.chapterRequests)
        assertEquals(2, repository.activeRevision(episode).second.size)
    }

    @Test fun savedWrongWholeEpisodeReturnStaysRejectedBeforeSecondChapterOrCommit() = runTest {
        val (episode, job) = queuedScript(review = true)
        val raw = javaClass.classLoader!!.getResourceAsStream("gemma-wrong-whole-episode-response.txt")!!.bufferedReader().use { it.readText() }
        val json = JSONObject(raw.substring(raw.indexOf('{'), raw.lastIndexOf('}') + 1))
        val llm = FakeLlm(FrozenChapter(json.getString("id"), json.getString("title"), json.getString("text")))
        val failure = try {
            coordinator(llm = llm).generateScript(episode, job) {}
            fail("The wrong episode-scoped response must not be repaired or accepted")
            error("unreachable")
        } catch (expected: IllegalArgumentException) { expected }
        assertTrue(failure.message!!.contains("wrong complete chapter"))
        assertEquals(listOf("chapter-1"), llm.chapterRequests)
        assertNull(repository.episode(episode).activeRevisionId)
        assertNull(repository.episode(episode).lockedRevisionId)
        assertTrue(repository.audio(episode).isEmpty())
    }

    @Test fun reviewOffReturnsLockedAudioJobWithoutLoadingTts() = runTest {
        val (episode, job) = queuedScript(review = false)
        val next = coordinator(llm = FakeLlm()).generateScript(episode, job) {}
        assertNotNull(next)
        assertEquals(EpisodePhase.LOCKED, repository.episode(episode).phase)
        assertEquals(JobKind.AUDIO, repository.latestJob(episode)?.kind)
    }

    @Test fun completeChapterWavsAssembleIntoFrozenEpisode() = runTest {
        val (episode, scriptJob) = queuedScript(review = true)
        coordinator(llm = FakeLlm()).generateScript(episode, scriptJob) {}
        val audioJob = repository.lockAndQueueAudio(episode)
        val tts = FakeTts()
        coordinator(tts = tts).generateAudio(episode, audioJob) {}
        val frozen = repository.episode(episode)
        assertEquals(EpisodePhase.FROZEN_READY, frozen.phase)
        assertEquals(listOf("chapter-1", "chapter-2"), tts.rendered)
        assertTrue(repository.resolveArtifact(requireNotNull(frozen.finalAudioPath)).isFile)
        assertTrue(repository.resolveArtifact(requireNotNull(frozen.timelinePath)).isFile)
        assertEquals(2, repository.audio(episode).size)
    }

    @Test fun renderFailureAtSecondChapterNeverPublishesFrozenEpisode() = runTest {
        val (episode, scriptJob) = queuedScript(review = true)
        coordinator(llm = FakeLlm()).generateScript(episode, scriptJob) {}
        val audioJob = repository.lockAndQueueAudio(episode)
        val error = try {
            coordinator(tts = FakeTts(failAt = 2)).generateAudio(episode, audioJob) {}
            fail("Expected render failure")
            error("unreachable")
        } catch (expected: IllegalStateException) { expected }
        assertTrue(error.message!!.contains("injected"))
        assertEquals(1, repository.audio(episode).size)
        assertEquals(EpisodePhase.GENERATING_AUDIO, repository.episode(episode).phase)
        repository.failJob(episode, audioJob, "injected render failure", "render:chapter-2")
        assertEquals(EpisodePhase.FAILED, repository.episode(episode).phase)
        assertTrue(artifacts.finalGenerationDir(episode, audioJob).notExists())
    }

    private suspend fun queuedScript(review: Boolean): Pair<String, String> {
        val id = repository.createEpisode()
        repository.addSource(id, "Source", "text/plain", "Useful source material.".byteInputStream())
        repository.moveToInstructions(id)
        return id to repository.queueScriptGeneration(id, "Explain it", review)
    }

    private fun coordinator(llm: LlmEngine = FakeLlm(), tts: TtsEngine = FakeTts()) = GenerationCoordinator(
        repository = repository,
        artifacts = artifacts,
        llmFactory = { llm },
        ttsFactory = { tts },
        testPackProvider = ::pack,
    )

    private fun pack(route: ModelRoute) = VerifiedModelPack(
        id = if (route == ModelRoute.GEMMA_4_E2B_LITERT_GPU) "gemma-4-e2b" else "supertonic-3",
        version = "test", route = route, androidAbi = "arm64-v8a", runtimeApiVersion = 1,
        declaredBackend = if (route == ModelRoute.GEMMA_4_E2B_LITERT_GPU) "LITERT_GPU" else "QNN_HTP",
        contract = if (route == ModelRoute.GEMMA_4_E2B_LITERT_GPU) GemmaModelContract(8_192, "0.16.1")
            else SupertonicModelContract(239, 238, 144, 5, 44_100, 1, 16, "ONNX Runtime 1.27.1 + QAIRT 2.49.0.260730"),
        manifestSha256 = "a".repeat(64), root = temporary.root, files = emptyList(),
    )

    private class FakeLlm(private val chapterOverride: FrozenChapter? = null) : LlmEngine {
        override val provenance = RuntimeProvenance(1, "GEMMA_4_E2B", "LITERT_GPU", "fake", false, setOf("model", "tokenizer", "gpu_delegate"))
        val chapterRequests = mutableListOf<String>()
        override suspend fun load(pack: VerifiedModelPack) = Unit
        override suspend fun createSourceNotes(source: SourceMaterial, chunkIndex: Int, chunkCount: Int) = SourceMaterial("notes", source.title, source.text)
        override suspend fun createOutline(sources: List<SourceMaterial>, instructions: String) = EpisodeOutline("Episode", listOf(
            OutlineChapter("chapter-1", "One", "First"), OutlineChapter("chapter-2", "Two", "Second"),
        ))
        override suspend fun createChapter(outline: EpisodeOutline, chapter: OutlineChapter, sources: List<SourceMaterial>, instructions: String): FrozenChapter {
            chapterRequests += chapter.id
            return chapterOverride ?: FrozenChapter(chapter.id, chapter.title, "Complete ${chapter.title} chapter transcript.")
        }
        override suspend fun editScript(requestJson: String) = error("unused")
        override fun close() = Unit
    }

    private class FakeTts(private val failAt: Int? = null) : TtsEngine {
        override val provenance = RuntimeProvenance(1, "SUPERTONIC_3_EXTERNAL_CONTEXT", "QNN_HTP", "fake", false,
            setOf("duration_context", "text_context", "vector_context", "vocoder_context", "htp"))
        val rendered = mutableListOf<String>()
        override suspend fun load(pack: VerifiedModelPack, voiceId: String) = Unit
        override suspend fun renderChapter(chapter: FrozenChapter, output: File, onProgress: suspend (dev.vibevoice.podcast.runtime.TtsSegmentProgress) -> Unit): AudioMetadata {
            rendered += chapter.id
            if (rendered.size == failAt) error("injected chapter render failure")
            output.parentFile!!.mkdirs()
            writeWav(output, 4_410, if (rendered.size == 1) 500 else -500)
            return WavInspector.inspectSupertonicOutput(output)
        }
        override fun close() = Unit

        private fun writeWav(file: File, frames: Int, sample: Int) {
            RandomAccessFile(file, "rw").use { out ->
                val bytes = frames * 2L
                out.writeBytes("RIFF"); out.u32(36 + bytes); out.writeBytes("WAVEfmt "); out.u32(16)
                out.u16(1); out.u16(1); out.u32(44_100); out.u32(88_200); out.u16(2); out.u16(16)
                out.writeBytes("data"); out.u32(bytes); repeat(frames) { out.u16(sample and 0xFFFF) }
            }
        }
        private fun RandomAccessFile.u16(value: Int) { write(value and 255); write((value ushr 8) and 255) }
        private fun RandomAccessFile.u32(value: Long) { u16((value and 0xFFFF).toInt()); u16(((value ushr 16) and 0xFFFF).toInt()) }
    }

    private fun File.notExists() = !exists()
}
