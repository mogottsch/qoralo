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
import dev.vibevoice.podcast.runtime.SupertonicQnnHtpEngine
import dev.vibevoice.podcast.runtime.TtsEngine
import dev.vibevoice.podcast.runtime.WavAssembler
import org.json.JSONArray
import org.json.JSONObject

class GenerationCoordinator(
    private val repository: PodcastRepository,
    private val artifacts: ArtifactStore,
    private val verifier: ModelPackVerifier = ModelPackVerifier(),
    private val llmFactory: () -> LlmEngine = ::GemmaLiteRtGpuEngine,
    private val ttsFactory: () -> TtsEngine = ::SupertonicQnnHtpEngine,
) {
    suspend fun generateScript(episodeId: String, jobId: String, progress: suspend (String) -> Unit): String? {
        repository.beginJob(jobId, "Verifying Gemma 4 E2B")
        val pack = verifier.verify(
            artifacts.modelPackRoot("gemma-4-e2b"),
            ModelPackRequirement(ModelRoute.GEMMA_4_E2B_LITERT_GPU, "gemma-4-e2b", BuildConfig.GEMMA_MANIFEST_SHA256),
        )
        val episode = repository.episode(episodeId)
        val sources = repository.sourceMaterials(episodeId)
        val engine = llmFactory()
        try {
            progress("Loading Gemma 4 E2B on GPU")
            engine.load(pack)
            repository.recordVerifiedPack(pack, requireNotNull(engine.provenance))
            progress("Creating the episode outline")
            val outline = engine.createOutline(sources, episode.instructions)
            require(outline.title.isNotBlank() && outline.chapters.size in 1..20) { "Gemma returned an invalid outline" }
            require(outline.chapters.map { it.id }.toSet().size == outline.chapters.size) { "Gemma returned duplicate chapter IDs" }
            val chapters = outline.chapters.mapIndexed { index, planned ->
                repository.updateJobProgress(jobId, index + 1, outline.chapters.size, "Writing ${planned.title}")
                progress("Writing chapter ${index + 1} of ${outline.chapters.size}")
                val generated = engine.createChapter(outline, planned, sources, episode.instructions)
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
        repository.beginJob(jobId, "Verifying Gemma 4 E2B")
        val pack = verifier.verify(
            artifacts.modelPackRoot("gemma-4-e2b"),
            ModelPackRequirement(ModelRoute.GEMMA_4_E2B_LITERT_GPU, "gemma-4-e2b", BuildConfig.GEMMA_MANIFEST_SHA256),
        )
        val (revision, chapters) = repository.activeRevision(episodeId)
        val userRequest = repository.latestUserMessage(episodeId)
        require(userRequest.baseRevisionId == revision.id) { "Agent request is stale" }
        val engine = llmFactory()
        try {
            progress("Loading the script editor")
            engine.load(pack)
            repository.recordVerifiedPack(pack, requireNotNull(engine.provenance))
            val request = JSONObject()
                .put("schemaVersion", 1)
                .put("baseRevisionId", revision.id)
                .put("instruction", userRequest.text)
                .put("allowedOperations", JSONArray(listOf("rewrite", "shorten", "remove", "split", "combine", "rename")))
                .put("title", revision.title)
                .put("chapters", JSONArray(chapters.map {
                    JSONObject().put("id", it.stableChapterId).put("title", it.title).put("text", it.text)
                }))
            val result = parseAgentResult(engine.editScript(request.toString()))
            repository.applyAgentRevision(episodeId, jobId, revision.id, result.title, result.chapters, result.summary)
        } finally {
            engine.close()
        }
    }

    suspend fun generateAudio(episodeId: String, jobId: String, progress: suspend (String) -> Unit) {
        val (episode, chapters) = repository.lockedChapterData(episodeId)
        repository.beginJob(jobId, "Verifying Supertonic", chapters.size)
        val pack = verifier.verify(
            artifacts.modelPackRoot("supertonic-3"),
            ModelPackRequirement(ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP, "supertonic-3", BuildConfig.SUPERTONIC_MANIFEST_SHA256),
        )
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
                repository.updateJobProgress(jobId, index + 1, chapters.size, "Creating ${chapter.title}")
                progress("Creating chapter ${index + 1} of ${chapters.size}")
                val output = artifacts.chapterWav(episodeId, chapter.position)
                val metadata = engine.renderChapter(FrozenChapter(chapter.stableChapterId, chapter.title, chapter.text), output)
                repository.commitChapterAudio(episodeId, chapter, metadata, output, cursorFrame)
                rendered += WavAssembler.Input(chapter.stableChapterId, chapter.title, output)
                cursorFrame += metadata.frameCount + if (index < chapters.lastIndex) pauseFrames else 0L
            }
        } finally {
            engine.close()
        }
        progress("Assembling ${episode.title}")
        val final = WavAssembler(artifacts).assemble(episodeId, rendered)
        repository.completeAudio(jobId, final.file, final.durationMs)
    }

    private fun parseAgentResult(raw: String): AgentResult {
        val json = JSONObject(raw)
        val keys = json.keys().asSequence().toSet()
        require(keys == setOf("schemaVersion", "title", "chapters", "summary")) { "Agent response schema is invalid" }
        require(json.getInt("schemaVersion") == 1) { "Agent response version is unsupported" }
        val array = json.getJSONArray("chapters")
        val chapters = List(array.length()) { index ->
            val chapter = array.getJSONObject(index)
            require(chapter.keys().asSequence().toSet() == setOf("id", "title", "text")) { "Agent chapter schema is invalid" }
            ChapterDraft(chapter.getString("id"), chapter.getString("title"), chapter.getString("text"))
        }
        return AgentResult(json.getString("title"), chapters, json.getString("summary"))
    }

    private data class AgentResult(val title: String, val chapters: List<ChapterDraft>, val summary: String)
}
