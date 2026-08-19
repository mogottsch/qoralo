package com.openmoss.ttsnano.onnxruntime // Modified for vibevoice experiment 0018: instrumentation and frozen prompt.

import android.app.Activity
import android.os.Bundle
import android.os.Debug
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.widget.TextView
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.sqrt
import org.json.JSONArray
import org.json.JSONObject

class MainActivity : Activity() {
    private val mainHandler = Handler(Looper.getMainLooper())
    private lateinit var logView: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        logView = TextView(this).apply { textSize = 14f; setTextIsSelectable(true) }
        setContentView(logView)
        val runId = intent.getStringExtra("run_id") ?: error("missing run_id")
        val profile = intent.getBooleanExtra("profile", false)
        val evidenceLabel = intent.getStringExtra("evidence_label") ?: if (profile) "profile" else "benchmark"
        require(Regex("[a-z0-9-]+").matches(evidenceLabel)) { "invalid evidence_label" }
        val runs = intent.getIntExtra("runs", if (profile) 1 else 4).coerceAtLeast(1)
        val threads = intent.getIntExtra("threads", 4).coerceAtLeast(1)
        appendLog("run=$runId evidence=$evidenceLabel profile=$profile runs=$runs threads=$threads")
        Thread { execute(runId, evidenceLabel, profile, runs, threads) }.start()
    }

    private fun execute(runId: String, evidenceLabel: String, profile: Boolean, runs: Int, threads: Int) {
        val runRoot = File(filesDir, runId)
        val evidenceDir = File(runRoot, "evidence/$evidenceLabel").apply { mkdirs() }
        val profileDir = if (profile) File(evidenceDir, "profiles").apply { mkdirs() } else null
        val outputFile = File(evidenceDir, if (profile) "profile-sample.wav" else "listening-sample.wav")
        val statusFile = File(evidenceDir, "status.txt")
        val resultFile = File(evidenceDir, "result.json")
        statusFile.writeText("running\n")
        val memorySampler = ProcessSampler().apply { start() }
        val root = JSONObject()
        try {
            val engine = MossOnnxDemoEngine(
                modelRoot = File(runRoot, "moss_tts_onnx"),
                outputDir = evidenceDir,
                cpuThreads = threads,
                profileDir = profileDir,
            )
            val setup = engine.setupMetrics
            val rows = JSONArray()
            val results = ArrayList<SynthesisResult>()
            try {
                repeat(runs) { index ->
                    val result = engine.synthesize(
                        textTokenIds = BenchmarkPrompt.TOKEN_IDS,
                        outputFile = outputFile,
                        voice = "Junhao",
                        maxFrames = 375,
                        seed = 20260818L,
                    )
                    results += result
                    rows.put(result.toJson(index))
                    appendLogFromWorker("run[$index] ${"%.3f".format(result.totalMs)} ms, ${result.generatedFrames} frames")
                }
            } finally {
                engine.close()
            }
            memorySampler.stopAndJoin()
            val audio = validateWav(outputFile)
            val setupJson = JSONObject().put("total_ms", setup.totalMs)
                .put("intra_op_threads", setup.intraOpThreads)
                .put("inter_op_threads", setup.interOpThreads)
                .put("component_ms", JSONObject(setup.componentMs))
            val warmRtfs = results.drop(1).map { it.totalMs / it.durationMs }
            val warmFirstAudio = results.drop(1).map { it.firstAudioMs }
            root.put("result", "passed")
                .put("run_id", runId)
                .put("profile", profile)
                .put("runtime_claim", "Android ONNX Runtime CPUExecutionProvider only; profiling is not HTP evidence.")
                .put("benchmark", JSONObject().put("runs", runs).put("setup", setupJson).put("run_metrics", rows)
                    .put("first_rtf", results.first().totalMs / results.first().durationMs)
                    .put("warm_rtf_median", median(warmRtfs))
                    .put("first_audio_first_ms", results.first().firstAudioMs)
                    .put("warm_first_audio_median_ms", median(warmFirstAudio)))
                .put("thread_measurement", memorySampler.threadJson(threads))
                .put("memory", memorySampler.memoryJson())
                .put("prompt", JSONObject()
                    .put("transcript_sha256", BenchmarkPrompt.TRANSCRIPT_SHA256)
                    .put("effective_text_sha256", BenchmarkPrompt.EFFECTIVE_TEXT_SHA256)
                    .put("tokenizer_model_sha256", BenchmarkPrompt.TOKENIZER_MODEL_SHA256)
                    .put("token_count", BenchmarkPrompt.TOKEN_COUNT)
                    .put("token_ids", JSONArray(BenchmarkPrompt.TOKEN_IDS.toList())))
                .put("generation", JSONObject().put("voice", "Junhao").put("max_frames", 375).put("seed", 20260818L))
                .put("audio", audio)
                .put("profile_prefixes", JSONObject(engine.expectedProfilePrefixes()))
            resultFile.writeText(root.toString(2) + "\n")
            statusFile.writeText("passed\n")
            appendLogFromWorker("PASSED ${resultFile.absolutePath}")
        } catch (error: Throwable) {
            memorySampler.stopAndJoin()
            root.put("result", "failed").put("error_type", error.javaClass.name).put("error", error.message ?: "")
            resultFile.writeText(root.toString(2) + "\n")
            statusFile.writeText("failed\n")
            appendLogFromWorker("FAILED ${error.javaClass.simpleName}: ${error.message}")
        }
    }

    private fun SynthesisResult.toJson(index: Int): JSONObject = JSONObject()
        .put("index", index).put("generated_frames", generatedFrames)
        .put("sample_rate_hz", sampleRate).put("sample_count", sampleCount)
        .put("audio_duration_ms", durationMs).put("end_to_end_ms", totalMs)
        .put("rtf", totalMs / durationMs).put("first_audio_ms", firstAudioMs)
        .put("first_audio_semantics", "Run start through full audio-tokenizer decode; first decoded PCM exists in memory. The official Android example is non-streaming.")
        .put("prefill_ms", prefillMs).put("autoregressive_decode_ms", autoregressiveDecodeMs)
        .put("local_decoder_ms", localDecoderMs).put("audio_tokenizer_ms", audioTokenizerMs)
        .put("wav_write_ms", wavWriteMs)

    private fun validateWav(file: File): JSONObject {
        val bytes = file.readBytes()
        require(bytes.size >= 44 && String(bytes, 0, 4) == "RIFF" && String(bytes, 8, 4) == "WAVE")
        fun u16(i: Int) = (bytes[i].toInt() and 255) or ((bytes[i + 1].toInt() and 255) shl 8)
        fun u32(i: Int) = u16(i).toLong() or (u16(i + 2).toLong() shl 16)
        val channels = u16(22); val rate = u32(24); val bits = u16(34); val dataBytes = u32(40)
        require(channels == 1 && rate == 48000L && bits == 16 && dataBytes == bytes.size.toLong() - 44)
        var sumSq = 0.0; var peak = 0
        var i = 44
        while (i + 1 < bytes.size) {
            val raw = u16(i); val sample = if (raw >= 32768) raw - 65536 else raw
            val absolute = kotlin.math.abs(sample); if (absolute > peak) peak = absolute
            val normalized = sample / 32768.0; sumSq += normalized * normalized; i += 2
        }
        val samples = dataBytes / 2
        return JSONObject().put("path", file.absolutePath).put("sha256", sha256(bytes))
            .put("container", "WAVE").put("encoding", "PCM signed 16-bit little-endian")
            .put("channels", channels).put("sample_rate_hz", rate).put("frames", samples)
            .put("duration_seconds", samples.toDouble() / rate).put("data_bytes", dataBytes)
            .put("peak", peak / 32768.0).put("rms", sqrt(sumSq / samples.coerceAtLeast(1)))
            .put("finite", true)
    }

    private fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(bytes).joinToString("") { "%02x".format(it) }
    private fun median(values: List<Double>): Any = if (values.isEmpty()) JSONObject.NULL else values.sorted()[values.size / 2]
    private fun appendLog(message: String) { logView.append(message + "\n") }
    private fun appendLogFromWorker(message: String) { mainHandler.post { appendLog(message) } }
}

