package dev.qoralo.podcast.ui

import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.qoralo.podcast.data.*
import dev.qoralo.podcast.ui.theme.QoraloTheme
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.Dispatchers
import android.os.Looper
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.io.RandomAccessFile
import java.util.UUID
import android.graphics.Bitmap
import android.os.Bundle
import android.os.SystemClock
import android.accessibilityservice.AccessibilityServiceInfo
import android.view.accessibility.AccessibilityWindowInfo
import android.graphics.Rect
import org.json.JSONObject
import java.security.MessageDigest

/** New owned cache fixtures + in-memory database only. No real user rows, models or inference. */
@RunWith(AndroidJUnit4::class)
class EpisodeManagementRegressionTest {
    @get:Rule val rule = createComposeRule()
    private fun <T> fixture(block: (PodcastRepository, PodcastDatabase, ArtifactStore) -> T): T {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val root = File(context.cacheDir, "episode-management-${UUID.randomUUID()}").apply { check(mkdir()) }
        val db = Room.inMemoryDatabaseBuilder(context, PodcastDatabase::class.java).allowMainThreadQueries().build()
        val store = ArtifactStore(File(root, "episodes"), File(root, "models"))
        return try { block(PodcastRepository(db, store, providerAdmission = false), db, store) }
        finally { db.close(); check(root.deleteRecursively()) }
    }
    @Test fun confirmationKeepsCapturedIdAndDoesNotDeleteBeforeExplicitConfirm() = fixture { repo, db, _ ->
        val a = runBlocking { repo.createEpisode() }; val b = runBlocking { repo.createEpisode() }
        val first = runBlocking { repo.episode(a) }.copy(title = "Owned draft A")
        val second = runBlocking { repo.episode(b) }.copy(title = "Owned draft B")
        var target by mutableStateOf<EpisodeDeletionTarget?>(null)
        var captured: String? = null
        rule.setContent { QoraloTheme {
            LibraryScreen(listOf(first, second), {}, {}, {}, episodeActions = { episode ->
                EpisodeOverflow(episode, {}, { target = EpisodeDeletionTarget(it.id, it.title) })
            })
            target?.let { selected -> DeleteEpisodeConfirmation(selected, false, null, { target = null }) {
                captured = selected.id
                runBlocking { repo.requestEpisodeDeletion(selected.id); repo.reapEpisodeDeletions() }
                target = null
            } }
        } }
        rule.onNodeWithContentDescription("Episode actions: Owned draft A").performClick()
        captureOwnedRoot("owned-overflow", "Episode details")
        rule.onNodeWithText("Delete episode").performClick()
        rule.onNodeWithText("Delete episode?").assertIsDisplayed()
        captureOwnedRoot("owned-delete-confirmation", "Delete episode?")
        assertNotNull(runBlocking { db.podcastDao().episode(a) })
        rule.onNodeWithText("Keep episode").performClick()
        assertNotNull(runBlocking { db.podcastDao().episode(a) })
        rule.onNodeWithContentDescription("Episode actions: Owned draft B").performClick()
        rule.onNodeWithText("Delete episode").performClick()
        rule.onNodeWithText("Delete episode").performClick()
        assertEquals(b, captured)
        assertNull(runBlocking { db.podcastDao().episode(b) })
        assertNotNull(runBlocking { db.podcastDao().episode(a) })
    }
    @Test fun deletingOtherEpisodePreservesSinglePlayerAndMatchingDeletionReleasesIt() = fixture { repo, db, store ->
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val a = runBlocking { repo.createEpisode() }; val b = runBlocking { repo.createEpisode() }
        val source = File(store.episodesRoot, "$a/fixture.wav").apply { parentFile!!.mkdirs() }
        wave(source)
        val episode = runBlocking { repo.episode(a) }.copy(phase = EpisodePhase.FROZEN_READY, durationMs = 10000)
        val host = PlaybackHost(context, repo::acquireEpisodeFiles)
        var saves = 0
        rule.setContent { QoraloTheme {
            Text("Owned player deletion fixture; no models")
            val active = host.active
            LaunchedEffect(active) { if (active != null) while (true) { active.session.tick(); kotlinx.coroutines.delay(50) } }
        } }
        try {
            rule.runOnIdle { host.open(episode, emptyList(), emptyList(), null, source, null, null) { _, _, _ -> saves++ }; host.active!!.session.player.volume = 0f; host.active!!.session.togglePlay() }
            rule.waitUntil(10_000) { host.active?.session?.isPlaying == true }
            val original = requireNotNull(host.active); val priorSaves = saves
            runBlocking { repo.requestEpisodeDeletion(b) }
            assertFalse(runBlocking(Dispatchers.Default) { host.closeIfEpisodeAndAwait(b) })
            rule.runOnIdle { assertSame(original, host.active); assertEquals(priorSaves, saves); assertTrue(original.session.wantsPlayback) }
            runBlocking { repo.reapEpisodeDeletions() }
            assertNull(runBlocking { db.podcastDao().episode(b) }); assertTrue(source.isFile)
            runBlocking { repo.requestEpisodeDeletion(a); repo.reapEpisodeDeletions() }
            assertNotNull(runBlocking { db.podcastDao().episode(a) }); assertTrue(source.isFile)
            assertTrue(runBlocking(Dispatchers.Default) { host.closeIfEpisodeAndAwait(a) })
            rule.runOnIdle { assertNull(host.active); assertTrue(original.session.isReleased) }
            runBlocking { repo.reapEpisodeDeletions() }
            assertNull(runBlocking { db.podcastDao().episode(a) }); assertFalse(source.exists())
        } finally { rule.runOnIdle { host.close() } }
    }
    @Test fun failedPlayerReleaseRetainsFilesAndDefaultDispatcherRetryAwaitsMainRelease() = fixture { repo, db, store ->
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val id = runBlocking { repo.createEpisode() }
        val source = File(store.episodesRoot, "$id/fixture.wav").apply { parentFile!!.mkdirs() }; wave(source)
        val episode = runBlocking { repo.episode(id) }.copy(phase = EpisodePhase.FROZEN_READY, durationMs = 10000)
        var fail = true
        var releases = 0
        val host = PlaybackHost(context, repo::acquireEpisodeFiles, releaseSession = { session ->
            assertSame(Looper.getMainLooper(), Looper.myLooper())
            releases++
            if (fail) { fail = false; error("Owned injected release failure") }
            session.close()
        })
        rule.setContent { QoraloTheme { Text("Owned release failure fixture; no models") } }
        try {
            rule.runOnIdle { host.open(episode, emptyList(), emptyList(), null, source, null, null) { _, _, _ -> error("Owned checkpoint failure") } }
            val original = rule.runOnIdle { requireNotNull(host.active) }
            runBlocking { repo.requestEpisodeDeletion(id) }
            assertThrows(IllegalStateException::class.java) { runBlocking(Dispatchers.Default) { host.closeIfEpisode(id) } }
            assertEquals(0, releases) // Wrong-thread access rejected before state/player mutation.
            assertThrows(IllegalStateException::class.java) { runBlocking(Dispatchers.Default) { host.closeIfEpisodeAndAwait(id) } }
            runBlocking { repo.reapEpisodeDeletions() }
            assertNotNull(runBlocking { db.podcastDao().episode(id) }); assertTrue(source.isFile)
            rule.runOnIdle { assertSame(original, host.active); assertFalse(original.session.isReleased) }
            assertTrue(runBlocking(Dispatchers.Default) { host.closeIfEpisodeAndAwait(id) })
            rule.runOnIdle { assertNull(host.active); assertTrue(original.session.isReleased); assertEquals(2, releases) }
            runBlocking { repo.reapEpisodeDeletions() }
            assertNull(runBlocking { db.podcastDao().episode(id) }); assertFalse(source.exists())
        } finally { rule.runOnIdle { fail = false; host.close() } }
    }

