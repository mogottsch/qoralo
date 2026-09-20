package dev.qoralo.podcast.generation

import android.app.ActivityManager
import android.content.Context
import dev.qoralo.podcast.data.PodcastRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

class GenerationWatchdog(
    private val context: Context,
    private val repository: PodcastRepository,
    private val scope: CoroutineScope,
    private val clock: () -> Long = System::currentTimeMillis,
) {
    fun start() {
        scope.launch {
            while (isActive) {
                val processAlive = context.getSystemService(ActivityManager::class.java)
                    .runningAppProcesses.orEmpty().any { it.processName == "${context.packageName}:generation" }
                reconcileOnce(processAlive)
                delay(POLL_MS)
            }
        }
    }

    suspend fun reconcileOnce(processAlive: Boolean, now: Long = clock()) {
        if (processAlive) return
        repository.runningJobs().forEach { job ->
            val heartbeat = job.heartbeatAtEpochMs ?: job.updatedAtEpochMs
            if (now - heartbeat >= ORPHAN_GRACE_MS) {
                repository.failJob(job.episodeId, job.id, "The isolated generation process ended unexpectedly", "process_death:${job.statusText}")
            }
        }
    }

    companion object {
        const val ORPHAN_GRACE_MS = 10_000L
        const val POLL_MS = 5_000L
    }
}
