package dev.vibevoice.podcast.data

import androidx.room.withTransaction
import dev.vibevoice.podcast.model.VerifiedModelPack
import dev.vibevoice.podcast.runtime.AudioMetadata
import dev.vibevoice.podcast.runtime.RuntimeProvenance
import dev.vibevoice.podcast.runtime.WavAssembler
import dev.vibevoice.podcast.runtime.WavInspector
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.isActive
import java.io.File
import java.io.InputStream
import java.util.UUID

class PodcastRepository(
    private val database: PodcastDatabase,
    private val artifacts: ArtifactStore,
    private val providerAdmission: Boolean = dev.vibevoice.podcast.runtime.ProviderAudioPlan.selected,
    private val clock: () -> Long = System::currentTimeMillis,
) {
    private val dao = database.podcastDao()
    private val streamReaders = mutableMapOf<dev.vibevoice.podcast.runtime.AudioAttemptBinding, dev.vibevoice.podcast.runtime.ProgressiveAudio.Reader>()
    private fun streamReader(binding: dev.vibevoice.podcast.runtime.AudioAttemptBinding) = synchronized(streamReaders) {
        streamReaders.getOrPut(binding) { dev.vibevoice.podcast.runtime.ProgressiveAudio.Reader(artifacts, binding) }
    }

    fun audioTextCapacity(texts: List<String>): dev.vibevoice.podcast.runtime.ScriptTextCapacity =
        if (providerAdmission) dev.vibevoice.podcast.runtime.ProviderAudioPlan.assess(artifacts, texts)
        else dev.vibevoice.podcast.runtime.SupertonicTextCapacity.assess(texts,
            dev.vibevoice.podcast.runtime.SupertonicTextCapacity.textLengthForManifest(dev.vibevoice.podcast.BuildConfig.SUPERTONIC_MANIFEST_SHA256))

    fun observeEpisodes(): Flow<List<EpisodeEntity>> = dao.observeEpisodes()
    fun observeEpisode(id: String): Flow<EpisodeEntity?> = dao.observeEpisode(id).map { it?.takeUnless { artifacts.episodeLeases.isDeleted(id) } }
    fun observeSources(id: String): Flow<List<EpisodeSourceEntity>> = dao.observeSources(id)
    fun observeChapters(id: String): Flow<List<ChapterEntity>> = dao.observeActiveChapters(id)
    fun observeMessages(id: String): Flow<List<AgentMessageEntity>> = dao.observeMessages(id)
    fun observeJob(id: String): Flow<GenerationJobEntity?> = dao.observeLatestJob(id)
    fun observeAudio(id: String): Flow<List<ChapterAudioEntity>> = dao.observeChapterAudio(id)
    fun observePlayback(id: String): Flow<PlaybackStateEntity?> = dao.observePlayback(id).map { saved ->
        if (saved != null) saved else {
            val episode = dao.episode(id)
            if (episode?.phase == EpisodePhase.FROZEN_READY) runCatching { audioBinding(id, null)?.let { streamPlayback(it) } }.getOrNull() else null
        }
    }
    fun observeLibraryPlayback(): Flow<List<PlaybackStateEntity>> = dao.observeLibraryPlayback()
    fun observeLibraryChapterCounts(): Flow<List<EpisodeChapterCount>> = dao.observeLibraryChapterCounts()

    fun acquireEpisodeFiles(id: String): java.io.Closeable = artifacts.episodeLeases.acquire(id)
    fun deletionRequested(id: String): Boolean = artifacts.episodeLeases.isDeleted(id)

    /** Immutable ID from the confirmation, never the current navigation selection. */
    suspend fun requestEpisodeDeletion(id: String) = database.withTransaction {
        val episode = dao.episode(id) ?: return@withTransaction
        artifacts.episodeLeases.tombstone(id)
        markDeleting(episode)
    }

    private suspend fun markDeleting(episode: EpisodeEntity) {
        if (episode.phase != "DELETING") dao.updateEpisode(episode.copy(phase = "DELETING", updatedAtEpochMs = clock()))
        // Running work keeps the global admission slot until its OS lease is gone. No next model
        // can be dispatched while a cancelled native worker is still unwinding.
        dao.episodeJobs(episode.id).filter { it.status == JobStatus.QUEUED }.forEach {
            dao.updateJob(it.copy(status = JobStatus.FAILED, statusText = "Episode deleted", failureStage = "episode_deletion",
                terminalAtEpochMs = clock(), updatedAtEpochMs = clock()))
        }
    }

    /** Restartable, idempotent cleanup. Files first, then cascading rows, tombstone retained.
     * A crash anywhere leaves an irreversible request that the next launch can finish.
     */
    suspend fun reapEpisodeDeletions() {
        for (id in artifacts.episodeLeases.tombstonedIds()) {
            try {
                if (dao.episode(id) == null) continue
                database.withTransaction { markDeleting(dao.episode(id) ?: return@withTransaction) }
                val lease = artifacts.episodeLeases.tryCleanupLease(id) ?: continue
                lease.use {
                    database.withTransaction {
                        // A source referenced by a different episode is shared, even if its stored
                        // path is under this ID. Keep those bytes; never touch model/shared roots.
                        val preserved = dao.foreignSourcePaths(id, "$id/").map {
                            artifacts.resolveEpisodeFile(it).toPath().toAbsolutePath().normalize()
                        }.toSet()
                        artifacts.episodeLeases.removeOwnedFiles(id, preserved)
                        dao.deleteEpisodeRows(id)
                    }
                    synchronized(streamReaders) { streamReaders.keys.removeAll { it.episodeId == id } }
                }
            } catch (cancelled: kotlinx.coroutines.CancellationException) { throw cancelled }
            catch (_: Exception) { /* Keep DELETING + marker. Retry locally; never broaden deletion. */ }
        }
    }

    suspend fun episodeDiagnostics(id: String): List<Pair<GenerationJobEntity, org.json.JSONObject?>> {
        requireEpisode(id)
        return dao.episodeJobs(id).map { it to dev.vibevoice.podcast.episode.EpisodeMetrics.read(artifacts, id, it.id) }
    }

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
        try {
            database.withTransaction {
                // The stream/file write can outlive the form. Recheck the captured episode at
                // commit so a queued generation cannot acquire a late, unfrozen source.
                val current = requireEpisode(episodeId)
                require(current.phase == EpisodePhase.SOURCES || current.phase == EpisodePhase.INSTRUCTIONS) { "Sources are frozen" }
                dao.insertSource(source)
            }
        } catch (error: Throwable) { artifacts.resolveEpisodeFile(stored.relativePath).delete(); throw error }
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
        var providerPlan: dev.vibevoice.podcast.runtime.ProviderAudioPlan.Saved? = null
        try {
            return database.withTransaction {
                val episode = requireEpisode(episodeId)
                require(episode.phase == EpisodePhase.GENERATING_SCRIPT) { "Script result is stale" }
                val job = requireJob(jobId)
                require(job.episodeId == episodeId && job.kind == JobKind.SCRIPT && job.status == JobStatus.RUNNING) { "Script job is stale or cross-wired" }
                insertRevision(revisionId, episode, null, title, chapters, stored)
                val now = clock()
                // Even review-OFF must keep the complete generated draft if this voice cannot accept it.
                // This checks the same normalized text that would be sent; it never shortens the script.
                var audioJob: GenerationJobEntity? = null
                var planFailed = false
                if (!episode.reviewEnabled && audioTextCapacity(chapters.map { it.text.trim() }).fits) {
                    val proposed = newJob(episodeId, JobKind.AUDIO, revisionId, "Waiting to create audio")
                    if (providerAdmission) {
                        // Failure to prepare audio must not discard a successfully generated complete script.
                        val plan = runCatching { dev.vibevoice.podcast.runtime.ProviderAudioPlan.save(artifacts, episodeId, revisionId,
                            stored.sha256, proposed.id, dao.chapters(revisionId).map { ChapterDraft(it.stableChapterId, it.title, it.text) }) }.getOrNull()
                        providerPlan = plan
                        if (plan == null) planFailed = true else audioJob = proposed.copy(id = plan.jobId)
                    } else audioJob = proposed
                }
                if (audioJob == null) {
                    dao.updateEpisode(episode.copy(title = title, phase = EpisodePhase.SCRIPT_DRAFT, activeRevisionId = revisionId,
                        failurePhase = if (planFailed) "audio_plan" else null,
                        failureMessage = if (planFailed) "Audio preparation could not be saved. Your complete script remains editable." else null,
                        updatedAtEpochMs = now))
                } else {
                    dao.updateEpisode(episode.copy(
                        title = title, phase = EpisodePhase.LOCKED, activeRevisionId = revisionId,
                        lockedRevisionId = revisionId, lockedContentHash = stored.sha256, lockedAtEpochMs = now, updatedAtEpochMs = now,
                    ))
                    dao.insertJob(audioJob)
                }
                dao.updateJob(job.copy(status = JobStatus.COMPLETE, statusText = "Script complete", terminalAtEpochMs = now, heartbeatAtEpochMs = now, updatedAtEpochMs = now))
                revisionId
            }
        } catch (error: Throwable) {
            providerPlan?.file?.delete()
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

    suspend fun lockAndQueueAudio(episodeId: String): String {
        var plan: dev.vibevoice.podcast.runtime.ProviderAudioPlan.Saved? = null
        try {
            return database.withTransaction {
                val episode = requireEpisode(episodeId)
                require(episode.phase == EpisodePhase.SCRIPT_DRAFT && episode.activeRevisionId != null) { "Only the current draft can be locked" }
                require(dao.activeJobCount(episodeId) == 0) { "Wait for the current agent edit to finish before locking" }
                require(dao.activeJobCount() == 0) { "Another on-device generation job is active" }
                val revision = dao.revision(episode.activeRevisionId) ?: error("Missing draft revision")
                val chapters = dao.chapters(revision.id)
                require(revision.episodeId == episodeId && chapters.isNotEmpty()) { "Cannot lock an invalid script" }
                require(artifacts.sha256(artifacts.resolveEpisodeFile(revision.relativePath)) == revision.contentHash) { "Draft file integrity mismatch" }
                // Recompute against current rows/pack inside the lock transaction; cached UI checks cannot authorize it.
                val capacity = audioTextCapacity(chapters.map { it.text })
                if (!capacity.fits) throw dev.vibevoice.podcast.runtime.AudioTextCapacityException(capacity)
                var job = newJob(episodeId, JobKind.AUDIO, revision.id, "Waiting to create audio")
                if (providerAdmission) {
                    plan = dev.vibevoice.podcast.runtime.ProviderAudioPlan.save(artifacts, episodeId, revision.id, revision.contentHash,
                        job.id, chapters.map { ChapterDraft(it.stableChapterId, it.title, it.text) })
                    job = job.copy(id = requireNotNull(plan).jobId)
                }
                val now = clock()
                dao.updateEpisode(episode.copy(
                    phase = EpisodePhase.LOCKED, lockedRevisionId = revision.id, lockedContentHash = revision.contentHash,
                    lockedAtEpochMs = now, failurePhase = null, failureMessage = null, updatedAtEpochMs = now,
                ))
                dao.insertJob(job)
                job.id
            }
        } catch (error: Throwable) { plan?.file?.delete(); throw error }
    }

    internal suspend fun verifyAudioPlan(episodeId: String, jobId: String, pack: VerifiedModelPack): List<dev.vibevoice.podcast.runtime.ProviderPublicationRecovery.Chapter>? {
        val contract = pack.contract as? dev.vibevoice.podcast.model.SupertonicModelContract ?: error("Missing audio contract")
        if (contract.providerPipeline == null) return null
        val job = requireJob(jobId); val (episode, chapters) = lockedChapterData(episodeId)
        require(job.kind == JobKind.AUDIO && job.episodeId == episodeId && job.requestedRevisionId == episode.lockedRevisionId && job.status == JobStatus.RUNNING)
        val revision = requireNotNull(dao.revision(requireNotNull(episode.lockedRevisionId)))
        require(revision.episodeId == episodeId && artifacts.sha256(artifacts.resolveEpisodeFile(revision.relativePath)) == revision.contentHash)
        val inputs = chapters.map { ChapterDraft(it.stableChapterId, it.title, it.text) }
        if (dev.vibevoice.podcast.runtime.ProviderPublicationRecovery.isRecovery(artifacts, episodeId, jobId)) {
            require(pack.manifestSha256 == dev.vibevoice.podcast.runtime.ProviderAudioPlan.PACK_SHA256)
            val (sourceJob, completed) = dev.vibevoice.podcast.runtime.ProviderPublicationRecovery.verify(artifacts, episodeId, jobId, revision.id, revision.contentHash, inputs)
            val previous = requireJob(sourceJob)
            require(previous.episodeId == episodeId && previous.kind == JobKind.AUDIO && previous.status == JobStatus.FAILED && previous.requestedRevisionId == revision.id)
            return completed
        }
        dev.vibevoice.podcast.runtime.ProviderAudioPlan.verify(artifacts, episodeId, jobId, revision.id, revision.contentHash, pack.manifestSha256, inputs)
        return null
    }

    /** Explicit new, non-neural publication attempt. Original failed job/plan/waves are immutable. */
    internal suspend fun queueProviderPublicationRecovery(episodeId: String, failedJobId: String, revisionId: String,
        completed: List<Pair<String, String>>): String {
        var saved: dev.vibevoice.podcast.runtime.ProviderAudioPlan.Saved? = null
        try {
            return database.withTransaction {
                val episode = requireEpisode(episodeId);val failed = requireJob(failedJobId)
                require(episode.phase == EpisodePhase.FAILED && episode.lockedRevisionId == revisionId && episode.activeRevisionId == revisionId)
                require(failed.episodeId == episodeId && failed.kind == JobKind.AUDIO && failed.status == JobStatus.FAILED && failed.requestedRevisionId == revisionId)
                require(dao.latestJob(episodeId)?.id == failedJobId && dao.activeJobCount() == 0)
                require(dao.chapterAudio(episodeId).isEmpty()) { "Recovery cannot overwrite published chapter audio" }
                val revision = requireNotNull(dao.revision(revisionId))
                require(revision.episodeId == episodeId && revision.contentHash == episode.lockedContentHash && artifacts.sha256(artifacts.resolveEpisodeFile(revision.relativePath)) == revision.contentHash)
                val chapters = dao.chapters(revisionId).map { ChapterDraft(it.stableChapterId, it.title, it.text) }
                val attempt = newJob(episodeId, JobKind.AUDIO, revisionId, "Publishing completed audio without inference")
                saved = dev.vibevoice.podcast.runtime.ProviderPublicationRecovery.save(artifacts, episodeId, revisionId, revision.contentHash, failedJobId, attempt.id, chapters, completed)
                val job = attempt.copy(id = requireNotNull(saved).jobId)
                dao.insertJob(job)
                dao.updateEpisode(episode.copy(phase = EpisodePhase.LOCKED, failurePhase = null, failureMessage = null, updatedAtEpochMs = clock()))
                job.id
            }
        } catch (error: Throwable) { saved?.file?.delete();throw error }
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
        if (deletionRequested(episodeId)) return@withTransaction false
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
        if (stillOwnsPhase) dao.updateEpisode(episode.copy(
            phase = if (job.kind == JobKind.AGENT_EDIT) EpisodePhase.SCRIPT_DRAFT else EpisodePhase.FAILED,
            failurePhase = failureStage, failureMessage = message.take(1000), updatedAtEpochMs = now,
        ))
        true
    }

    /** Guard-only CAS: authenticate the exact locked plan/stream and sole active AUDIO attempt. */
    suspend fun abortOwnedAudio(binding: dev.vibevoice.podcast.runtime.AudioAttemptBinding, reason: String): Boolean = database.withTransaction {
        val job=dao.latestJob(binding.episodeId) ?: return@withTransaction false
        val episode=dao.episode(binding.episodeId) ?: return@withTransaction false
        val deleting = episode.phase == "DELETING" && deletionRequested(binding.episodeId)
        if(job.id!=binding.jobId || job.status!=JobStatus.RUNNING || job.kind!=JobKind.AUDIO || dao.activeJobCount()!=1 ||
            (episode.phase!=EpisodePhase.GENERATING_AUDIO && !deleting) || audioBinding(binding.episodeId,binding.jobId)!=binding) return@withTransaction false
        if (deleting) {
            // A tombstone must not disable the already-authenticated resource guard while native
            // teardown is blocked. Retain DELETING, and persist only this exact worker's failure.
            val now = clock()
            dao.updateJob(job.copy(status = JobStatus.FAILED, statusText = "Episode deleted", failureStage = "owned_resource_guard",
                errorMessage = "Owned validation stopped during deletion", terminalAtEpochMs = now, heartbeatAtEpochMs = now, updatedAtEpochMs = now))
            true
        } else failJob(binding.episodeId,binding.jobId,"Owned validation stopped: $reason. Completed audio is retained; no retry was queued.","owned_resource_guard")
    }

    /** Explicit user action for drafts hidden by older failed-edit handling. Never retries the edit. */
    suspend fun returnToSavedDraft(episodeId: String, failedJobId: String, revisionId: String) = database.withTransaction {
        val episode = requireEpisode(episodeId)
        val job = requireNotNull(dao.latestJob(episodeId)) { "No failed editing request exists" }
        require(job.id == failedJobId && episode.activeRevisionId == revisionId && canReturnToSavedDraft(episode, job)) {
            "The saved draft or editing request changed; reopen the episode"
        }
        require(dao.activeJobCount() == 0) { "Wait for the current on-device job to finish" }
        val revision = requireNotNull(dao.revision(revisionId)) { "The saved revision is missing" }
        require(revision.episodeId == episodeId) { "The saved revision belongs to another episode" }
        val message = requireNotNull(dao.message(requireNotNull(job.requestMessageId))) { "The editing request is missing" }
        require(message.episodeId == episodeId && message.role == AgentRole.USER && message.baseRevisionId == revisionId) {
            "The editing request does not belong to this revision"
        }
        require(dao.chapterAudio(episodeId).isEmpty()) { "An episode with audio history cannot be reopened by edit recovery" }
        val chapters = dao.chapters(revisionId)
        validateScript(revision.title, chapters.map { ChapterDraft(it.stableChapterId, it.title, it.text) })
        val artifact = artifacts.resolveEpisodeFile(revision.relativePath)
        require(artifact.isFile && artifacts.sha256(artifact) == revision.contentHash) { "The saved revision file failed its integrity check" }
        // Only reopen the existing draft. Retain the failed job, request, failure metadata and all immutable content.
        dao.updateEpisode(episode.copy(phase = EpisodePhase.SCRIPT_DRAFT, updatedAtEpochMs = clock()))
    }

    suspend fun runningJobs(): List<GenerationJobEntity> = dao.runningJobs().filterNot { deletionRequested(it.episodeId) }
    suspend fun queuedJobs(): List<GenerationJobEntity> = dao.queuedJobs().filterNot { deletionRequested(it.episodeId) }

    suspend fun markQueuedDispatchAttempt(episodeId: String, jobId: String): GenerationJobEntity? = database.withTransaction {
        if (deletionRequested(episodeId)) return@withTransaction null
        val job = requireJob(jobId)
        require(job.episodeId == episodeId) { "Dispatch command is cross-wired" }
        if (job.status != JobStatus.QUEUED) return@withTransaction null
        val now = clock()
        job.copy(dispatchAttemptCount = job.dispatchAttemptCount + 1, lastDispatchAtEpochMs = now, updatedAtEpochMs = now)
            .also { dao.updateJob(it) }
    }

    suspend fun failQueuedJob(episodeId: String, jobId: String, message: String, stage: String = "service_dispatch"): Boolean = database.withTransaction {
        if (deletionRequested(episodeId)) return@withTransaction false
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

    private suspend fun audioBinding(episodeId: String, requestedJob: String?): dev.vibevoice.podcast.runtime.AudioAttemptBinding? {
        val episode = dao.episode(episodeId) ?: return null
        val job = (if (requestedJob != null) dao.job(requestedJob) else dao.latestJob(episodeId)) ?: return null
        if (job.episodeId != episodeId || job.kind != JobKind.AUDIO || job.requestedRevisionId == null) return null
        val revision = dao.revision(job.requestedRevisionId) ?: return null
        if (revision.episodeId != episodeId || episode.lockedRevisionId != revision.id || episode.lockedContentHash != revision.contentHash) return null
        val header = artifacts.resolveEpisodeFile("$episodeId/audio-stream/${job.id}/binding.json")
        if (!header.isFile || header.length() !in 1..8192) return null
        val value = org.json.JSONObject(header.readText())
        val pack = value.getString("packSha256")
        val frontend = if (value.isNull("frontendVersion")) null else value.getString("frontendVersion")
        if (Regex("[a-f0-9]{64}").matches(job.id)) {
            val plan = artifacts.resolveEpisodeFile("$episodeId/audio-plans/${job.id}.json")
            require(plan.isFile && artifacts.sha256(plan) == job.id)
            val planValue = org.json.JSONObject(plan.readText())
            require(planValue.getString("packSha256") == pack && planValue.getString("episodeId") == episodeId &&
                planValue.getString("revisionId") == revision.id && planValue.getString("revisionSha256") == revision.contentHash)
            val plannedFrontend = if (planValue.optString("kind") == dev.vibevoice.podcast.runtime.ProviderPublicationRecovery.KIND) null else planValue.optString("frontendVersion").takeIf { it.isNotBlank() }
            require(frontend == plannedFrontend)
        } else require(pack == dev.vibevoice.podcast.BuildConfig.SUPERTONIC_MANIFEST_SHA256 && frontend == null)
        val binding = dev.vibevoice.podcast.runtime.AudioAttemptBinding(episodeId, job.id, revision.id, revision.contentHash, pack, frontend)
        require(header.readBytes().contentEquals(dev.vibevoice.podcast.runtime.ProgressiveAudio.bindingBytes(binding)))
        return binding
    }

    fun observeAudioAvailability(episodeId: String, attemptId: String? = null): Flow<dev.vibevoice.podcast.runtime.AudioAvailability?> = kotlinx.coroutines.flow.flow {
        var prior: dev.vibevoice.podcast.runtime.AudioAvailability? = null
        while (kotlinx.coroutines.currentCoroutineContext().isActive) {
            val next = runCatching {
                val episode = requireEpisode(episodeId)
                if (attemptId == null && episode.phase == EpisodePhase.FROZEN_READY) return@runCatching null
                val binding = audioBinding(episodeId, attemptId) ?: return@runCatching prior?.takeIf { attemptId != null }?.copy(state = dev.vibevoice.podcast.runtime.AudioAvailabilityState.STALE)
                val job = requireJob(binding.jobId)
                val state = when {
                    dao.latestJob(episodeId)?.id != binding.jobId -> dev.vibevoice.podcast.runtime.AudioAvailabilityState.STALE
                    job.status == JobStatus.FAILED -> dev.vibevoice.podcast.runtime.AudioAvailabilityState.FAILED
                    job.status == JobStatus.COMPLETE && episode.phase == EpisodePhase.FROZEN_READY && episode.finalAudioPath?.startsWith("$episodeId/final/${job.id}/") == true -> dev.vibevoice.podcast.runtime.AudioAvailabilityState.COMPLETE
                    job.status in setOf(JobStatus.QUEUED, JobStatus.RUNNING) -> dev.vibevoice.podcast.runtime.AudioAvailabilityState.GENERATING
                    else -> dev.vibevoice.podcast.runtime.AudioAvailabilityState.STALE
                }
                streamReader(binding).read(state, if (state == dev.vibevoice.podcast.runtime.AudioAvailabilityState.COMPLETE) episode.finalAudioSha256 else null)
            }.getOrElse {
                if (it is kotlinx.coroutines.CancellationException) throw it
                prior?.copy(state = dev.vibevoice.podcast.runtime.AudioAvailabilityState.STALE, problem = "Audio availability could not be verified")
            }
            if (next != prior) { emit(next);prior = next }
            kotlinx.coroutines.delay(250)
        }
    }.flowOn(kotlinx.coroutines.Dispatchers.IO)

    /** Off-main, read-only transcript timing. Empty means chapter-only fallback; never fabricate word alignment. */
    suspend fun verifiedTranscriptPassages(episodeId: String): List<dev.vibevoice.podcast.runtime.TranscriptPassage> = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
        runCatching {
            val episode = requireEpisode(episodeId)
            if (episode.phase != EpisodePhase.FROZEN_READY) return@runCatching emptyList()
            val job = requireNotNull(dao.latestJob(episodeId));require(job.kind == JobKind.AUDIO && job.status == JobStatus.COMPLETE)
            val revision = requireNotNull(dao.revision(requireNotNull(episode.lockedRevisionId)))
            require(revision.episodeId == episodeId && revision.id == job.requestedRevisionId && revision.contentHash == episode.lockedContentHash)
            require(artifacts.sha256(artifacts.resolveEpisodeFile(revision.relativePath)) == revision.contentHash)
            val chapters = dao.chapters(revision.id)
            val binding = audioBinding(episodeId, job.id)
            if (binding != null) {
                val available = streamReader(binding).read(dev.vibevoice.podcast.runtime.AudioAvailabilityState.COMPLETE, episode.finalAudioSha256)
                if (available.state == dev.vibevoice.podcast.runtime.AudioAvailabilityState.COMPLETE && binding.frontendVersion == dev.vibevoice.podcast.runtime.ProviderTextFrontend.VERSION) {
                    return@runCatching available.chunks.filter { it.passageKind == dev.vibevoice.podcast.runtime.AudioPassageKind.PROVIDER_SEGMENT }.map { chunk ->
                        val chapter = chapters.single { it.stableChapterId == chunk.chapterId && it.position == chunk.chapterPosition }
                        val start = requireNotNull(chunk.sourceStartUtf16); val end = requireNotNull(chunk.sourceEndUtf16)
                        require(start >= 0 && end in (start + 1)..chapter.text.length)
                        dev.vibevoice.podcast.runtime.TranscriptPassage(chunk.chapterId, chunk.chapterPosition, chunk.segmentIndex, start, end, chunk.speechStartFrame, chunk.endFrame)
                    }
                }
            }
            // Legacy recovered provider audio (including2194) has an immutable recovery plan binding receipt hashes.
            if (!Regex("[a-f0-9]{64}").matches(job.id)) return@runCatching emptyList()
            fun plan(id: String): org.json.JSONObject {
                val file = artifacts.resolveEpisodeFile("$episodeId/audio-plans/$id.json")
                require(file.isFile && file.length() in 1..8_388_608 && artifacts.sha256(file) == id)
                return org.json.JSONObject(file.readText())
            }
            val recovery = plan(job.id)
            if (recovery.optString("kind") != dev.vibevoice.podcast.runtime.ProviderPublicationRecovery.KIND) return@runCatching emptyList()
            require(recovery.getString("episodeId") == episodeId && recovery.getString("revisionId") == revision.id && recovery.getString("revisionSha256") == revision.contentHash)
            val sourcePlan = plan(recovery.getString("sourceJobId"))
            require(sourcePlan.getString("episodeId") == episodeId && sourcePlan.getString("revisionId") == revision.id && sourcePlan.getString("revisionSha256") == revision.contentHash &&
                sourcePlan.getString("frontendVersion") == dev.vibevoice.podcast.runtime.ProviderTextFrontend.VERSION && sourcePlan.getString("packSha256") == recovery.getString("packSha256"))
            val completed = recovery.getJSONArray("chapters"); val planned = sourcePlan.getJSONArray("chapters"); val audio = dao.chapterAudio(episodeId)
            require(completed.length() == chapters.size && planned.length() == chapters.size && audio.size == chapters.size)
            val result = mutableListOf<dev.vibevoice.podcast.runtime.TranscriptPassage>()
            chapters.forEachIndexed { i, chapter ->
                val saved = completed.getJSONObject(i); val input = planned.getJSONObject(i); val recording = audio.single { it.position == chapter.position && it.stableChapterId == chapter.stableChapterId }
                require(recording.lockedRevisionId == revision.id && recording.sha256 == saved.getString("sha256"))
                require(artifacts.sha256(artifacts.resolveEpisodeFile(recording.relativePath)) == recording.sha256)
                val source = artifacts.resolveEpisodeFile(saved.getString("path")); val receipt = File(source.parentFile, "provider-receipt.json")
                require(receipt.isFile && artifacts.sha256(receipt) == saved.getString("receiptSha256"))
                val metadata = org.json.JSONObject(receipt.readText())
                val rawHash = java.security.MessageDigest.getInstance("SHA-256").digest(chapter.text.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
                require(input.getString("id") == chapter.stableChapterId && input.getString("textSha256") == rawHash && metadata.getString("rawChapterSha256") == rawHash &&
                    metadata.getString("waveSha256") == recording.sha256 && metadata.getString("packSha256") == sourcePlan.getString("packSha256") &&
                    metadata.getString("frontendVersion") == dev.vibevoice.podcast.runtime.ProviderTextFrontend.VERSION && metadata.getInt("gapFrames") == 13230)
                val spans = dev.vibevoice.podcast.runtime.ProviderTextFrontend.segmentSpans(chapter.text)
                val segments = metadata.getJSONArray("segments"); val plannedSegments = input.getJSONArray("segments")
                require(segments.length() == spans.size && plannedSegments.length() == spans.size)
                var cursor = recording.startFrame
                spans.forEachIndexed { n, span ->
                    val segment = segments.getJSONObject(n); val expected = plannedSegments.getJSONObject(n)
                    val hash = java.security.MessageDigest.getInstance("SHA-256").digest(span.raw.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
                    require(hash == expected.getString("rawSha256") && hash == segment.getString("rawSegmentSha256") && segment.getString("idsSha256") == expected.getString("idsSha256"))
                    val frames = segment.getLong("frameCount"); require(frames > 0 && frames == segment.getLong("nativeLatentLength") * 3072)
                    if (n > 0) cursor += 13230
                    result += dev.vibevoice.podcast.runtime.TranscriptPassage(chapter.stableChapterId, chapter.position, n, span.startUtf16, span.endUtf16, cursor, cursor + frames)
                    cursor += frames
                }
                require(cursor == recording.endFrame && cursor - recording.startFrame == recording.frameCount)
            }
            result
        }.getOrElse {
            if (it is kotlinx.coroutines.CancellationException) throw it
            emptyList()
        }
    }

    fun streamPlayback(binding: dev.vibevoice.podcast.runtime.AudioAttemptBinding): PlaybackStateEntity? =
        dev.vibevoice.podcast.runtime.StreamPlaybackStore.read(artifacts, binding)

    suspend fun saveStreamPlayback(binding: dev.vibevoice.podcast.runtime.AudioAttemptBinding, positionMs: Long, speed: Float, transcript: Boolean) = database.withTransaction {
        val actual = audioBinding(binding.episodeId, binding.jobId)
        if (actual != binding || dao.latestJob(binding.episodeId)?.id != binding.jobId) return@withTransaction
        val episode = requireEpisode(binding.episodeId)
        val available = streamReader(binding).read(dev.vibevoice.podcast.runtime.AudioAvailabilityState.GENERATING)
        require(available.canListen && speed.isFinite() && speed in 0.25f..4f)
        val position = positionMs.coerceIn(0, available.availableMs)
        dev.vibevoice.podcast.runtime.StreamPlaybackStore.save(artifacts, binding, position, speed, transcript, clock())
        if (episode.phase == EpisodePhase.FROZEN_READY && episode.finalAudioPath?.startsWith("${binding.episodeId}/final/${binding.jobId}/") == true) {
            dao.upsertPlayback(PlaybackStateEntity(binding.episodeId, position, speed, transcript, clock()))
        }
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

    private fun validateScript(title: String, chapters: List<ChapterDraft>) = validateCompleteScript(title, chapters)

    private suspend fun requireEpisode(id: String): EpisodeEntity {
        artifacts.episodeLeases.requireLive(id)
        return dao.episode(id) ?: error("Episode not found")
    }
    private suspend fun requireJob(id: String) = dao.job(id) ?: error("Generation job not found")
    private fun newJob(episodeId: String, kind: String, revisionId: String?, text: String): GenerationJobEntity {
        val now = clock()
        return GenerationJobEntity(UUID.randomUUID().toString(), episodeId, kind, JobStatus.QUEUED, revisionId, 0, 0, text, null, now, now)
    }

    private fun approximateSeconds(text: String): Int = (text.split(Regex("\\s+")).count { it.isNotBlank() } / 2.5).toInt().coerceAtLeast(1)

    companion object {
        private const val MAX_EPISODE_SOURCE_BYTES = 5L * 1024L * 1024L
    }
}

data class JobClaim(
    val job: GenerationJobEntity,
    val episode: EpisodeEntity,
    val message: AgentMessageEntity?,
)
