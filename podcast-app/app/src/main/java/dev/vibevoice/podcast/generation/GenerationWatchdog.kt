package dev.vibevoice.podcast.generation

import android.app.ActivityManager
import android.content.Context
import dev.vibevoice.podcast.data.PodcastRepository
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
                if (!processAlive) {
                    repository.runningJobs().forEach { job ->
                        val heartbeat = job.heartbeatAtEpochMs ?: job.updatedAtEpochMs
                        if (clock() - heartbeat >= ORPHAN_GRACE_MS) {
                            repository.failJob(job.episodeId, job.id, "The isolated generation process ended unexpectedly", "process_death:${job.statusText}")
                        }
                    }
                }
                delay(POLL_MS)
            }
        }
    }

    companion object {
        const val ORPHAN_GRACE_MS = 10_000L
        const val POLL_MS = 5_000L
    }
}
