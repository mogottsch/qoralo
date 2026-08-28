package dev.vibevoice.podcast

import android.app.Application
import dev.vibevoice.podcast.data.ArtifactStore
import dev.vibevoice.podcast.data.PodcastDatabase
import dev.vibevoice.podcast.data.PodcastRepository
import dev.vibevoice.podcast.generation.GenerationWatchdog
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob

class PodcastApplication : Application() {
    val database by lazy { PodcastDatabase.open(this) }
    val artifacts by lazy { ArtifactStore(this) }
    val repository by lazy { PodcastRepository(database, artifacts) }
    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onCreate() {
        super.onCreate()
        if (getProcessName() == packageName) GenerationWatchdog(this, repository, appScope).start()
    }
}
