package dev.vibevoice.podcast.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.requiredWidth
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.assertHasClickAction
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.hasSetTextAction
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.vibevoice.podcast.data.ChapterAudioEntity
import dev.vibevoice.podcast.data.ChapterEntity
import dev.vibevoice.podcast.data.EpisodeEntity
import dev.vibevoice.podcast.data.EpisodePhase
import dev.vibevoice.podcast.data.GenerationJobEntity
import dev.vibevoice.podcast.data.JobKind
import dev.vibevoice.podcast.data.JobStatus
import dev.vibevoice.podcast.ui.theme.VibeVoiceTheme
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.io.RandomAccessFile

@RunWith(AndroidJUnit4::class)
class ScreenSemanticsTest {
    @get:Rule val rule = createComposeRule()

    @Test fun libraryAndSourcesExposeFunctionalPrimaryActionsAt320dpAnd2xFont() {
        setNarrow { LibraryScreen(emptyList(), {}, {}, {}) }
        rule.onNodeWithText("Create an episode").assertIsDisplayed().assertHasClickAction()
        setNarrow { SourcesScreen(emptyList(), {}, { _, _ -> }, {}, {}, {}) }
        rule.onNodeWithText("Paste text").assertIsDisplayed().assertHasClickAction()
        rule.onNodeWithText("Choose a file").assertIsDisplayed().assertHasClickAction()
        rule.onNodeWithText("Continue").assertIsDisplayed()
    }

    @Test fun instructionsHaveOneEditableFieldHintChipsReviewToggleAndCreate() {
        val episode = episode(EpisodePhase.INSTRUCTIONS)
        rule.setContent { VibeVoiceTheme { InstructionsScreen(episode, {}, { _, _ -> }) } }
        assertEquals(1, rule.onAllNodes(hasSetTextAction()).fetchSemanticsNodes().size)
        rule.onNodeWithText("Length").performClick()
        rule.onNodeWithText("Initial instructions", useUnmergedTree = true).assertExists()
        rule.onNodeWithText("Create").assertIsEnabled()
        rule.onNodeWithText("Review script first").assertIsDisplayed()
    }

    @Test fun reviewAgentAndLockKeepTranscriptReadOnlyAndConsequencesExplicit() {
        var agent by mutableStateOf(false)
        var lock by mutableStateOf(false)
        rule.setContent {
            VibeVoiceTheme {
                ReviewScreen(chapters(), emptyList(), null, agent, lock, {}, { agent = true }, { agent = false }, {}, { lock = true }, { lock = false }, {})
            }
        }
        assertEquals(0, rule.onAllNodes(hasSetTextAction()).fetchSemanticsNodes().size)
        rule.onNodeWithText("Edit with agent").performClick()
        rule.onNodeWithText("I can rewrite, shorten, remove, split, combine, or rename chapters.").assertIsDisplayed()
        rule.onNodeWithText("Ask for a change…").assertIsDisplayed()
        agent = false; lock = true
        rule.onNodeWithText("Ready to create audio?").assertIsDisplayed()
        rule.onNodeWithText("These 2 chapters can’t be changed once audio generation starts.").assertIsDisplayed()
        rule.onNodeWithText("Lock & create").assertHasClickAction()
    }

    @Test fun generationShowsChapterProgressAndFailClosedBoundary() {
        val job = GenerationJobEntity("job", "episode", JobKind.AUDIO, JobStatus.RUNNING, "revision", 1, 2, "Creating One", null, 1, 2)
        rule.setContent { VibeVoiceTheme { GeneratingScreen(episode(EpisodePhase.GENERATING_AUDIO), job, {}) } }
        rule.onNodeWithText("CHAPTER 1 OF 2").assertIsDisplayed()
        rule.onNodeWithText("The selected inference route must succeed; no fallback will be used.").assertIsDisplayed()
    }

    @Test fun playerExposesTransportExportAndLyricsLikeFrozenTranscript() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val wav = File(context.cacheDir, "ui-player.wav").also { writeWav(it, 44_100) }
        val episode = episode(EpisodePhase.FROZEN_READY).copy(title = "Why cities remember rivers", finalAudioPath = wav.path, durationMs = 1_000)
        val chapter = chapters().first()
        val audio = ChapterAudioEntity("audio", "episode", "revision", chapter.stableChapterId, 0, wav.path, "a".repeat(64), wav.length(), 44_100, 1, 44_100, 0, 44_100)
        rule.setContent { VibeVoiceTheme { PlayerScreen(episode, listOf(chapter), listOf(audio), null, wav, {}, {}, { _, _, _ -> }) } }
        rule.onNodeWithText("Now playing").assertIsDisplayed()
        rule.onNodeWithContentDescription("Play").assertHasClickAction()
        rule.onNodeWithText("Transcript").performClick()
        rule.onNodeWithText("Chapter 1 · Before the street grid").assertIsDisplayed()
        rule.onNodeWithText("Every city carries the shape of the water that made it.").assertIsDisplayed()
    }

    private fun setNarrow(content: @androidx.compose.runtime.Composable () -> Unit) {
        rule.setContent {
            val density = LocalDensity.current
            CompositionLocalProvider(LocalDensity provides Density(density.density, 2f)) {
                Box(Modifier.requiredWidth(320.dp)) { VibeVoiceTheme { content() } }
            }
        }
    }

    private fun episode(phase: String) = EpisodeEntity(
        "episode", "Episode", phase, "", true, "revision", if (phase == EpisodePhase.FROZEN_READY || phase == EpisodePhase.GENERATING_AUDIO) "revision" else null,
        if (phase == EpisodePhase.FROZEN_READY || phase == EpisodePhase.GENERATING_AUDIO) "a".repeat(64) else null, 1, null, null, null, null, null, 1, 2,
    )

    private fun chapters() = listOf(
        ChapterEntity("row-1", "revision", "chapter-1", 0, "Before the street grid", "Every city carries the shape of the water that made it.", 60),
        ChapterEntity("row-2", "revision", "chapter-2", 1, "What flooding remembers", "The water has not forgotten.", 60),
    )

    private fun writeWav(file: File, frames: Int) {
        RandomAccessFile(file, "rw").use { out ->
            val bytes = frames * 2L; out.setLength(0)
            out.writeBytes("RIFF"); out.u32(36 + bytes); out.writeBytes("WAVEfmt "); out.u32(16)
            out.u16(1); out.u16(1); out.u32(44_100); out.u32(88_200); out.u16(2); out.u16(16)
            out.writeBytes("data"); out.u32(bytes); repeat(frames) { out.u16(if (it % 2 == 0) 500 else 0) }
        }
    }
    private fun RandomAccessFile.u16(value: Int) { write(value and 255); write((value ushr 8) and 255) }
    private fun RandomAccessFile.u32(value: Long) { u16((value and 0xFFFF).toInt()); u16(((value ushr 16) and 0xFFFF).toInt()) }
}
