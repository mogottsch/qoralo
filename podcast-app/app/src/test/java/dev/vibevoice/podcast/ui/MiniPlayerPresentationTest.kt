package dev.vibevoice.podcast.ui

import dev.vibevoice.podcast.runtime.AudioAttemptBinding
import dev.vibevoice.podcast.runtime.AudioAvailabilityState
import org.junit.Assert.*
import org.junit.Test

class MiniPlayerPresentationTest {
    @Test fun bufferingRetainsPauseActionButExplicitPauseAndFocusLossShowPlay() {
        val buffering = MiniPlayerPresentation.from(false, true, true, AudioAvailabilityState.GENERATING, null, true)
        assertTrue(buffering.pauseAction); assertTrue(buffering.status.startsWith("Buffering"))
        val preparing = MiniPlayerPresentation.from(false, true, false, null, null, false)
        assertTrue(preparing.pauseAction); assertEquals("Buffering", preparing.status)
        // USER_PAUSE, AUDIO_FOCUS and NOISY_ROUTE all clear wantsPlayback in the shared session.
        val paused = MiniPlayerPresentation.from(false, false, false, AudioAvailabilityState.GENERATING, null, false)
        assertFalse(paused.pauseAction); assertEquals("Paused", paused.status)
    }
    @Test fun staleDisablesControlsAndDoesNotAdvertisePlayback() {
        val stale = MiniPlayerPresentation.from(false, false, false, AudioAvailabilityState.STALE, "Changed attempt", false)
        assertFalse(stale.controlsEnabled); assertFalse(stale.pauseAction); assertEquals("Changed attempt", stale.status)
    }
    @Test fun stoppedGenerationIsStillPlayableWhileFinishedMasterCanReplay() {
        assertTrue(MiniPlayerPresentation.from(false, false, false, AudioAvailabilityState.FAILED, null, false).controlsEnabled)
        val done = MiniPlayerPresentation.from(false, false, false, null, null, true)
        assertEquals("Finished", done.status); assertFalse(done.pauseAction); assertTrue(done.controlsEnabled)
    }
    @Test fun activeIdentitySurvivesMinimizeNavigationReopenAndLiveFinalization() {
        val binding = AudioAttemptBinding("a", "attempt", "revision", "revision-hash", "pack-hash")
        val live = PlaybackIdentity("a", binding, null)
        assertTrue(live.canReuse("a", "attempt", null))
        assertTrue(live.canReuse("a", null, "/master-after-finalization.wav"))
        assertFalse(live.canReuse("b", null, null))
        assertFalse(live.canReuse("a", "different-attempt", null))
        val final = PlaybackIdentity("a", null, "/master.wav")
        assertTrue(final.canReuse("a", null, "/master.wav"))
        assertFalse(final.canReuse("a", null, "/different-master.wav"))
        assertFalse(final.canReuse("a", "attempt", "/master.wav"))
        assertFalse(final.canReuse("b", null, "/master.wav"))
    }
}
