package dev.vibevoice.podcast.runtime

/** Optional observation seam for an explicitly scoped diagnostic; production uses null. Never changes a response. */
interface GemmaRequestObserver {
    fun beforeRequest(mode: String, request: String, systemInstruction: String, outputLimit: Int)
    fun responseReturned(raw: String)
    fun requestFailed(error: GemmaRequestException)
    /** Called only after raw output was offered to responseReturned; optional telemetry must not affect inference. */
    fun conversationReturned(conversation: com.google.ai.edge.litertlm.Conversation) {}
}
