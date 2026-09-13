package dev.vibevoice.podcast.ui

import androidx.compose.material3.Text
import androidx.compose.runtime.*
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
import java.util.UUID

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
        rule.setContent { VibeVoiceTheme {
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
        rule.onNodeWithText("Delete episode").performClick()
        rule.onNodeWithText("Delete episode?").assertIsDisplayed()
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
        rule.setContent { VibeVoiceTheme {
            Text("Owned player deletion fixture; no models")
            val active = host.active
            LaunchedEffect(active) { if (active != null) while (true) { active.session.tick(); kotlinx.coroutines.delay(50) } }
        } }
        try {
            rule.runOnIdle { host.open(episode, emptyList(), emptyList(), null, source, null, null) { _, _, _ -> saves++ }; host.active!!.session.player.volume = 0f; host.active!!.session.togglePlay() }
            rule.waitUntil(10_000) { host.active?.session?.isPlaying == true }
            val original = requireNotNull(host.active); val priorSaves = saves
            runBlocking { repo.requestEpisodeDeletion(b) }
            rule.runOnIdle { assertFalse(host.closeIfEpisode(b)); assertSame(original, host.active); assertEquals(priorSaves, saves); assertTrue(original.session.wantsPlayback) }
            runBlocking { repo.reapEpisodeDeletions() }
            assertNull(runBlocking { db.podcastDao().episode(b) }); assertTrue(source.isFile)
            runBlocking { repo.requestEpisodeDeletion(a); repo.reapEpisodeDeletions() }
            assertNotNull(runBlocking { db.podcastDao().episode(a) }); assertTrue(source.isFile)
            rule.runOnIdle { assertTrue(host.closeIfEpisode(a)); assertNull(host.active) }
            runBlocking { repo.reapEpisodeDeletions() }
            assertNull(runBlocking { db.podcastDao().episode(a) }); assertFalse(source.exists())
        } finally { rule.runOnIdle { host.close() } }
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
        rule.setContent { VibeVoiceTheme { EpisodeDiagnosticsScreen("Owned diagnostics fixture", attempts, null, {}) } }
        rule.onNodeWithText("Measurements were not recorded for this attempt. Existing history is kept without replaying generation.").performScrollTo().assertIsDisplayed()
        assertNull(attempts.single().second)
        assertTrue(runBlocking { repo.runningJobs() }.isEmpty()); assertTrue(runBlocking { repo.queuedJobs() }.isEmpty())
    }
    private fun wave(file: File) = RandomAccessFile(file, "rw").use { out ->
        fun u16(v: Int) { out.write(v and 255); out.write(v ushr 8 and 255) }
        fun u32(v: Int) { u16(v and 65535); u16(v ushr 16 and 65535) }
        out.writeBytes("RIFF"); u32(36 + 882000); out.writeBytes("WAVEfmt "); u32(16)
        u16(1); u16(1); u32(44100); u32(88200); u16(2); u16(16); out.writeBytes("data"); u32(882000)
        out.write(ByteArray(882000)); out.fd.sync()
    }
}
