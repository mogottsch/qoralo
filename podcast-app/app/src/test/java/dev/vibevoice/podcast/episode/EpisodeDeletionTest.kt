package dev.vibevoice.podcast.episode

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import dev.vibevoice.podcast.data.*
import kotlinx.coroutines.test.runTest
import org.junit.*
import org.junit.Assert.*
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.io.File

@RunWith(RobolectricTestRunner::class)
class EpisodeDeletionTest {
    @get:Rule val temp = TemporaryFolder()
    private lateinit var db: PodcastDatabase
    private lateinit var store: ArtifactStore
    private lateinit var repo: PodcastRepository
    @Before fun setup() {
        db = Room.inMemoryDatabaseBuilder(ApplicationProvider.getApplicationContext<Context>(), PodcastDatabase::class.java).allowMainThreadQueries().build()
        store = ArtifactStore(temp.newFolder("episodes"), temp.newFolder("models"))
        repo = PodcastRepository(db, store, providerAdmission = false)
    }
    @After fun close() { db.close() }
    private suspend fun queued(): Pair<String, String> {
        val id = repo.createEpisode(); repo.addSource(id, "Source", "text/plain", "Synthetic owned source.".byteInputStream())
        repo.moveToInstructions(id)
        return id to repo.queueScriptGeneration(id, "Synthetic instructions", true)
    }
    @Test fun queuedDeletionNeverDispatchesAndDeletesOnlyConfirmedId() = runTest {
        val (owned, job) = queued(); val other = repo.createEpisode()
        val otherSource = repo.addSource(other, "Other", "text/plain", "Keep other data".byteInputStream())
        val model = File(store.modelPacksRoot, "model").apply { writeText("shared model") }
        repo.requestEpisodeDeletion(owned)
        assertTrue(repo.queuedJobs().isEmpty()); assertNull(repo.markQueuedDispatchAttempt(owned, job))
        repo.reapEpisodeDeletions(); repo.reapEpisodeDeletions()
        assertNull(db.podcastDao().episode(owned)); assertNull(db.podcastDao().job(job))
        assertNotNull(repo.episode(other)); assertEquals("Keep other data", store.readText(otherSource.relativePath))
        assertEquals("shared model", model.readText()); assertFalse(File(store.episodesRoot, owned).exists())
    }
    @Test fun runningDeletionWaitsForAllFileLeasesAndLateCallbacksCannotResurrect() = runTest {
        val (owned, job) = queued(); repo.claimJob(owned, job, JobKind.SCRIPT, "Synthetic work")
        val worker = repo.acquireEpisodeFiles(owned); val player = repo.acquireEpisodeFiles(owned)
        repo.requestEpisodeDeletion(owned); repo.reapEpisodeDeletions()
        assertEquals("DELETING", db.podcastDao().episode(owned)?.phase)
        assertEquals(1, db.podcastDao().activeJobCount()) // Slot held while native work may still exist.
        try { repo.commitGeneratedScript(owned, job, "Late", listOf(ChapterDraft("one", "One", "Late text."))); fail("late callback") }
        catch (_: EpisodeDeletedException) { }
        worker.close(); repo.reapEpisodeDeletions(); assertNotNull(db.podcastDao().episode(owned))
        player.close(); repo.reapEpisodeDeletions(); assertNull(db.podcastDao().episode(owned))
        assertEquals(0, db.podcastDao().activeJobCount())
        assertThrows(EpisodeDeletedException::class.java) { store.writeRevision(owned, "late", "Late", listOf(ChapterDraft("c", "C", "Late"))) }
        assertFalse(File(store.episodesRoot, owned).exists())
    }
    @Test fun crashBetweenDurableMarkerAndDatabaseUpdateIsReconciledWithoutReplay() = runTest {
        val (owned, job) = queued()
        store.episodeLeases.tombstone(owned) // Simulated interruption before markDeleting transaction.
        val restarted = PodcastRepository(db, ArtifactStore(store.episodesRoot, store.modelPacksRoot), providerAdmission = false)
        assertTrue(restarted.queuedJobs().isEmpty())
        restarted.reapEpisodeDeletions()
        assertNull(db.podcastDao().episode(owned)); assertNull(db.podcastDao().job(job))
    }
    @Test fun finishedEpisodeDeletionKeepsSharedSourceAndOtherHistory() = runTest {
        val (owned, job) = queued(); repo.claimJob(owned, job, JobKind.SCRIPT, "Synthetic")
        repo.commitGeneratedScript(owned, job, "Owned", listOf(ChapterDraft("one", "One", "Synthetic finished content.")))
        val episode = repo.episode(owned)
        db.podcastDao().updateEpisode(episode.copy(phase = EpisodePhase.FROZEN_READY)) // Owned fixture only.
        val source = db.podcastDao().sources(owned).single(); val other = repo.createEpisode()
        db.podcastDao().insertSource(source.copy(id = "shared-reference", episodeId = other))
        val audio = File(store.episodesRoot, "$owned/audio-stream/attempt/part.wav").apply { parentFile.mkdirs(); writeText("synthetic") }
        repo.requestEpisodeDeletion(owned); repo.reapEpisodeDeletions()
        assertNull(db.podcastDao().episode(owned)); assertFalse(audio.exists())
        assertEquals("Synthetic owned source.", store.readText(source.relativePath))
        assertEquals("shared-reference", db.podcastDao().sources(other).single().id)
    }
}
