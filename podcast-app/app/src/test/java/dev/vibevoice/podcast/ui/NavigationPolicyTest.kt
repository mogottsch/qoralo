package dev.vibevoice.podcast.ui

import dev.vibevoice.podcast.data.EpisodePhase
import org.junit.Assert.assertEquals
import org.junit.Test

class NavigationPolicyTest {
    @Test fun everyPersistedLifecyclePhaseResumesToAnAccessibleScreen() {
        val expected = mapOf(
            EpisodePhase.SOURCES to AppScreen.Sources,
            EpisodePhase.INSTRUCTIONS to AppScreen.Instructions,
            EpisodePhase.GENERATING_SCRIPT to AppScreen.Generating,
            EpisodePhase.SCRIPT_DRAFT to AppScreen.Review,
            EpisodePhase.LOCKED to AppScreen.Generating,
            EpisodePhase.GENERATING_AUDIO to AppScreen.Generating,
            EpisodePhase.FROZEN_READY to AppScreen.Player,
            EpisodePhase.FAILED to AppScreen.Generating,
        )
        expected.forEach { (phase, screen) -> assertEquals("phase=$phase", screen, screenForPersistedPhase(phase)) }
    }
}
