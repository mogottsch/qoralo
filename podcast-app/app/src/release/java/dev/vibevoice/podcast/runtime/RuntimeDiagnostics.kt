package dev.vibevoice.podcast.runtime

import com.google.ai.edge.litertlm.Conversation

/** Release has no diagnostic controls, output capture, or limit overrides. */
internal object RuntimeDiagnostics {
    fun retainProviderIntermediates(): Boolean = false
    suspend fun beginJob(context: android.content.Context, episodeId: String, jobId: String) = Unit
    fun endJob() = Unit
    fun verifiedGemma(pack: dev.vibevoice.podcast.model.VerifiedModelPack) = Unit
    fun responseReturned(raw: String) = Unit
    fun requestFailed(error: GemmaRequestException) = Unit
    fun jobFailed(error: Throwable) = Unit
    fun configurePlayer(episodeId: String, player: androidx.media3.exoplayer.ExoPlayer) = Unit
    fun beforeExport(context: android.content.Context, episodeId: String, uri: android.net.Uri) = Unit
    fun exportFinished(episodeId: String, uri: android.net.Uri) = Unit
    fun outputLimit(mode: String, productionLimit: Int): Int = productionLimit
    fun beforeRequest(mode: String, request: String, systemInstruction: String, outputLimit: Int, responseSchema: String? = null) = Unit
    fun send(conversation: Conversation, request: String, responseFormat: com.google.ai.edge.litertlm.ResponseFormat? = null): String =
        conversation.sendMessage(request, responseFormat = responseFormat).toString()
    fun qnnProfileDirectory(): String = ""
}
