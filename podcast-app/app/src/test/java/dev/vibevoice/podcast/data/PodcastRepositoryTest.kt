package dev.vibevoice.podcast.data

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.io.RandomAccessFile
import dev.vibevoice.podcast.runtime.WavInspector

@RunWith(RobolectricTestRunner::class)
class PodcastRepositoryTest {
    @get:Rule val temporary = TemporaryFolder()
    private lateinit var database: PodcastDatabase
    private lateinit var repository: PodcastRepository
    private var now = 1_000L

    @Before fun setUp() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        database = Room.inMemoryDatabaseBuilder(context, PodcastDatabase::class.java).allowMainThreadQueries().build()
        repository = PodcastRepository(database, ArtifactStore(temporary.newFolder("episodes"), temporary.newFolder("models"))) { ++now }
    }

    @After fun close() = database.close()

    @Test fun safeFailureSummarySurvivesExistingJobAndEpisodePersistenceWithoutPrivateText() = runTest {
        val episodeId = episodeAtInstructions()
        val jobId = repository.queueScriptGeneration(episodeId, "Use the normal full chapter request", true)
        repository.claimJob(episodeId, jobId, JobKind.SCRIPT, "Writing chapter 5")
        val original = org.json.JSONException("PRIVATE_RESPONSE_SENTINEL")
        val failure = dev.vibevoice.podcast.runtime.GemmaRequestException("chapter",
            dev.vibevoice.podcast.runtime.GemmaFailurePhase.JSON_PARSE,
            dev.vibevoice.podcast.runtime.FailureTypeGraph.capture(original), original)
        val summary = dev.vibevoice.podcast.runtime.generationFailureMessage(RuntimeException("PRIVATE_WRAPPER", failure))
        assertTrue(repository.failJob(episodeId, jobId, summary))
        assertEquals(summary, repository.latestJob(episodeId)?.errorMessage)
        assertEquals(summary, repository.episode(episodeId).failureMessage)
        assertTrue(summary.contains("JSON_PARSE")); assertTrue(summary.contains("JSONException"))
        assertFalse(summary.contains("PRIVATE_")); assertEquals(EpisodePhase.FAILED, repository.episode(episodeId).phase)
    }

    @Test fun reviewOnStopsAtImmutableDraftThenUserLocks() = runTest {
        val episodeId = episodeAtInstructions()
        val jobId = repository.queueScriptGeneration(episodeId, "Explain it clearly", true)
        repository.claimJob(episodeId, jobId, JobKind.SCRIPT, "starting")
        val revision = repository.commitGeneratedScript(episodeId, jobId, "Title", chapters())
        assertEquals(EpisodePhase.SCRIPT_DRAFT, repository.episode(episodeId).phase)
        assertEquals(revision, repository.episode(episodeId).activeRevisionId)

        val audioJob = repository.lockAndQueueAudio(episodeId)
        val locked = repository.episode(episodeId)
        assertEquals(EpisodePhase.LOCKED, locked.phase)
        assertEquals(revision, locked.lockedRevisionId)
        expectIllegal { repository.addPastedForTest(episodeId) }
        assertEquals(JobKind.AUDIO, repository.latestJob(episodeId)?.kind)
        assertEquals(audioJob, repository.latestJob(episodeId)?.id)
    }

    @Test fun reviewOffOversizedNarrationKeepsFullCompletedDraftAndDoesNotQueueAudio() = runTest {
        val id = episodeAtInstructions(); val text = "Full requested narration. ".repeat(200).trim()
        val job = repository.queueScriptGeneration(id, "Keep the full chapter", false)
        repository.claimJob(id, job, JobKind.SCRIPT, "writing")
        val revision = repository.commitGeneratedScript(id, job, "Full draft", listOf(ChapterDraft("c1", "Full chapter", text)))
        val episode = repository.episode(id)
        assertEquals(EpisodePhase.SCRIPT_DRAFT, episode.phase); assertFalse(episode.reviewEnabled)
        assertEquals(revision, episode.activeRevisionId); assertEquals(null, episode.lockedRevisionId)
        assertEquals(null, episode.lockedAtEpochMs); assertEquals(JobKind.SCRIPT, repository.latestJob(id)?.kind)
        assertEquals(JobStatus.COMPLETE, repository.latestJob(id)?.status)
        assertEquals(text, repository.activeRevision(id).second.single().text)
        assertTrue(repository.resolveArtifact(repository.activeRevision(id).first.relativePath).isFile)
    }

    @Test fun manualCapacityBlockIsTransactionalAndDoesNotAlterDraftOrJobs() = runTest {
        val id = episodeAtInstructions(); val text = "Narration. ".repeat(500).trim()
        val job = repository.queueScriptGeneration(id, "Full narration", true)
        repository.claimJob(id, job, JobKind.SCRIPT, "writing")
        repository.commitGeneratedScript(id, job, "Full draft", listOf(ChapterDraft("c1", "One", text)))
        val before = repository.episode(id); val revision = repository.activeRevision(id)
        try { repository.lockAndQueueAudio(id); fail("capacity must reject") }
        catch (error: dev.vibevoice.podcast.runtime.AudioTextCapacityException) {
            assertFalse(error.capacity.fits); assertTrue(error.message!!.contains("full draft stays editable"))
        }
        assertEquals(before, repository.episode(id)); assertEquals(revision, repository.activeRevision(id))
        assertEquals(job, repository.latestJob(id)?.id); assertEquals(JobStatus.COMPLETE, repository.latestJob(id)?.status)
    }

    @Test fun lockRechecksChangedRevisionInsteadOfUsingEarlierCapacityApproval() = runTest {
        val id = episodeAtInstructions(); val job = repository.queueScriptGeneration(id, "Narration", true)
        repository.claimJob(id, job, JobKind.SCRIPT, "writing")
        val base = repository.commitGeneratedScript(id, job, "Draft", listOf(ChapterDraft("c1", "One", "Short narration.")))
        assertTrue(dev.vibevoice.podcast.runtime.SupertonicTextCapacity.configured(repository.activeRevision(id).second.map { it.text }).fits)
        val edit = repository.queueAgentEdit(id, "Develop the full chapter")
        repository.claimJob(id, edit, JobKind.AGENT_EDIT, "editing")
        val full = "Full narration. ".repeat(300).trim()
        val newRevision = repository.applyAgentRevision(id, edit, base, "Draft", listOf(ChapterDraft("c1", "One", full)), "Expanded")
        try { repository.lockAndQueueAudio(id); fail("must check the new full revision") }
        catch (_: dev.vibevoice.podcast.runtime.AudioTextCapacityException) { }
        assertEquals(newRevision, repository.episode(id).activeRevisionId)
        assertEquals(EpisodePhase.SCRIPT_DRAFT, repository.episode(id).phase)
        assertEquals(full, repository.activeRevision(id).second.single().text)
        assertEquals(JobKind.AGENT_EDIT, repository.latestJob(id)?.kind)
    }

    @Test fun exactConfiguredCapacityCanStillLockWithoutModelInvocation() = runTest {
        val limit = dev.vibevoice.podcast.runtime.SupertonicTextCapacity.textLengthForManifest(dev.vibevoice.podcast.BuildConfig.SUPERTONIC_MANIFEST_SHA256)!! - 9
        val id = episodeAtInstructions(); val job = repository.queueScriptGeneration(id, "Boundary", true)
        repository.claimJob(id, job, JobKind.SCRIPT, "writing")
        repository.commitGeneratedScript(id, job, "Draft", listOf(ChapterDraft("c1", "One", "a".repeat(limit-1)+".")))
        val audio = repository.lockAndQueueAudio(id)
        assertEquals(EpisodePhase.LOCKED, repository.episode(id).phase)
        assertEquals(audio, repository.latestJob(id)?.id); assertEquals(JobKind.AUDIO, repository.latestJob(id)?.kind)
    }

    @Test fun reviewOffAtomicallyLocksAndQueuesAudio() = runTest {
        val episodeId = episodeAtInstructions()
        val jobId = repository.queueScriptGeneration(episodeId, "Keep it short", false)
        repository.claimJob(episodeId, jobId, JobKind.SCRIPT, "starting")
        val revision = repository.commitGeneratedScript(episodeId, jobId, "Title", chapters())
        val episode = repository.episode(episodeId)
        assertEquals(EpisodePhase.LOCKED, episode.phase)
        assertEquals(revision, episode.lockedRevisionId)
        assertNotNull(episode.lockedContentHash)
        assertEquals(JobKind.AUDIO, repository.latestJob(episodeId)?.kind)
    }

    @Test fun claimRejectsCrossWiredAndDuplicateCommands() = runTest {
        val first = episodeAtInstructions()
        val job = repository.queueScriptGeneration(first, "Instruction", true)
        val second = repository.createEpisode()
        expectIllegal { repository.claimJob(second, job, JobKind.SCRIPT, "wrong") }
        repository.claimJob(first, job, JobKind.SCRIPT, "right")
        expectIllegal { repository.claimJob(first, job, JobKind.SCRIPT, "duplicate") }
    }

    @Test fun agentJobOwnsItsMessageAndBlocksSecondEditAndLock() = runTest {
        val episodeId = draftEpisode()
        val editJob = repository.queueAgentEdit(episodeId, "Shorten chapter one")
        expectIllegal { repository.queueAgentEdit(episodeId, "Different request") }
        val claim = repository.claimJob(episodeId, editJob, JobKind.AGENT_EDIT, "editing")
        assertEquals("Shorten chapter one", claim.message?.text)
        expectIllegal { repository.lockAndQueueAudio(episodeId) }
        val revision = requireNotNull(repository.episode(episodeId).activeRevisionId)
        repository.applyAgentRevision(episodeId, editJob, revision, "Title", chapters("Rewritten"), "Chapter 1 shortened")
        assertFalse(repository.failJob(episodeId, editJob, "late failure"))
        repository.lockAndQueueAudio(episodeId)
        assertEquals(EpisodePhase.LOCKED, repository.episode(episodeId).phase)
    }

    @Test fun audioCannotCompleteWithoutEveryLockedChapter() = runTest {
        val episodeId = draftEpisode()
        val audioJob = repository.lockAndQueueAudio(episodeId)
        repository.claimJob(episodeId, audioJob, JobKind.AUDIO, "audio", 2)
        val fake = dev.vibevoice.podcast.runtime.WavAssembler.Result(
            temporary.newFile("final.wav"), "0".repeat(64), 0,
            temporary.newFile("timeline.json"), "0".repeat(64), 0, 0, 0,
        )
        expectIllegal { repository.completeAudio(episodeId, audioJob, fake) }
        assertEquals(EpisodePhase.GENERATING_AUDIO, repository.episode(episodeId).phase)
    }

    @Test fun chapterAudioRejectsWrongRevisionAtWriteBoundary() = runTest {
        val episodeId = draftEpisode()
        val audioJob = repository.lockAndQueueAudio(episodeId)
        repository.claimJob(episodeId, audioJob, JobKind.AUDIO, "rendering", 2)
        val locked = repository.lockedChapterData(episodeId).second.first()
        val file = temporary.newFile("chapter.wav").also(::writeWav)
        val metadata = WavInspector.inspectSupertonicOutput(file)
        expectIllegal { repository.commitChapterAudio(episodeId, audioJob, locked.copy(rowId = "wrong", revisionId = "another-revision"), metadata, file, 0) }
        assertTrue(repository.audio(episodeId).isEmpty())
    }

    @Test fun staleFailureNeverRegressesLockedEpisode() = runTest {
        val episodeId = draftEpisode()
        val editJob = repository.queueAgentEdit(episodeId, "Rename it")
        val claim = repository.claimJob(episodeId, editJob, JobKind.AGENT_EDIT, "editing")
        val base = requireNotNull(claim.job.requestedRevisionId)
        repository.applyAgentRevision(episodeId, editJob, base, "Renamed", chapters(), "Renamed episode")
        repository.lockAndQueueAudio(episodeId)
        assertFalse(repository.failJob(episodeId, editJob, "stale crash"))
        assertEquals(EpisodePhase.LOCKED, repository.episode(episodeId).phase)
    }

    private suspend fun episodeAtInstructions(): String {
        val id = repository.createEpisode()
        repository.addPastedForTest(id)
        repository.moveToInstructions(id)
        return id
    }

    private suspend fun draftEpisode(): String {
        val id = episodeAtInstructions()
        val job = repository.queueScriptGeneration(id, "Instruction", true)
        repository.claimJob(id, job, JobKind.SCRIPT, "starting")
        repository.commitGeneratedScript(id, job, "Title", chapters())
        return id
    }

    private fun chapters(text: String = "Complete chapter text.") = listOf(
        ChapterDraft("chapter-1", "One", text),
        ChapterDraft("chapter-2", "Two", "Second complete chapter."),
    )

    private suspend fun expectIllegal(block: suspend () -> Unit) {
        try {
            block()
            fail("Expected IllegalArgumentException")
        } catch (_: IllegalArgumentException) {
            // Expected invariant rejection.
        }
    }

    private suspend fun PodcastRepository.addPastedForTest(id: String) {
        addSource(id, "Source", "text/plain", "Source material".byteInputStream())
    }

    private fun writeWav(file: java.io.File) {
        RandomAccessFile(file, "rw").use { out ->
            val frames = 100; val bytes = frames * 2L
            out.writeBytes("RIFF"); out.u32(36 + bytes); out.writeBytes("WAVEfmt "); out.u32(16)
            out.u16(1); out.u16(1); out.u32(44_100); out.u32(88_200); out.u16(2); out.u16(16)
            out.writeBytes("data"); out.u32(bytes); repeat(frames) { out.u16(500) }
        }
    }
    private fun RandomAccessFile.u16(value: Int) { write(value and 255); write((value ushr 8) and 255) }
    private fun RandomAccessFile.u32(value: Long) { u16((value and 0xFFFF).toInt()); u16(((value ushr 16) and 0xFFFF).toInt()) }
}
