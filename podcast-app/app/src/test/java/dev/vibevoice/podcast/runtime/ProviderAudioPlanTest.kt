package dev.vibevoice.podcast.runtime

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import dev.vibevoice.podcast.data.*
import dev.vibevoice.podcast.model.*
import kotlinx.coroutines.test.runTest
import org.json.JSONObject
import org.junit.*
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.io.File
import java.io.RandomAccessFile

@RunWith(RobolectricTestRunner::class)
class ProviderAudioPlanTest {
    @get:Rule val temp = TemporaryFolder()
    private lateinit var database: PodcastDatabase
    private lateinit var artifacts: ArtifactStore
    private lateinit var repository: PodcastRepository
    @Before fun setup() {
        assumeTrue("Provider-configured test variant only", ProviderAudioPlan.selected)
        val source = System.getenv("PODCAST_PROVIDER_PACK")
        assumeTrue("Explicit local data-only pack fixture; no model calls", source != null)
        val context = ApplicationProvider.getApplicationContext<Context>()
        database = Room.inMemoryDatabaseBuilder(context, PodcastDatabase::class.java).allowMainThreadQueries().build()
        artifacts = ArtifactStore(temp.newFolder("episodes"), temp.newFolder("models"))
        val pack = artifacts.modelPackRoot(ProviderAudioPlan.PACK_ID); require(pack.mkdirs())
        File(requireNotNull(source), "manifest.json").copyTo(File(pack, "manifest.json"))
        val files = JSONObject(File(pack, "manifest.json").readText()).getJSONArray("files")
        repeat(files.length()) { i ->
            val entry = files.getJSONObject(i); val file = File(pack, entry.getString("path")); file.parentFile.mkdirs()
            if (entry.getString("role") == "SUPERTONIC_UNICODE_INDEXER") File(source, entry.getString("path")).copyTo(file)
            else RandomAccessFile(file, "rw").use { it.setLength(entry.getLong("bytes")) }
        }
        // Other assets are deliberately sparse placeholders: this fixture may pass LIGHT input admission, never full model verification.
        repository = PodcastRepository(database, artifacts)
    }
    @After fun cleanup() { if (::database.isInitialized) database.close() }
    private suspend fun draft(text: String, review: Boolean = true): String {
        val id = repository.createEpisode()
        repository.addSource(id, "Source", "text/plain", "A saved source.".byteInputStream())
        repository.moveToInstructions(id)
        val job = repository.queueScriptGeneration(id, "Keep the whole chapter", review)
        repository.claimJob(id, job, JobKind.SCRIPT, "Writing")
        repository.commitGeneratedScript(id, job, "Title", listOf(ChapterDraft("c1", "One", text)))
        return id
    }
    @Test fun longWholeChapterAdmitsSegmentsAndLocksWithContentAddressedPackBoundPlan() = runTest {
        val text = "A complete sentence about a walk through the village. ".repeat(45).trim()
        val id = draft(text); val revision = repository.activeRevision(id)
        val capacity = repository.audioTextCapacity(listOf(text))
        assertTrue(capacity.fits); assertTrue(capacity.providerPipeline); assertTrue(capacity.chapters.single().segmentCount > 1)
        val job = repository.lockAndQueueAudio(id)
        assertTrue(Regex("[a-f0-9]{64}").matches(job))
        val file = artifacts.resolveEpisodeFile("$id/audio-plans/$job.json")
        assertEquals(job, artifacts.sha256(file))
        val plan = JSONObject(file.readText())
        assertEquals(revision.first.id, plan.getString("revisionId"))
        assertEquals(revision.first.contentHash, plan.getString("revisionSha256"))
        assertEquals(ProviderAudioPlan.PACK_SHA256, plan.getString("packSha256"))
        ProviderAudioPlan.verify(artifacts, id, job, revision.first.id, revision.first.contentHash, ProviderAudioPlan.PACK_SHA256,
            listOf(ChapterDraft("c1", "One", text)))
        assertEquals(text, repository.activeRevision(id).second.single().text)
        assertEquals(EpisodePhase.LOCKED, repository.episode(id).phase)
    }
    @Test fun autoReviewOffUsesSameProviderPlanAndPreservesOriginalText() = runTest {
        val text = "A clear sentence to narrate. ".repeat(80).trim()
        val id = draft(text, false);val episode = repository.episode(id);val job = repository.latestJob(id)!!
        assertEquals(EpisodePhase.LOCKED, episode.phase); assertEquals(JobKind.AUDIO, job.kind)
        assertEquals(job.id, artifacts.sha256(artifacts.resolveEpisodeFile("$id/audio-plans/${job.id}.json")))
        assertEquals(text, repository.activeRevision(id).second.single().text)
    }
    @Test fun overlongSentenceAndUnsupportedInputNeverSilentlySplitOrLock() = runTest {
        for (text in listOf("x".repeat(350) + ".", "Unsupported 🀄 character.")) {
            val id = draft(text, false)
            assertEquals(EpisodePhase.SCRIPT_DRAFT, repository.episode(id).phase)
            assertEquals(JobKind.SCRIPT, repository.latestJob(id)?.kind);assertEquals(JobStatus.COMPLETE, repository.latestJob(id)?.status)
            assertEquals(text, repository.activeRevision(id).second.single().text)
            val before = repository.episode(id)
            try { repository.lockAndQueueAudio(id); fail("must reject") } catch (_: AudioTextCapacityException) {}
            assertEquals(before, repository.episode(id))
        }
    }
    @Test fun modifiedPlanAndPackAreRejectedWithoutModelInvocation() = runTest {
        val id = draft("One complete sentence."); val revision = repository.activeRevision(id).first
        val job = repository.lockAndQueueAudio(id);val chapters = listOf(ChapterDraft("c1", "One", "One complete sentence."))
        assertThrows(IllegalArgumentException::class.java) { ProviderAudioPlan.verify(artifacts, id, job, revision.id, revision.contentHash, "changed-pack", chapters) }
        artifacts.resolveEpisodeFile("$id/audio-plans/$job.json").appendText(" ")
        assertThrows(IllegalArgumentException::class.java) { ProviderAudioPlan.verify(artifacts, id, job, revision.id, revision.contentHash, ProviderAudioPlan.PACK_SHA256, chapters) }
        assertEquals(EpisodePhase.LOCKED, repository.episode(id).phase)
    }
    @Test fun nonceSeparatesAttemptsAndDuplicateLockCannotOverwriteTheFirstPlan() = runTest {
        val text = "A complete test sentence.";val id = draft(text);val revision = repository.activeRevision(id).first
        val job = repository.lockAndQueueAudio(id);val file = artifacts.resolveEpisodeFile("$id/audio-plans/$job.json");val original = file.readBytes()
        try { repository.lockAndQueueAudio(id); fail("duplicate lock must not create another attempt") } catch (_: IllegalArgumentException) {}
        assertArrayEquals(original, file.readBytes());assertEquals(job, repository.latestJob(id)?.id)
        val chapters = listOf(ChapterDraft("c1", "One", text));val nonce = JSONObject(original.toString(Charsets.UTF_8)).getString("nonce")
        assertThrows(IllegalArgumentException::class.java) { ProviderAudioPlan.save(artifacts, id, revision.id, revision.contentHash, nonce, chapters) }
        val other = ProviderAudioPlan.save(artifacts, id, revision.id, revision.contentHash, "new-explicit-attempt-nonce", chapters)
        assertNotEquals(job, other.jobId);assertArrayEquals(original, file.readBytes())
        // Verification after a repository recreation consumes the persisted nonce, never generates another one.
        ProviderAudioPlan.verify(artifacts, id, job, revision.id, revision.contentHash, ProviderAudioPlan.PACK_SHA256, chapters)
        assertEquals(job, PodcastRepository(database, artifacts).latestJob(id)?.id)
    }
    @Test fun legacyUuidMissingPlanAndStaleRevisionNeverBecomeNewProviderExecution() = runTest {
        val text = "A sentence.";val id = draft(text);val revision = repository.activeRevision(id).first
        val job = repository.lockAndQueueAudio(id);val chapters = listOf(ChapterDraft("c1", "One", text))
        for ((candidate, base) in listOf("11111111-1111-1111-1111-111111111111" to revision.id, job to "stale-revision")) {
            assertThrows(IllegalArgumentException::class.java) { ProviderAudioPlan.verify(artifacts, id, candidate, base, revision.contentHash, ProviderAudioPlan.PACK_SHA256, chapters) }
        }
        artifacts.resolveEpisodeFile("$id/audio-plans/$job.json").delete()
        assertThrows(IllegalArgumentException::class.java) { ProviderAudioPlan.verify(artifacts, id, job, revision.id, revision.contentHash, ProviderAudioPlan.PACK_SHA256, chapters) }
        assertEquals(job, repository.latestJob(id)?.id)
    }
    @Test fun completedPublicationRecoveryUsesNewJobAndNeverConstructsAnInferenceEngine() = runTest {
        val text="A sentence.";val id=draft(text);val revision=repository.activeRevision(id).first
        val oldJob=repository.lockAndQueueAudio(id);repository.claimJob(id,oldJob,JobKind.AUDIO,"Rendering")
        repository.failJob(id,oldJob,"Synthetic publication failure")
        val failed=repository.latestJob(id)!!;val locked=repository.episode(id)
        val base=JSONObject(artifacts.resolveEpisodeFile("$id/audio-plans/$oldJob.json").readText()).getJSONArray("chapters").getJSONObject(0)
        val segment=base.getJSONArray("segments").getJSONObject(0)
        val folder=File(artifacts.episodesRoot,"$id/chapters/.provider-test").apply { mkdirs() }
        val wave=File(folder,"complete-chapter.wav")
        RandomAccessFile(wave,"rw").use { out ->
            fun u16(v:Int) {out.write(v and 255);out.write((v ushr 8) and 255)}
            fun u32(v:Int) {u16(v and 65535);u16((v ushr 16) and 65535)}
            out.writeBytes("RIFF");u32(36+3072*2);out.writeBytes("WAVEfmt ");u32(16);u16(1);u16(1);u32(44100);u32(88200);u16(2);u16(16);out.writeBytes("data");u32(3072*2);repeat(3072){u16(1200)}
        }
        wave.copyTo(File(folder,"segment-0.wav"));val metadata=WavInspector.inspectSupertonicOutput(wave)
        val entry=JSONObject().put("index",0).put("nativeLatentLength",1).put("frameCount",3072)
            .put("idsSha256",segment.getString("idsSha256")).put("processedSha256",segment.getString("processedSha256"))
            .put("rawSegmentSha256",segment.getString("rawSha256")).put("neuralCalls",11)
            .put("nativeTextLength",segment.getInt("nativeTextLength")).put("noiseOffset",0).put("noiseConsumed",144).put("waveSha256",metadata.sha256)
        File(folder,"provider-receipt.json").writeText(JSONObject().put("status","complete_chapter").put("packSha256",ProviderAudioPlan.PACK_SHA256)
            .put("frontendVersion",ProviderTextFrontend.VERSION).put("chapterId","c1").put("rawChapterSha256",base.getString("textSha256"))
            .put("waveSha256",metadata.sha256).put("frameCount",3072).put("steps",8).put("speedHundredths",105).put("gapFrames",13230)
            .put("randomSeed",20260911).put("cpuFallback",false).put("provider","QNN_HTP").put("segments",org.json.JSONArray().put(entry)).toString())
        val newJob=repository.queueProviderPublicationRecovery(id,oldJob,revision.id,listOf(artifacts.relativeToEpisodes(wave) to metadata.sha256))
        assertNotEquals(oldJob,newJob)
        val pack=ModelPackVerifier().verify(File(requireNotNull(System.getenv("PODCAST_PROVIDER_PACK"))),
            ModelPackRequirement(ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP,ProviderAudioPlan.PACK_ID,ProviderAudioPlan.PACK_SHA256))
        val coordinator=dev.vibevoice.podcast.generation.GenerationCoordinator(repository,artifacts,
            llmFactory={error("LLM factory forbidden in publication")},ttsFactory={error("TTS factory forbidden in publication")},testPackProvider={pack})
        coordinator.generateAudio(id,newJob) {}
        val ready=repository.episode(id)
        assertEquals(EpisodePhase.FROZEN_READY,ready.phase);assertEquals(metadata.sha256,ready.finalAudioSha256)
        assertEquals(failed,database.podcastDao().job(oldJob));assertEquals(locked.lockedAtEpochMs,ready.lockedAtEpochMs)
        assertEquals(metadata.sha256,ProviderPublication.hash(wave));assertEquals(JobStatus.COMPLETE,repository.latestJob(id)?.status)
        val passages=repository.verifiedTranscriptPassages(id)
        assertEquals(1,passages.size);assertEquals(text,text.substring(passages.single().sourceStartUtf16,passages.single().sourceEndUtf16))
        assertEquals(0L,passages.single().speechStartFrame);assertEquals(3072L,passages.single().endFrame)
        File(folder,"provider-receipt.json").appendText(" ")
        assertTrue(repository.verifiedTranscriptPassages(id).isEmpty()) // Never guess timing after a receipt integrity mismatch.
    }

    @Test fun actualLocalPackPassesFullDataIntegrityAndDeclaresProviderRecipe() {
        val pack = ModelPackVerifier().verify(File(requireNotNull(System.getenv("PODCAST_PROVIDER_PACK"))),
            ModelPackRequirement(ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP, ProviderAudioPlan.PACK_ID, ProviderAudioPlan.PACK_SHA256))
        val shape = pack.contract as SupertonicModelContract
        assertEquals(320, shape.textLength);assertEquals(512, shape.latentLength);assertEquals(8, shape.diffusionSteps)
        assertEquals(105, shape.providerPipeline!!.speedHundredths);assertEquals(13230, shape.providerPipeline.gapFrames)
        assertEquals(13, pack.files.size)
    }
    @Test fun lightAdmissionDoesNotMasqueradeAsFullModelIntegrityVerification() {
        assertTrue(repository.audioTextCapacity(listOf("A sentence.")).fits)
        assertThrows(ModelPackException.Integrity::class.java) {
            ModelPackVerifier().verify(artifacts.modelPackRoot(ProviderAudioPlan.PACK_ID),
                ModelPackRequirement(ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP, ProviderAudioPlan.PACK_ID, ProviderAudioPlan.PACK_SHA256))
        }
    }
}
