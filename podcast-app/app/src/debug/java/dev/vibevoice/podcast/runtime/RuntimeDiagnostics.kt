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
    @Volatile private var providerRetention = false
    fun retainProviderIntermediates(): Boolean = providerRetention
    suspend fun beginJob(context: android.content.Context, episodeId: String, jobId: String) {
        providerRetention = false
        runCatching {
            val marker = File(context.filesDir, "provider-integration/active.json")
            if (marker.isFile && marker.length() in 1..8192) {
                val control = JSONObject(marker.readText())
                val run = control.getString("runId")
                require(Regex("provider-app-[a-z0-9-]{1,48}").matches(run))
                if (control.getString("episodeId") == episodeId) {
                    val app = context.applicationContext as dev.vibevoice.podcast.PodcastApplication
                    val episode = app.repository.episode(episodeId)
                    val job = requireNotNull(app.repository.latestJob(episodeId))
                    require(ProviderAudioPlan.selected && control.getString("packSha256") == ProviderAudioPlan.PACK_SHA256)
                    require(job.id == jobId && job.kind == dev.vibevoice.podcast.data.JobKind.AUDIO && job.status == dev.vibevoice.podcast.data.JobStatus.QUEUED)
                    require(episode.lockedRevisionId == control.getString("revisionId") && episode.lockedContentHash == control.getString("revisionSha256"))
                    val apkHash = app.artifacts.sha256(File(context.applicationInfo.sourceDir))
                    require(apkHash == control.getString("appApkSha256"))
                    val root = File(marker.parentFile, run); require(root.mkdir())
                    File(root, "job-identity.json").writeText(JSONObject().put("runId", run).put("episodeId", episodeId).put("jobId", jobId)
                        .put("revisionId", episode.lockedRevisionId).put("revisionSha256", episode.lockedContentHash)
                        .put("packSha256", ProviderAudioPlan.PACK_SHA256).put("appApkSha256", apkHash).put("pid", android.os.Process.myPid()).toString(2))
                    providerRetention = true
                }
            }
        }
        dev.vibevoice.podcast.e2e.ShortProductDiagnostics.beginJob(context, episodeId, jobId)
        dev.vibevoice.podcast.diagnostics.UserFailureDiagnostics.beginJob(context, episodeId, jobId)
    }
    fun endJob() {
        providerRetention = false
        dev.vibevoice.podcast.diagnostics.UserFailureDiagnostics.endJob()
        dev.vibevoice.podcast.e2e.ShortProductDiagnostics.endJob()
    }
    fun verifiedGemma(pack: dev.vibevoice.podcast.model.VerifiedModelPack) =
        dev.vibevoice.podcast.diagnostics.UserFailureDiagnostics.verifiedGemma(pack)
    fun responseReturned(raw: String) = dev.vibevoice.podcast.diagnostics.UserFailureDiagnostics.responseReturned(raw)
    fun requestFailed(error: GemmaRequestException) = dev.vibevoice.podcast.diagnostics.UserFailureDiagnostics.failed(error)
    fun jobFailed(error: Throwable) = dev.vibevoice.podcast.diagnostics.UserFailureDiagnostics.jobFailed(error)
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

    fun beforeRequest(mode: String, request: String, systemInstruction: String, outputLimit: Int, responseSchema: String? = null) {
        dev.vibevoice.podcast.diagnostics.UserFailureDiagnostics.beforeRequest(mode, request, systemInstruction, outputLimit, responseSchema)
        dev.vibevoice.podcast.e2e.ShortProductDiagnostics.beforeRequest(mode, request, systemInstruction, outputLimit, responseSchema)
        val capture = active ?: return
        this.mode = mode
        capture.evidence.write("gemma-$mode-request.json", request)
        capture.evidence.write("gemma-$mode-system.txt", systemInstruction)
        responseSchema?.let { capture.evidence.write("gemma-$mode-response-schema.json", it) }
        capture.evidence.json("gemma-$mode-options.json", JSONObject().put("backend", "GPU")
            .put("contextTokens", 8192).put("maxOutputTokens", outputLimit).put("topK", 1)
            .put("thinking", false).put("freshConversation", true).put("constrainedDecoding", responseSchema != null)
            .put("actualOutputTokens", JSONObject.NULL)
            .put("metricLimitation", "Callback chunks are not token IDs; this is not a throughput benchmark"))
        require(request.toByteArray(Charsets.UTF_8).size + systemInstruction.toByteArray(Charsets.UTF_8).size <= capture.contract.maxRequestUtf8Bytes) {
            "Wiring request exceeds its pinned UTF-8 byte budget; no truncation or retry"
        }
    }

    fun send(conversation: Conversation, request: String, responseFormat: com.google.ai.edge.litertlm.ResponseFormat? = null): String {
        val capture = active ?: return dev.vibevoice.podcast.e2e.ShortProductDiagnostics.send(conversation, request, responseFormat)
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
        }, responseFormat = responseFormat)
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
