package dev.qoralo.podcast.wiring

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.IBinder
import android.os.Process
import androidx.core.app.NotificationCompat
import dev.qoralo.podcast.BuildConfig
import dev.qoralo.podcast.PodcastApplication
import dev.qoralo.podcast.R
import dev.qoralo.podcast.model.ModelPackRequirement
import dev.qoralo.podcast.model.ModelPackVerifier
import dev.qoralo.podcast.model.ModelRoute
import dev.qoralo.podcast.model.SupertonicModelContract
import dev.qoralo.podcast.runtime.FrozenChapter
import dev.qoralo.podcast.runtime.GemmaLiteRtGpuEngine
import dev.qoralo.podcast.runtime.RuntimeDiagnostics
import dev.qoralo.podcast.runtime.RuntimeProvenance
import dev.qoralo.podcast.runtime.SourceMaterial
import dev.qoralo.podcast.runtime.SupertonicQnnHtpEngine
import dev.qoralo.podcast.runtime.SupertonicTextNormalizer
import dev.qoralo.podcast.runtime.WavInspector
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/** Debug-only, same-UID, single-attempt real engine probe. Never publishes a product episode. */
class RuntimeWiringService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val deadlines = Executors.newSingleThreadScheduledExecutor()
    private val stageLock = Any()
    private var stageId = 0
    @Volatile private var stage = "dispatch"
    @Volatile private var failedStage: String? = null
    @Volatile private var evidence: WiringEvidence? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (evidence != null) return START_NOT_STICKY
        val runId = intent?.getStringExtra("runId").orEmpty()
        if (!WiringContract.validRunId(runId) || intent?.getStringExtra("contractSha256") != WiringContract.SHA256) {
            stopSelf(); return START_NOT_STICKY
        }
        check(Application.getProcessName() == "$packageName:generation") { "Wiring must run in :generation" }
        val root = File(filesDir, "wiring/$runId")
        check(root.isDirectory && !File(root, "service-started.json").exists()) { "Missing/new-run evidence directory required" }
        val log = WiringEvidence(root)
        evidence = log
        log.json("service-started.json", JSONObject().put("pid", Process.myPid()).put("process", Application.getProcessName())
            .put("contractSha256", WiringContract.SHA256).put("debug", BuildConfig.DEBUG))
        startNotification()
        scope.launch {
            try {
                val contract = WiringContract.load(this@RuntimeWiringService)
                deadlines.schedule({ abort("total_deadline", IllegalStateException("Pinned total deadline exceeded")) }, contract.totalMs, TimeUnit.MILLISECONDS)
                deadlines.scheduleWithFixedDelay({
                    runCatching {
                        if (root.walkTopDown().filter(File::isFile).sumOf(File::length) > contract.maxEvidenceBytes) {
                            abort("evidence_quota", IllegalStateException("Pinned evidence byte limit exceeded"))
                        }
                    }.onFailure { abort("evidence_monitor", it) }
                }, 1, 1, TimeUnit.SECONDS)
                NativeStdioCapture(root).use {
                    RuntimeDiagnostics.enable(contract, log) { abort("raw_output_limit", it) }
                    runProbe(contract, log)
                }
                log.json("inventory.json", log.inventory())
                log.finish("observations_complete", "finished")
            } catch (error: Throwable) {
                log.finish("failed", failedStage ?: stage, error)
            } finally {
                RuntimeDiagnostics.disable()
                deadlines.shutdownNow()
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
        }
        return START_NOT_STICKY
    }

    private suspend fun runProbe(contract: WiringContract, log: WiringEvidence) {
        val app = application as PodcastApplication
        val packs = step(contract, "verify-packs") {
            check(app.repository.runningJobs().isEmpty() && app.repository.queuedJobs().isEmpty()) { "Product generation is active; wiring refused" }
            val verifier = ModelPackVerifier()
            val gemma = verifier.verify(app.artifacts.modelPackRoot("gemma-4-e2b"),
                ModelPackRequirement(ModelRoute.GEMMA_4_E2B_LITERT_GPU, "gemma-4-e2b", BuildConfig.GEMMA_MANIFEST_SHA256))
            val qnn = verifier.verify(app.artifacts.modelPackRoot("supertonic-3"),
                ModelPackRequirement(ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP, "supertonic-3", BuildConfig.SUPERTONIC_MANIFEST_SHA256))
            val shape = qnn.contract as SupertonicModelContract
            check(shape.textLength == 239 && shape.latentLength == 238) { "This gate pins the accepted T239/L238 pack" }
            log.json("verified-packs.json", JSONObject().put("gemmaManifestSha256", gemma.manifestSha256)
                .put("supertonicManifestSha256", qnn.manifestSha256).put("qnnContract", shape.toString()))
            gemma to qnn
        }
        val sources = listOf(SourceMaterial("wiring-source-1", "Buried streams", contract.inputs.getValue("source.txt")))
        val instructions = contract.inputs.getValue("instructions.txt")
        val llm = GemmaLiteRtGpuEngine()
        try {
            step(contract, "gemma-load") { llm.load(packs.first); reported(log, "gemma", requireNotNull(llm.provenance)) }
            val outline = step(contract, "gemma-outline") {
                val value = llm.createOutline(sources, instructions)
                log.json("outline-parsed.json", JSONObject().put("title", value.title).put("chapters", JSONArray(value.chapters.map {
                    JSONObject().put("id", it.id).put("title", it.title).put("brief", it.brief)
                })))
                require(value.title.isNotBlank() && value.chapters.size == 1 && value.chapters.single().id == "chapter-1") {
                    "Outline did not satisfy the single-chapter wiring request; no retry"
                }
                value
            }
            step(contract, "gemma-chapter") {
                val chapter = llm.createChapter(outline, outline.chapters.single(), sources, instructions)
                log.json("chapter-parsed.json", JSONObject().put("id", chapter.id).put("title", chapter.title).put("text", chapter.text))
                require(chapter.id == "chapter-1" && chapter.title.isNotBlank() && chapter.text.isNotBlank()) { "Invalid complete chapter response" }
                log.snapshot("gemma-after-generation")
            }
        } finally { step(contract, "gemma-close") { llm.close() } }

        val tts = SupertonicQnnHtpEngine()
        try {
            step(contract, "qnn-load") { tts.load(packs.second, "M1/SID5"); reported(log, "qnn", requireNotNull(tts.provenance)) }
            step(contract, "qnn-short") {
                val text = contract.inputs.getValue("canonical-short.txt")
                log.write("canonical-normalized.txt", SupertonicTextNormalizer.normalize(text))
                val output = File(log.root, "canonical-short.wav")
                val metadata = tts.renderChapter(FrozenChapter("canonical-short", "Canonical short input", text), output)
                check(metadata == WavInspector.inspectSupertonicOutput(output))
                log.json("canonical-wav.json", JSONObject().put("sha256", metadata.sha256).put("bytes", output.length())
                    .put("frames", metadata.frameCount).put("sampleRateHz", metadata.sampleRateHz).put("channels", metadata.channelCount)
                    .put("listeningVerdict", "not_reviewed").put("claim", "one profiled wiring sample; no RTF campaign"))
                log.snapshot("qnn-after-short")
            }
            step(contract, "qnn-capacity") {
                val text = contract.inputs.getValue("realistic-chapter.txt")
                val normalized = SupertonicTextNormalizer.normalize(text)
                require(normalized.codePointCount(0, normalized.length) + 9 > 239) { "Capacity probe is not oversized" }
                log.write("realistic-normalized.txt", normalized)
                val directory = File(log.root, "capacity-output").apply { check(mkdir()) }
                val output = File(directory, "chapter.wav")
                val failure = try {
                    tts.renderChapter(FrozenChapter("realistic-capacity", "Before the street grid", text), output)
                    null
                } catch (error: Throwable) { error }
                log.json("capacity-observation.json", JSONObject().put("exception", failure?.stackTraceToString() ?: JSONObject.NULL)
                    .put("normalizedWrappedCodepoints", normalized.codePointCount(0, normalized.length) + 9)
                    .put("outputEntries", JSONArray(directory.list().orEmpty().toList())))
                require(failure != null && generateSequence(failure) { it.cause }.any {
                    it.message?.contains("complete chapter exceeds compiled QNN text capacity; no splitting was attempted") == true
                }) { "Expected exact native text-capacity rejection; other failures do not count" }
                require(directory.listFiles().orEmpty().isEmpty()) { "Capacity rejection left a partial or published WAV" }
                log.event("expected_capacity_rejection", "T239/L238 cannot render this complete chapter; not product E2E")
            }
        } finally { step(contract, "qnn-close") { tts.close() } }
    }

    private suspend fun <T> step(contract: WiringContract, label: String, block: suspend () -> T): T {
        val log = requireNotNull(evidence)
        val token = synchronized(stageLock) { check(!log.terminal); stage = label; ++stageId }
        log.event("stage_begin", "$label deadlineMs=${contract.deadlineMs(label)}")
        val timer = deadlines.schedule({
            synchronized(stageLock) {
                if (stageId == token && !log.terminal) abort(label, IllegalStateException("Pinned stage deadline exceeded"))
            }
        }, contract.deadlineMs(label), TimeUnit.MILLISECONDS)
        try { return block().also { log.event("stage_complete", label) } }
        catch (error: Throwable) {
            if (failedStage == null) failedStage = label
            log.event("stage_error", "$label: ${error.stackTraceToString()}"); throw error
        }
        finally { synchronized(stageLock) { ++stageId }; timer.cancel(false) }
    }

    private fun reported(log: WiringEvidence, label: String, value: RuntimeProvenance) {
        log.json("$label-runtime-reported.json", JSONObject().put("runtimeVersion", value.runtimeVersion)
            .put("backend", value.backend).put("cpuFallbackEnabled", value.cpuFallbackEnabled)
            .put("readyComponents", JSONArray(value.readyComponents.sorted()))
            .put("evidenceStatus", "runtime declaration; maps/RPC/profiles must independently establish physical provider"))
        log.snapshot("$label-after-load")
    }

    private fun abort(label: String, error: Throwable) {
        try { evidence?.finish("timeout_or_limit", label, error) }
        finally {
            // JNI may not cooperate with cancellation. Never kill the UI/other process.
            if (Application.getProcessName() == "$packageName:generation") Process.killProcess(Process.myPid())
        }
    }

    override fun onTimeout(startId: Int, fgsType: Int) = abort("android_fgs_timeout", IllegalStateException("Android service timeout"))
    override fun onDestroy() { scope.cancel(); deadlines.shutdownNow(); super.onDestroy() }

    private fun startNotification() {
        getSystemService(NotificationManager::class.java).createNotificationChannel(NotificationChannel("runtime-wiring", "Debug runtime wiring", NotificationManager.IMPORTANCE_LOW))
        val notification = NotificationCompat.Builder(this, "runtime-wiring").setSmallIcon(R.drawable.ic_notification)
            .setContentTitle("Debug runtime wiring").setContentText("Bounded real requests; no fallback or retries")
            .setOngoing(true).build()
        startForeground(4199, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
    }
}
