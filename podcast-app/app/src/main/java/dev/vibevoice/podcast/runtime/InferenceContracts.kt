package dev.vibevoice.podcast.runtime

import dev.vibevoice.podcast.model.VerifiedModelPack
import java.io.Closeable
import java.io.File

data class SourceMaterial(val id: String, val title: String, val text: String)
data class OutlineChapter(val id: String, val title: String, val brief: String)
data class EpisodeOutline(val title: String, val chapters: List<OutlineChapter>)
data class FrozenChapter(val id: String, val title: String, val text: String)
data class AudioMetadata(val sampleRateHz: Int, val channelCount: Int, val frameCount: Long, val sha256: String)
data class RuntimeProvenance(
    val runtimeApiVersion: Int,
    val model: String,
    val backend: String,
    val runtimeVersion: String,
    val cpuFallbackEnabled: Boolean,
    val readyComponents: Set<String>,
)

interface LlmEngine : Closeable {
    val provenance: RuntimeProvenance?
    suspend fun load(pack: VerifiedModelPack)
    suspend fun createSourceNotes(source: SourceMaterial, chunkIndex: Int, chunkCount: Int): SourceMaterial
    suspend fun createOutline(sources: List<SourceMaterial>, instructions: String): EpisodeOutline
    suspend fun createChapter(outline: EpisodeOutline, chapter: OutlineChapter, sources: List<SourceMaterial>, instructions: String): FrozenChapter
    suspend fun editScript(requestJson: String): String
}

interface TtsEngine : Closeable {
    val provenance: RuntimeProvenance?
    suspend fun load(pack: VerifiedModelPack, voiceId: String = "M1/SID5")
    suspend fun renderChapter(chapter: FrozenChapter, output: File): AudioMetadata
}

open class InferenceRouteException(message: String, cause: Throwable? = null) : Exception(message, cause)
