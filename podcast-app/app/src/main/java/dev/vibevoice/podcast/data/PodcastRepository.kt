package dev.vibevoice.podcast.data

import androidx.room.withTransaction
import dev.vibevoice.podcast.model.VerifiedModelPack
import dev.vibevoice.podcast.runtime.AudioMetadata
import dev.vibevoice.podcast.runtime.RuntimeProvenance
import dev.vibevoice.podcast.runtime.WavAssembler
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
    fun observeLibraryPlayback(): Flow<List<PlaybackStateEntity>> = dao.observeLibraryPlayback()
    fun observeLibraryChapterCounts(): Flow<List<EpisodeChapterCount>> = dao.observeLibraryChapterCounts()

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
        require(episode.phase == EpisodePhase.SOURCES || episode.phase == EpisodePhase.INSTRUCTIONS) { "Episode is not accepting sources" }
        require(dao.sources(episodeId).isNotEmpty()) { "Add at least one source" }
        if (episode.phase != EpisodePhase.INSTRUCTIONS) {
            dao.updateEpisode(episode.copy(phase = EpisodePhase.INSTRUCTIONS, updatedAtEpochMs = clock()))
        }
    }

    suspend fun saveInstructionDraft(episodeId: String, instructions: String, reviewEnabled: Boolean) = database.withTransaction {
        require(instructions.length <= 2_000) { "Instructions exceed the 2,000-character limit" }
        val episode = requireEpisode(episodeId)
        // A delayed UI save must never regress generation or mutate a locked episode.
        if (episode.phase == EpisodePhase.SOURCES || episode.phase == EpisodePhase.INSTRUCTIONS) {
            dao.updateEpisode(episode.copy(instructions = instructions, reviewEnabled = reviewEnabled, updatedAtEpochMs = clock()))
        }
    }

    suspend fun queueScriptGeneration(episodeId: String, instructions: String, reviewEnabled: Boolean): String = database.withTransaction {
        val episode = requireEpisode(episodeId)
        require(episode.phase == EpisodePhase.INSTRUCTIONS) { "Episode is not ready for instructions" }
        require(instructions.isNotBlank() && instructions.length <= 2_000) { "Instructions must contain 1–2,000 characters" }
        val acceptedSources = dao.sources(episodeId)
        require(acceptedSources.isNotEmpty()) { "Add at least one source" }
        require(acceptedSources.sumOf { it.byteCount } <= MAX_EPISODE_SOURCE_BYTES) { "Episode sources exceed the 5 MB generation limit" }
        require(dao.activeJobCount() == 0) { "Another on-device generation job is active" }
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
                require(job.episodeId == episodeId && job.kind == JobKind.SCRIPT && job.status == JobStatus.RUNNING) { "Script job is stale or cross-wired" }
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
                dao.updateJob(job.copy(status = JobStatus.COMPLETE, statusText = "Script complete", terminalAtEpochMs = now, heartbeatAtEpochMs = now, updatedAtEpochMs = now))
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
        require(dao.activeJobCount() == 0) { "Another on-device generation job is active" }
        val now = clock()
        val message = AgentMessageEntity(UUID.randomUUID().toString(), episodeId, AgentRole.USER, request.trim(), episode.activeRevisionId, null, now)
        dao.insertMessage(message)
        val job = newJob(episodeId, JobKind.AGENT_EDIT, episode.activeRevisionId, "Editing the draft").copy(requestMessageId = message.id)
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
                require(job.episodeId == episodeId && job.kind == JobKind.AGENT_EDIT && job.requestedRevisionId == baseRevisionId &&
                    job.status == JobStatus.RUNNING && job.requestMessageId != null
                ) { "Agent job is stale or cross-wired" }
                insertRevision(revisionId, episode, baseRevisionId, title, chapters, stored)
                val now = clock()
                dao.insertMessage(AgentMessageEntity(UUID.randomUUID().toString(), episodeId, AgentRole.AGENT, summary.trim(), baseRevisionId, revisionId, now))
                dao.updateEpisode(episode.copy(title = title, activeRevisionId = revisionId, updatedAtEpochMs = now))
                dao.updateJob(job.copy(status = JobStatus.COMPLETE, statusText = "Changes ready", terminalAtEpochMs = now, heartbeatAtEpochMs = now, updatedAtEpochMs = now))
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
        require(dao.activeJobCount(episodeId) == 0) { "Wait for the current agent edit to finish before locking" }
        require(dao.activeJobCount() == 0) { "Another on-device generation job is active" }
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

    suspend fun claimJob(episodeId: String, jobId: String, expectedKind: String, status: String, totalChapters: Int = 0): JobClaim = database.withTransaction {
        val job = requireJob(jobId)
        val episode = requireEpisode(episodeId)
        require(job.episodeId == episodeId && job.kind == expectedKind) { "Generation command is cross-wired" }
        require(job.status == JobStatus.QUEUED) { "Generation job was already claimed" }
        require(dao.runningJobCount() == 0) { "Another model-heavy job is running" }
        when (expectedKind) {
            JobKind.SCRIPT -> require(episode.phase == EpisodePhase.GENERATING_SCRIPT && job.requestedRevisionId == null) { "Script job does not match episode state" }
            JobKind.AGENT_EDIT -> require(episode.phase == EpisodePhase.SCRIPT_DRAFT && episode.activeRevisionId == job.requestedRevisionId && job.requestMessageId != null) { "Agent job does not match the active draft" }
            JobKind.AUDIO -> require(episode.phase == EpisodePhase.LOCKED && episode.lockedRevisionId == job.requestedRevisionId) { "Audio job does not match the locked revision" }
            else -> error("Unknown job kind")
        }
        val message = job.requestMessageId?.let { id -> dao.message(id) ?: error("Agent job message is missing") }
        if (message != null) require(message.episodeId == episodeId && message.baseRevisionId == job.requestedRevisionId) { "Agent job message is cross-wired" }
        val now = clock()
        val claimed = job.copy(status = JobStatus.RUNNING, statusText = status, totalChapters = totalChapters, heartbeatAtEpochMs = now, updatedAtEpochMs = now)
        dao.updateJob(claimed)
        val phase = if (expectedKind == JobKind.AUDIO) EpisodePhase.GENERATING_AUDIO else episode.phase
        dao.updateEpisode(episode.copy(phase = phase, updatedAtEpochMs = now))
        JobClaim(claimed, episode, message)
    }

    suspend fun updateJobProgress(episodeId: String, jobId: String, expectedKind: String, current: Int, total: Int, status: String) = database.withTransaction {
        val job = requireJob(jobId)
        require(job.episodeId == episodeId && job.kind == expectedKind && job.status == JobStatus.RUNNING) { "Cannot update an unclaimed or cross-wired job" }
        val episode = requireEpisode(episodeId)
        val now = clock()
        dao.updateJob(job.copy(currentChapter = current, totalChapters = total, statusText = status, heartbeatAtEpochMs = now, updatedAtEpochMs = now))
        dao.updateEpisode(episode.copy(currentChapterPosition = current.takeIf { it > 0 }, updatedAtEpochMs = now))
    }

    suspend fun lockedChapterData(episodeId: String): Pair<EpisodeEntity, List<ChapterEntity>> {
        val episode = requireEpisode(episodeId)
        require(episode.lockedRevisionId != null && episode.lockedContentHash != null) { "Episode is not locked" }
        val revision = dao.revision(episode.lockedRevisionId) ?: error("Missing locked revision")
        require(revision.contentHash == episode.lockedContentHash) { "Locked revision integrity mismatch" }
        return episode to dao.chapters(revision.id)
    }

    suspend fun resetChapterAudio(episodeId: String) = dao.clearChapterAudio(episodeId)

    suspend fun commitChapterAudio(episodeId: String, jobId: String, chapter: ChapterEntity, metadata: AudioMetadata, file: File, startFrame: Long) = database.withTransaction {
        val episode = requireEpisode(episodeId)
        val lockedRevisionId = episode.lockedRevisionId ?: error("Episode is not locked")
        val job = requireJob(jobId)
        require(job.episodeId == episodeId && job.kind == JobKind.AUDIO && job.status == JobStatus.RUNNING &&
            job.requestedRevisionId == lockedRevisionId && episode.phase == EpisodePhase.GENERATING_AUDIO
        ) { "Chapter audio write has no matching running locked-revision job" }
        require(chapter.revisionId == lockedRevisionId && dao.chapters(lockedRevisionId).any {
            it.rowId == chapter.rowId && it.stableChapterId == chapter.stableChapterId && it.position == chapter.position
        }) { "Chapter audio does not belong to the locked revision" }
        require(file.isFile && file.length() > 44L) { "Chapter audio artifact is missing" }
        val inspected = WavInspector.inspectSupertonicOutput(file)
        require(inspected == metadata) { "Chapter WAV changed across the native/storage boundary" }
        dao.insertChapterAudio(ChapterAudioEntity(
            UUID.randomUUID().toString(), episodeId, lockedRevisionId, chapter.stableChapterId, chapter.position,
            artifacts.relativeToEpisodes(file), inspected.sha256, file.length(), inspected.sampleRateHz, inspected.channelCount,
            inspected.frameCount, startFrame, startFrame + inspected.frameCount,
        ))
    }

    suspend fun completeAudio(episodeId: String, jobId: String, result: WavAssembler.Result) = database.withTransaction {
        val job = requireJob(jobId)
        val episode = requireEpisode(episodeId)
        require(job.episodeId == episodeId && job.kind == JobKind.AUDIO && job.status == JobStatus.RUNNING) { "Audio completion is stale or cross-wired" }
        require(episode.phase == EpisodePhase.GENERATING_AUDIO && episode.lockedRevisionId == job.requestedRevisionId) { "Audio job revision or phase mismatch" }
        val locked = dao.chapters(requireNotNull(episode.lockedRevisionId))
        val rendered = dao.chapterAudio(episodeId)
        require(rendered.size == locked.size && rendered.map { it.position } == locked.map { it.position } &&
            rendered.map { it.stableChapterId } == locked.map { it.stableChapterId } && rendered.all { it.lockedRevisionId == episode.lockedRevisionId }
        ) { "Frozen episode does not have complete locked-chapter audio coverage" }
        rendered.forEach {
            val file = artifacts.resolveEpisodeFile(it.relativePath)
            val inspected = WavInspector.inspectSupertonicOutput(file)
            require(inspected.sha256 == it.sha256 && file.length() == it.byteCount) { "Chapter audio changed before final commit" }
        }
        val finalInspection = WavInspector.inspectSupertonicOutput(result.audioFile)
        require(finalInspection.sha256 == result.audioSha256 && result.audioFile.length() == result.audioByteCount) { "Final WAV integrity mismatch" }
        require(result.timelineFile.isFile && artifacts.sha256(result.timelineFile) == result.timelineSha256 && result.timelineFile.length() == result.timelineByteCount) { "Timeline integrity mismatch" }
        val now = clock()
        dao.updateEpisode(episode.copy(
            phase = EpisodePhase.FROZEN_READY,
            finalAudioPath = artifacts.relativeToEpisodes(result.audioFile),
            finalAudioSha256 = result.audioSha256,
            finalAudioByteCount = result.audioByteCount,
            timelinePath = artifacts.relativeToEpisodes(result.timelineFile),
            timelineSha256 = result.timelineSha256,
            timelineByteCount = result.timelineByteCount,
            durationMs = result.durationMs,
            currentChapterPosition = null,
            failurePhase = null,
            failureMessage = null,
            updatedAtEpochMs = now,
        ))
        dao.updateJob(job.copy(status = JobStatus.COMPLETE, statusText = "Episode ready", currentChapter = job.totalChapters,
            terminalAtEpochMs = now, heartbeatAtEpochMs = now, updatedAtEpochMs = now))
    }

    suspend fun failJob(episodeId: String, jobId: String, message: String, stage: String? = null): Boolean = database.withTransaction {
        val job = requireJob(jobId)
        require(job.episodeId == episodeId) { "Failure command is cross-wired" }
        if (job.status != JobStatus.RUNNING) return@withTransaction false
        val episode = requireEpisode(episodeId)
        val now = clock()
        val failureStage = stage ?: job.statusText
        dao.updateJob(job.copy(status = JobStatus.FAILED, errorMessage = message.take(1000), failureStage = failureStage,
            statusText = "Generation failed", terminalAtEpochMs = now, heartbeatAtEpochMs = now, updatedAtEpochMs = now))
        val stillOwnsPhase = when (job.kind) {
            JobKind.SCRIPT -> episode.phase == EpisodePhase.GENERATING_SCRIPT
            JobKind.AGENT_EDIT -> episode.phase == EpisodePhase.SCRIPT_DRAFT && episode.activeRevisionId == job.requestedRevisionId
            JobKind.AUDIO -> episode.phase == EpisodePhase.GENERATING_AUDIO && episode.lockedRevisionId == job.requestedRevisionId
            else -> false
        }
        if (stillOwnsPhase) dao.updateEpisode(episode.copy(phase = EpisodePhase.FAILED, failurePhase = "$failureStage", failureMessage = message.take(1000), updatedAtEpochMs = now))
        true
    }

    suspend fun runningJobs(): List<GenerationJobEntity> = dao.runningJobs()
    suspend fun queuedJobs(): List<GenerationJobEntity> = dao.queuedJobs()

    suspend fun markQueuedDispatchAttempt(episodeId: String, jobId: String): GenerationJobEntity? = database.withTransaction {
        val job = requireJob(jobId)
        require(job.episodeId == episodeId) { "Dispatch command is cross-wired" }
        if (job.status != JobStatus.QUEUED) return@withTransaction null
        val now = clock()
        job.copy(dispatchAttemptCount = job.dispatchAttemptCount + 1, lastDispatchAtEpochMs = now, updatedAtEpochMs = now)
            .also { dao.updateJob(it) }
    }

    suspend fun failQueuedJob(episodeId: String, jobId: String, message: String, stage: String = "service_dispatch"): Boolean = database.withTransaction {
        val job = requireJob(jobId)
        require(job.episodeId == episodeId) { "Queued failure command is cross-wired" }
        if (job.status != JobStatus.QUEUED) return@withTransaction false
        val episode = requireEpisode(episodeId)
        val ownsState = when (job.kind) {
            JobKind.SCRIPT -> episode.phase == EpisodePhase.GENERATING_SCRIPT
            JobKind.AGENT_EDIT -> episode.phase == EpisodePhase.SCRIPT_DRAFT && episode.activeRevisionId == job.requestedRevisionId
            JobKind.AUDIO -> episode.phase == EpisodePhase.LOCKED && episode.lockedRevisionId == job.requestedRevisionId
            else -> false
        }
        val now = clock()
        dao.updateJob(job.copy(status = JobStatus.FAILED, errorMessage = message.take(1000), failureStage = stage,
            statusText = "Generation failed", terminalAtEpochMs = now, updatedAtEpochMs = now))
        if (ownsState && job.kind != JobKind.AGENT_EDIT) {
            dao.updateEpisode(episode.copy(phase = EpisodePhase.FAILED, failurePhase = stage, failureMessage = message.take(1000), updatedAtEpochMs = now))
        } else if (ownsState) {
            dao.updateEpisode(episode.copy(failurePhase = stage, failureMessage = message.take(1000), updatedAtEpochMs = now))
        }
        true
    }

    suspend fun savePlayback(episodeId: String, positionMs: Long, speed: Float, transcript: Boolean) {
        val episode = requireEpisode(episodeId)
        require(episode.phase == EpisodePhase.FROZEN_READY) { "Playback is available only for frozen episodes" }
        dao.upsertPlayback(PlaybackStateEntity(episodeId, positionMs.coerceAtLeast(0), speed, transcript, clock()))
    }

    suspend fun episode(id: String): EpisodeEntity = requireEpisode(id)
    suspend fun latestJob(episodeId: String): GenerationJobEntity? = dao.latestJob(episodeId)
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

    companion object {
        private val CHAPTER_ID = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
        private const val MAX_EPISODE_SOURCE_BYTES = 5L * 1024L * 1024L
    }
}

data class JobClaim(
    val job: GenerationJobEntity,
    val episode: EpisodeEntity,
    val message: AgentMessageEntity?,
)
