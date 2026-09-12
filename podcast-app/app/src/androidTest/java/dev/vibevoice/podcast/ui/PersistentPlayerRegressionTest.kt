package dev.vibevoice.podcast.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.vibevoice.podcast.data.*
import dev.vibevoice.podcast.ui.theme.VibeVoiceTheme
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.io.RandomAccessFile

/** Synthetic PCM/UI evidence only. No model loading, synthesis, or user database writes. */
@RunWith(AndroidJUnit4::class)
class PersistentPlayerRegressionTest {
    @get:Rule val rule = createComposeRule()

    @Test fun sharedPlayerKeepsPlayingThroughCollapseNavigationReopenAndBindsControlsToActiveEpisode() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val root = File(context.cacheDir, "persistent-player-test-${System.nanoTime()}").also { it.mkdirs() }
        val file = File(root, "synthetic-silence.wav").also(::writeSilentWav)
        val database = Room.inMemoryDatabaseBuilder(context, PodcastDatabase::class.java).allowMainThreadQueries().build()
        val repository = PodcastRepository(database, ArtifactStore(File(root, "episodes"), File(root, "models")), providerAdmission = false)
        val a = episode("a")
        val b = episode("b")
        runBlocking { database.podcastDao().insertEpisode(a); database.podcastDao().insertEpisode(b) }
        lateinit var host: PlaybackHost
        var expanded by mutableStateOf(true)
        var route by mutableStateOf("Library")
        val writes = mutableListOf<Pair<String, Long>>()
        rule.setContent {
            host = remember { PlaybackHost(context) }
            PlaybackHostEffects(host, repository)
            VibeVoiceTheme {
                Column {
                    val active = host.active
                    if (active != null && !expanded) MiniPlayer(active.episode.title, active.session, { expanded = true })
                    if (active != null && expanded) PlayerScreen(active.episode, emptyList(), emptyList(), null, null,
                        onBack = { expanded = false }, onExport = {}, onPersist = { _, _, _ -> }, sharedPlayback = active)
                    else Text(route)
                }
            }
        }
        try {
            rule.runOnIdle { host.open(a, emptyList(), emptyList(), null, file, null, PlaybackStateEntity("a", 12_000, 1.5f, false, 1)) { p, _, _ -> writes += "a" to p } }
            val session = host.active!!.session
            val player = session.player
            rule.onNodeWithContentDescription("Play", useUnmergedTree = true).performClick()
            rule.waitUntil(10_000) { session.isPlaying }
            val before = session.positionMs
            rule.onNodeWithContentDescription("Minimize player").performClick()
            rule.onNodeWithContentDescription("Open player: Synthetic episode a").assertIsDisplayed()
            for (destination in listOf("Settings", "Sources for episode b", "Library")) {
                rule.runOnIdle { route = destination }
                rule.onNodeWithText(destination).assertIsDisplayed()
            }
            rule.waitUntil(10_000) { session.positionMs > before + 500 }
            rule.onNodeWithContentDescription("Pause", useUnmergedTree = true).performClick()
            rule.runOnIdle { assertSame(player, host.active!!.session.player); assertFalse(session.wantsPlayback); assertEquals(1.5f, session.speed) }
            val paused = session.positionMs
            rule.onNodeWithContentDescription("Open player: Synthetic episode a").performClick()
            rule.runOnIdle {
                assertSame(session, host.active!!.session); assertEquals(paused, session.positionMs)
                host.open(a, emptyList(), emptyList(), null, file, null, PlaybackStateEntity("a", 0, 1f, false, 2)) { _, _, _ -> fail("Reopen must not install a second session") }
                assertSame(session, host.active!!.session); assertEquals(1.5f, session.speed)
            }
            rule.onNodeWithContentDescription("Minimize player").performClick()
            rule.onNodeWithContentDescription("Back 15 seconds", useUnmergedTree = true).performClick()
            rule.runOnIdle { assertEquals((paused - 15_000).coerceAtLeast(0), session.positionMs) }
            rule.runOnIdle {
                host.open(b, emptyList(), emptyList(), null, file, null, null) { p, _, _ -> writes += "b" to p }
                assertEquals("b", host.active!!.session.episodeId); assertNotSame(player, host.active!!.session.player)
                assertTrue(writes.any { it.first == "a" }); assertFalse(writes.any { it.first == "b" })
                host.close()
            }
        } finally {
            rule.runOnIdle { host.close() }
            rule.waitForIdle()
            database.close(); root.deleteRecursively()
        }
    }

    @Test fun manualTranscriptScrollSurvivesChapterChangesUntilExplicitFollow() {
        var position by mutableLongStateOf(0)
        val rows = (0..15).map { i -> TranscriptPassage("p$i", "c${i / 4}", i / 4, "Synthetic chapter ${i / 4}",
            "Synthetic passage $i. This complete passage has measured segment timing, not individual word alignment.",
            TranscriptInterval(i * 44_100L, (i + 1) * 44_100L, 44_100), TranscriptPrecision.SEGMENT) }
        rule.setContent { VibeVoiceTheme { TranscriptSheet("synthetic", TranscriptTimeline(rows), position, true, false, {}) } }
        rule.onNodeWithText("Following · stop").assertIsDisplayed()
        rule.onNode(hasScrollToIndexAction()).performTouchInput { swipeUp() }
        rule.onNodeWithText("Follow playback").assertIsDisplayed()
        val before = rule.onNode(hasScrollToIndexAction()).fetchSemanticsNode().config[SemanticsProperties.VerticalScrollAxisRange].value()
        rule.runOnIdle { position = 15_000 }
        val after = rule.onNode(hasScrollToIndexAction()).fetchSemanticsNode().config[SemanticsProperties.VerticalScrollAxisRange].value()
        assertEquals("Chapter advancement must not scroll against the reader", before, after, 0.01f)
        rule.onNodeWithText("Follow playback").performClick()
        rule.onNodeWithText(rows.last().text).assertIsDisplayed()
        rule.onNodeWithText("Following · stop").assertIsDisplayed()
    }

    private fun episode(id: String) = EpisodeEntity(id, "Synthetic episode $id", EpisodePhase.FROZEN_READY, "", true,
        "revision-$id", "revision-$id", "hash-$id", 1, null, 60_000, null, null, null, 1, 1)

    private fun writeSilentWav(file: File) {
        RandomAccessFile(file, "rw").use { out ->
            val bytes = 60 * 44_100L * 2
            out.setLength(44 + bytes)
            fun u16(v: Int) { out.write(v and 255); out.write((v ushr 8) and 255) }
            fun u32(v: Long) { u16((v and 65535).toInt()); u16(((v ushr 16) and 65535).toInt()) }
            out.seek(0); out.writeBytes("RIFF"); u32(36 + bytes); out.writeBytes("WAVEfmt "); u32(16)
            u16(1); u16(1); u32(44_100); u32(88_200); u16(2); u16(16); out.writeBytes("data"); u32(bytes)
        }
    }
}
