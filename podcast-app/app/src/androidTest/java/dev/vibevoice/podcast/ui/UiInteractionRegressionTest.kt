package dev.vibevoice.podcast.ui

import androidx.compose.ui.geometry.Offset
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.espresso.Espresso
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.vibevoice.podcast.data.*
import dev.vibevoice.podcast.ui.theme.VibeVoiceTheme
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.io.RandomAccessFile
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference

@RunWith(AndroidJUnit4::class)
class UiInteractionRegressionTest {
    @get:Rule val rule = createComposeRule()

    @Test fun nearLimitHintIsDisabledThenEditingRestoresValidInsertion() {
        val observed = AtomicReference("")
        rule.setContent { VibeVoiceTheme { InstructionsScreen(episode(EpisodePhase.INSTRUCTIONS).copy(instructions = "a".repeat(1990)), {}, { _, _ -> },
            onDraftChanged = { text, _ -> observed.set(text) }) } }
        rule.onNodeWithText("Length").performScrollTo().assertIsNotEnabled()
        rule.onNode(hasSetTextAction()).performScrollTo().performTextReplacement("Edited draft")
        Espresso.closeSoftKeyboard()
        rule.onNodeWithText("Length").performScrollTo().assertIsEnabled().performClick()
        rule.runOnIdle { assertEquals("Edited draft\nKeep it under five minutes.", observed.get()) }
        rule.onNodeWithText("Create").assertIsDisplayed().assertIsEnabled()
    }

    @Test fun pausedScrubPreviewSurvivesMoreThanOnePollingInterval() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val file = File(context.cacheDir, "synthetic-scrub-silence-60s.wav").also(::writeSilentWav)
        val saved = AtomicLong(-1)
        rule.setContent { VibeVoiceTheme { PlayerScreen(episode(EpisodePhase.FROZEN_READY), emptyList(), emptyList(), null, file, {}, {},
            { position, _, _ -> saved.set(position) }) } }
        val slider = rule.onNodeWithContentDescription("Playback position")
        slider.assertIsDisplayed().performTouchInput {
            down(Offset(center.x * 0.4f, center.y))
            moveTo(Offset(center.x * 1.5f, center.y))
        }
        Thread.sleep(1100)
        rule.mainClock.advanceTimeBy(1200)
        slider.performTouchInput { up() }
        rule.runOnIdle { assertTrue("Committed scrub target was ${saved.get()}, not the held preview", saved.get() in 40_000L..55_000L) }
    }

    @Test fun switchingEpisodesDisposesPlaybackToItsOriginalOwner() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val a = episode(EpisodePhase.FROZEN_READY).copy(id = "episode-a")
        val b = episode(EpisodePhase.FROZEN_READY).copy(id = "episode-b")
        var shown by mutableStateOf(a)
        val files = mapOf(a.id to File(context.cacheDir, "owner-a.wav").also(::writeSilentWav),
            b.id to File(context.cacheDir, "owner-b.wav").also(::writeSilentWav))
        val writes = mutableMapOf<String, Pair<Long, Float>>()
        rule.setContent {
            val current = shown
            VibeVoiceTheme { PlayerScreen(current, emptyList(), emptyList(),
                if (current.id == a.id) PlaybackStateEntity(a.id, 30_000, 1.5f, false, 1) else null,
                files.getValue(current.id), {}, {}, { position, speed, _ -> writes[current.id] = position to speed }) }
        }
        rule.waitForIdle()
        rule.runOnIdle { shown = b }
        rule.waitForIdle()
        rule.runOnIdle {
            assertEquals(30_000L, writes[a.id]?.first)
            assertEquals(1.5f, writes[a.id]?.second)
            assertFalse("A's disposal must not save into B", writes.containsKey(b.id))
        }
    }

    private fun episode(phase: String) = EpisodeEntity("ui-test", "Synthetic UI episode", phase, "", true, null, null, null, null,
        null, 60_000, null, null, null, 1, 1)

    private fun writeSilentWav(file: File) {
        RandomAccessFile(file, "rw").use { out ->
            val bytes = 60 * 44_100L * 2
            out.setLength(44 + bytes)
            out.seek(0); out.writeBytes("RIFF"); out.u32(36 + bytes); out.writeBytes("WAVEfmt "); out.u32(16)
            out.u16(1); out.u16(1); out.u32(44_100); out.u32(88_200); out.u16(2); out.u16(16)
            out.writeBytes("data"); out.u32(bytes)
        }
    }
    private fun RandomAccessFile.u16(value: Int) { write(value and 255); write((value ushr 8) and 255) }
    private fun RandomAccessFile.u32(value: Long) { u16((value and 65535).toInt()); u16(((value ushr 16) and 65535).toInt()) }
}
