package dev.vibevoice.podcast.runtime

import com.google.ai.edge.litertlm.Conversation

/** Release has no diagnostic controls, output capture, or limit overrides. */
internal object RuntimeDiagnostics {
    fun outputLimit(mode: String, productionLimit: Int): Int = productionLimit
    fun beforeRequest(mode: String, request: String, systemInstruction: String, outputLimit: Int) = Unit
    fun send(conversation: Conversation, request: String): String = conversation.sendMessage(request).toString()
    fun qnnProfileDirectory(): String = ""
}
