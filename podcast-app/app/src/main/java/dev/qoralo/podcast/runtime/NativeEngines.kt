package dev.qoralo.podcast.runtime

import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.Contents
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Engine as LiteRtEngine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.SamplerConfig
import com.google.ai.edge.litertlm.ResponseFormat
import com.google.ai.edge.litertlm.ThinkingConfig
import dev.qoralo.podcast.model.GemmaModelContract
import dev.qoralo.podcast.model.ModelFileRole
import dev.qoralo.podcast.model.ModelRoute
import dev.qoralo.podcast.model.SupertonicModelContract
import dev.qoralo.podcast.model.VerifiedModelPack
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import dev.qoralo.podcast.episode.ChapterRetryNotice
import dev.qoralo.podcast.episode.EpisodeMetrics
import dev.qoralo.podcast.episode.runtimeRequestMetrics
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/** Official LiteRT-LM 0.16.1 Android API; only Backend.GPU is ever configured. */
class GemmaLiteRtGpuEngine(private val observer: GemmaRequestObserver? = null) : LlmEngine {
    private var engine: LiteRtEngine? = null
    override var provenance: RuntimeProvenance? = null
        private set

    override suspend fun load(pack: VerifiedModelPack) = withContext(Dispatchers.IO) {
        requireRoute(pack, ModelRoute.GEMMA_4_E2B_LITERT_GPU)
        require(engine == null) { "Gemma engine is already loaded" }
        val contract = pack.contract as? GemmaModelContract ?: throw InferenceRouteException("Gemma pack contract type mismatch")
        require(contract.contextTokens == 8_192 && contract.runtimeVersion == "0.16.1") { "Gemma runtime contract mismatch" }
        val model = pack.files.single { it.role == ModelFileRole.GEMMA_MODEL }.file
        val cache = File(pack.root.parentFile?.parentFile, "runtime-cache/gemma-4-e2b-gpu").apply { mkdirs() }
        try {
            val created = LiteRtEngine(
                EngineConfig(
                    modelPath = model.absolutePath,
                    backend = Backend.GPU(),
                    maxNumTokens = 8_192,
                    cacheDir = cache.absolutePath,
                ),
            )
            created.initialize()
            engine = created
            provenance = RuntimeProvenance(
                runtimeApiVersion = 1,
                model = "GEMMA_4_E2B",
                backend = "LITERT_GPU",
                runtimeVersion = "LiteRT-LM 0.16.1",
                cpuFallbackEnabled = false,
                readyComponents = setOf("model", "tokenizer", "gpu_delegate"),
            )
            RuntimeDiagnostics.verifiedGemma(pack)
        } catch (cancelled: CancellationException) { close(); throw cancelled }
        catch (error: Throwable) {
            close()
            throw InferenceRouteException("Gemma 4 E2B LiteRT GPU failed to initialize", error)
        }
    }

    override suspend fun createSourceNotes(source: SourceMaterial, chunkIndex: Int, chunkCount: Int): SourceMaterial {
        require(source.text.length <= SourcePreparer.MAX_REQUEST_CHARS) { "Source-notes request exceeds the Gemma context budget" }
        val request = JSONObject().put("schemaVersion", 1).put("sourceId", source.id).put("title", source.title)
            .put("chunkIndex", chunkIndex).put("chunkCount", chunkCount).put("text", source.text)
        val json = JSONObject(generate("source_notes", request.toString()))
        val notes = validatedSourceNotes(json.getString("notes"))
        return SourceMaterial("${source.id}-notes-$chunkIndex", source.title, notes)
    }

    override suspend fun createOutline(sources: List<SourceMaterial>, instructions: String): EpisodeOutline {
        val request = requestJson(sources, instructions).toString()
        require(request.length <= MAX_GENERATION_REQUEST_CHARS) { "Outline request exceeds the Gemma context budget" }
        val json = JSONObject(generate("outline", request))
        val chapters = json.getJSONArray("chapters")
        return EpisodeOutline(json.getString("title"), List(chapters.length()) { index ->
            val item = chapters.getJSONObject(index)
            OutlineChapter(item.getString("id"), item.getString("title"), item.getString("brief"))
        })
    }

