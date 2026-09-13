package dev.vibevoice.podcast.generation

import dev.vibevoice.podcast.BuildConfig
import dev.vibevoice.podcast.data.ArtifactStore
import dev.vibevoice.podcast.data.ChapterDraft
import dev.vibevoice.podcast.data.JobKind
import dev.vibevoice.podcast.data.PodcastRepository
import dev.vibevoice.podcast.model.ModelPackRequirement
import dev.vibevoice.podcast.model.ModelPackVerifier
import dev.vibevoice.podcast.model.ModelRoute
import dev.vibevoice.podcast.runtime.FrozenChapter
import dev.vibevoice.podcast.runtime.GemmaLiteRtGpuEngine
import dev.vibevoice.podcast.runtime.LlmEngine
import dev.vibevoice.podcast.runtime.SourcePreparer
import dev.vibevoice.podcast.runtime.ConfiguredTtsEngine
import dev.vibevoice.podcast.runtime.TtsEngine
import dev.vibevoice.podcast.runtime.WavAssembler
import org.json.JSONArray
import org.json.JSONObject
import dev.vibevoice.podcast.episode.EpisodeMetrics
import kotlinx.coroutines.*

class GenerationCoordinator(
    private val repository: PodcastRepository,
    private val artifacts: ArtifactStore,
    private val verifier: ModelPackVerifier = ModelPackVerifier(),
    private val llmFactory: () -> LlmEngine = { GemmaLiteRtGpuEngine() },
    private val ttsFactory: () -> TtsEngine = ::ConfiguredTtsEngine,
    private val testPackProvider: ((ModelRoute) -> dev.vibevoice.podcast.model.VerifiedModelPack)? = null,
    private val audioGuardFactory: ((dev.vibevoice.podcast.runtime.AudioAttemptBinding) -> dev.vibevoice.podcast.runtime.AudioExecutionGuard?)? = null,
) {
    suspend fun generateScript(episodeId: String, jobId: String, progress: suspend (String) -> Unit): String? =
        managedJob(episodeId, jobId, JobKind.SCRIPT) { generateScriptImpl(episodeId, jobId, progress) }

    private suspend fun generateScriptImpl(episodeId: String, jobId: String, progress: suspend (String) -> Unit): String? {
        repository.claimJob(episodeId, jobId, JobKind.SCRIPT, "Verifying Gemma 4 E2B")
        val pack = loadPack(ModelRoute.GEMMA_4_E2B_LITERT_GPU)
        val episode = repository.episode(episodeId)
        val sources = repository.sourceMaterials(episodeId)
        val engine = llmFactory()
        try {
            progress("Loading Gemma 4 E2B on GPU")
            stage("setup") { engine.load(pack) }
            repository.recordVerifiedPack(pack, requireNotNull(engine.provenance))
            val preparedSources = SourcePreparer().prepare(sources, engine, progress)
            progress("Creating the episode outline")
            val outline = engine.createOutline(preparedSources, episode.instructions)
            require(outline.title.isNotBlank() && outline.chapters.size in 1..20) { "Gemma returned an invalid outline" }
            require(outline.chapters.map { it.id }.toSet().size == outline.chapters.size) { "Gemma returned duplicate chapter IDs" }
            val chapters = outline.chapters.mapIndexed { index, planned ->
                repository.updateJobProgress(episodeId, jobId, JobKind.SCRIPT, index + 1, outline.chapters.size, "Writing ${planned.title}")
                progress("Writing chapter ${index + 1} of ${outline.chapters.size}")
                val generated = engine.createChapter(outline, planned, preparedSources, episode.instructions)
                require(generated.id == planned.id) { "Gemma returned the wrong complete chapter" }
                ChapterDraft(generated.id, generated.title, generated.text)
            }
            repository.commitGeneratedScript(episodeId, jobId, outline.title, chapters)
        } finally {
            stage("teardown") { engine.close() }
        }
        val next = repository.latestJob(episodeId)
        return next?.takeIf { it.kind == JobKind.AUDIO }?.id
    }

    suspend fun editDraft(episodeId: String, jobId: String, progress: suspend (String) -> Unit) =
        managedJob(episodeId, jobId, JobKind.AGENT_EDIT) { editDraftImpl(episodeId, jobId, progress) }

    private suspend fun editDraftImpl(episodeId: String, jobId: String, progress: suspend (String) -> Unit) {
        val claim = repository.claimJob(episodeId, jobId, JobKind.AGENT_EDIT, "Verifying Gemma 4 E2B")
        val pack = loadPack(ModelRoute.GEMMA_4_E2B_LITERT_GPU)
        val (revision, chapters) = repository.activeRevision(episodeId)
        val userRequest = requireNotNull(claim.message) { "Agent request is missing" }
        require(userRequest.baseRevisionId == revision.id) { "Agent request is stale" }
        val engine = llmFactory()
        try {
            progress("Loading the script editor")
            stage("setup") { engine.load(pack) }
            repository.recordVerifiedPack(pack, requireNotNull(engine.provenance))
            val request = agentEditRequest(revision, chapters, userRequest)
            val result = parseAgentRevision(engine.editScript(request))
            repository.applyAgentRevision(episodeId, jobId, revision.id, result.title, result.chapters, result.summary)
        } finally {
            stage("teardown") { engine.close() }
        }
    }

    suspend fun generateAudio(episodeId: String, jobId: String, progress: suspend (String) -> Unit) =
        managedJob(episodeId, jobId, JobKind.AUDIO) { generateAudioImpl(episodeId, jobId, progress) }

    private suspend fun generateAudioImpl(episodeId: String, jobId: String, progress: suspend (String) -> Unit) {
        val (episode, chapters) = repository.lockedChapterData(episodeId)
        repository.claimJob(episodeId, jobId, JobKind.AUDIO, "Verifying Supertonic", chapters.size)
        val pack = loadPack(ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP)
        val recovery = repository.verifyAudioPlan(episodeId, jobId, pack)
        val stream = dev.vibevoice.podcast.runtime.ProgressiveAudio.create(artifacts,
            dev.vibevoice.podcast.runtime.AudioAttemptBinding(episodeId, jobId, requireNotNull(episode.lockedRevisionId),
                requireNotNull(episode.lockedContentHash), pack.manifestSha256,
                if (recovery == null) (pack.contract as? dev.vibevoice.podcast.model.SupertonicModelContract)?.providerPipeline?.frontendVersion else null))
        repository.resetChapterAudio(episodeId)
        if (recovery != null) {
            currentCoroutineContext()[EpisodeMetrics]?.recovered()
            require(recovery.size == chapters.size)
            val rendered = mutableListOf<WavAssembler.Input>()
            var cursor = 0L
            chapters.forEachIndexed { index, chapter ->
                val saved = recovery[index]
                repository.updateJobProgress(episodeId, jobId, JobKind.AUDIO, index + 1, chapters.size, "Publishing saved chapter ${index + 1}; no inference")
                progress("Publishing completed audio without running the voice model")
                val output = artifacts.chapterWav(episodeId, chapter.position)
                dev.vibevoice.podcast.runtime.ProviderPublication.publish(saved.source, output, saved.metadata.sha256)
                val chunk = stream.append(index, chapter.stableChapterId, 0, output, saved.metadata)
                currentCoroutineContext()[EpisodeMetrics]?.audioAvailable(chunk.endFrame)
                repository.commitChapterAudio(episodeId, jobId, chapter, saved.metadata, output, cursor)
                rendered += WavAssembler.Input(chapter.stableChapterId, chapter.title, output)
                cursor += saved.metadata.frameCount + if (index < chapters.lastIndex) 44_100L * 700L / 1_000L else 0
            }
            stage("finalization") {
                val final = WavAssembler(artifacts).assemble(episodeId, jobId, rendered)
                stream.finish(final.totalFrames, final.audioSha256)
                repository.completeAudio(episodeId, jobId, final)
            }
            return // Crucially before constructing/loading any TtsEngine.
        }
        val guard=audioGuardFactory?.invoke(stream.binding)
        var engine: TtsEngine?=null
        val rendered = mutableListOf<WavAssembler.Input>()
        var cursorFrame = 0L
        val pauseFrames = 44_100L * 700L / 1_000L
        try {
            guard?.start();guard?.check()
            engine=ttsFactory()
            progress("Loading four Supertonic contexts on HTP")
            stage("setup") { engine.load(pack, "M1/SID5") }
            guard?.check()
            repository.recordVerifiedPack(pack, requireNotNull(engine.provenance))
            chapters.forEachIndexed { index, chapter ->
                repository.updateJobProgress(episodeId, jobId, JobKind.AUDIO, index + 1, chapters.size, "Creating ${chapter.title}")
                progress("Creating chapter ${index + 1} of ${chapters.size}")
                val output = artifacts.chapterWav(episodeId, chapter.position)
                var streamedSegments = 0
                val spans = if (stream.binding.frontendVersion != null) dev.vibevoice.podcast.runtime.ProviderTextFrontend.segmentSpans(chapter.text) else emptyList()
                guard?.check()
                val metadata = stage("render") { engine.renderChapter(FrozenChapter(chapter.stableChapterId, chapter.title, chapter.text), output) { segment ->
                    guard?.check()
                    segment.completedFile?.let { file ->
                        require(segment.completed == streamedSegments + 1 && segment.completedMetadata != null)
                        val span = spans.getOrNull(streamedSegments)
                        if (stream.binding.frontendVersion != null) require(span != null && segment.total == spans.size)
                        val chunk = stream.append(index, chapter.stableChapterId, streamedSegments, file, segment.completedMetadata,
                            if (span != null) dev.vibevoice.podcast.runtime.AudioPassageKind.PROVIDER_SEGMENT else dev.vibevoice.podcast.runtime.AudioPassageKind.COMPLETE_CHAPTER,
                            span?.startUtf16, span?.endUtf16)
                        currentCoroutineContext()[EpisodeMetrics]?.audioAvailable(chunk.endFrame)
                        streamedSegments++
                    }
                    val status = "Chapter ${index + 1} of ${chapters.size}: speech segments ${segment.completed} of ${segment.total} ready"
                    repository.updateJobProgress(episodeId, jobId, JobKind.AUDIO, index + 1, chapters.size, status)
                    progress(status)
                } }
                if (stream.binding.frontendVersion != null) require(streamedSegments == spans.size && streamedSegments > 0)
                if (streamedSegments == 0) {
                    val chunk = stream.append(index, chapter.stableChapterId, 0, output, metadata)
                    currentCoroutineContext()[EpisodeMetrics]?.audioAvailable(chunk.endFrame)
                }
                repository.commitChapterAudio(episodeId, jobId, chapter, metadata, output, cursorFrame)
                rendered += WavAssembler.Input(chapter.stableChapterId, chapter.title, output)
                cursorFrame += metadata.frameCount + if (index < chapters.lastIndex) pauseFrames else 0L
            }
        } finally {
            stage("teardown") { dev.vibevoice.podcast.runtime.closeGuardedAudio(guard) { engine?.close() } }
        }
        repository.updateJobProgress(episodeId, jobId, JobKind.AUDIO, chapters.size + 1, chapters.size, "Assembling episode")
        progress("Assembling ${episode.title}")
        stage("finalization") {
            val final = WavAssembler(artifacts).assemble(episodeId, jobId, rendered)
            stream.finish(final.totalFrames, final.audioSha256)
            repository.completeAudio(episodeId, jobId, final)
        }
    }

    private suspend fun <T> stage(name: String, block: suspend () -> T): T {
        val metrics = currentCoroutineContext()[EpisodeMetrics]
        return if (metrics != null) metrics.measure(name, block) else block()
    }

    private suspend fun <T> managedJob(episodeId: String, jobId: String, kind: String, block: suspend () -> T): T {
        val enteredNs = System.nanoTime()
        repository.acquireEpisodeFiles(episodeId).use {
            repository.episode(episodeId)
            val pending = repository.latestJob(episodeId)
            require(pending?.id == jobId && pending.kind == kind && pending.status == dev.vibevoice.podcast.data.JobStatus.QUEUED) { "Job is not the current unclaimed attempt" }
            val metrics = EpisodeMetrics(artifacts, episodeId, jobId, kind, startNs = enteredNs)
            var failure: Throwable? = null
            try {
                return coroutineScope {
                    val worker = async { withContext(metrics) { block() } }
                    val deletion = launch(Dispatchers.IO) {
                        while (worker.isActive) {
                            if (repository.deletionRequested(episodeId)) {
                                worker.cancel(CancellationException("Episode deleted")); break
                            }
                            delay(250)
                        }
                    }
                    try { worker.await() } finally { deletion.cancel() }
                }
            } catch (error: Throwable) { failure = error; throw error }
            finally { metrics.finish(failure) }
            // coroutineScope waits for blocked JNI/native teardown, even after cancellation.
            // Only then does use release the cross-process file lease. Never kill the package.
        }
    }

    private fun loadPack(route: ModelRoute): dev.vibevoice.podcast.model.VerifiedModelPack {
        testPackProvider?.let { return it(route) }
        val (directory, id, hash) = when (route) {
            ModelRoute.GEMMA_4_E2B_LITERT_GPU -> Triple("gemma-4-e2b", "gemma-4-e2b", BuildConfig.GEMMA_MANIFEST_SHA256)
            ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP -> Triple(BuildConfig.SUPERTONIC_PACK_ID, BuildConfig.SUPERTONIC_PACK_ID, BuildConfig.SUPERTONIC_MANIFEST_SHA256)
        }
        return verifier.verify(artifacts.modelPackRoot(directory), ModelPackRequirement(route, id, hash))
    }

}
