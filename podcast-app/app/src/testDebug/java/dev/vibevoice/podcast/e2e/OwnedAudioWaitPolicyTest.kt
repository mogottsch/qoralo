package dev.vibevoice.podcast.e2e

import dev.vibevoice.podcast.data.GenerationJobEntity
import dev.vibevoice.podcast.data.JobKind
import dev.vibevoice.podcast.data.JobStatus
import org.junit.Assert.*
import org.junit.Test

class OwnedAudioWaitPolicyTest {
    private fun job(status:String)=GenerationJobEntity("j","e",JobKind.AUDIO,status,"r",0,1,"guard",null,1,1)
    @Test fun admissionFailureWinsImmediatelyEvenIfListenIsAbsentOrStaleVisible() {
        val failed=job(JobStatus.FAILED).copy(failureStage="owned_resource_guard",errorMessage="Owned validation stopped: ADMISSION")
        for(visible in listOf(false,true)) assertEquals(OwnedListenDecision.TERMINAL,OwnedAudioWaitPolicy.listen("e","j",failed,visible))
        assertEquals("Owned validation stopped: ADMISSION",failed.errorMessage)
        assertFalse(OwnedAudioWaitPolicy.retainRunning("e","j",failed))
    }
    @Test fun onlyRunningExactOwnedAttemptCanExposeListenOrBeAwaitedAfterUiFailure() {
        val running=job(JobStatus.RUNNING)
        assertEquals(OwnedListenDecision.WAIT,OwnedAudioWaitPolicy.listen("e","j",running,false))
        assertEquals(OwnedListenDecision.LISTEN,OwnedAudioWaitPolicy.listen("e","j",running,true))
        assertTrue(OwnedAudioWaitPolicy.retainRunning("e","j",running))
        for(other in listOf(null,running.copy(id="other"),running.copy(episodeId="other"),running.copy(kind=JobKind.SCRIPT))) {
            assertEquals(OwnedListenDecision.IDENTITY_CHANGED,OwnedAudioWaitPolicy.listen("e","j",other,true))
            assertFalse(OwnedAudioWaitPolicy.retainRunning("e","j",other))
        }
    }
    @Test fun queuedAndCompletedWorkAreNotContinuedAfterUiFailure() {
        assertEquals(OwnedListenDecision.WAIT,OwnedAudioWaitPolicy.listen("e","j",job(JobStatus.QUEUED),true))
        assertEquals(OwnedListenDecision.TERMINAL,OwnedAudioWaitPolicy.listen("e","j",job(JobStatus.COMPLETE),false))
        assertFalse(OwnedAudioWaitPolicy.retainRunning("e","j",job(JobStatus.QUEUED)))
        assertFalse(OwnedAudioWaitPolicy.retainRunning("e","j",job(JobStatus.COMPLETE)))
    }
}
