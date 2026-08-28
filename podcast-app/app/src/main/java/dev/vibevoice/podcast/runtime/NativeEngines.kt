package dev.vibevoice.podcast.runtime

import dev.vibevoice.podcast.model.ModelRoute
import dev.vibevoice.podcast.model.VerifiedModelPack
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/** JNI/runtime is supplied by the installed APK; the verified Gemma pack contains data only. */
class GemmaLiteRtGpuEngine : LlmEngine {
    private var handle = 0L
    override var provenance: RuntimeProvenance? = null
        private set

    override suspend fun load(pack: VerifiedModelPack) = withContext(Dispatchers.IO) {
        requireRoute(pack, ModelRoute.GEMMA_4_E2B_LITERT_GPU)
        try {
            NativeAppRuntime.ensureLoaded()
            handle = GemmaNative.create(pack.root.absolutePath)
            if (handle == 0L) throw InferenceRouteException("Gemma LiteRT GPU initialization returned no engine")
            provenance = validateProvenance(
                GemmaNative.provenance(handle),
                expectedModel = "GEMMA_4_E2B",
                expectedBackend = "LITERT_GPU",
                requiredComponents = setOf("model", "tokenizer", "gpu_delegate"),
            )
        } catch (error: Throwable) {
            close()
            throw InferenceRouteException("Gemma 4 E2B LiteRT GPU failed to initialize", error)
        }
    }

    override suspend fun createOutline(sources: List<SourceMaterial>, instructions: String): EpisodeOutline {
        val json = JSONObject(generate("outline", requestJson(sources, instructions).toString()))
        val chapters = json.getJSONArray("chapters")
        return EpisodeOutline(
            title = json.getString("title"),
            chapters = List(chapters.length()) { index ->
                val chapter = chapters.getJSONObject(index)
                OutlineChapter(chapter.getString("id"), chapter.getString("title"), chapter.getString("brief"))
            },
        )
    }

    override suspend fun createChapter(
        outline: EpisodeOutline,
        chapter: OutlineChapter,
        sources: List<SourceMaterial>,
        instructions: String,
    ): FrozenChapter {
        val request = requestJson(sources, instructions)
            .put("outline", JSONObject().put("title", outline.title).put("chapters", JSONArray(outline.chapters.map {
                JSONObject().put("id", it.id).put("title", it.title).put("brief", it.brief)
            })))
            .put("requestedChapterId", chapter.id)
        val json = JSONObject(generate("chapter", request.toString()))
        return FrozenChapter(json.getString("id"), json.getString("title"), json.getString("text"))
    }

    override suspend fun editScript(requestJson: String): String = generate("edit", requestJson)

    private suspend fun generate(mode: String, request: String): String = withContext(Dispatchers.Default) {
        check(handle != 0L) { "Gemma engine is not loaded" }
        try {
            GemmaNative.generate(handle, mode, request) ?: throw InferenceRouteException("Gemma returned no result")
        } catch (error: Throwable) {
            throw InferenceRouteException("Gemma LiteRT GPU $mode request failed", error)
        }
    }

    override fun close() {
        if (handle != 0L) runCatching { GemmaNative.destroy(handle) }
        handle = 0L
        provenance = null
    }

    private fun requestJson(sources: List<SourceMaterial>, instructions: String) = JSONObject()
        .put("schemaVersion", 1)
        .put("instructions", instructions)
        .put("sources", JSONArray(sources.map { JSONObject().put("id", it.id).put("title", it.title).put("text", it.text) }))
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
            handle = SupertonicNative.create(pack.root.absolutePath, voiceId)
            if (handle == 0L) throw InferenceRouteException("Supertonic QNN initialization returned no engine")
            provenance = validateProvenance(
                SupertonicNative.provenance(handle),
                expectedModel = "SUPERTONIC_3_EXTERNAL_CONTEXT",
                expectedBackend = "QNN_HTP",
                requiredComponents = setOf("duration_context", "text_context", "vector_context", "vocoder_context", "htp"),
            )
        } catch (error: Throwable) {
            close()
            throw InferenceRouteException("Supertonic external-context QNN/HTP failed to initialize", error)
        }
    }

    override suspend fun renderChapter(chapter: FrozenChapter, output: File): AudioMetadata = withContext(Dispatchers.IO) {
        check(handle != 0L) { "Supertonic engine is not loaded" }
        output.parentFile?.mkdirs()
        val temporary = File(output.parentFile, ".${output.name}.tmp")
        temporary.delete()
        try {
            if (!SupertonicNative.renderCompleteChapter(handle, chapter.id, chapter.text, temporary.absolutePath)) {
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

private fun validateProvenance(
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

private object NativeAppRuntime {
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

private object GemmaNative {
    @JvmStatic external fun create(packRoot: String): Long
    @JvmStatic external fun provenance(handle: Long): String?
    @JvmStatic external fun generate(handle: Long, mode: String, requestJson: String): String?
    @JvmStatic external fun destroy(handle: Long)
}

private object SupertonicNative {
    @JvmStatic external fun create(packRoot: String, voiceId: String): Long
    @JvmStatic external fun provenance(handle: Long): String?
    @JvmStatic external fun renderCompleteChapter(handle: Long, chapterId: String, text: String, outputWav: String): Boolean
    @JvmStatic external fun destroy(handle: Long)
}
