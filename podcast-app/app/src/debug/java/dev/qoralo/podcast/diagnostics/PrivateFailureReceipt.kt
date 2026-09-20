package dev.qoralo.podcast.diagnostics

import dev.qoralo.podcast.runtime.GemmaRequestException
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest

/** Opt-in ONLY. Immutable, bounded app-private receipts; never a logcat/UI/export sink. */
internal class PrivateFailureReceipt(private val root: File, identity: JSONObject) {
    private var bytesWritten = 0L
    private var sequence = 0
    private var pending: File? = null
    private var returned = false
    private var raw: JSONObject? = null
    private var rawReason = "SDK send has not returned output"
    private val observationErrors = mutableListOf<String>()

    init {
        check(root.mkdir()) { "Private receipt root already exists or cannot be created" }
        root.setReadable(false, false); root.setWritable(false, false); root.setExecutable(false, false)
        check(root.setReadable(true, true) && root.setWritable(true, true) && root.setExecutable(true, true))
        putJson(File(root, "identity.json"), identity)
    }

    fun modelBinding(value: JSONObject) = observe { putJson(File(root, "model-runtime.json"), value) }

    fun beforeRequest(mode: String, request: String, instruction: String, outputLimit: Int, responseSchema: String? = null) {
        pending = null; returned = false; raw = null; rawReason = "SDK send has not returned output"
        observe {
            check(++sequence <= 64) { "Private request count bound" }
            val directory = File(root, "request-%03d".format(sequence))
            check(directory.mkdir())
            pending = directory
            val requestRef = put(File(directory, "request.json"), request.toByteArray(Charsets.UTF_8))
            val instructionRef = put(File(directory, "system.txt"), instruction.toByteArray(Charsets.UTF_8))
            val schemaRef = responseSchema?.let { put(File(directory, "response-schema.json"), it.toByteArray(Charsets.UTF_8)) }
            putJson(File(directory, "config.json"), JSONObject().put("mode", mode)
                .put("responseFormat", if (schemaRef != null) "json_schema" else "none")
                .put("responseSchema", schemaRef ?: JSONObject.NULL)
                .put("constrainedDecoding", schemaRef != null)
                .put("request", requestRef).put("systemInstruction", instructionRef)
                .put("backend", "GPU").put("runtime", "LiteRT-LM 0.16.1").put("contextTokens", 8192)
                .put("maxOutputTokens", outputLimit).put("topK", 1).put("topP", 1.0).put("temperature", 1.0)
                .put("thinking", false).put("channels", JSONArray()).put("freshConversation", true)
                .put("sendApi", "synchronous sendMessage; returned Message.toString UTF-8")
                .put("actualInputTokens", JSONObject.NULL).put("actualOutputTokens", JSONObject.NULL)
                .put("tokenReason", "SDK token IDs/counters not captured; no inferred character-to-token count"))
        }
    }

    fun responseReturned(value: String) {
        returned = true
        rawReason = "SDK returned output, but private receipt was unavailable; original response unchanged"
        observe {
            val directory = requireNotNull(pending)
            raw = put(File(directory, "response.txt"), value.toByteArray(Charsets.UTF_8))
            putJson(File(directory, "returned.json"), JSONObject().put("raw", raw))
        }
    }

    fun failed(error: GemmaRequestException) = observe {
        val directory = requireNotNull(pending)
        var detail: JSONObject? = null
        // Throwable messages may contain user/model text. They go ONLY to this private opt-in sink.
        observe { detail = put(File(directory, "private-exception.txt"), requireNotNull(error.cause).stackTraceToString().toByteArray(Charsets.UTF_8)) }
        putJson(File(directory, "failure.json"), JSONObject()
            .put("phase", error.failurePhase.name).put("safeSummary", error.message)
            .put("causeGraph", JSONArray(error.typeGraph.nodes.map { n -> JSONObject().put("type", n.type)
                .put("cause", n.cause ?: JSONObject.NULL).put("suppressed", JSONArray(n.suppressed))
                .put("sdkStatus", n.sdkStatus ?: JSONObject.NULL) }))
            .put("causeGraphTruncated", error.typeGraph.truncated)
            .put("sdkReturnedOutput", returned).put("rawResponse", raw ?: JSONObject.NULL)
            .put("rawResponseUnavailableReason", if (raw == null) rawReason else JSONObject.NULL)
            .put("underlyingException", detail ?: JSONObject.NULL)
            .put("underlyingExceptionUnavailableReason", if (detail == null) "Private receipt unavailable; original exception retained as cause" else JSONObject.NULL)
            .put("observationErrorTypes", JSONArray(observationErrors)))
    }

    fun jobFailed(error: Throwable) = observe {
        var detail: JSONObject? = null
        observe { detail = put(File(root, "private-job-exception.txt"), error.stackTraceToString().toByteArray(Charsets.UTF_8)) }
        putJson(File(root, "job-failure.json"), JSONObject()
            .put("safeSummary", dev.qoralo.podcast.runtime.generationFailureMessage(error))
            .put("lastRequestDirectory", pending?.name ?: JSONObject.NULL)
            .put("sdkReturnedOutput", returned).put("rawResponse", raw ?: JSONObject.NULL)
            .put("rawResponseUnavailableReason", if (raw == null) rawReason else JSONObject.NULL)
            .put("underlyingException", detail ?: JSONObject.NULL)
            .put("underlyingExceptionUnavailableReason", if (detail == null) "Private receipt unavailable; original failure unchanged" else JSONObject.NULL)
            .put("observationErrorTypes", JSONArray(observationErrors)))
    }

    fun finished() = observe { putJson(File(root, "finished.json"), JSONObject().put("requestCount", sequence)
        .put("observationErrorTypes", JSONArray(observationErrors)).put("captureOnly", true)) }

    private fun observe(action: () -> Unit) {
        try { action() } catch (error: Throwable) {
            if (observationErrors.size < 16) observationErrors += error.javaClass.name.take(160)
        }
    }
    private fun putJson(file: File, value: JSONObject) = put(file, (value.toString(2) + "\n").toByteArray(Charsets.UTF_8))
    private fun put(file: File, bytes: ByteArray): JSONObject {
        check(bytes.size <= 1_048_576 && bytesWritten + bytes.size <= 8_388_608) { "Private receipt byte bound; nothing truncated" }
        check(file.createNewFile()) { "Private receipt exists; never overwrite" }
        bytesWritten += bytes.size // Reserve even failed/partial writes; the quota cannot undercount them.
        file.setReadable(false, false); file.setWritable(false, false)
        check(file.setReadable(true, true) && file.setWritable(true, true))
        FileOutputStream(file).use { it.write(bytes); it.fd.sync() }
        return JSONObject().put("file", file.name).put("bytes", bytes.size).put("sha256", sha256(bytes))
    }
    companion object {
        fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
    }
}
