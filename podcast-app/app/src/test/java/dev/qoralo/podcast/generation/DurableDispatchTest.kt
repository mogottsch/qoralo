package dev.qoralo.podcast.generation

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import dev.qoralo.podcast.data.ArtifactStore
import dev.qoralo.podcast.data.ChapterDraft
import dev.qoralo.podcast.data.EpisodePhase
import dev.qoralo.podcast.data.JobKind
import dev.qoralo.podcast.data.JobStatus
import dev.qoralo.podcast.data.PodcastDatabase
import dev.qoralo.podcast.data.PodcastRepository
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class DurableDispatchTest {
    @get:Rule val temporary = TemporaryFolder()
    private lateinit var database: PodcastDatabase
    private lateinit var repository: PodcastRepository
    private var now = 10_000L

    @Before fun setUp() {
        database = Room.inMemoryDatabaseBuilder(ApplicationProvider.getApplicationContext<Context>(), PodcastDatabase::class.java).allowMainThreadQueries().build()
        repository = PodcastRepository(database, ArtifactStore(temporary.newFolder(), temporary.newFolder()), providerAdmission = false) { now }
    }
    @After fun close() = database.close()

    @Test fun serviceLaunchFailureTerminalizesPreClaimQueuedJob() = runTest {
        val (episode, job) = queuedScript(true)
        QueuedCommandDispatcher(repository, this) { error("foreground service start rejected") }.dispatchOnce()
        assertEquals(JobStatus.FAILED, repository.latestJob(episode)?.status)
        assertEquals(EpisodePhase.FAILED, repository.episode(episode).phase)
        assertTrue(repository.queuedJobs().isEmpty())
    }

    @Test fun restartDispatcherFindsReviewOffAudioHandoffQueuedJob() = runTest {
        val (episode, scriptJob) = queuedScript(false)
        repository.claimJob(episode, scriptJob, JobKind.SCRIPT, "script")
        repository.commitGeneratedScript(episode, scriptJob, "Episode", listOf(ChapterDraft("chapter-1", "One", "Complete chapter.")))
        val launched = mutableListOf<String>()
        QueuedCommandDispatcher(repository, this) { launched += "${it.kind}:${it.id}" }.dispatchOnce()
        val audio = repository.latestJob(episode)!!
        assertEquals(listOf("AUDIO:${audio.id}"), launched)
        assertEquals(JobStatus.QUEUED, audio.status)
        assertEquals(EpisodePhase.LOCKED, repository.episode(episode).phase)
    }

    @Test fun frequentPollsBeforeClaimTimeoutNeitherRelaunchNorConsumeAttempt() = runTest {
        val (episode, _) = queuedScript(true)
        var launches = 0
        val dispatcher = QueuedCommandDispatcher(repository, this, { now }) { launches++ }
        dispatcher.dispatchOnce()
        repeat(7) {
            now += QueuedCommandDispatcher.POLL_MS
            dispatcher.dispatchOnce()
        }
        val queued = repository.latestJob(episode)!!
        assertEquals(JobStatus.QUEUED, queued.status)
        assertEquals(1, queued.dispatchAttemptCount)
        assertEquals(1, launches)
    }

    @Test fun unacknowledgedCommandExhaustsOnlyAfterThreeElapsedTimeoutWindows() = runTest {
        val (episode, _) = queuedScript(true)
        var launches = 0
        val dispatcher = QueuedCommandDispatcher(repository, this, { now }) { launches++ }
        dispatcher.dispatchOnce()
        repeat(2) {
            now += QueuedCommandDispatcher.CLAIM_TIMEOUT_MS
            dispatcher.dispatchOnce()
        }
        assertEquals(JobStatus.QUEUED, repository.latestJob(episode)?.status)
        assertEquals(3, repository.latestJob(episode)?.dispatchAttemptCount)
        assertEquals(3, launches)
        now += QueuedCommandDispatcher.CLAIM_TIMEOUT_MS
        dispatcher.dispatchOnce()
        assertEquals(JobStatus.FAILED, repository.latestJob(episode)?.status)
        assertEquals(EpisodePhase.FAILED, repository.episode(episode).phase)
        assertTrue(repository.queuedJobs().isEmpty())
    }

    @Test fun failedReviewOffAudioHandoffDispatchCannotStrandLockedEpisode() = runTest {
        val (episode, scriptJob) = queuedScript(false)
        repository.claimJob(episode, scriptJob, JobKind.SCRIPT, "script")
        repository.commitGeneratedScript(episode, scriptJob, "Episode", listOf(ChapterDraft("chapter-1", "One", "Complete chapter.")))
        QueuedCommandDispatcher(repository, this) { error("generation process died before audio claim") }.dispatchOnce()
        assertEquals(JobStatus.FAILED, repository.latestJob(episode)?.status)
        assertEquals(EpisodePhase.FAILED, repository.episode(episode).phase)
        assertTrue(repository.queuedJobs().isEmpty())
    }

    @Test fun watchdogDeterministicallyMarksDeadRunningProcessButNotLiveOne() = runTest {
        val (episode, job) = queuedScript(true)
        repository.claimJob(episode, job, JobKind.SCRIPT, "creating outline")
        val watchdog = GenerationWatchdog(ApplicationProvider.getApplicationContext(), repository, this) { now }
        watchdog.reconcileOnce(processAlive = true, now = now + GenerationWatchdog.ORPHAN_GRACE_MS)
        assertEquals(JobStatus.RUNNING, repository.latestJob(episode)?.status)
        watchdog.reconcileOnce(processAlive = false, now = now + GenerationWatchdog.ORPHAN_GRACE_MS)
        assertEquals(JobStatus.FAILED, repository.latestJob(episode)?.status)
        assertEquals(EpisodePhase.FAILED, repository.episode(episode).phase)
        assertTrue(repository.episode(episode).failurePhase!!.startsWith("process_death:"))
    }

    @Test fun instructionsSourcesInstructionsRoundTripIsIdempotent() = runTest {
        val (episode, _) = queuedScriptSeedOnly()
        assertEquals(EpisodePhase.INSTRUCTIONS, repository.episode(episode).phase)
        repository.moveToInstructions(episode)
        assertEquals(EpisodePhase.INSTRUCTIONS, repository.episode(episode).phase)
    }

    private suspend fun queuedScript(review: Boolean): Pair<String, String> {
        val (episode, _) = queuedScriptSeedOnly()
        return episode to repository.queueScriptGeneration(episode, "Instruction", review)
    }

    private suspend fun queuedScriptSeedOnly(): Pair<String, Unit> {
        val episode = repository.createEpisode()
        repository.addSource(episode, "Source", "text/plain", "source".byteInputStream())
        repository.moveToInstructions(episode)
        return episode to Unit
    }
}
