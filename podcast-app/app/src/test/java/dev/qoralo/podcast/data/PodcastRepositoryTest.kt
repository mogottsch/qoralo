package dev.qoralo.podcast.data

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.flow.first
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
import dev.qoralo.podcast.runtime.WavInspector

@RunWith(RobolectricTestRunner::class)
class PodcastRepositoryTest {
    @get:Rule val temporary = TemporaryFolder()
    private lateinit var database: PodcastDatabase
    private lateinit var repository: PodcastRepository
    private var now = 1_000L

    @Before fun setUp() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        database = Room.inMemoryDatabaseBuilder(context, PodcastDatabase::class.java).allowMainThreadQueries().build()
        repository = PodcastRepository(database, ArtifactStore(temporary.newFolder("episodes"), temporary.newFolder("models")), providerAdmission = false) { ++now }
    }

    @After fun close() = database.close()

    @Test fun safeFailureSummarySurvivesExistingJobAndEpisodePersistenceWithoutPrivateText() = runTest {
        val episodeId = episodeAtInstructions()
        val jobId = repository.queueScriptGeneration(episodeId, "Use the normal full chapter request", true)
        repository.claimJob(episodeId, jobId, JobKind.SCRIPT, "Writing chapter 5")
        val original = org.json.JSONException("PRIVATE_RESPONSE_SENTINEL")
        val failure = dev.qoralo.podcast.runtime.GemmaRequestException("chapter",
            dev.qoralo.podcast.runtime.GemmaFailurePhase.JSON_PARSE,
            dev.qoralo.podcast.runtime.FailureTypeGraph.capture(original), original)
        val summary = dev.qoralo.podcast.runtime.generationFailureMessage(RuntimeException("PRIVATE_WRAPPER", failure))
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
        catch (error: dev.qoralo.podcast.runtime.AudioTextCapacityException) {
            assertFalse(error.capacity.fits); assertTrue(error.message!!.contains("full draft stays editable"))
        }
        assertEquals(before, repository.episode(id)); assertEquals(revision, repository.activeRevision(id))
        assertEquals(job, repository.latestJob(id)?.id); assertEquals(JobStatus.COMPLETE, repository.latestJob(id)?.status)
    }

    @Test fun lockRechecksChangedRevisionInsteadOfUsingEarlierCapacityApproval() = runTest {
        val id = episodeAtInstructions(); val job = repository.queueScriptGeneration(id, "Narration", true)
        repository.claimJob(id, job, JobKind.SCRIPT, "writing")
        val base = repository.commitGeneratedScript(id, job, "Draft", listOf(ChapterDraft("c1", "One", "Short narration.")))
        assertTrue(repository.audioTextCapacity(repository.activeRevision(id).second.map { it.text }).fits)
        val edit = repository.queueAgentEdit(id, "Develop the full chapter")
        repository.claimJob(id, edit, JobKind.AGENT_EDIT, "editing")
        val full = "Full narration. ".repeat(300).trim()
        val newRevision = repository.applyAgentRevision(id, edit, base, "Draft", listOf(ChapterDraft("c1", "One", full)), "Expanded")
        try { repository.lockAndQueueAudio(id); fail("must check the new full revision") }
        catch (_: dev.qoralo.podcast.runtime.AudioTextCapacityException) { }
        assertEquals(newRevision, repository.episode(id).activeRevisionId)
        assertEquals(EpisodePhase.SCRIPT_DRAFT, repository.episode(id).phase)
        assertEquals(full, repository.activeRevision(id).second.single().text)
        assertEquals(JobKind.AGENT_EDIT, repository.latestJob(id)?.kind)
    }

    @Test fun exactConfiguredCapacityCanStillLockWithoutModelInvocation() = runTest {
        val limit = dev.qoralo.podcast.runtime.SupertonicTextCapacity.textLengthForManifest(dev.qoralo.podcast.BuildConfig.SUPERTONIC_MANIFEST_SHA256)!! - 9
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

    @Test fun failedRunningEditKeepsCompleteDraftAccessibleAndRetainsFailedRequest() = runTest {
        val id = draftEpisode(); val before = repository.activeRevision(id)
        val file = repository.resolveArtifact(before.first.relativePath); val bytes = file.readBytes()
        val job = repository.queueAgentEdit(id, "Make this more engaging")
        repository.claimJob(id, job, JobKind.AGENT_EDIT, "Editing")
        val messages = repository.observeMessages(id).first()
        assertTrue(repository.failJob(id, job, "JSON parsing failed"))
        assertEquals(EpisodePhase.SCRIPT_DRAFT, repository.episode(id).phase)
        assertEquals(before, repository.activeRevision(id)); assertTrue(bytes.contentEquals(file.readBytes()))
        assertEquals(messages, repository.observeMessages(id).first())
        assertEquals(JobStatus.FAILED, repository.latestJob(id)?.status)
        assertEquals("JSON parsing failed", repository.latestJob(id)?.errorMessage)
        assertEquals(0, database.podcastDao().activeJobCount())
        assertFalse(repository.failJob(id, job, "Late duplicate failure"))
        assertEquals("JSON parsing failed", repository.latestJob(id)?.errorMessage)
        // Only a deliberate new chat request queues another job; failure itself never retries.
        assertTrue(repository.queueAgentEdit(id, "A different request") != job)
    }

    @Test fun explicitReturnFromLegacyFailedEditChangesOnlyPhaseAndTimestamp() = runTest {
        val (id, job, revision) = legacyFailedEdit()
        val episode = repository.episode(id); val before = repository.activeRevision(id)
        val failed = repository.latestJob(id); val messages = repository.observeMessages(id).first()
        val file = repository.resolveArtifact(before.first.relativePath); val bytes = file.readBytes()
        assertTrue(canReturnToSavedDraft(episode, failed))
        repository.returnToSavedDraft(id, job, revision)
        val after = repository.episode(id)
        assertEquals(episode.copy(phase = EpisodePhase.SCRIPT_DRAFT, updatedAtEpochMs = after.updatedAtEpochMs), after)
        assertEquals(before, repository.activeRevision(id)); assertEquals(failed, repository.latestJob(id))
        assertEquals(messages, repository.observeMessages(id).first()); assertTrue(bytes.contentEquals(file.readBytes()))
        assertEquals(0, database.podcastDao().activeJobCount())
        expectIllegal { repository.returnToSavedDraft(id, job, revision) }
    }

    @Test fun legacyReturnRejectsStaleIdentifiersAndForeignActiveWork() = runTest {
        val (id, job, revision) = legacyFailedEdit(); val before = repository.episode(id)
        expectIllegal { repository.returnToSavedDraft(id, "stale-job", revision) }
        expectIllegal { repository.returnToSavedDraft(id, job, "stale-revision") }
        val other = episodeAtInstructions(); repository.queueScriptGeneration(other, "Other user work", true)
        expectIllegal { repository.returnToSavedDraft(id, job, revision) }
        assertEquals(before, repository.episode(id))
    }

    @Test fun legacyReturnRejectsCorruptSavedArtifactWithoutClearingFailure() = runTest {
        val (id, job, revision) = legacyFailedEdit(); val before = repository.episode(id)
        repository.resolveArtifact(repository.activeRevision(id).first.relativePath).appendText("corrupted fixture")
        expectIllegal { repository.returnToSavedDraft(id, job, revision) }
        assertEquals(before, repository.episode(id)); assertEquals(JobStatus.FAILED, repository.latestJob(id)?.status)
    }

    @Test fun recoveryEligibilityRejectsLockedWrongKindCrossOwnerOrIncompleteHistory() = runTest {
        val (id, _, _) = legacyFailedEdit(); val episode = repository.episode(id); val job = repository.latestJob(id)!!
        assertFalse(canReturnToSavedDraft(episode.copy(lockedRevisionId = episode.activeRevisionId), job))
        assertFalse(canReturnToSavedDraft(episode.copy(lockedAtEpochMs = 1), job))
        assertFalse(canReturnToSavedDraft(episode.copy(lockedContentHash = "locked"), job))
        assertFalse(canReturnToSavedDraft(episode.copy(finalAudioSha256 = "audio"), job))
        assertFalse(canReturnToSavedDraft(episode.copy(finalAudioByteCount = 100), job))
        assertFalse(canReturnToSavedDraft(episode.copy(timelineSha256 = "timeline"), job))
        assertFalse(canReturnToSavedDraft(episode.copy(durationMs = 100), job))
        assertFalse(canReturnToSavedDraft(episode, job.copy(kind = JobKind.AUDIO)))
        assertFalse(canReturnToSavedDraft(episode, job.copy(kind = JobKind.SCRIPT)))
        assertFalse(canReturnToSavedDraft(episode, job.copy(episodeId = "other")))
        assertFalse(canReturnToSavedDraft(episode, job.copy(requestMessageId = null)))
        assertFalse(canReturnToSavedDraft(episode, job.copy(status = JobStatus.RUNNING)))
        assertFalse(canReturnToSavedDraft(episode.copy(activeRevisionId = "other"), job))
        assertFalse(canReturnToSavedDraft(null, job)); assertFalse(canReturnToSavedDraft(episode, null))
    }

    @Test fun failedRunningEditCannotReopenLockedOrSupersededRevision() = runTest {
        for (locked in listOf(true, false)) {
            val id = draftEpisode(); val base = repository.activeRevision(id).first.id
            val job = repository.queueAgentEdit(id, "Edit the base")
            repository.claimJob(id, job, JobKind.AGENT_EDIT, "Editing")
            val current = repository.episode(id)
            // Host fixtures model a stale callback after the state it owned ceased to be current.
            val changed = if (locked) current.copy(phase = EpisodePhase.LOCKED, lockedRevisionId = base,
                lockedContentHash = repository.activeRevision(id).first.contentHash, lockedAtEpochMs = 99)
                else current.copy(activeRevisionId = "superseding-revision")
            database.podcastDao().updateEpisode(changed)
            assertTrue(repository.failJob(id, job, "Late edit failure"))
            assertEquals(changed, repository.episode(id))
            assertFalse(canReturnToSavedDraft(changed, repository.latestJob(id)))
        }
    }

    @Test fun queuedEditingFailureAlsoKeepsDraftAndFailedChatHistory() = runTest {
        val id = draftEpisode(); val revision = repository.activeRevision(id)
        val job = repository.queueAgentEdit(id, "Change the tone")
        val messages = repository.observeMessages(id).first()
        assertTrue(repository.failQueuedJob(id, job, "Dispatch unavailable"))
        assertEquals(EpisodePhase.SCRIPT_DRAFT, repository.episode(id).phase)
        assertEquals(revision, repository.activeRevision(id)); assertEquals(messages, repository.observeMessages(id).first())
        assertEquals(JobStatus.FAILED, repository.latestJob(id)?.status)
    }

    private suspend fun legacyFailedEdit(): Triple<String, String, String> {
        val id = draftEpisode(); val revision = repository.activeRevision(id).first.id
        val job = repository.queueAgentEdit(id, "Change the tone")
        repository.claimJob(id, job, JobKind.AGENT_EDIT, "Editing")
        repository.failJob(id, job, "Saved parse failure")
        // Host-only fixture reproduces the older persisted phase; production never performs this mutation.
        database.podcastDao().updateEpisode(repository.episode(id).copy(phase = EpisodePhase.FAILED))
        return Triple(id, job, revision)
    }

    @Test fun audioCannotCompleteWithoutEveryLockedChapter() = runTest {
        val episodeId = draftEpisode()
        val audioJob = repository.lockAndQueueAudio(episodeId)
        repository.claimJob(episodeId, audioJob, JobKind.AUDIO, "audio", 2)
        val fake = dev.qoralo.podcast.runtime.WavAssembler.Result(
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

    @Test fun retryingAStoppedScriptQueuesTheSameWorkAgainAndKeepsTheFailedAttempt() = runTest {
        val episodeId = episodeAtInstructions()
        val failedJobId = repository.queueScriptGeneration(episodeId, "Use the normal full chapter request", true)
        repository.claimJob(episodeId, failedJobId, JobKind.SCRIPT, "Verifying Gemma 4 E2B")
        repository.failJob(episodeId, failedJobId, "Gemma LiteRT GPU chapter failed at JSON_PARSE")
        assertEquals(EpisodePhase.FAILED, repository.episode(episodeId).phase)

        val retryJobId = repository.retryFailedGeneration(episodeId, failedJobId)

        assertTrue(retryJobId != failedJobId)
        val episode = repository.episode(episodeId)
        assertEquals(EpisodePhase.GENERATING_SCRIPT, episode.phase)
        assertEquals("Use the normal full chapter request", episode.instructions)
        assertTrue(episode.reviewEnabled)
        // The failure is cleared from the episode, not from history.
        assertEquals(null, episode.failureMessage)
        val queued = repository.latestJob(episodeId)
        assertEquals(retryJobId, queued?.id)
        assertEquals(JobStatus.QUEUED, queued?.status)
        assertEquals(JobKind.SCRIPT, queued?.kind)
        assertEquals(1, repository.queuedJobs().count { it.id == retryJobId })
        val failed = database.podcastDao().job(failedJobId)
        assertEquals(JobStatus.FAILED, failed?.status)
        assertEquals("Gemma LiteRT GPU chapter failed at JSON_PARSE", failed?.errorMessage)
    }

    @Test fun retryIsRefusedForAStaleJobOrAnEpisodeThatIsNotStopped() = runTest {
        val episodeId = episodeAtInstructions()
        val jobId = repository.queueScriptGeneration(episodeId, "Use the normal full chapter request", true)
        // Still running: nothing to retry, and a second job must never be queued alongside it.
        repository.claimJob(episodeId, jobId, JobKind.SCRIPT, "Verifying Gemma 4 E2B")
        try { repository.retryFailedGeneration(episodeId, jobId); fail("running job retried") }
        catch (_: IllegalArgumentException) { }

        repository.failJob(episodeId, jobId, "stopped")
        try { repository.retryFailedGeneration(episodeId, "not-the-failed-job"); fail("stale job id accepted") }
        catch (_: IllegalArgumentException) { }
        assertEquals(EpisodePhase.FAILED, repository.episode(episodeId).phase)
        assertEquals(jobId, repository.latestJob(episodeId)?.id)
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