private class ProcessSampler {
    private val running = AtomicBoolean(false)
    private var thread: Thread? = null
    private var samples = 0
    private var minThreads = Int.MAX_VALUE
    private var maxThreads = 0
    private var maxVmRssKb = 0L
    private var maxVmHwmKb = 0L
    private var maxPssKb = 0L
    fun start() {
        running.set(true)
        thread = Thread {
            while (running.get()) {
                val status = File("/proc/self/status").readText()
                fun field(name: String): Long = Regex("(?m)^$name:\\s+(\\d+)").find(status)?.groupValues?.get(1)?.toLong() ?: 0L
                val n = field("Threads").toInt(); minThreads = minOf(minThreads, n); maxThreads = maxOf(maxThreads, n)
                maxVmRssKb = maxOf(maxVmRssKb, field("VmRSS")); maxVmHwmKb = maxOf(maxVmHwmKb, field("VmHWM"))
                if (samples % 10 == 0) maxPssKb = maxOf(maxPssKb, Debug.getPss().toLong())
                samples++
                SystemClock.sleep(50)
            }
        }.apply { name = "measurement-sampler"; start() }
    }
    fun stopAndJoin() { running.set(false); thread?.join(5000) }
    fun threadJson(configured: Int) = JSONObject().put("configured_ort_intra_op_threads", configured)
        .put("configured_ort_inter_op_threads", 1).put("process_threads_min", if (minThreads == Int.MAX_VALUE) 0 else minThreads)
        .put("process_threads_max", maxThreads).put("sampling_interval_ms", 50).put("samples", samples)
        .put("semantics", "Configured ORT pools plus sampled total Linux process thread count; process count includes Android/runtime/sampler threads.")
    fun memoryJson() = JSONObject().put("peak_vm_hwm_kib", maxVmHwmKb).put("peak_sampled_vm_rss_kib", maxVmRssKb)
        .put("peak_sampled_pss_kib", maxPssKb).put("rss_thread_sampling_interval_ms", 50)
        .put("pss_sampling_interval_ms", 500).put("samples", samples)
        .put("semantics", "VmHWM is cumulative process RSS high-water from /proc/self/status. VmRSS and Debug.getPss are sampled process-wide values, not isolated model allocations.")
}
