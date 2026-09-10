package dev.vibevoice.podcast.ui

import android.app.Application
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.viewModelScope
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import dev.vibevoice.podcast.data.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withTimeout
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
class UiPersistenceTest {
    @get:Rule val temporary = TemporaryFolder()
    private lateinit var database: PodcastDatabase
    private lateinit var repository: PodcastRepository
    private lateinit var application: Application
    private val models = mutableListOf<PodcastViewModel>()

    @Before fun setup() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        application = ApplicationProvider.getApplicationContext()
        database = Room.inMemoryDatabaseBuilder(application, PodcastDatabase::class.java).allowMainThreadQueries().build()
        repository = PodcastRepository(database, ArtifactStore(temporary.newFolder(), temporary.newFolder()))
    }
    @After fun close() { models.forEach { it.viewModelScope.cancel() }; database.close(); Dispatchers.resetMain() }
    private fun model(handle: SavedStateHandle = SavedStateHandle()) = PodcastViewModel(application, handle, repository).also(models::add)

    @Test fun playbackSaveAfterBackOrEpisodeSwitchKeepsOriginalOwnership() = runTest {
        val a = readyEpisode()
        val b = readyEpisode()
        val vm = model()
        vm.selectEpisode(a)
        vm.showLibrary()
        vm.savePlayback(a.id, 30_000, 1.5f, true).join()
        val saved = repository.observePlayback(a.id).first()!!
        assertEquals(30_000L, saved.positionMs); assertEquals(1.5f, saved.speed); assertTrue(saved.transcriptVisible)
        vm.selectEpisode(b)
        vm.savePlayback(a.id, 31_000, 1.5f, false).join()
        assertEquals(31_000L, repository.observePlayback(a.id).first()!!.positionMs)
        assertNull(repository.observePlayback(b.id).first())
        vm.selectEpisode(a)
        assertEquals(31_000L, repository.observePlayback(a.id).first()!!.positionMs)
    }

    @Test fun draftTextAndReviewSurviveNavigationRecreationAndEpisodeSwitchWithoutJobs() = runTest {
        val a = instructionsEpisode()
        val b = instructionsEpisode()
        val handle = SavedStateHandle()
        val vm = model(handle)
        vm.selectEpisode(a)
        val save = vm.saveInstructionDraft(a.id, "QA preserve my draft instructions", false)
        vm.showSources(); vm.showInstructions(); vm.selectEpisode(b)
        save.join()
        assertEquals("QA preserve my draft instructions", repository.episode(a.id).instructions)
        assertFalse(repository.episode(a.id).reviewEnabled)
        assertEquals("QA preserve my draft instructions", vm.instructionDraft(a).instructions)
        assertFalse(vm.instructionDraft(a).reviewEnabled)
        assertEquals("", vm.instructionDraft(b).instructions)
        val restored = model(SavedStateHandle(handle.keys().associateWith { handle.get<Any?>(it) }))
        assertEquals("QA preserve my draft instructions", restored.instructionDraft(a).instructions)
        assertFalse(restored.instructionDraft(a).reviewEnabled)
        assertEquals("", restored.instructionDraft(b).instructions)
        assertTrue(repository.queuedJobs().isEmpty()); assertTrue(repository.runningJobs().isEmpty())
    }

    @Test fun delayedDraftWriteCannotChangeQueuedClaimedOrLockedInputs() = runTest {
        val episode = instructionsEpisode()
        val job = repository.queueScriptGeneration(episode.id, "Final instructions", true)
        repository.saveInstructionDraft(episode.id, "stale queued UI write", false)
        assertEquals("Final instructions", repository.episode(episode.id).instructions)
        repository.claimJob(episode.id, job, JobKind.SCRIPT, "writing")
        repository.saveInstructionDraft(episode.id, "stale after claim", false)
        assertTrue(repository.episode(episode.id).reviewEnabled)
        repository.commitGeneratedScript(episode.id, job, "Final episode", listOf(ChapterDraft("chapter-1", "One", "Complete frozen chapter.")))
        repository.lockAndQueueAudio(episode.id)
        val locked = repository.episode(episode.id)
        repository.saveInstructionDraft(episode.id, "stale after lock", false)
        assertEquals(locked, repository.episode(episode.id))
    }

    @Test fun hintInsertionAtLimitIsRejectedWithoutTruncatingEditableDraft() {
        val current = "a".repeat(1990)
        assertNull(InstructionDraftPolicy.appendedHint(current, "Keep it under five minutes."))
        assertEquals("Edited draft\nKeep it under five minutes.", InstructionDraftPolicy.appendedHint("Edited draft", "Keep it under five minutes."))
        assertEquals(2000, InstructionDraftPolicy.appendedHint("a".repeat(1998), "b")!!.length)
    }

    private suspend fun readyEpisode(): EpisodeEntity {
        val id = repository.createEpisode()
        val value = repository.episode(id).copy(phase = EpisodePhase.FROZEN_READY, durationMs = 60_000)
        database.podcastDao().updateEpisode(value)
        return value
    }
    private suspend fun instructionsEpisode(): EpisodeEntity {
        val id = repository.createEpisode()
        repository.addSource(id, "Source", "text/plain", "Source material.".byteInputStream())
        repository.moveToInstructions(id)
        return repository.episode(id)
    }
}