    @Test fun historicalDiagnosticsSayUnavailableWithoutLaunchingGeneration() = fixture { repo, _, _ ->
        val id = runBlocking { repo.createEpisode() }
        runBlocking {
            repo.addSource(id, "Synthetic source", "text/plain", "Owned fixture only".byteInputStream())
            repo.moveToInstructions(id)
            val job = repo.queueScriptGeneration(id, "Owned fixture", true)
            repo.failQueuedJob(id, job, "Synthetic historical failure")
        }
        val attempts = runBlocking { repo.episodeDiagnostics(id) }
        rule.setContent { QoraloTheme { EpisodeDiagnosticsScreen("Owned diagnostics fixture", attempts, null, {}) } }
        val missing = "Measurements were not recorded for this attempt. Existing history is kept without replaying generation."
        // A lazy item below a large-font header does not exist in the semantics tree yet.
        // Search by scrolling the container; retain the identical visible-text assertion.
        rule.onNode(hasScrollAction()).performScrollToNode(hasText(missing))
        rule.onNodeWithText(missing).assertIsDisplayed()
        captureOwnedRoot("owned-historical-unavailable", "Episode details")
        assertNull(attempts.single().second)
        assertTrue(runBlocking { repo.runningJobs() }.isEmpty()); assertTrue(runBlocking { repo.queuedJobs() }.isEmpty())
    }
    /** Authenticate the focused owned accessibility window before full compositor capture.
     * Compose captureToImage uses Activity-relative PixelCopy and cannot prove popup/dialog pixels.
     * Keep root/marker AND focused-window identity paired; unknown ownership never authorizes capture.
     */
    private fun captureOwnedRoot(state: String, marker: String) {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val args = InstrumentationRegistry.getArguments()
        val run = args.getString("diagnosticRun") ?: return
        val profile = args.getString("profile") ?: return
        require(listOf(run, profile).all { Regex("[A-Za-z0-9_-]{1,96}").matches(it) })
        require(state in setOf("owned-overflow", "owned-delete-confirmation", "owned-historical-unavailable"))
        val context = instrumentation.targetContext
        val root = File(context.filesDir, "episode-management-captures/$run/$profile").apply { require(isDirectory || mkdirs()) }
        val image = File(root, "$state.png"); val receipt = File(root, "$state.json")
        require(!image.exists() && !receipt.exists())
        val metadata = JSONObject().put("schemaVersion", 1).put("diagnosticRun", run).put("profile", profile).put("state", state)
            .put("captureScope", "full compositor; paired focused target-app accessibility window and displayed synthetic semantic marker")
            .put("newCacheAndInMemoryFixtureOnly", true).put("modelCalls", 0).put("userEpisodeDeletion", false)
            .put("appApkSha256", args.getString("appApkSha256")).put("testApkSha256", args.getString("testApkSha256"))
            .put("fontScale", context.resources.configuration.fontScale.toDouble()).put("densityDpi", context.resources.configuration.densityDpi)
            .put("appLastUpdateTimeMs", context.packageManager.getPackageInfo(context.packageName, 0).lastUpdateTime)
        var originalAccessibilityFlags: Int? = null
        var capturePhase = "automation-flags"
        var windowRead = 0
        fun ownedWindow(): JSONObject {
            val diagnostics = org.json.JSONArray()
            val windows = instrumentation.uiAutomation.windows
            val candidates = windows.filter { it.type == AccessibilityWindowInfo.TYPE_APPLICATION && (it.isFocused || it.isActive) }
                .mapNotNull { window ->
                    val content = window.root ?: return@mapNotNull null
                    if (content.packageName?.toString() != context.packageName) return@mapNotNull null
                    // Compose 1.7.6's node provider does not implement find-by-text. Walk
                    // its actual children instead; cap work and never retain node text.
                    val pending = ArrayDeque<android.view.accessibility.AccessibilityNodeInfo>().apply { add(content) }
                    val seen = HashSet<android.view.accessibility.AccessibilityNodeInfo>()
                    var matches = false
                    while (pending.isNotEmpty() && seen.size < 512) {
                        val node = pending.removeFirst()
                        if (!seen.add(node)) continue
                        if (node.isVisibleToUser && (node.text?.toString() == marker || node.contentDescription?.toString() == marker)) { matches = true; break }
                        require(node.childCount <= 128) { "Unbounded accessibility child count" }
                        repeat(node.childCount) { child -> node.getChild(child)?.let(pending::addLast) }
                    }
                    diagnostics.put(JSONObject().put("id", window.id).put("ownedPackage", true).put("focused", window.isFocused)
                        .put("active", window.isActive).put("nodesVisited", seen.size).put("markerFound", matches))
                    if (!matches) return@mapNotNull null
                    val bounds = Rect(); window.getBoundsInScreen(bounds)
                    JSONObject().put("id", window.id).put("package", content.packageName.toString()).put("bounds", bounds.toShortString())
                        .put("focused", window.isFocused).put("active", window.isActive).put("markerVisibleInWindow", true)
                }
            metadata.put("windowRead${++windowRead}", JSONObject().put("totalWindows", windows.size).put("ownedCandidates", diagnostics).put("matches", candidates.size))
            require(candidates.size == 1) { "Focused fixture window ownership is unknown or ambiguous" }
            return candidates.single()
        }
        try {
            val service = instrumentation.uiAutomation.serviceInfo
            originalAccessibilityFlags = service.flags
            service.flags = service.flags or AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS
            instrumentation.uiAutomation.serviceInfo = service
            rule.waitForIdle()
            instrumentation.waitForIdleSync()
            SystemClock.sleep(100) // Bounded compositor settle; no production timing measurement.
            rule.onNodeWithText(marker).assertIsDisplayed()
            val node = rule.onNode(isRoot() and hasAnyDescendant(hasText(marker)), useUnmergedTree = true)
            capturePhase = "owned-window-settle"
            val settleStart = SystemClock.elapsedRealtime()
            val windowKeys = listOf("id", "package", "bounds", "focused", "active")
            var windowBefore = ownedWindow()
            var stableSince = SystemClock.elapsedRealtime()
            while (SystemClock.elapsedRealtime() - stableSince < 400) {
                require(SystemClock.elapsedRealtime() - settleStart < 2500) { "Owned window did not settle within capture bound" }
                SystemClock.sleep(100)
                val observed = ownedWindow()
                if (windowKeys.any { windowBefore.get(it) != observed.get(it) }) stableSince = SystemClock.elapsedRealtime()
                windowBefore = observed
            }
            metadata.put("windowSettleMs", SystemClock.elapsedRealtime() - settleStart).put("stableWindowMinimumMs", 400)
            val before = node.fetchSemanticsNode(); val beforeId = before.id; val beforeBounds = before.boundsInRoot
            val start = SystemClock.elapsedRealtime()
            capturePhase = "compositor-screenshot"
            val bitmap = requireNotNull(instrumentation.uiAutomation.takeScreenshot())
            try {
                metadata.put("widthPx", bitmap.width).put("heightPx", bitmap.height)
                image.outputStream().use { check(bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)); it.fd.sync() }
            } finally { bitmap.recycle() }
            capturePhase = "owned-window-after"
            val after = node.fetchSemanticsNode(); val windowAfter = ownedWindow()
            rule.onNodeWithText(marker).assertIsDisplayed()
            val paired = beforeId == after.id && beforeBounds == after.boundsInRoot &&
                listOf("id", "package", "bounds", "focused", "active").all { windowBefore.get(it) == windowAfter.get(it) }
            metadata.put("status", if (paired) "paired_owned_window" else "unpaired_window_changed").put("capturePaired", paired)
                .put("windowBefore", windowBefore).put("windowAfter", windowAfter)
                .put("rootIdBefore", beforeId).put("rootIdAfter", after.id).put("boundsBefore", beforeBounds.toString()).put("boundsAfter", after.boundsInRoot.toString())
                .put("captureStartElapsedMs", start).put("captureEndElapsedMs", SystemClock.elapsedRealtime()).put("bytes", image.length())
                .put("sha256", MessageDigest.getInstance("SHA-256").digest(image.readBytes()).joinToString("") { "%02x".format(it) })
        } catch (error: Throwable) {
            metadata.put("status", "capture_unavailable").put("capturePaired", false).put("errorType", error.javaClass.simpleName).put("capturePhase", capturePhase)
        } finally {
            val restored = runCatching {
                val flags = requireNotNull(originalAccessibilityFlags)
                val service = instrumentation.uiAutomation.serviceInfo; service.flags = flags
                instrumentation.uiAutomation.serviceInfo = service
                instrumentation.uiAutomation.serviceInfo.flags == flags
            }.getOrDefault(false)
            metadata.put("automationServiceFlagsRestored", restored)
        }
        receipt.writeText(metadata.toString(2))
        instrumentation.sendStatus(0, Bundle().apply { putString("episodeManagementCapture", receipt.absolutePath) })
    }

    private fun wave(file: File) = RandomAccessFile(file, "rw").use { out ->
        fun u16(v: Int) { out.write(v and 255); out.write(v ushr 8 and 255) }
        fun u32(v: Int) { u16(v and 65535); u16(v ushr 16 and 65535) }
        out.writeBytes("RIFF"); u32(36 + 882000); out.writeBytes("WAVEfmt "); u32(16)
        u16(1); u16(1); u32(44100); u32(88200); u16(2); u16(16); out.writeBytes("data"); u32(882000)
        out.write(ByteArray(882000)); out.fd.sync()
    }
}
