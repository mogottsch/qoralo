package dev.vibevoice.podcast.wiring

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.IBinder
import android.os.Process
import android.os.SystemClock
import androidx.core.app.NotificationCompat
import dev.vibevoice.podcast.BuildConfig
import dev.vibevoice.podcast.PodcastApplication
import dev.vibevoice.podcast.R
import dev.vibevoice.podcast.model.ModelPackRequirement
import dev.vibevoice.podcast.model.ModelPackVerifier
import dev.vibevoice.podcast.model.ModelRoute
import dev.vibevoice.podcast.runtime.FrozenChapter
import dev.vibevoice.podcast.runtime.RuntimeDiagnostics
import dev.vibevoice.podcast.runtime.SupertonicQnnHtpEngine
import dev.vibevoice.podcast.runtime.SupertonicTextNormalizer
import dev.vibevoice.podcast.runtime.WavInspector
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/** Private debug first-request engineering probe. No LLM, product job or capacity probe. */
class TtsOnlyService : Service() {
    private val worker = Executors.newSingleThreadExecutor()
    private val deadlines = Executors.newScheduledThreadPool(2)
    private val stageLock = Any()
    private var stageToken = 0
    @Volatile private var stage = "dispatch"
    @Volatile private var log: WiringEvidence? = null
    private val optionalWarnings = mutableListOf<String>()

