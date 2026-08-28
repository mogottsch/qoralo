package dev.vibevoice.podcast.generation

import android.content.Context
import dev.vibevoice.podcast.data.GenerationJobEntity
import dev.vibevoice.podcast.data.JobKind
import dev.vibevoice.podcast.data.PodcastRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

class QueuedCommandDispatcher(
    private val repository: PodcastRepository,
    private val scope: CoroutineScope,
    private val clock: () -> Long = System::currentTimeMillis,
    private val launch: (GenerationJobEntity) -> Unit,
) {
    constructor(context: Context, repository: PodcastRepository, scope: CoroutineScope) : this(
        repository,
        scope,
        System::currentTimeMillis,
        { job -> GenerationService.start(context, job) },
    )

    fun start() {
        scope.launch {
            while (isActive) {
                dispatchOnce()
                delay(POLL_MS)
            }
        }
    }

    suspend fun dispatchOnce() {
        repository.queuedJobs().forEach { queued ->
            val lastDispatch = queued.lastDispatchAtEpochMs
            if (lastDispatch != null && clock() - lastDispatch < CLAIM_TIMEOUT_MS) return@forEach
            if (queued.dispatchAttemptCount >= MAX_DISPATCH_ATTEMPTS) {
                repository.failQueuedJob(queued.episodeId, queued.id, "The isolated generation service could not claim this command", "service_dispatch_exhausted")
                return@forEach
            }
            val job = repository.markQueuedDispatchAttempt(queued.episodeId, queued.id) ?: return@forEach
            try {
                launch(job)
            } catch (error: Throwable) {
                repository.failQueuedJob(
                    job.episodeId,
                    job.id,
                    error.message ?: "Could not start the isolated generation service",
                )
            }
        }
    }

    companion object {
        const val POLL_MS = 2_000L
        const val CLAIM_TIMEOUT_MS = 15_000L
        const val MAX_DISPATCH_ATTEMPTS = 3
    }
}