    override suspend fun createChapter(
        outline: EpisodeOutline,
        chapter: OutlineChapter,
        sources: List<SourceMaterial>,
        instructions: String,
        preceding: List<ChapterRecap>,
    ): FrozenChapter {
        val request = requestJson(sources, instructions)
            .put("outline", JSONObject().put("title", outline.title).put("chapters", JSONArray(outline.chapters.map {
                JSONObject().put("id", it.id).put("title", it.title).put("brief", it.brief)
            })))
            .put("requestedChapterId", chapter.id)
            .put("requestedChapter", JSONObject().put("id", chapter.id).put("title", chapter.title).put("brief", chapter.brief))
            .put("alreadySpokenChapters", JSONArray(preceding.map {
                JSONObject().put("title", it.title).apply { if (it.ending.isNotBlank()) put("ending", it.ending) }
            }))
        val serialized = request.toString()
        require(serialized.length <= MAX_GENERATION_REQUEST_CHARS) { "Chapter request exceeds the Gemma context budget" }
        val schema = chapterResponseSchema(chapter)
        var attempt = 1
        var constrained = true
        while (true) {
            try {
                val json = JSONObject(generate("chapter", serialized,
                    singleChapterInstruction(chapter, chapterWordCeiling(attempt), preceding), schema.takeIf { constrained }))
                return FrozenChapter(json.getString("id"), json.getString("title"), json.getString("text"))
            } catch (error: GemmaRequestException) {
                // A grammar the runtime refuses fails the request at SEND before any token is produced. That
                // must not cost the episode: drop the constraint once and continue with the plain request,
                // which is exactly the behaviour that existed before constrained decoding.
                if (constrained && error.failurePhase == GemmaFailurePhase.SEND) {
                    constrained = false
                    currentCoroutineContext().ensureActive()
                    continue
                }
                // Constrained decoding makes a malformed envelope unreachable, so an unparsed response means the
                // model never finished inside the output ceiling. Only that case earns another, shorter attempt.
                if (!shouldRetryChapter(error, attempt)) throw error
                currentCoroutineContext().ensureActive()
                attempt++
                currentCoroutineContext()[ChapterRetryNotice]?.retrying(attempt, CHAPTER_ATTEMPTS)
            }
        }
    }

    override suspend fun editScript(requestJson: String): String {
        require(requestJson.length <= MAX_GENERATION_REQUEST_CHARS) { "Agent edit request exceeds the Gemma context budget" }
        return generate("edit", requestJson)
    }

    @OptIn(com.google.ai.edge.litertlm.ExperimentalApi::class)
    private suspend fun generate(mode: String, request: String, specificInstruction: String? = null,
        schemaOverride: String? = null): String = withContext(Dispatchers.Default) {
        currentCoroutineContext().ensureActive()
        val metrics = currentCoroutineContext()[EpisodeMetrics]
        val started = System.nanoTime()
        fun elapsed(ns: Long) = (System.nanoTime() - ns).coerceAtLeast(0) / 1_000_000.0
        var setupMs: Double? = null
        var sendMs: Double? = null
        var counters: com.google.ai.edge.litertlm.BenchmarkInfo? = null
        var outcome = "failed"
        val loaded = engine ?: error("Gemma engine is not loaded")
        val maxOutput = RuntimeDiagnostics.outputLimit(mode, when (mode) {
            "source_notes", "outline" -> 1_200
            "chapter", "edit" -> 4_096
            else -> error("Unsupported Gemma request mode")
        })
        val instruction = specificInstruction ?: systemInstruction(mode)
        val responseSchema = responseSchemaForMode(mode) ?: schemaOverride
        val responseFormat = responseSchema?.let(ResponseFormat::json)
        RuntimeDiagnostics.beforeRequest(mode, request, instruction, maxOutput, responseSchema)
        runCatching { observer?.beforeRequest(mode, request, instruction, maxOutput, responseSchema) }
        try {
        executeGemmaRequest(
            mode = mode,
            create = {
                val begin = System.nanoTime()
                try { loaded.createConversation(ConversationConfig(
                    systemInstruction = Contents.of(instruction),
                    samplerConfig = SamplerConfig(topK = 1, topP = 1.0, temperature = 1.0),
                    channels = emptyList(),
                    maxOutputToken = maxOutput,
                    thinkingConfig = ThinkingConfig(enableThinking = false),
                    enableResponseFormat = responseFormat != null,
                )) } finally { setupMs = elapsed(begin) }
            },
            send = { conversation ->
                val begin = System.nanoTime()
                try {
                    val raw = RuntimeDiagnostics.send(conversation, request, responseFormat)
                    runCatching { observer?.responseReturned(raw) }
                    runCatching { observer?.conversationReturned(conversation) }
                    raw
                } finally {
                    sendMs = elapsed(begin)
                    if (metrics != null) counters = runCatching { conversation.getBenchmarkInfo() }.getOrNull()
                }
            },
            returned = { raw -> runCatching { RuntimeDiagnostics.responseReturned(raw) }; Unit },
            failed = { error ->
                runCatching { RuntimeDiagnostics.requestFailed(error) }
                runCatching { observer?.requestFailed(error) }
            },
        ).also { currentCoroutineContext().ensureActive(); outcome = "complete" }
        } catch (cancelled: CancellationException) { outcome = "cancelled"; throw cancelled }
        finally {
            metrics?.request(runtimeRequestMetrics(mode, outcome, elapsed(started), setupMs, sendMs,
                counters?.lastPrefillTokenCount, counters?.lastDecodeTokenCount,
                counters?.lastPrefillTokensPerSecond, counters?.lastDecodeTokensPerSecond,
                counters?.initTimeInSecond, counters?.timeToFirstTokenInSecond, maxOutput))
        }
    }

