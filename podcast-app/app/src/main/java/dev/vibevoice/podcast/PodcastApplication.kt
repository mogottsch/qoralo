package dev.vibevoice.podcast

import android.app.Application
import dev.vibevoice.podcast.data.ArtifactStore
import dev.vibevoice.podcast.data.PodcastDatabase
import dev.vibevoice.podcast.data.PodcastRepository

class PodcastApplication : Application() {
    val database by lazy { PodcastDatabase.open(this) }
    val artifacts by lazy { ArtifactStore(this) }
    val repository by lazy { PodcastRepository(database, artifacts) }
}
