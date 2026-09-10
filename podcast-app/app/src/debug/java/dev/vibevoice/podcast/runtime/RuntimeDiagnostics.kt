package dev.vibevoice.podcast.runtime

import com.google.ai.edge.litertlm.Conversation
import com.google.ai.edge.litertlm.Message
import com.google.ai.edge.litertlm.MessageCallback
import dev.vibevoice.podcast.wiring.WiringContract
import dev.vibevoice.podcast.wiring.WiringEvidence
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.CountDownLatch
import java.util.concurrent.atomic.AtomicReference

/** Available only in debug builds; enabled solely by the private wiring service. */
internal object RuntimeDiagnostics {
    suspend fun beginJob(context: android.content.Context, episodeId: String, jobId: String) =
        dev.vibevoice.podcast.e2e.ShortProductDiagnostics.beginJob(context, episodeId, jobId)
    fun endJob() = dev.vibevoice.podcast.e2e.ShortProductDiagnostics.endJob()
    fun configurePlayer(episodeId: String, player: androidx.media3.exoplayer.ExoPlayer) =
        dev.vibevoice.podcast.e2e.ShortProductDiagnostics.configurePlayer(episodeId, player)
    fun beforeExport(context: android.content.Context, episodeId: String, uri: android.net.Uri) =
        dev.vibevoice.podcast.e2e.ShortProductDiagnostics.beforeExport(context, episodeId, uri)
    fun exportFinished(episodeId: String, uri: android.net.Uri) =
        dev.vibevoice.podcast.e2e.ShortProductDiagnostics.exportFinished(episodeId, uri)
    private data class Capture(val contract: WiringContract, val evidence: WiringEvidence, val stop: (Throwable) -> Unit)
    @Volatile private var active: Capture? = null
    @Volatile private var ttsOnlyEvidence: WiringEvidence? = null
    @Volatile private var mode = ""

    fun enable(contract: WiringContract, evidence: WiringEvidence, stop: (Throwable) -> Unit) {
        check(active == null && ttsOnlyEvidence == null)
        active = Capture(contract, evidence, stop)
    }
    fun enableTtsOnly(evidence: WiringEvidence) {
        check(active == null && ttsOnlyEvidence == null)
        ttsOnlyEvidence = evidence
    }
    fun disable() { active = null; ttsOnlyEvidence = null }

    fun outputLimit(mode: String, productionLimit: Int): Int = active?.contract?.outputTokens(mode) ?: productionLimit

    fun beforeRequest(mode: String, request: String, systemInstruction: String, outputLimit: Int) {
        dev.vibevoice.podcast.e2e.ShortProductDiagnostics.beforeRequest(mode, request, systemInstruction, outputLimit)
        val capture = active ?: return
        this.mode = mode
        capture.evidence.write("gemma-$mode-request.json", request)
        capture.evidence.write("gemma-$mode-system.txt", systemInstruction)
        capture.evidence.json("gemma-$mode-options.json", JSONObject().put("backend", "GPU")
            .put("contextTokens", 8192).put("maxOutputTokens", outputLimit).put("topK", 1)
            .put("thinking", false).put("freshConversation", true)
            .put("actualOutputTokens", JSONObject.NULL)
            .put("metricLimitation", "Callback chunks are not token IDs; this is not a throughput benchmark"))
        require(request.toByteArray(Charsets.UTF_8).size + systemInstruction.toByteArray(Charsets.UTF_8).size <= capture.contract.maxRequestUtf8Bytes) {
            "Wiring request exceeds its pinned UTF-8 byte budget; no truncation or retry"
        }
    }

    fun send(conversation: Conversation, request: String): String {
        val capture = active ?: return dev.vibevoice.podcast.e2e.ShortProductDiagnostics.send(conversation, request)
        val requestMode = mode
        val output = File(capture.evidence.root, "gemma-$requestMode-raw.txt")
        check(output.createNewFile()) { "Wiring request cannot be repeated" }
        val done = CountDownLatch(1)
        val failure = AtomicReference<Throwable?>()
        conversation.sendMessageAsync(request, object : MessageCallback {
            override fun onMessage(message: Message) {
                try {
                    val bytes = message.toString().toByteArray(Charsets.UTF_8)
                    synchronized(output) {
                        FileOutputStream(output, true).use { it.write(bytes); it.fd.sync() }
                        capture.evidence.event("raw_chunk", "$requestMode ${bytes.size} bytes")
                        if (output.length() > capture.contract.maxRawResponseBytes) {
                            capture.stop(IllegalStateException("Gemma raw output exceeded pinned byte limit"))
                        }
                    }
                } catch (error: Throwable) { failure.set(error); done.countDown(); capture.stop(error) }
            }
            override fun onDone() { capture.evidence.event("callback_done", requestMode); done.countDown() }
            override fun onError(throwable: Throwable) { failure.set(throwable); capture.evidence.event("callback_error", throwable.stackTraceToString()); done.countDown() }
        })
        // Blocking native work is bounded by the service's independent kill deadline,
        // not a coroutine timeout that could wait forever for JNI cancellation.
        done.await()
        failure.get()?.let { throw it }
        return output.readText(Charsets.UTF_8)
    }

    fun qnnProfileDirectory(): String = (active?.evidence ?: ttsOnlyEvidence)?.let {
        File(it.root, "qnn-profiles").apply { check(mkdir()) }.absolutePath
    } ?: ""
}