    override fun close() {
        engine?.let { runCatching { it.close() } }
        engine = null
        provenance = null
    }

    private fun requestJson(sources: List<SourceMaterial>, instructions: String) = JSONObject()
        .put("schemaVersion", 1).put("instructions", instructions)
        .put("sources", JSONArray(sources.map { JSONObject().put("id", it.id).put("title", it.title).put("text", it.text) }))

    private fun systemInstruction(mode: String): String = when (mode) {
        "source_notes" -> sourceNotesInstruction()
        "outline" -> "Design a coherent spoken podcast outline from the supplied notes and instructions. Follow the requested chapter count and IDs. Each brief is a short content plan, not a miniature transcript. Give every chapter its own material: name in each brief the specific facts, figures, names or events from the notes that this chapter alone will cover, and never assign the same fact to two chapters. Drop material the instructions call uninteresting rather than spreading it across chapters. Return only JSON: {\"title\":\"...\",\"chapters\":[{\"id\":\"chapter-1\",\"title\":\"...\",\"brief\":\"...\"}]}."
        "chapter" -> error("A chapter request requires its concrete single-chapter instruction")
        "edit" -> SCRIPT_EDIT_INSTRUCTION
        else -> error("Unsupported Gemma request mode")
    }

    private companion object {
        const val MAX_GENERATION_REQUEST_CHARS = 20_000
    }
}

/** APK-supplied JNI/runtime executes QNN/HTP; the verified Supertonic pack contains data only. */
class SupertonicQnnHtpEngine : TtsEngine {
    private var handle = 0L
    override var provenance: RuntimeProvenance? = null
        private set

    override suspend fun load(pack: VerifiedModelPack, voiceId: String) = withContext(Dispatchers.IO) {
        requireRoute(pack, ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP)
        try {
            NativeAppRuntime.ensureLoaded()
            handle = SupertonicNative.create(pack.root.absolutePath, voiceId, RuntimeDiagnostics.qnnProfileDirectory())
            if (handle == 0L) throw InferenceRouteException("Supertonic QNN initialization returned no engine")
            val reported = validateProvenance(
                SupertonicNative.provenance(handle),
                expectedModel = "SUPERTONIC_3_EXTERNAL_CONTEXT",
                expectedBackend = "QNN_HTP",
                requiredComponents = setOf("duration_context", "text_context", "vector_context", "vocoder_context", "htp"),
            )
            val contract = pack.contract as? SupertonicModelContract
                ?: throw InferenceRouteException("Supertonic pack contract type mismatch")
            provenance = requireMatchingSupertonicContract(contract, reported)
        } catch (error: Throwable) {
            close()
            throw InferenceRouteException("Supertonic external-context QNN/HTP failed to initialize", error)
        }
    }

