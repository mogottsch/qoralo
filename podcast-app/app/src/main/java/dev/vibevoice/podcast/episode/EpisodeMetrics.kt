package dev.vibevoice.podcast.episode

import dev.vibevoice.podcast.data.ArtifactStore
import kotlinx.coroutines.CancellationException
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import kotlin.coroutines.AbstractCoroutineContextElement
import kotlin.coroutines.CoroutineContext

/** Content-free local diagnostics. Runtime counters only; never tokenize words or use KV totals. */
data class LlmRequestMetrics(
    val mode: String,
    val outcome: String,
    val totalMs: Double,
    val conversationSetupMs: Double?,
    val sendWallMs: Double?,
    val prefillTokens: Int?,
    val decodeTokens: Int?,
    val prefillTokensPerSecond: Double?,
    val decodeTokensPerSecond: Double?,
    val runtimeInitMs: Double?,
    val runtimeTtftMs: Double?,
) {
    fun json(): JSONObject = JSONObject().put("mode", mode).put("outcome", outcome).put("totalMs", totalMs)
        .nullable("conversationSetupMs", conversationSetupMs).nullable("sendWallMs", sendWallMs)
        .nullable("prefillTokens", prefillTokens).nullable("decodeTokens", decodeTokens)
        .nullable("prefillTokensPerSecond", prefillTokensPerSecond).nullable("decodeTokensPerSecond", decodeTokensPerSecond)
        .nullable("runtimeInitMs", runtimeInitMs).nullable("runtimeTtftMs", runtimeTtftMs)
}

fun JSONObject.nullable(name: String, value: Any?): JSONObject = put(name, value ?: JSONObject.NULL)
fun validTime(value: Double?): Double? = value?.takeIf { it.isFinite() && it >= 0 }
fun validRate(value: Double?, tokens: Int?): Double? = value?.takeIf { it.isFinite() && it > 0 && tokens != null && tokens > 0 }

/** Runtime's own last-prefill/last-decode counters are scoped to one fresh Conversation request. */
fun runtimeRequestMetrics(mode: String, outcome: String, totalMs: Double, setupMs: Double?, sendMs: Double?,
    prefillTokens: Int? = null, decodeTokens: Int? = null, prefillRate: Double? = null, decodeRate: Double? = null,
    initSeconds: Double? = null, ttftSeconds: Double? = null): LlmRequestMetrics {
    require(mode in setOf("source_notes", "outline", "chapter", "edit"))
    require(outcome in setOf("complete", "failed", "cancelled"))
    val prefill = prefillTokens?.takeIf { it >= 0 }; val decode = decodeTokens?.takeIf { it >= 0 }
    return LlmRequestMetrics(mode, outcome, requireNotNull(validTime(totalMs)), validTime(setupMs), validTime(sendMs),
        prefill, decode, validRate(prefillRate, prefill), validRate(decodeRate, decode),
        validTime(initSeconds?.times(1000))?.takeIf { it > 0 }, validTime(ttftSeconds?.times(1000))?.takeIf { it > 0 })
}

/** One job's monotonic boundaries. Persist eagerly at boundaries, never log raw content/errors.
 * An interrupted RUNNING record remains incomplete: no fabricated end time after process death.
 */
