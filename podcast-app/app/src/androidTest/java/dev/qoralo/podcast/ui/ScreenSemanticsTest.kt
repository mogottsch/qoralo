package dev.qoralo.podcast.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.requiredWidth
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.assertHasClickAction
import androidx.compose.ui.test.assertHasNoClickAction
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.hasSetTextAction
import androidx.compose.ui.test.hasScrollToIndexAction
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.performScrollToNode
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performSemanticsAction
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.qoralo.podcast.data.ChapterAudioEntity
import dev.qoralo.podcast.data.ChapterEntity
import dev.qoralo.podcast.data.EpisodeEntity
import dev.qoralo.podcast.data.EpisodePhase
import dev.qoralo.podcast.data.GenerationJobEntity
import dev.qoralo.podcast.data.JobKind
import dev.qoralo.podcast.data.JobStatus
import dev.qoralo.podcast.ui.theme.QoraloTheme
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.io.RandomAccessFile

@RunWith(AndroidJUnit4::class)
class ScreenSemanticsTest {
    @get:Rule val rule = createComposeRule()
    private lateinit var platformDensity: Density
    private lateinit var wrapperDensity: Density

    @Test fun libraryExposesFunctionalPrimaryActionAt320dpAnd2xFont() {
        setNarrow { LibraryScreen(emptyList(), {}, {}, {}) }
        rule.onNodeWithText("Create an episode").assertIsDisplayed().assertHasClickAction()
    }

    @Test fun sourcesExposeFunctionalPrimaryActionsAt320dpAnd2xFont() {
        setNarrow { SourcesScreen(emptyList(), {}, { _, _ -> }, {}, {}, {}) }
        rule.onNodeWithText("Paste text").assertIsDisplayed().assertHasClickAction()
        rule.onNodeWithText("Choose a file").assertIsDisplayed().assertHasClickAction()
        rule.onNodeWithText("Continue").assertIsDisplayed()
    }

    @Test fun libraryShowsUnfinishedEpisodeAsResumableStatusRow() {
        val unfinished = episode(EpisodePhase.SCRIPT_DRAFT).copy(title = "Draft episode")
        setNarrow { LibraryScreen(listOf(unfinished), {}, {}, {}) }
        rule.onNodeWithText("Continue creating").assertExists()
        rule.onNodeWithText("Draft episode").assertExists().assertHasClickAction()
        rule.onNodeWithText("Draft ready to review").assertExists()
    }

    @Test fun instructionsHaveOneEditableFieldHintChipsReviewToggleAndCreate() {
        val episode = episode(EpisodePhase.INSTRUCTIONS)
        setNarrow { InstructionsScreen(episode, {}, { _, _ -> }) }
        assertEquals(1, rule.onAllNodes(hasSetTextAction()).fetchSemanticsNodes().size)
        rule.onNodeWithText("Initial instructions", useUnmergedTree = true).assertExists()
        rule.onNodeWithText("Create").assertIsDisplayed()
        rule.onNode(hasScrollToIndexAction()).performScrollToNode(hasText("Length"))
        rule.onNodeWithText("Length").assertIsDisplayed().performClick()
        rule.onNodeWithText("Create").assertIsDisplayed().assertIsEnabled()
        rule.onNode(hasScrollToIndexAction()).performScrollToNode(hasText("Review script first"))
        rule.onNodeWithText("Review script first").assertIsDisplayed()
        rule.onNodeWithContentDescription("Review script first").assertIsDisplayed().assertHasClickAction()
    }

