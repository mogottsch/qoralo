package dev.vibevoice.podcast.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(
    entities = [
        EpisodeEntity::class,
        EpisodeSourceEntity::class,
        ScriptRevisionEntity::class,
        ChapterEntity::class,
        AgentMessageEntity::class,
        GenerationJobEntity::class,
        ChapterAudioEntity::class,
        PlaybackStateEntity::class,
        InstalledModelEntity::class,
    ],
    version = 1,
    exportSchema = true,
)
abstract class PodcastDatabase : RoomDatabase() {
    abstract fun podcastDao(): PodcastDao

    companion object {
        @Volatile private var instance: PodcastDatabase? = null

        fun open(context: Context): PodcastDatabase = instance ?: synchronized(this) {
            instance ?: Room.databaseBuilder(context.applicationContext, PodcastDatabase::class.java, "podcast.db")
                .setJournalMode(JournalMode.WRITE_AHEAD_LOGGING)
                .enableMultiInstanceInvalidation()
                .build()
                .also { instance = it }
        }
    }
}
