package dev.vibevoice.podcast.ui

import dev.vibevoice.podcast.data.EpisodePhase

fun screenForPersistedPhase(phase: String?): AppScreen = when (phase) {
    null -> AppScreen.Library
    EpisodePhase.SOURCES -> AppScreen.Sources
    EpisodePhase.INSTRUCTIONS -> AppScreen.Instructions
    EpisodePhase.GENERATING_SCRIPT, EpisodePhase.LOCKED, EpisodePhase.GENERATING_AUDIO, EpisodePhase.FAILED -> AppScreen.Generating
    EpisodePhase.SCRIPT_DRAFT -> AppScreen.Review
    EpisodePhase.FROZEN_READY -> AppScreen.Player
    else -> AppScreen.Library
}