    @Test fun reviewAgentAndLockKeepTranscriptReadOnlyAndConsequencesExplicit() {
        var agent by mutableStateOf(false)
        var lock by mutableStateOf(false)
        setNarrow {
            ReviewScreen(chapters(), emptyList(), null, agent, lock, {}, { agent = true }, { agent = false }, {}, { lock = true }, { lock = false }, {})
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
        var current by mutableStateOf(episode(EpisodePhase.GENERATING_AUDIO))
        setNarrow { GeneratingScreen(current, job, {}) }
        assertReadableText("Creating episode")
        rule.onNodeWithText("CHAPTER 1 OF 2").assertIsDisplayed()
        rule.onNodeWithText("The selected inference route must succeed; no fallback will be used.").performScrollTo().assertIsDisplayed()
        rule.runOnIdle { current = current.copy(phase = EpisodePhase.FAILED, failureMessage = "Synthetic failure") }
        assertReadableText("Episode stopped")
    }

    @Test fun readyHeroUsesReadableFullWidthMetadataAndNoEmptyRecentHeading() {
        val current = episode(EpisodePhase.FROZEN_READY).copy(title = "Why cities remember rivers", durationMs = 30_000)
        setNarrow { LibraryScreen(listOf(current), {}, {}, {},
            listOf(dev.qoralo.podcast.data.PlaybackStateEntity(current.id, 12_000, 1.5f, false, 1)), mapOf(current.id to 3)) }
        assertReadableText("CONTINUE LISTENING")
        rule.onNodeWithText(current.title).assertExists().assertHasClickAction()
        rule.onNodeWithText("Recent episodes").assertDoesNotExist()
    }

    @Test fun playerExposesTransportExportAndLyricsLikeFrozenTranscript() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val wav = File(context.cacheDir, "ui-player.wav").also { writeWav(it, 44_100) }
        val episode = episode(EpisodePhase.FROZEN_READY).copy(title = "Why cities remember rivers", finalAudioPath = wav.path, durationMs = 1_000)
        val chapter = chapters().first()
        val audio = ChapterAudioEntity("audio", "episode", "revision", chapter.stableChapterId, 0, wav.path, "a".repeat(64), wav.length(), 44_100, 1, 44_100, 0, 44_100)
        setNarrow { PlayerScreen(episode, listOf(chapter), listOf(audio), null, wav, {}, {}, { _, _, _ -> }) }
        rule.onNodeWithText("Now playing").assertIsDisplayed()
        assertReadableText("−15")
        assertReadableText("+15")
        rule.onNodeWithContentDescription("Play").assertHasClickAction()
        rule.onNodeWithText("Transcript").performClick()
        rule.onNodeWithText("Chapter 1 · Before the street grid").assertIsDisplayed()
        rule.onNodeWithText("Frozen chapter transcript").assertIsDisplayed()
        rule.onNodeWithText("Follows playback").assertDoesNotExist()
        rule.onNodeWithText("Every city carries the shape of the water that made it.").assertIsDisplayed().assertHasNoClickAction()
    }

    private fun assertReadableText(text: String) {
        val node = rule.onNodeWithText(text).assertIsDisplayed()
        val layouts = mutableListOf<TextLayoutResult>()
        node.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { action -> action(layouts) }
        TextLayoutDiagnostics.retain(text, node, layouts, platformDensity, wrapperDensity)
        assertTrue("No real text layout for $text", layouts.isNotEmpty())
        val ancestors = generateSequence(node.fetchSemanticsNode()) { it.parent }.take(64).toList()
        assertTrue("Semantic ancestor chain too deep for $text", ancestors.last().parent == null)
        val problems = TextReadabilityAssertions.problems(text, layouts.map(TextReadabilityAssertions::snapshot), ancestors.map { it.boundsInRoot })
        assertTrue("Unreadable $text: ${problems.joinToString()}", problems.isEmpty())
        assertTrue("Ancestor clips the text height for $text", node.fetchSemanticsNode().boundsInRoot.height + 1 >= layouts.maxOf { it.size.height })
    }

    private fun setNarrow(content: @androidx.compose.runtime.Composable () -> Unit) {
        rule.setContent {
            val density = LocalDensity.current
            val wrapper = Density(density.density, 2f)
            SideEffect { platformDensity = density; wrapperDensity = wrapper }
            CompositionLocalProvider(LocalDensity provides wrapper) {
                Box(Modifier.requiredWidth(320.dp)) { QoraloTheme { content() } }
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
