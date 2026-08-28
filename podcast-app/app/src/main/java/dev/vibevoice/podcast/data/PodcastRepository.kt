package dev.vibevoice.podcast.data

import androidx.room.withTransaction
import dev.vibevoice.podcast.model.VerifiedModelPack
import dev.vibevoice.podcast.runtime.AudioMetadata
import dev.vibevoice.podcast.runtime.RuntimeProvenance
import dev.vibevoice.podcast.runtime.WavInspector
import kotlinx.coroutines.flow.Flow
import java.io.File
import java.io.InputStream
import java.util.UUID

class PodcastRepository(
    private val database: PodcastDatabase,
    private val artifacts: ArtifactStore,
    private val clock: () -> Long = System::currentTimeMillis,
) {
    private val dao = database.podcastDao()

    fun observeEpisodes(): Flow<List<EpisodeEntity>> = dao.observeEpisodes()
    fun observeEpisode(id: String): Flow<EpisodeEntity?> = dao.observeEpisode(id)
    fun observeSources(id: String): Flow<List<EpisodeSourceEntity>> = dao.observeSources(id)
    fun observeChapters(id: String): Flow<List<ChapterEntity>> = dao.observeActiveChapters(id)
    fun observeMessages(id: String): Flow<List<AgentMessageEntity>> = dao.observeMessages(id)
    fun observeJob(id: String): Flow<GenerationJobEntity?> = dao.observeLatestJob(id)
    fun observeAudio(id: String): Flow<List<ChapterAudioEntity>> = dao.observeChapterAudio(id)
    fun observePlayback(id: String): Flow<PlaybackStateEntity?> = dao.observePlayback(id)

    suspend fun createEpisode(): String {
        val id = UUID.randomUUID().toString()
        val now = clock()
        dao.insertEpisode(EpisodeEntity(id, "Untitled episode", EpisodePhase.SOURCES, "", true, null, null, null, null, null, null, null, null, null, now, now))
        return id
    }

    suspend fun addSource(episodeId: String, title: String, mimeType: String, input: InputStream): EpisodeSourceEntity {
        val episode = requireEpisode(episodeId)
        require(episode.phase == EpisodePhase.SOURCES || episode.phase == EpisodePhase.INSTRUCTIONS) { "Sources are frozen" }
        val id = UUID.randomUUID().toString()
        val stored = artifacts.writeSource(episodeId, id, input)
        val source = EpisodeSourceEntity(
            id, episodeId, title.trim().ifBlank { "Pasted source" }, mimeType,
            stored.relativePath, stored.text.split(Regex("\\s+")).count { it.isNotBlank() },
            stored.byteCount, stored.sha256, clock(),
        )
        try { dao.insertSource(source) } catch (error: Throwable) { artifacts.resolveEpisodeFile(stored.relativePath).delete(); throw error }
        return source
    }

    suspend fun removeSource(episodeId: String, sourceId: String) {
        val episode = requireEpisode(episodeId)
        require(episode.phase == EpisodePhase.SOURCES || episode.phase == EpisodePhase.INSTRUCTIONS) { "Sources are frozen" }
        val source = dao.sources(episodeId).singleOrNull { it.id == sourceId } ?: return
        if (dao.deleteSourceById(sourceId) > 0) artifacts.resolveEpisodeFile(source.relativePath).delete()
    }

    suspend fun moveToInstructions(episodeId: String) = database.withTransaction {
        val episode = requireEpisode(episodeId)
        require(episode.phase == EpisodePhase.SOURCES) { "Episode is not accepting sources" }
        require(dao.sources(episodeId).isNotEmpty()) { "Add at least one source" }
        dao.updateEpisode(episode.copy(phase = EpisodePhase.INSTRUCTIONS, updatedAtEpochMs = clock()))
    }

    suspend fun queueScriptGeneration(episodeId: String, instructions: String, reviewEnabled: Boolean): String = database.withTransaction {
        val episode = requireEpisode(episodeId)
        require(episode.phase == EpisodePhase.INSTRUCTIONS) { "Episode is not ready for instructions" }
        require(dao.sources(episodeId).isNotEmpty()) { "Add at least one source" }
        val job = newJob(episodeId, JobKind.SCRIPT, null, "Preparing sources")
        dao.insertJob(job)
        dao.updateEpisode(episode.copy(
            phase = EpisodePhase.GENERATING_SCRIPT,
            instructions = instructions.trim(),
            reviewEnabled = reviewEnabled,
            failurePhase = null,
            failureMessage = null,
            updatedAtEpochMs = clock(),
        ))
        job.id
    }

    suspend fun sourceMaterials(episodeId: String): List<dev.vibevoice.podcast.runtime.SourceMaterial> =
        dao.sources(episodeId).map { dev.vibevoice.podcast.runtime.SourceMaterial(it.id, it.title, artifacts.readText(it.relativePath)) }

    suspend fun commitGeneratedScript(episodeId: String, jobId: String, title: String, chapters: List<ChapterDraft>): String {
        validateScript(title, chapters)
        val revisionId = UUID.randomUUID().toString()
        val stored = artifacts.writeRevision(episodeId, revisionId, title, chapters)
        try {
            return database.withTransaction {
                val episode = requireEpisode(episodeId)
                require(episode.phase == EpisodePhase.GENERATING_SCRIPT) { "Script result is stale" }
                val job = requireJob(jobId)
                require(job.kind == JobKind.SCRIPT && job.status != JobStatus.COMPLETE) { "Script job is stale" }
                insertRevision(revisionId, episode, null, title, chapters, stored)
                val now = clock()
                if (episode.reviewEnabled) {
                    dao.updateEpisode(episode.copy(title = title, phase = EpisodePhase.SCRIPT_DRAFT, activeRevisionId = revisionId, updatedAtEpochMs = now))
                } else {
                    dao.updateEpisode(episode.copy(
                        title = title, phase = EpisodePhase.LOCKED, activeRevisionId = revisionId,
                        lockedRevisionId = revisionId, lockedContentHash = stored.sha256, lockedAtEpochMs = now, updatedAtEpochMs = now,
                    ))
                    dao.insertJob(newJob(episodeId, JobKind.AUDIO, revisionId, "Waiting to create audio"))
                }
                dao.updateJob(job.copy(status = JobStatus.COMPLETE, statusText = "Script complete", updatedAtEpochMs = now))
                revisionId
            }
        } catch (error: Throwable) {
            artifacts.resolveEpisodeFile(stored.relativePath).delete()
            throw error
        }
    }

    suspend fun queueAgentEdit(episodeId: String, request: String): String = database.withTransaction {
        val episode = requireEpisode(episodeId)
        require(episode.phase == EpisodePhase.SCRIPT_DRAFT && episode.activeRevisionId != null) { "Only an unlocked draft can be edited" }
        require(request.isNotBlank()) { "Describe the requested change" }
        val now = clock()
        dao.insertMessage(AgentMessageEntity(UUID.randomUUID().toString(), episodeId, AgentRole.USER, request.trim(), episode.activeRevisionId, null, now))
        val job = newJob(episodeId, JobKind.AGENT_EDIT, episode.activeRevisionId, "Editing the draft")
        dao.insertJob(job)
        job.id
    }

    suspend fun activeRevision(episodeId: String): Pair<ScriptRevisionEntity, List<ChapterEntity>> {
        val episode = requireEpisode(episodeId)
        val id = episode.activeRevisionId ?: error("Episode has no active revision")
        return (dao.revision(id) ?: error("Missing active revision")) to dao.chapters(id)
    }

    suspend fun applyAgentRevision(
        episodeId: String,
        jobId: String,
        baseRevisionId: String,
        title: String,
        chapters: List<ChapterDraft>,
        summary: String,
    ): String {
        validateScript(title, chapters)
        require(summary.isNotBlank()) { "Agent change summary is missing" }
        val revisionId = UUID.randomUUID().toString()
        val stored = artifacts.writeRevision(episodeId, revisionId, title, chapters)
        try {
            return database.withTransaction {
                val episode = requireEpisode(episodeId)
                require(episode.phase == EpisodePhase.SCRIPT_DRAFT) { "Draft was locked while the agent was working" }
                require(episode.activeRevisionId == baseRevisionId) { "Agent result is stale" }
                val job = requireJob(jobId)
                require(job.kind == JobKind.AGENT_EDIT && job.requestedRevisionId == baseRevisionId) { "Agent job is stale" }
                insertRevision(revisionId, episode, baseRevisionId, title, chapters, stored)
                val now = clock()
                dao.insertMessage(AgentMessageEntity(UUID.randomUUID().toString(), episodeId, AgentRole.AGENT, summary.trim(), baseRevisionId, revisionId, now))
                dao.updateEpisode(episode.copy(title = title, activeRevisionId = revisionId, updatedAtEpochMs = now))
                dao.updateJob(job.copy(status = JobStatus.COMPLETE, statusText = "Changes ready", updatedAtEpochMs = now))
                revisionId
            }
        } catch (error: Throwable) {
            artifacts.resolveEpisodeFile(stored.relativePath).delete()
            throw error
        }
    }

    suspend fun lockAndQueueAudio(episodeId: String): String = database.withTransaction {
        val episode = requireEpisode(episodeId)
        require(episode.phase == EpisodePhase.SCRIPT_DRAFT && episode.activeRevisionId != null) { "Only the current draft can be locked" }
        val revision = dao.revision(episode.activeRevisionId) ?: error("Missing draft revision")
        require(dao.chapters(revision.id).isNotEmpty()) { "Cannot lock an empty script" }
        val now = clock()
        dao.updateEpisode(episode.copy(
            phase = EpisodePhase.LOCKED, lockedRevisionId = revision.id, lockedContentHash = revision.contentHash,
            lockedAtEpochMs = now, failurePhase = null, failureMessage = null, updatedAtEpochMs = now,
        ))
        val job = newJob(episodeId, JobKind.AUDIO, revision.id, "Waiting to create audio")
        dao.insertJob(job)
        job.id
    }

    suspend fun beginJob(jobId: String, status: String, totalChapters: Int = 0) = database.withTransaction {
        val job = requireJob(jobId)
        val episode = requireEpisode(job.episodeId)
        val now = clock()
        dao.updateJob(job.copy(status = JobStatus.RUNNING, statusText = status, totalChapters = totalChapters, updatedAtEpochMs = now))
        val phase = if (job.kind == JobKind.AUDIO) EpisodePhase.GENERATING_AUDIO else episode.phase
        dao.updateEpisode(episode.copy(phase = phase, updatedAtEpochMs = now))
    }

    suspend fun updateJobProgress(jobId: String, current: Int, total: Int, status: String) = database.withTransaction {
        val job = requireJob(jobId)
        val episode = requireEpisode(job.episodeId)
        val now = clock()
        dao.updateJob(job.copy(currentChapter = current, totalChapters = total, statusText = status, updatedAtEpochMs = now))
        dao.updateEpisode(episode.copy(currentChapterPosition = current, updatedAtEpochMs = now))
    }

    suspend fun lockedChapterData(episodeId: String): Pair<EpisodeEntity, List<ChapterEntity>> {
        val episode = requireEpisode(episodeId)
        require(episode.lockedRevisionId != null && episode.lockedContentHash != null) { "Episode is not locked" }
        val revision = dao.revision(episode.lockedRevisionId) ?: error("Missing locked revision")
        require(revision.contentHash == episode.lockedContentHash) { "Locked revision integrity mismatch" }
        return episode to dao.chapters(revision.id)
    }

    suspend fun resetChapterAudio(episodeId: String) = dao.clearChapterAudio(episodeId)

    suspend fun commitChapterAudio(episodeId: String, chapter: ChapterEntity, metadata: AudioMetadata, file: File, startFrame: Long) {
        val episode = requireEpisode(episodeId)
        val lockedRevisionId = episode.lockedRevisionId ?: error("Episode is not locked")
        require(file.isFile && file.length() > 44L) { "Chapter audio artifact is missing" }
        val inspected = WavInspector.inspectSupertonicOutput(file)
        require(inspected == metadata) { "Chapter WAV changed across the native/storage boundary" }
        dao.insertChapterAudio(ChapterAudioEntity(
            UUID.randomUUID().toString(), episodeId, lockedRevisionId, chapter.stableChapterId, chapter.position,
            artifacts.relativeToEpisodes(file), inspected.sha256, file.length(), inspected.sampleRateHz, inspected.channelCount,
            inspected.frameCount, startFrame, startFrame + inspected.frameCount,
        ))
    }

    suspend fun completeAudio(jobId: String, finalFile: File, durationMs: Long) = database.withTransaction {
        val job = requireJob(jobId)
        require(job.kind == JobKind.AUDIO) { "Not an audio job" }
        val episode = requireEpisode(job.episodeId)
        require(episode.lockedRevisionId == job.requestedRevisionId) { "Audio job revision mismatch" }
        val now = clock()
        dao.updateEpisode(episode.copy(
            phase = EpisodePhase.FROZEN_READY, finalAudioPath = artifacts.relativeToEpisodes(finalFile),
            durationMs = durationMs, currentChapterPosition = null, failurePhase = null, failureMessage = null, updatedAtEpochMs = now,
        ))
        dao.updateJob(job.copy(status = JobStatus.COMPLETE, statusText = "Episode ready", currentChapter = job.totalChapters, updatedAtEpochMs = now))
    }

    suspend fun failJob(jobId: String, message: String) = database.withTransaction {
        val job = requireJob(jobId)
        val episode = requireEpisode(job.episodeId)
        val now = clock()
        dao.updateJob(job.copy(status = JobStatus.FAILED, errorMessage = message.take(1000), statusText = "Generation failed", updatedAtEpochMs = now))
        dao.updateEpisode(episode.copy(phase = EpisodePhase.FAILED, failurePhase = job.kind, failureMessage = message.take(1000), updatedAtEpochMs = now))
    }

    suspend fun savePlayback(episodeId: String, positionMs: Long, speed: Float, transcript: Boolean) {
        val episode = requireEpisode(episodeId)
        require(episode.phase == EpisodePhase.FROZEN_READY) { "Playback is available only for frozen episodes" }
        dao.upsertPlayback(PlaybackStateEntity(episodeId, positionMs.coerceAtLeast(0), speed, transcript, clock()))
    }

    suspend fun episode(id: String): EpisodeEntity = requireEpisode(id)
    suspend fun latestJob(episodeId: String): GenerationJobEntity? = dao.latestJob(episodeId)
    suspend fun latestUserMessage(episodeId: String): AgentMessageEntity = dao.latestUserMessage(episodeId) ?: error("Agent request is missing")
    suspend fun chapters(revisionId: String): List<ChapterEntity> = dao.chapters(revisionId)
    suspend fun recordVerifiedPack(pack: VerifiedModelPack, provenance: RuntimeProvenance) {
        val json = org.json.JSONObject()
            .put("runtimeApiVersion", provenance.runtimeApiVersion)
            .put("model", provenance.model)
            .put("backend", provenance.backend)
            .put("runtimeVersion", provenance.runtimeVersion)
            .put("cpuFallbackEnabled", provenance.cpuFallbackEnabled)
            .put("readyComponents", org.json.JSONArray(provenance.readyComponents.sorted()))
            .toString()
        dao.upsertInstalledModel(InstalledModelEntity(
            pack.id, pack.version, pack.route.name, pack.root.absolutePath, pack.manifestSha256, json, clock(),
        ))
    }
    suspend fun audio(episodeId: String): List<ChapterAudioEntity> = dao.chapterAudio(episodeId)
    fun resolveArtifact(path: String): File = artifacts.resolveEpisodeFile(path)

    private suspend fun insertRevision(
        revisionId: String,
        episode: EpisodeEntity,
        base: String?,
        title: String,
        chapters: List<ChapterDraft>,
        stored: StoredFile,
    ) {
        val number = dao.latestRevisionNumber(episode.id) + 1
        dao.insertRevision(ScriptRevisionEntity(revisionId, episode.id, base, number, title.trim(), stored.sha256, stored.relativePath, clock()))
        dao.insertChapters(chapters.mapIndexed { index, chapter ->
            ChapterEntity(UUID.randomUUID().toString(), revisionId, chapter.stableId, index, chapter.title.trim(), chapter.text.trim(), approximateSeconds(chapter.text))
        })
    }

    private fun validateScript(title: String, chapters: List<ChapterDraft>) {
        require(title.isNotBlank() && title.length <= 200) { "Invalid episode title" }
        require(chapters.size in 1..20) { "A script must contain 1–20 complete chapters" }
        require(chapters.map { it.stableId }.toSet().size == chapters.size) { "Chapter IDs must be unique" }
        chapters.forEach {
            require(CHAPTER_ID.matches(it.stableId)) { "Invalid chapter ID" }
            require(it.title.isNotBlank() && it.title.length <= 200) { "Invalid chapter title" }
            require(it.text.isNotBlank() && it.text.length <= 100_000) { "Invalid complete chapter transcript" }
        }
    }

    private suspend fun requireEpisode(id: String) = dao.episode(id) ?: error("Episode not found")
    private suspend fun requireJob(id: String) = dao.job(id) ?: error("Generation job not found")
    private fun newJob(episodeId: String, kind: String, revisionId: String?, text: String): GenerationJobEntity {
        val now = clock()
        return GenerationJobEntity(UUID.randomUUID().toString(), episodeId, kind, JobStatus.QUEUED, revisionId, 0, 0, text, null, now, now)
    }

    private fun approximateSeconds(text: String): Int = (text.split(Regex("\\s+")).count { it.isNotBlank() } / 2.5).toInt().coerceAtLeast(1)

    companion object { private val CHAPTER_ID = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,127}") }
}