    override fun onBind(intent: Intent?): IBinder? = null
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (log != null) return START_NOT_STICKY
        val run = intent?.getStringExtra("runId").orEmpty()
        if (!TtsOnlyContract.validRunId(run) || intent?.getStringExtra("contractSha256") != TtsOnlyContract.SHA256) {
            stopSelf(); return START_NOT_STICKY
        }
        check(Application.getProcessName() == "$packageName:generation")
        val root = File(filesDir, "tts-only/$run")
        check(root.isDirectory && !File(root, "service-started.json").exists())
        val evidence = WiringEvidence(root).also { log = it }
        evidence.json("service-started.json", JSONObject().put("pid", Process.myPid()).put("uid", Process.myUid())
            .put("process", Application.getProcessName()).put("contractSha256", TtsOnlyContract.SHA256))
        getSystemService(NotificationManager::class.java).createNotificationChannel(NotificationChannel("tts-only", "Debug one TTS request", NotificationManager.IMPORTANCE_LOW))
        startForeground(4201, NotificationCompat.Builder(this, "tts-only").setSmallIcon(R.drawable.ic_notification)
            .setContentTitle("Debug canonical TTS once").setContentText("No Gemma or automatic retry").setOngoing(true).build(), ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        worker.execute {
            val tts = SupertonicQnnHtpEngine()
            var closed = false
            try {
                val contract = TtsOnlyContract.load(this)
                deadlines.schedule({ abort("total_deadline", IllegalStateException("TTS-only service deadline")) }, contract.json.getLong("serviceSeconds"), TimeUnit.SECONDS)
                deadlines.scheduleWithFixedDelay({
                    if (root.walkTopDown().filter(File::isFile).sumOf(File::length) > contract.json.getLong("maxEvidenceBytes")) {
                        abort("evidence_quota", IllegalStateException("TTS-only evidence limit"))
                    }
                }, 1, 1, TimeUnit.SECONDS)
                NativeStdioCapture(root).use {
                    RuntimeDiagnostics.enableTtsOnly(evidence)
                    runBlocking {
                        val app = application as PodcastApplication
                        val pack = step(contract, "verify") {
                            check(app.repository.runningJobs().isEmpty() && app.repository.queuedJobs().isEmpty())
                            require(BuildConfig.SUPERTONIC_MANIFEST_SHA256 == contract.manifestSha)
                            ModelPackVerifier().verify(app.artifacts.modelPackRoot("supertonic-3"), ModelPackRequirement(
                                ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP, "supertonic-3", contract.manifestSha))
                        }
                        evidence.json("verified-pack.json", JSONObject().put("manifestSha256", pack.manifestSha256).put("contract", pack.contract.toString()))
                        evidence.write("actual-request.txt", contract.text)
                        evidence.write("actual-normalized.txt", SupertonicTextNormalizer.normalize(contract.text))
                        optional("tokenization") { evidence.json("tokenization-reconstruction.json", contract.reconstructedTokens(pack.root)) }
                        optional("before-load") { evidence.snapshot("before-load") }
                        val loadStart = SystemClock.elapsedRealtimeNanos()
                        step(contract, "load") { tts.load(pack, contract.voice) }
                        val loadMs = (SystemClock.elapsedRealtimeNanos() - loadStart) / 1e6
                        optional("runtime-declaration") {
                            val value = requireNotNull(tts.provenance)
                            evidence.json("runtime-reported.json", JSONObject().put("backend", value.backend).put("runtimeVersion", value.runtimeVersion)
                                .put("cpuFallbackEnabled", value.cpuFallbackEnabled).put("readyComponents", JSONArray(value.readyComponents.sorted()))
                                .put("claim", "runtime declaration; profiles/RPC evidence must establish actual execution separately"))
                            evidence.snapshot("after-load")
                        }
                        val output = File(root, "canonical-short.wav")
                        val renderStart = SystemClock.elapsedRealtimeNanos()
                        val audio = step(contract, "render") {
                            tts.renderChapter(FrozenChapter(contract.chapterId, "Canonical first TTS request", contract.text), output)
                        }
                        val renderMs = (SystemClock.elapsedRealtimeNanos() - renderStart) / 1e6
                        require(audio == WavInspector.inspectSupertonicOutput(output))
                        // The complete WAV already exists atomically before optional metrics/profiles/close.
                        optional("wav-metrics") {
                            val seconds = audio.frameCount.toDouble() / audio.sampleRateHz
                            evidence.json("wav-result.json", JSONObject().put("file", output.name).put("sha256", audio.sha256)
                                .put("bytes", output.length()).put("frames", audio.frameCount).put("sampleRateHz", audio.sampleRateHz)
                                .put("channels", audio.channelCount).put("pcmBits", 16).put("audioSeconds", seconds)
                                .put("setupLoadMs", loadMs).put("renderMs", renderMs).put("firstRequestRtf", renderMs / 1000.0 / seconds)
                                .put("timingBoundary", "load covers four-context adapter load; render includes normalization, native duration/text/5vector/vocoder and WAV validation/publication; excludes verify/load/close")
                                .put("warmMedianRtf", JSONObject.NULL).put("warmMedianUnavailable", "only one first request authorized")
                                .put("logicalTtsRequests", 1).put("expectedInternalRuns", contract.json.getJSONObject("expectedSessionRunCounts"))
                                .put("listeningVerdict", "not_reviewed").put("claim", "one profiled engineering request; not full chapter, campaign or product E2E"))
                            evidence.snapshot("after-render")
                        }
                        step(contract, "close") { tts.close() }; closed = true
                        optional("after-close") { evidence.snapshot("after-close") }
                    }
                }
                optional("optional-warnings") { evidence.json("optional-evidence.json", JSONObject().put("warnings", JSONArray(optionalWarnings)).put("validWavNeverDeletedForMissingMetric", true)) }
                optional("inventory") { evidence.json("inventory.json", evidence.inventory()) }
                evidence.finish("tts_complete", "finished")
            } catch (error: Throwable) {
                // Preserve any completed WAV and all partial raw files even when later evidence/close fails.
                evidence.finish("tts_failed", stage, error)
            } finally {
                if (!closed) {
                    val closeGuard = deadlines.schedule({ abort("close", IllegalStateException("Cleanup close deadline")) }, 30, TimeUnit.SECONDS)
                    try { tts.close() } finally { closeGuard.cancel(false) }
                }
                RuntimeDiagnostics.disable()
                deadlines.shutdownNow()
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
        }
        return START_NOT_STICKY
    }

    private suspend fun <T> step(contract: TtsOnlyContract, name: String, block: suspend () -> T): T {
        val evidence = requireNotNull(log)
        val token = synchronized(stageLock) { check(!evidence.terminal); stage = name; ++stageToken }
        evidence.event("stage_begin", "$name deadlineMs=${contract.deadlineMs(name)}")
        val timer = deadlines.schedule({ synchronized(stageLock) {
            if (stageToken == token && !evidence.terminal) abort(name, IllegalStateException("TTS-only stage deadline"))
        } }, contract.deadlineMs(name), TimeUnit.MILLISECONDS)
        try { return block().also { evidence.event("stage_complete", name) } }
        finally { synchronized(stageLock) { ++stageToken }; timer.cancel(false) }
    }

    private fun optional(name: String, block: () -> Unit) {
        try { block() } catch (error: Throwable) {
            optionalWarnings += "$name: $error"
            runCatching { log?.event("optional_evidence_unavailable", "$name: $error") }
        }
    }
    private fun abort(where: String, error: Throwable) {
        try { log?.finish("timeout_or_limit", where, error) }
        finally { if (Application.getProcessName() == "$packageName:generation") Process.killProcess(Process.myPid()) }
    }
    override fun onTimeout(startId: Int, fgsType: Int) = abort("android_fgs_timeout", IllegalStateException("Android FGS timeout"))
    override fun onDestroy() { worker.shutdownNow(); super.onDestroy() }
}
