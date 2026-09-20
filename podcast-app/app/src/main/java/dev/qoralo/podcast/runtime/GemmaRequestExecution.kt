package dev.qoralo.podcast.runtime

import org.json.JSONObject
import java.util.IdentityHashMap

enum class GemmaFailurePhase { CONVERSATION_CREATE, SEND, CONVERSATION_CLOSE, JSON_EXTRACTION, JSON_PARSE }

/** Content-free graph; only an allowlisted typed SDK status prefix may be extracted from a message. */
data class FailureTypeNode(val type: String, val cause: Int?, val suppressed: List<Int>, val sdkStatus: String? = null)
data class FailureTypeGraph(val nodes: List<FailureTypeNode>, val truncated: Boolean) {
    fun safeText(): String = nodes.mapIndexed { index, node ->
        "$index:${node.type.substringAfterLast('.').take(48)}(cause=${node.cause},suppressed=${node.suppressed},sdk=${node.sdkStatus})"
    }.joinToString(";") + if (truncated) ";graph_truncated" else ""

    companion object {
        fun capture(error: Throwable): FailureTypeGraph {
            val seen = IdentityHashMap<Throwable, Int>()
            val nodes = mutableListOf<FailureTypeNode>()
            var truncated = false
            fun visit(value: Throwable): Int? {
                seen[value]?.let { return it }
                if (nodes.size == 8) { truncated = true; return null }
                val index = nodes.size
                seen[value] = index
                val type = value.javaClass.name.take(160).replace(Regex("[^A-Za-z0-9_.$]"), "_")
                nodes += FailureTypeNode(type, null, emptyList())
                val cause = runCatching { value.cause }.getOrNull()?.let(::visit)
                val suppressed = runCatching { value.suppressed }.getOrDefault(emptyArray())
                if (suppressed.size > 4) truncated = true
                nodes[index] = FailureTypeNode(type, cause, suppressed.take(4).mapNotNull(::visit), typedSdkStatus(value))
                return index
            }
            visit(error)
            return FailureTypeGraph(nodes, truncated)
        }

        private fun typedSdkStatus(error: Throwable): String? {
            if (error.javaClass.name != "com.google.ai.edge.litertlm.LiteRtLmJniException") return null
            val prefix = runCatching { error.message?.take(80) }.getOrNull() ?: return null
            val numeric = Regex("^Status Code: ([0-9]{1,2})\\.").find(prefix)?.groupValues?.get(1)?.toIntOrNull()
            if (numeric != null && numeric in 0..16) return "code_$numeric"
            val named = prefix.substringBefore(':')
            return named.takeIf { it in setOf("OK", "CANCELLED", "UNKNOWN", "INVALID_ARGUMENT", "DEADLINE_EXCEEDED",
                "NOT_FOUND", "ALREADY_EXISTS", "PERMISSION_DENIED", "RESOURCE_EXHAUSTED", "FAILED_PRECONDITION",
                "ABORTED", "OUT_OF_RANGE", "UNIMPLEMENTED", "INTERNAL", "UNAVAILABLE", "DATA_LOSS", "UNAUTHENTICATED") }
        }
    }
}

class GemmaRequestException(
    val requestMode: String,
    val failurePhase: GemmaFailurePhase,
    val typeGraph: FailureTypeGraph,
    cause: Throwable,
) : InferenceRouteException(
    "Gemma LiteRT GPU ${safeMode(requestMode)} failed at ${failurePhase.name}; ${typeGraph.safeText()}", cause,
) {
    companion object {
        private fun safeMode(mode: String) = mode.takeIf { it in setOf("source_notes", "outline", "chapter", "edit") } ?: "unknown_mode"
    }
}

/** Preserve structured Gemma metadata across outer wrappers without displaying private cause messages. */
fun generationFailureMessage(error: Throwable): String {
    val pending = ArrayDeque<Throwable>().apply { add(error) }
    val seen = IdentityHashMap<Throwable, Boolean>()
    while (pending.isNotEmpty() && seen.size < 8) {
        val next = pending.removeFirst()
        if (seen.put(next, true) != null) continue
        if (next is GemmaRequestException) return requireNotNull(next.message).take(1000)
        runCatching { next.cause }.getOrNull()?.let(pending::addLast)
        runCatching { next.suppressed }.getOrDefault(emptyArray()).take(4).forEach(pending::addLast)
    }
    return ("Generation failed; " + FailureTypeGraph.capture(error).safeText()).take(1000)
}

/** Same one Conversation/send/use/first-{..last-} parsing as before; no retry, repair, or response alteration. */
internal fun <C : AutoCloseable> executeGemmaRequest(
    mode: String,
    create: () -> C,
    send: (C) -> String,
    returned: (String) -> Unit = {},
    failed: (GemmaRequestException) -> Unit = {},
): String {
    var phase = GemmaFailurePhase.CONVERSATION_CREATE
    try {
        val raw = create().use { conversation ->
            phase = GemmaFailurePhase.SEND
            val response = send(conversation)
            // Receipt failures are observational only, and raw bytes exist even if close later fails.
            runCatching { returned(response) }
            phase = GemmaFailurePhase.CONVERSATION_CLOSE
            response
        }
        phase = GemmaFailurePhase.JSON_EXTRACTION
        val start = raw.indexOf('{')
        val end = raw.lastIndexOf('}')
        require(start >= 0 && end > start) { "Gemma response did not contain a JSON object" }
        val json = raw.substring(start, end + 1)
        phase = GemmaFailurePhase.JSON_PARSE
        JSONObject(json)
        return json
    } catch (cancelled: kotlinx.coroutines.CancellationException) {
        throw cancelled // Keep cancellation distinct; use() still closes and retains suppressed failures.
    } catch (error: Throwable) {
        val failure = GemmaRequestException(mode, phase, FailureTypeGraph.capture(error), error)
        runCatching { failed(failure) }
        // Preserve structured runtime failures; cancellation is handled separately above.
        throw failure
    }
}