class EpisodeMetrics(private val artifacts: ArtifactStore, val episodeId: String, val jobId: String,
    kind: String, startNs: Long? = null, private val now: () -> Long = System::nanoTime) : AbstractCoroutineContextElement(Key) {
    companion object Key : CoroutineContext.Key<EpisodeMetrics> {
        fun read(artifacts: ArtifactStore, episodeId: String, jobId: String): JSONObject? = runCatching {
            require(Regex("[A-Za-z0-9_-]{1,128}").matches(jobId))
            val file = File(artifacts.resolveEpisodeFile("$episodeId/diagnostics"), "$jobId.json")
            if (!file.isFile) return@runCatching null
            require(file.length() in 1..1_048_576)
            JSONObject(file.readText()).also {
                require(it.getInt("schemaVersion") == 1 && it.getString("episodeId") == episodeId && it.getString("jobId") == jobId)
            }
        }.getOrNull()
    }
    private val started = startNs ?: now()
    private var outcome = "running"
    private var kind = kind
    private var wallMs: Double? = null
    private var audioFrames = 0L
    private val stages = linkedMapOf<String, Double>()
    private val requests = mutableListOf<LlmRequestMetrics>()
    private var omittedRequests = 0
    init { require(kind in setOf("SCRIPT", "AGENT_EDIT", "AUDIO")); persist() }
    private fun elapsed(start: Long) = (now() - start).coerceAtLeast(0) / 1_000_000.0
    suspend fun <T> measure(stage: String, block: suspend () -> T): T {
        require(stage in setOf("setup", "render", "finalization", "teardown"))
        val begin = now()
        try { return block() } finally { synchronized(this) { stages[stage] = (stages[stage] ?: 0.0) + elapsed(begin); persist() } }
    }
    @Synchronized fun recovered() { kind = "PUBLICATION_RECOVERY"; persist() }
    @Synchronized fun audioAvailable(frames: Long) { require(frames >= audioFrames); audioFrames = frames; persist() }
    @Synchronized fun request(value: LlmRequestMetrics) {
        if (requests.size < 512) requests += value else omittedRequests++
        persist()
    }
    @Synchronized fun finish(error: Throwable?) {
        outcome = when (error) { null -> "complete"; is CancellationException -> "cancelled"; else -> "failed" }
        wallMs = elapsed(started); persist()
    }
    @Synchronized fun snapshot(): JSONObject {
        fun aggregate(prefill: Boolean): Double? {
            if (requests.isEmpty() || omittedRequests > 0) return null
            var tokens = 0L; var seconds = 0.0
            for (request in requests) {
                val count = (if (prefill) request.prefillTokens else request.decodeTokens) ?: return null
                val rate = (if (prefill) request.prefillTokensPerSecond else request.decodeTokensPerSecond) ?: return null
                if (count <= 0) return null
                tokens += count; seconds += count / rate
            }
            return validRate(tokens / seconds, 1)
        }
        val audioMs = audioFrames.takeIf { it > 0 }?.let { it * 1000.0 / 44100 }
        return JSONObject().put("schemaVersion", 1).put("episodeId", episodeId).put("jobId", jobId)
            .put("kind", kind).put("outcome", outcome).nullable("wallMs", wallMs)
            .put("wallBoundary", "coordinator entry through engine teardown and final publication; excludes queue wait")
            .put("stageBoundary", "setup=engine.load; render=chapter synthesis including callbacks; finalization=master assembly and commit; teardown=engine.close")
            .put("runtimeCounterBoundary", "LiteRT-LM 0.16.1 BenchmarkInfo last-prefill/last-decode for one fresh conversation; unavailable fields are null")
            .put("ttsDurationBoundary", "validated available PCM at 44100 Hz including prescribed segment/chapter gaps; partial unless complete")
            .nullable("setupMs", stages["setup"]).nullable("renderMs", stages["render"])
            .nullable("finalizationMs", stages["finalization"]).nullable("teardownMs", stages["teardown"])
            .nullable("audioDurationMs", audioMs).put("availableAudioFrames", audioFrames)
            .nullable("wallRtf", if (kind == "AUDIO" && audioMs != null) wallMs?.div(audioMs) else null)
            .nullable("renderRtf", if (kind == "AUDIO" && audioMs != null) stages["render"]?.div(audioMs) else null)
            .put("rtfDefinition", "elapsed time / available audio duration; lower is faster; recovery has no synthesis RTF")
            .nullable("llmPrefillTokensPerSecond", aggregate(true)).nullable("llmDecodeTokensPerSecond", aggregate(false))
            .put("llmAggregateBoundary", "total runtime-reported tokens / sum(count / runtime-reported rate); all requests required, no KV/word estimates")
            .put("requests", JSONArray(requests.map { it.json() })).put("omittedRequests", omittedRequests)
    }
    private fun persist() {
        // Diagnostics failure cannot change inference results; deletion forbids new files.
        runCatching {
            require(Regex("[A-Za-z0-9_-]{1,128}").matches(jobId))
            val destination = artifacts.resolveEpisodeFile("$episodeId/diagnostics/$jobId.json")
            artifacts.writeAtomically(destination, snapshot().toString().toByteArray(Charsets.UTF_8))
        }
    }
}
