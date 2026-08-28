package dev.vibevoice.podcast.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import kotlinx.coroutines.flow.Flow

@Dao
interface PodcastDao {
    @Insert suspend fun insertEpisode(value: EpisodeEntity)
    @Update suspend fun updateEpisode(value: EpisodeEntity)
    @Query("SELECT * FROM episodes WHERE id = :id") suspend fun episode(id: String): EpisodeEntity?
    @Query("SELECT * FROM episodes WHERE id = :id") fun observeEpisode(id: String): Flow<EpisodeEntity?>
    @Query("SELECT * FROM episodes ORDER BY updatedAtEpochMs DESC") fun observeEpisodes(): Flow<List<EpisodeEntity>>

    @Insert suspend fun insertSource(value: EpisodeSourceEntity)
    @Query("DELETE FROM episode_sources WHERE id = :id") suspend fun deleteSourceById(id: String): Int
    @Query("SELECT * FROM episode_sources WHERE episodeId = :episodeId ORDER BY createdAtEpochMs") suspend fun sources(episodeId: String): List<EpisodeSourceEntity>
    @Query("SELECT * FROM episode_sources WHERE episodeId = :episodeId ORDER BY createdAtEpochMs") fun observeSources(episodeId: String): Flow<List<EpisodeSourceEntity>>

    @Insert suspend fun insertRevision(value: ScriptRevisionEntity)
    @Insert suspend fun insertChapters(values: List<ChapterEntity>)
    @Query("SELECT * FROM script_revisions WHERE id = :id") suspend fun revision(id: String): ScriptRevisionEntity?
    @Query("SELECT COALESCE(MAX(revisionNumber), 0) FROM script_revisions WHERE episodeId = :episodeId") suspend fun latestRevisionNumber(episodeId: String): Int
    @Query("SELECT * FROM chapters WHERE revisionId = :revisionId ORDER BY position") suspend fun chapters(revisionId: String): List<ChapterEntity>
    @Query("SELECT c.* FROM chapters c INNER JOIN episodes e ON c.revisionId = e.activeRevisionId WHERE e.id = :episodeId ORDER BY c.position") fun observeActiveChapters(episodeId: String): Flow<List<ChapterEntity>>
    @Query("SELECT c.* FROM chapters c INNER JOIN episodes e ON c.revisionId = e.lockedRevisionId WHERE e.id = :episodeId ORDER BY c.position") suspend fun lockedChapters(episodeId: String): List<ChapterEntity>

    @Insert suspend fun insertMessage(value: AgentMessageEntity)
    @Query("SELECT * FROM agent_messages WHERE episodeId = :episodeId ORDER BY createdAtEpochMs") fun observeMessages(episodeId: String): Flow<List<AgentMessageEntity>>
    @Query("SELECT * FROM agent_messages WHERE episodeId = :episodeId AND role = 'USER' ORDER BY createdAtEpochMs DESC, rowid DESC LIMIT 1") suspend fun latestUserMessage(episodeId: String): AgentMessageEntity?

    @Insert suspend fun insertJob(value: GenerationJobEntity)
    @Update suspend fun updateJob(value: GenerationJobEntity)
    @Query("SELECT * FROM generation_jobs WHERE id = :id") suspend fun job(id: String): GenerationJobEntity?
    @Query("SELECT * FROM generation_jobs WHERE episodeId = :episodeId ORDER BY createdAtEpochMs DESC, rowid DESC LIMIT 1") fun observeLatestJob(episodeId: String): Flow<GenerationJobEntity?>
    @Query("SELECT * FROM generation_jobs WHERE episodeId = :episodeId ORDER BY createdAtEpochMs DESC, rowid DESC LIMIT 1") suspend fun latestJob(episodeId: String): GenerationJobEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun insertChapterAudio(value: ChapterAudioEntity)
    @Query("DELETE FROM chapter_audio WHERE episodeId = :episodeId") suspend fun clearChapterAudio(episodeId: String)
    @Query("SELECT * FROM chapter_audio WHERE episodeId = :episodeId ORDER BY position") suspend fun chapterAudio(episodeId: String): List<ChapterAudioEntity>
    @Query("SELECT * FROM chapter_audio WHERE episodeId = :episodeId ORDER BY position") fun observeChapterAudio(episodeId: String): Flow<List<ChapterAudioEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsertPlayback(value: PlaybackStateEntity)
    @Query("SELECT * FROM playback_state WHERE episodeId = :episodeId") fun observePlayback(episodeId: String): Flow<PlaybackStateEntity?>

    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsertInstalledModel(value: InstalledModelEntity)
    @Query("SELECT * FROM installed_models ORDER BY route") fun observeInstalledModels(): Flow<List<InstalledModelEntity>>
}
