package dev.qoralo.podcast.data

import org.junit.Assert.*
import org.junit.Test

class FailedGenerationRetryTest {
    private fun episode(phase: String = EpisodePhase.FAILED, instructions: String = "Explain it",
        activeRevisionId: String? = null, lockedRevisionId: String? = null, lockedContentHash: String? = null,
        finalAudioPath: String? = null) = EpisodeEntity(
        id = "episode-1", title = "Untitled episode", phase = phase, instructions = instructions,
        reviewEnabled = true, activeRevisionId = activeRevisionId, lockedRevisionId = lockedRevisionId,
        lockedContentHash = lockedContentHash, lockedAtEpochMs = lockedContentHash?.let { 1L },
        finalAudioPath = finalAudioPath, durationMs = null, currentChapterPosition = null,
        failurePhase = null, failureMessage = "stopped", createdAtEpochMs = 1, updatedAtEpochMs = 2)

    private fun job(kind: String = JobKind.SCRIPT, status: String = JobStatus.FAILED, episodeId: String = "episode-1") =
        GenerationJobEntity("job-1", episodeId, kind, status, null, 0, 0, "Generation failed", "boom", 1, 2)

    @Test fun aStoppedScriptWithNoSavedRevisionCanBeRetried() {
        assertTrue(canRetryFailedGeneration(episode(), job()))
    }

    @Test fun aStoppedAudioRunWithALockedScriptCanBeRetried() {
        assertTrue(canRetryFailedGeneration(
            episode(lockedRevisionId = "revision-1", lockedContentHash = "hash"), job(kind = JobKind.AUDIO)))
    }

    @Test fun aFailedChatEditUsesDraftRecoveryInsteadOfRetry() {
        assertFalse(canRetryFailedGeneration(episode(activeRevisionId = "revision-1"), job(kind = JobKind.AGENT_EDIT)))
    }

    @Test fun nothingIsRetriedUnlessTheEpisodeAndItsLatestJobBothFailed() {
        assertFalse(canRetryFailedGeneration(episode(phase = EpisodePhase.GENERATING_SCRIPT), job()))
        assertFalse(canRetryFailedGeneration(episode(), job(status = JobStatus.RUNNING)))
        assertFalse(canRetryFailedGeneration(episode(), job(status = JobStatus.COMPLETE)))
        assertFalse(canRetryFailedGeneration(null, job()))
        assertFalse(canRetryFailedGeneration(episode(), null))
    }

    @Test fun aRetryNeverOffersToOverwriteSavedOrFinishedWork() {
        // A saved script revision means the script run already produced durable content.
        assertFalse(canRetryFailedGeneration(episode(activeRevisionId = "revision-1"), job()))
        assertFalse(canRetryFailedGeneration(episode(lockedRevisionId = "revision-1", lockedContentHash = "hash"), job()))
        // A finished episode must never be rebuilt by a retry.
        assertFalse(canRetryFailedGeneration(
            episode(lockedRevisionId = "revision-1", lockedContentHash = "hash", finalAudioPath = "final.wav"),
            job(kind = JobKind.AUDIO)))
        // Audio cannot restart without the locked script it consumes.
        assertFalse(canRetryFailedGeneration(episode(), job(kind = JobKind.AUDIO)))
    }

    @Test fun aScriptRetryNeedsInstructionsAndTheJobMustBelongToTheEpisode() {
        assertFalse(canRetryFailedGeneration(episode(instructions = "   "), job()))
        assertFalse(canRetryFailedGeneration(episode(), job(episodeId = "another-episode")))
    }
}
