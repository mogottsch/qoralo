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

class GenerationCoordinator(
    private val repository: PodcastRepository,
    private val artifacts: ArtifactStore,
    private val verifier: ModelPackVerifier = ModelPackVerifier(),
    private val llmFactory: () -> LlmEngine = { GemmaLiteRtGpuEngine() },
    private val ttsFactory: () -> TtsEngine = ::ConfiguredTtsEngine,
    private val testPackProvider: ((ModelRoute) -> dev.vibevoice.podcast.model.VerifiedModelPack)? = null,
) {
    suspend fun generateScript(episodeId: String, jobId: String, progress: suspend (String) -> Unit): String? {
        repository.claimJob(episodeId, jobId, JobKind.SCRIPT, "Verifying Gemma 4 E2B")
        val pack = loadPack(ModelRoute.GEMMA_4_E2B_LITERT_GPU)
        val episode = repository.episode(episodeId)
        val sources = repository.sourceMaterials(episodeId)
        val engine = llmFactory()
        try {
            progress("Loading Gemma 4 E2B on GPU")
            engine.load(pack)
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
            engine.close()
        }
        val next = repository.latestJob(episodeId)
        return next?.takeIf { it.kind == JobKind.AUDIO }?.id
    }

    suspend fun editDraft(episodeId: String, jobId: String, progress: suspend (String) -> Unit) {
        val claim = repository.claimJob(episodeId, jobId, JobKind.AGENT_EDIT, "Verifying Gemma 4 E2B")
        val pack = loadPack(ModelRoute.GEMMA_4_E2B_LITERT_GPU)
        val (revision, chapters) = repository.activeRevision(episodeId)
        val userRequest = requireNotNull(claim.message) { "Agent request is missing" }
        require(userRequest.baseRevisionId == revision.id) { "Agent request is stale" }
        val engine = llmFactory()
        try {
            progress("Loading the script editor")
            engine.load(pack)
            repository.recordVerifiedPack(pack, requireNotNull(engine.provenance))
            val request = agentEditRequest(revision, chapters, userRequest)
            val result = parseAgentRevision(engine.editScript(request))
            repository.applyAgentRevision(episodeId, jobId, revision.id, result.title, result.chapters, result.summary)
        } finally {
            engine.close()
        }
    }

    suspend fun generateAudio(episodeId: String, jobId: String, progress: suspend (String) -> Unit) {
        val (episode, chapters) = repository.lockedChapterData(episodeId)
        repository.claimJob(episodeId, jobId, JobKind.AUDIO, "Verifying Supertonic", chapters.size)
        val pack = loadPack(ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP)
        repository.verifyAudioPlan(episodeId, jobId, pack)
        repository.resetChapterAudio(episodeId)
        val engine = ttsFactory()
        val rendered = mutableListOf<WavAssembler.Input>()
        var cursorFrame = 0L
        val pauseFrames = 44_100L * 700L / 1_000L
        try {
            progress("Loading four Supertonic contexts on HTP")
            engine.load(pack, "M1/SID5")
            repository.recordVerifiedPack(pack, requireNotNull(engine.provenance))
            chapters.forEachIndexed { index, chapter ->
                repository.updateJobProgress(episodeId, jobId, JobKind.AUDIO, index + 1, chapters.size, "Creating ${chapter.title}")
                progress("Creating chapter ${index + 1} of ${chapters.size}")
                val output = artifacts.chapterWav(episodeId, chapter.position)
                val metadata = engine.renderChapter(FrozenChapter(chapter.stableChapterId, chapter.title, chapter.text), output) { segment ->
                    val status = "Chapter ${index + 1} of ${chapters.size}: speech segments ${segment.completed} of ${segment.total} ready"
                    repository.updateJobProgress(episodeId, jobId, JobKind.AUDIO, index + 1, chapters.size, status)
                    progress(status)
                }
                repository.commitChapterAudio(episodeId, jobId, chapter, metadata, output, cursorFrame)
                rendered += WavAssembler.Input(chapter.stableChapterId, chapter.title, output)
                cursorFrame += metadata.frameCount + if (index < chapters.lastIndex) pauseFrames else 0L
            }
        } finally {
            engine.close()
        }
        repository.updateJobProgress(episodeId, jobId, JobKind.AUDIO, chapters.size + 1, chapters.size, "Assembling episode")
        progress("Assembling ${episode.title}")
        val final = WavAssembler(artifacts).assemble(episodeId, jobId, rendered)
        repository.completeAudio(episodeId, jobId, final)
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
