package dev.vibevoice.podcast.ui

import android.graphics.Bitmap
import android.os.Bundle
import android.os.SystemClock
import androidx.compose.foundation.layout.*
import androidx.compose.material3.Text
import androidx.compose.material3.Surface
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.vibevoice.podcast.data.*
import dev.vibevoice.podcast.runtime.AudioAttemptBinding
import dev.vibevoice.podcast.runtime.AudioAvailability
import dev.vibevoice.podcast.runtime.AudioAvailabilityState
import dev.vibevoice.podcast.runtime.AudioPassageKind
import dev.vibevoice.podcast.runtime.AvailableAudioChunk
import dev.vibevoice.podcast.runtime.ProviderTextFrontend
import dev.vibevoice.podcast.ui.theme.QoraloTheme
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.io.RandomAccessFile
import java.security.MessageDigest
import org.json.JSONObject
import org.json.JSONArray

/** Synthetic PCM/UI evidence only. No model loading, synthesis, or user database writes. */
@RunWith(AndroidJUnit4::class)
class PersistentPlayerRegressionTest {
    @get:Rule val rule = createComposeRule()
    private val captureAttempt = System.currentTimeMillis().toString() + "-" + System.nanoTime().toString()

    @Test fun sharedPlayerKeepsPlayingThroughCollapseNavigationReopenAndBindsControlsToActiveEpisode() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val root = File(context.cacheDir, "persistent-player-test-${System.nanoTime()}").also { it.mkdirs() }
        val file = File(root, "synthetic-silence.wav").also(::writeSilentWav)
        val database = Room.inMemoryDatabaseBuilder(context, PodcastDatabase::class.java).allowMainThreadQueries().build()
        val repository = PodcastRepository(database, ArtifactStore(File(root, "episodes"), File(root, "models")), providerAdmission = false)
        val a = episode("a")
        val b = episode("b")
        runBlocking {
            for (ep in listOf(a, b)) {
                database.podcastDao().insertEpisode(ep)
                database.podcastDao().insertRevision(ScriptRevisionEntity("revision-${ep.id}", ep.id, null, 1,
                    ep.title, "hash-${ep.id}", "synthetic-${ep.id}.json", 1))
                database.podcastDao().insertChapters(listOf(ChapterEntity("row-${ep.id}", "revision-${ep.id}", "chapter-${ep.id}",
                    0, "Synthetic chapter", "This is a synthetic playback fixture. No model or user content is involved.", 60)))
            }
        }
        lateinit var host: PlaybackHost
        var expanded by mutableStateOf(true)
        var route by mutableStateOf("Library")
        var statusBarTopPx = 0
        val writes = mutableListOf<Pair<String, Long>>()
        rule.setContent {
            host = remember { PlaybackHost(context) }
            PlaybackHostEffects(host, repository)
            QoraloTheme {
                statusBarTopPx = WindowInsets.statusBars.getTop(LocalDensity.current)
                Surface(color = MaterialTheme.colorScheme.surface) {
                // Mirror PodcastApp's edge-to-edge inset ownership, not a bare fixture Column.
                Column(Modifier.fillMaxSize().then(if (!expanded) Modifier.windowInsetsPadding(WindowInsets.statusBars) else Modifier)) {
                    val active = host.active
                    if (active != null && !expanded) MiniPlayer(active.episode.title, active.session, { expanded = true })
                    if (active != null && expanded) PlayerScreen(active.episode, active.chapters, active.audio, null, null,
                        onBack = { expanded = false }, onExport = {}, onPersist = { _, _, _ -> }, sharedPlayback = active)
                    else Text(route)
                }
                }
            }
        }
        try {
            rule.runOnIdle { host.open(a, emptyList(), emptyList(), null, file, null, PlaybackStateEntity("a", 12_000, 1.5f, false, 1)) { p, _, _ -> writes += "a" to p } }
            val session = host.active!!.session
            val player = session.player
            rule.onNodeWithContentDescription("Play", useUnmergedTree = true).performClick()
            rule.waitUntil(10_000) { session.isPlaying && host.active!!.chapters.size == 1 }
            rule.onNodeWithText("Now playing").assertIsDisplayed()
            captureSynthetic("full-player") { playbackSnapshot(host.active!!, if (expanded) "full-player" else route) }
            val before = session.positionMs
            rule.onNodeWithContentDescription("Minimize player").performClick()
            rule.onNodeWithContentDescription("Open player: Synthetic episode a").assertIsDisplayed()
            for (destination in listOf("Settings", "Sources for episode b", "Library")) {
                rule.runOnIdle { route = destination }
                rule.onNodeWithText(destination).assertIsDisplayed()
                if (destination == "Settings") {
                    val title = rule.onNodeWithContentDescription("Open player: Synthetic episode a").assertIsDisplayed().fetchSemanticsNode()
                    val pause = rule.onNodeWithContentDescription("Pause", useUnmergedTree = true).assertIsDisplayed().fetchSemanticsNode()
                    assertTrue("Mini title must clear the system status bar", title.boundsInRoot.top >= statusBarTopPx)
                    assertTrue("Mini controls must clear the system status bar", pause.boundsInRoot.top >= statusBarTopPx)
                    captureSynthetic("minimized-settings") { playbackSnapshot(host.active!!, if (expanded) "full-player" else route) }
                }
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
        var availableCount by mutableIntStateOf(0)
        val binding = AudioAttemptBinding("synthetic", "job", "revision", "revision-hash", "pack-hash", ProviderTextFrontend.VERSION)
        val chapters = (0..3).map { c -> ChapterEntity("row-$c", "revision", "c$c", c, "Synthetic chapter $c",
            (c * 4 until c * 4 + 4).joinToString("\n\n") { i ->
                "Synthetic passage $i. This complete passage has measured segment timing, not individual word alignment."
            }, 60) }
        // Synthetic measured intervals only; no media files are opened and no model runs.
        val chunks = chapters.flatMap { chapter -> ProviderTextFrontend.segmentSpans(chapter.text).mapIndexed { index, span ->
            val ordinal = chapter.position * 4 + index
            AvailableAudioChunk(ordinal, chapter.position, chapter.stableChapterId, index, File("synthetic-$ordinal.wav"),
                "synthetic-$ordinal", ordinal * 44_100L, 44_100L, 0, AudioPassageKind.PROVIDER_SEGMENT, span.startUtf16, span.endUtf16)
        } }
        val rows = TranscriptTiming.progressive("synthetic", chapters, AudioAvailability(binding, chunks, AudioAvailabilityState.COMPLETE)).passages
        rule.setContent {
            val timeline = remember(availableCount) { TranscriptTiming.progressive("synthetic", chapters,
                AudioAvailability(binding, chunks.take(availableCount), if (availableCount == chunks.size) AudioAvailabilityState.COMPLETE else AudioAvailabilityState.GENERATING)) }
            QoraloTheme { TranscriptSheet("synthetic", timeline, position, true, false, {}) }
        }
        rule.onNodeWithText("Following · stop").assertIsDisplayed()
        rule.onNodeWithTag("Transcript passages").performTouchInput { swipeUp() }
        rule.onNodeWithText("Follow playback").assertIsDisplayed()
        val initial = rule.onNodeWithTag("Transcript passages").fetchSemanticsNode()
        val before = initial.config[SemanticsProperties.VerticalScrollAxisRange].value()
        val viewport = initial.boundsInRoot
        val transitions = JSONArray()
        var stable = true
        for (count in listOf(1, 4, 8, 16)) {
            rule.runOnIdle { availableCount = count; position = (count - 1) * 1_000L }
            val node = rule.onNodeWithTag("Transcript passages").fetchSemanticsNode()
            val axis = node.config[SemanticsProperties.VerticalScrollAxisRange].value()
            val same = kotlin.math.abs(before - axis) <= 0.01f && node.boundsInRoot == viewport
            stable = stable && same
            transitions.put(JSONObject().put("availableChunks", count).put("scrollAxis", axis).put("sameViewportAndPosition", same))
            rule.onNodeWithText("Follow playback").assertIsDisplayed()
        }
        val after = rule.onNodeWithTag("Transcript passages").fetchSemanticsNode().config[SemanticsProperties.VerticalScrollAxisRange].value()
        // Preserve the failed visual state too; never lose the evidence by asserting first.
        captureSynthetic("transcript-manual") {
            JSONObject().put("episodeId", "synthetic").put("episodePhase", "SYNTHETIC_TRANSCRIPT")
                .put("uiState", "manual").put("positionMs", position).put("scrollAxisBefore", before)
                .put("scrollAxis", after).put("manualPositionPreserved", stable).put("availabilityTransitions", transitions).put("activePassage", 15)
        }
        assertTrue("0→partial→more→complete and chapter advancement must preserve the manual viewport: $transitions", stable)
        assertEquals("Chapter advancement must not scroll against the reader", before, after, 0.01f)
        rule.onNodeWithText("Follow playback").performClick()
        rule.onNodeWithText(rows.last().text).assertIsDisplayed()
        rule.onNodeWithText("Following · stop").assertIsDisplayed()
        captureSynthetic("transcript-follow-resumed") {
            JSONObject().put("episodeId", "synthetic").put("episodePhase", "SYNTHETIC_TRANSCRIPT")
                .put("uiState", "following").put("positionMs", position).put("activePassage", 15)
        }
    }

    private fun playbackSnapshot(active: ActivePlayback, surface: String): JSONObject = JSONObject()
        .put("episodeId", active.identity.episodeId).put("episodePhase", active.episode.phase).put("uiState", surface)
        .put("sessionIdentity", System.identityHashCode(active.session)).put("playerIdentity", System.identityHashCode(active.session.player))
        .put("positionMs", active.session.positionMs).put("durationMs", active.session.durationMs).put("speed", active.session.speed.toDouble())
        .put("isPlaying", active.session.isPlaying).put("wantsPlayback", active.session.wantsPlayback)

    /** Four bounded captures per profile, private and synthetic. Preserve prior attempts rather than overwrite. */
    private fun captureSynthetic(state: String, snapshot: () -> JSONObject) {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val args = InstrumentationRegistry.getArguments()
        fun pathPart(key: String, fallback: String): String = (args.getString(key) ?: fallback).also {
            require(it.matches(Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,159}"))) { "Unsafe capture argument: $key" }
        }
        val run = pathPart("diagnosticRun", "synthetic-player")
        val profile = pathPart("profile", "unspecified")
        val directory = File(context.filesDir, "player-ui-captures/$run/$profile/$captureAttempt/.private-ui").also { require(it.mkdirs() || it.isDirectory) }
        val image = File(directory, "$state.png")
        val metadataFile = File(directory, "$state.json")
        require(!image.exists() && !metadataFile.exists())
        rule.waitForIdle()
        val before = rule.runOnIdle { snapshot().put("elapsedRealtimeMs", SystemClock.elapsedRealtime()) }
        val bitmap = requireNotNull(instrumentation.uiAutomation.takeScreenshot()) { "Synthetic screenshot unavailable" }
        val width = bitmap.width
        val height = bitmap.height
        try { image.outputStream().use { output -> check(bitmap.compress(Bitmap.CompressFormat.PNG, 100, output)); output.fd.sync() } }
        finally { bitmap.recycle() }
        val after = rule.runOnIdle { snapshot().put("elapsedRealtimeMs", SystemClock.elapsedRealtime()) }
        val stableKeys = listOf("episodeId", "episodePhase", "uiState", "sessionIdentity", "playerIdentity", "speed")
        val sameState = stableKeys.all { before.opt(it) == after.opt(it) }
        val metadata = JSONObject().put("schemaVersion", 1).put("diagnosticRun", run).put("profile", profile).put("state", state)
            .put("syntheticOnly", true).put("surfaceKind", "isolated-shared-host-fixture").put("modelsLoaded", false).put("before", before).put("after", after)
            .put("sameIdentityAndPhase", sameState).put("widthPx", width).put("heightPx", height)
            .put("fontScale", context.resources.configuration.fontScale.toDouble()).put("densityDpi", context.resources.configuration.densityDpi)
            .put("screenWidthDp", context.resources.configuration.screenWidthDp).put("bytes", image.length())
            .put("sha256", MessageDigest.getInstance("SHA-256").digest(image.readBytes()).joinToString("") { "%02x".format(it) })
        metadataFile.writeText(metadata.toString(2))
        instrumentation.sendStatus(0, Bundle().apply {
            putString("playerUiScreenshot", image.absolutePath)
            putString("playerUiMetadata", metadataFile.absolutePath)
        })
        assertTrue("Screenshot identity/phase changed while capturing $state; preserve evidence but do not review it as stable", sameState)
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