    override suspend fun renderChapter(chapter: FrozenChapter, output: File, onProgress: suspend (TtsSegmentProgress) -> Unit): AudioMetadata = withContext(Dispatchers.IO) {
        check(handle != 0L) { "Supertonic engine is not loaded" }
        output.parentFile?.mkdirs()
        val temporary = File(output.parentFile, ".${output.name}.tmp")
        temporary.delete()
        try {
            val normalizedText = SupertonicTextNormalizer.normalize(chapter.text)
            if (!SupertonicNative.renderCompleteChapter(handle, chapter.id, normalizedText, temporary.absolutePath)) {
                throw InferenceRouteException("Supertonic rejected the complete chapter")
            }
            if (!temporary.isFile || temporary.length() == 0L) throw InferenceRouteException("Supertonic emitted no chapter WAV")
            val metadata = WavInspector.inspectSupertonicOutput(temporary)
            AtomicArtifactCommit.commit(temporary, output)
            metadata
        } catch (error: Throwable) {
            temporary.delete()
            throw InferenceRouteException("Complete-chapter Supertonic QNN/HTP synthesis failed; no splitting or fallback was attempted", error)
        }
    }

    override fun close() {
        if (handle != 0L) runCatching { SupertonicNative.destroy(handle) }
        handle = 0L
        provenance = null
    }
}

internal fun validateProvenance(
    raw: String?,
    expectedModel: String,
    expectedBackend: String,
    requiredComponents: Set<String>,
): RuntimeProvenance {
    val json = try { JSONObject(raw ?: error("Native runtime returned no provenance")) } catch (error: Throwable) {
        throw InferenceRouteException("Native runtime provenance is invalid", error)
    }
    val components = json.getJSONArray("readyComponents").let { array ->
        (0 until array.length()).map(array::getString).toSet()
    }
    val value = RuntimeProvenance(
        runtimeApiVersion = json.getInt("runtimeApiVersion"),
        model = json.getString("model"),
        backend = json.getString("backend"),
        runtimeVersion = json.getString("runtimeVersion"),
        cpuFallbackEnabled = json.getBoolean("cpuFallbackEnabled"),
        readyComponents = components,
    )
    if (value.runtimeApiVersion != 1 || value.model != expectedModel || value.backend != expectedBackend ||
        value.cpuFallbackEnabled || !components.containsAll(requiredComponents)
    ) throw InferenceRouteException("Native runtime did not prove the required $expectedBackend route readiness")
    return value
}

internal fun requireMatchingSupertonicContract(
    contract: SupertonicModelContract,
    reported: RuntimeProvenance,
): RuntimeProvenance {
    require(reported.runtimeVersion == "ONNX Runtime 1.27.1 / QAIRT 2.49.0.260730" &&
        reported.componentInt("text_length") == contract.textLength &&
        reported.componentInt("latent_length") == contract.latentLength &&
        reported.componentInt("latent_channels") == contract.latentChannels &&
        reported.componentInt("diffusion_steps") == contract.diffusionSteps &&
        reported.componentInt("sample_rate_hz") == contract.sampleRateHz &&
        reported.componentInt("channel_count") == contract.channelCount &&
        reported.componentInt("pcm_bits") == contract.pcmBits
    ) { "Native Supertonic readiness does not match the authenticated pack contract" }
    return reported
}

private fun RuntimeProvenance.componentInt(key: String): Int = readyComponents
    .singleOrNull { it.startsWith("$key=") }
    ?.substringAfter('=')?.toIntOrNull()
    ?: throw InferenceRouteException("Native runtime provenance is missing $key")

internal object NativeAppRuntime {
    @Volatile private var loaded = false

    @Synchronized
    fun ensureLoaded() {
        if (!loaded) {
            System.loadLibrary("podcast_runtime")
            loaded = true
        }
    }
}

private fun requireRoute(pack: VerifiedModelPack, expected: ModelRoute) {
    if (pack.route != expected) throw InferenceRouteException("Expected $expected, received ${pack.route}")
}

private object SupertonicNative {
    @JvmStatic external fun create(packRoot: String, voiceId: String, debugProfileDirectory: String): Long
    @JvmStatic external fun provenance(handle: Long): String?
    @JvmStatic external fun renderCompleteChapter(handle: Long, chapterId: String, text: String, outputWav: String): Boolean
    @JvmStatic external fun destroy(handle: Long)
}
