package dev.vibevoice.podcast

import android.app.Application
import dev.vibevoice.podcast.data.ArtifactStore
import dev.vibevoice.podcast.data.PodcastDatabase
import dev.vibevoice.podcast.data.PodcastRepository
import dev.vibevoice.podcast.generation.GenerationWatchdog
import dev.vibevoice.podcast.generation.QueuedCommandDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive

class PodcastApplication : Application() {
    val database by lazy { PodcastDatabase.open(this) }
    val artifacts by lazy { ArtifactStore(this) }
    val repository by lazy { PodcastRepository(database, artifacts) }
    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onCreate() {
        super.onCreate()
        if (getProcessName() == packageName) {
            appScope.launch {
                while (isActive) { repository.reapEpisodeDeletions(); delay(1_000) }
            }
            GenerationWatchdog(this, repository, appScope).start()
            QueuedCommandDispatcher(this, repository, appScope).start()
        }
    }
}
