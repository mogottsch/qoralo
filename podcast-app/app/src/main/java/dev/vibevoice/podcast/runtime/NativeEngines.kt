package dev.vibevoice.podcast.runtime

import android.annotation.SuppressLint
import dev.vibevoice.podcast.model.ModelRoute
import dev.vibevoice.podcast.model.VerifiedModelPack
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/** JNI is supplied by the verified Gemma pack; absence or failure is terminal for this route. */
class GemmaLiteRtGpuEngine : LlmEngine {
    private var handle = 0L

    @SuppressLint("UnsafeDynamicallyLoadedCode") // Entrypoint is size/hash verified immediately before loading.
    override suspend fun load(pack: VerifiedModelPack) = withContext(Dispatchers.IO) {
        requireRoute(pack, ModelRoute.GEMMA_4_E2B_LITERT_GPU)
        try {
            System.load(pack.entrypoint.absolutePath)
            handle = GemmaNative.create(pack.root.absolutePath)
            if (handle == 0L) throw InferenceRouteException("Gemma LiteRT GPU initialization returned no engine")
        } catch (error: Throwable) {
            throw InferenceRouteException("Gemma 4 E2B LiteRT GPU failed to initialize", error)
        }
    }

    override suspend fun createOutline(sources: List<SourceMaterial>, instructions: String): EpisodeOutline {
        val result = generate("outline", requestJson(sources, instructions).toString())
        val json = JSONObject(result)
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
    }

    private fun requestJson(sources: List<SourceMaterial>, instructions: String) = JSONObject()
        .put("schemaVersion", 1)
        .put("instructions", instructions)
        .put("sources", JSONArray(sources.map { JSONObject().put("id", it.id).put("title", it.title).put("text", it.text) }))
}

/** JNI is supplied by the verified Supertonic pack and must execute the external-context QNN/HTP route. */
class SupertonicQnnHtpEngine : TtsEngine {
    private var handle = 0L

    @SuppressLint("UnsafeDynamicallyLoadedCode") // Entrypoint is size/hash verified immediately before loading.
    override suspend fun load(pack: VerifiedModelPack, voiceId: String) = withContext(Dispatchers.IO) {
        requireRoute(pack, ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP)
        try {
            System.load(pack.entrypoint.absolutePath)
            handle = SupertonicNative.create(pack.root.absolutePath, voiceId)
            if (handle == 0L) throw InferenceRouteException("Supertonic QNN initialization returned no engine")
        } catch (error: Throwable) {
            throw InferenceRouteException("Supertonic external-context QNN/HTP failed to initialize", error)
        }
    }

    override suspend fun renderChapter(chapter: FrozenChapter, output: File): AudioMetadata = withContext(Dispatchers.IO) {
        check(handle != 0L) { "Supertonic engine is not loaded" }
        output.parentFile?.mkdirs()
        val temporary = File(output.parentFile, ".${output.name}.tmp")
        temporary.delete()
        try {
            val result = SupertonicNative.renderCompleteChapter(handle, chapter.id, chapter.text, temporary.absolutePath)
                ?: throw InferenceRouteException("Supertonic returned no chapter metadata")
            if (!temporary.isFile || temporary.length() == 0L) throw InferenceRouteException("Supertonic emitted no chapter WAV")
            if (!temporary.renameTo(output)) throw InferenceRouteException("Could not commit chapter WAV")
            AudioMetadata(result.sampleRateHz, result.channelCount, result.frameCount, result.sha256)
        } catch (error: Throwable) {
            temporary.delete()
            throw InferenceRouteException("Complete-chapter Supertonic QNN/HTP synthesis failed; no splitting or fallback was attempted", error)
        }
    }

    override fun close() {
        if (handle != 0L) runCatching { SupertonicNative.destroy(handle) }
        handle = 0L
    }
}

private fun requireRoute(pack: VerifiedModelPack, expected: ModelRoute) {
    if (pack.route != expected) throw InferenceRouteException("Expected $expected, received ${pack.route}")
}

private object GemmaNative {
    @JvmStatic external fun create(packRoot: String): Long
    @JvmStatic external fun generate(handle: Long, mode: String, requestJson: String): String?
    @JvmStatic external fun destroy(handle: Long)
}

data class NativeAudioResult(val sampleRateHz: Int, val channelCount: Int, val frameCount: Long, val sha256: String)

private object SupertonicNative {
    @JvmStatic external fun create(packRoot: String, voiceId: String): Long
    @JvmStatic external fun renderCompleteChapter(handle: Long, chapterId: String, text: String, outputWav: String): NativeAudioResult?
    @JvmStatic external fun destroy(handle: Long)
}
