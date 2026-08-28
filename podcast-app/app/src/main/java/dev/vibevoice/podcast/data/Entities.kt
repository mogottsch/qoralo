package dev.vibevoice.podcast.data

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

object EpisodePhase {
    const val SOURCES = "SOURCES"
    const val INSTRUCTIONS = "INSTRUCTIONS"
    const val GENERATING_SCRIPT = "GENERATING_SCRIPT"
    const val SCRIPT_DRAFT = "SCRIPT_DRAFT"
    const val LOCKED = "LOCKED"
    const val GENERATING_AUDIO = "GENERATING_AUDIO"
    const val FROZEN_READY = "FROZEN_READY"
    const val FAILED = "FAILED"
}

object JobKind { const val SCRIPT = "SCRIPT"; const val AGENT_EDIT = "AGENT_EDIT"; const val AUDIO = "AUDIO" }
object JobStatus { const val QUEUED = "QUEUED"; const val RUNNING = "RUNNING"; const val COMPLETE = "COMPLETE"; const val FAILED = "FAILED" }
object AgentRole { const val USER = "USER"; const val AGENT = "AGENT" }

@Entity(tableName = "episodes")
data class EpisodeEntity(
    @PrimaryKey val id: String,
    val title: String,
    val phase: String,
    val instructions: String,
    val reviewEnabled: Boolean,
    val activeRevisionId: String?,
    val lockedRevisionId: String?,
    val lockedContentHash: String?,
    val lockedAtEpochMs: Long?,
    val finalAudioPath: String?,
    val durationMs: Long?,
    val currentChapterPosition: Int?,
    val failurePhase: String?,
    val failureMessage: String?,
    val createdAtEpochMs: Long,
    val updatedAtEpochMs: Long,
    val finalAudioSha256: String? = null,
    val finalAudioByteCount: Long? = null,
    val timelinePath: String? = null,
    val timelineSha256: String? = null,
    val timelineByteCount: Long? = null,
)

@Entity(
    tableName = "episode_sources",
    foreignKeys = [ForeignKey(EpisodeEntity::class, ["id"], ["episodeId"], onDelete = ForeignKey.CASCADE)],
    indices = [Index("episodeId")],
)
data class EpisodeSourceEntity(
    @PrimaryKey val id: String,
    val episodeId: String,
    val title: String,
    val mimeType: String,
    val relativePath: String,
    val wordCount: Int,
    val byteCount: Long,
    val sha256: String,
    val createdAtEpochMs: Long,
)

@Entity(
    tableName = "script_revisions",
    foreignKeys = [ForeignKey(EpisodeEntity::class, ["id"], ["episodeId"], onDelete = ForeignKey.CASCADE)],
    indices = [Index("episodeId"), Index(value = ["episodeId", "revisionNumber"], unique = true)],
)
data class ScriptRevisionEntity(
    @PrimaryKey val id: String,
    val episodeId: String,
    val baseRevisionId: String?,
    val revisionNumber: Int,
    val title: String,
    val contentHash: String,
    val relativePath: String,
    val createdAtEpochMs: Long,
)

@Entity(
    tableName = "chapters",
    foreignKeys = [ForeignKey(ScriptRevisionEntity::class, ["id"], ["revisionId"], onDelete = ForeignKey.CASCADE)],
    indices = [Index("revisionId"), Index(value = ["revisionId", "position"], unique = true), Index(value = ["revisionId", "stableChapterId"], unique = true)],
)
data class ChapterEntity(
    @PrimaryKey val rowId: String,
    val revisionId: String,
    val stableChapterId: String,
    val position: Int,
    val title: String,
    val text: String,
    val approximateDurationSeconds: Int,
)

@Entity(
    tableName = "agent_messages",
    foreignKeys = [ForeignKey(EpisodeEntity::class, ["id"], ["episodeId"], onDelete = ForeignKey.CASCADE)],
    indices = [Index("episodeId")],
)
data class AgentMessageEntity(
    @PrimaryKey val id: String,
    val episodeId: String,
    val role: String,
    val text: String,
    val baseRevisionId: String?,
    val resultRevisionId: String?,
    val createdAtEpochMs: Long,
)

@Entity(
    tableName = "generation_jobs",
    foreignKeys = [ForeignKey(EpisodeEntity::class, ["id"], ["episodeId"], onDelete = ForeignKey.CASCADE)],
    indices = [Index("episodeId")],
)
data class GenerationJobEntity(
    @PrimaryKey val id: String,
    val episodeId: String,
    val kind: String,
    val status: String,
    val requestedRevisionId: String?,
    val currentChapter: Int,
    val totalChapters: Int,
    val statusText: String,
    val errorMessage: String?,
    val createdAtEpochMs: Long,
    val updatedAtEpochMs: Long,
    val requestMessageId: String? = null,
    val failureStage: String? = null,
    val heartbeatAtEpochMs: Long? = null,
    val terminalAtEpochMs: Long? = null,
    val dispatchAttemptCount: Int = 0,
    val lastDispatchAtEpochMs: Long? = null,
)

@Entity(
    tableName = "chapter_audio",
    foreignKeys = [ForeignKey(EpisodeEntity::class, ["id"], ["episodeId"], onDelete = ForeignKey.CASCADE)],
    indices = [Index("episodeId"), Index(value = ["episodeId", "position"], unique = true)],
)
data class ChapterAudioEntity(
    @PrimaryKey val id: String,
    val episodeId: String,
    val lockedRevisionId: String,
    val stableChapterId: String,
    val position: Int,
    val relativePath: String,
    val sha256: String,
    val byteCount: Long,
    val sampleRateHz: Int,
    val channelCount: Int,
    val frameCount: Long,
    val startFrame: Long,
    val endFrame: Long,
)

@Entity(
    tableName = "playback_state",
    foreignKeys = [ForeignKey(EpisodeEntity::class, ["id"], ["episodeId"], onDelete = ForeignKey.CASCADE)],
)
data class PlaybackStateEntity(
    @PrimaryKey val episodeId: String,
    val positionMs: Long,
    val speed: Float,
    val transcriptVisible: Boolean,
    val updatedAtEpochMs: Long,
)

@Entity(tableName = "installed_models", indices = [Index(value = ["route"], unique = true)])
data class InstalledModelEntity(
    @PrimaryKey val id: String,
    val version: String,
    val route: String,
    val rootPath: String,
    val manifestSha256: String,
    val runtimeProvenanceJson: String,
    val verifiedAtEpochMs: Long,
)
