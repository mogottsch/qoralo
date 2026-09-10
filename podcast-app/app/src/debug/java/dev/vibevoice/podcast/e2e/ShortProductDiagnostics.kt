package dev.vibevoice.podcast.e2e

import android.app.Application
import android.content.Context
import android.net.Uri
import android.os.Process
import android.os.SystemClock
import androidx.media3.exoplayer.ExoPlayer
import com.google.ai.edge.litertlm.Conversation
import dev.vibevoice.podcast.BuildConfig
import dev.vibevoice.podcast.PodcastApplication
import dev.vibevoice.podcast.runtime.SupertonicTextNormalizer
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.Timer
import java.util.TimerTask

/** Observation/one-scenario bounds only. No alternative coordinator, model factory, sampler or profiles. */
internal object ShortProductDiagnostics {
    private data class Job(val root: File, val kind: String, val start: Long, val timer: Timer, var requests: Int = 0, var pending: File? = null)
    private var job: Job? = null
    private var uiRoot: File? = null
    private var uiEpisode: String? = null
    @Volatile var player: ExoPlayer? = null
        private set
    @Volatile var exportedUri: Uri? = null
        private set

    fun write(file: File, bytes: ByteArray) {
        check(file.createNewFile()) { "Evidence already exists: ${file.name}" }
        FileOutputStream(file).use { it.write(bytes); it.fd.sync() }
    }
    fun json(file: File, value: JSONObject) = write(file, (value.toString(2) + "\n").toByteArray())
    fun enableUi(root: File, episode: String) {
        check(BuildConfig.SHORT_PRODUCT_E2E && uiRoot == null)
        uiRoot = root; uiEpisode = episode; exportedUri = null; player = null
    }
    fun disableUi() { uiRoot = null; uiEpisode = null; player = null; exportedUri = null }
    fun configurePlayer(episode: String, value: ExoPlayer) {
        if (!BuildConfig.SHORT_PRODUCT_E2E || episode != uiEpisode) return
        value.volume = 0f // BEFORE prepare/play; never modify system volume or unrelated players.
        check(value.volume == 0f && !value.playWhenReady)
        player = value
    }
    fun beforeExport(context: Context, episode: String, uri: Uri) {
        if (!BuildConfig.SHORT_PRODUCT_E2E || episode != uiEpisode) return
        val root = requireNotNull(uiRoot)
        require(uri.scheme == "content" && uri.authority in setOf("com.android.providers.downloads.documents", "com.android.externalstorage.documents")) {
            "Owned probe export must remain local; no output stream opened"
        }
        val expected = "podcast-${root.name}.wav"
        val docId = android.provider.DocumentsContract.getDocumentId(uri)
        if (uri.authority == "com.android.externalstorage.documents") require(docId == "primary:Download/$expected")
        context.contentResolver.query(uri, arrayOf(android.provider.OpenableColumns.DISPLAY_NAME, android.provider.OpenableColumns.SIZE), null, null, null).use { cursor ->
            require(cursor != null && cursor.moveToFirst() && cursor.getString(0) == expected && !cursor.isNull(1) && cursor.getLong(1) == 0L) {
                "Owned export must be the new empty uniquely named local document; no stream opened"
            }
        }
        json(File(root, "export-before-write.json"), JSONObject().put("episodeId", episode).put("uri", uri.toString())
            .put("expectedName", expected).put("emptyBeforeWrite", true).put("localAuthorityCheckedBeforeStream", true))
    }
    fun exportFinished(episode: String, uri: Uri) {
        if (episode != uiEpisode) return
        exportedUri = uri
        uiRoot?.let { root -> runCatching { json(File(root, "export-callback.json"), JSONObject().put("episodeId", episode).put("uri", uri.toString())) } }
    }
    suspend fun beginJob(context: Context, episode: String, id: String) {
        if (!BuildConfig.SHORT_PRODUCT_E2E) return
        val marker = File(context.filesDir, "${ShortProductPolicy.DIRECTORY}/active.json")
        if (!marker.isFile) return
        val control = JSONObject(marker.readText())
        if (control.getString("episodeId") != episode) return
        ShortProductPolicy.load(context)
        check(control.getString("contractSha256") == ShortProductPolicy.CONTRACT_SHA)
        val run = control.getString("runId"); require(ShortProductPolicy.validRun(run))
        require(id.matches(Regex("[a-zA-Z0-9-]+")))
        check(Application.getProcessName() == "${context.packageName}:generation" && job == null)
        val app = context.applicationContext as PodcastApplication
        val entity = requireNotNull(app.database.podcastDao().job(id))
        check(entity.episodeId == episode && entity.status in setOf("QUEUED", "RUNNING"))
        require(app.repository.episode(episode).reviewEnabled) { "Owned scenario requires persisted review ON before any model work" }
        val parent = File(context.filesDir, "${ShortProductPolicy.DIRECTORY}/$run/jobs")
        val previous = parent.listFiles().orEmpty().filter { it.isDirectory }.map {
            JSONObject(File(it, "started.json").readText()).getString("kind")
        }
        val order = listOf("SCRIPT", "AGENT_EDIT", "AUDIO")
        require(previous.size < order.size && previous.toSet() == order.take(previous.size).toSet() && entity.kind == order[previous.size]) {
            "Outside scoped one-script/one-edit/one-audio job sequence; no extra inference"
        }
        val root = File(parent, id)
        check(!root.exists() && root.mkdirs())
        val start = SystemClock.elapsedRealtime()
        json(File(root, "started.json"), JSONObject().put("episodeId", episode).put("jobId", id).put("kind", entity.kind)
            .put("process", Application.getProcessName()).put("pid", Process.myPid()).put("elapsedRealtimeMs", start)
            .put("profiling", "UNAVAILABLE_BY_DESIGN").put("normalOutputLimits", true))
        write(File(root, "proc-status-before.txt"), File("/proc/self/status").readBytes())
        if (entity.kind == "AUDIO") {
            val (_, chapters) = app.repository.lockedChapterData(episode)
            ShortProductPolicy.validateFinal(chapters.map { it.stableChapterId to it.text })
            json(File(root, "locked-inputs.json"), JSONObject().put("chapters", JSONArray(chapters.map {
                val normalized = SupertonicTextNormalizer.normalize(it.text)
                JSONObject().put("id", it.stableChapterId).put("text", it.text).put("normalized", normalized)
                    .put("normalizedCodepoints", normalized.codePointCount(0, normalized.length))
                    .put("inputEvidence", "source normalization, not captured native buffers")
            })))
        }
        val timer = Timer("short-product-job-bound", true)
        job = Job(root, entity.kind, start, timer)
        timer.schedule(object : TimerTask() {
            override fun run() {
                runCatching { json(File(root, "timeout.json"), JSONObject().put("jobId", id).put("kind", entity.kind)
                    .put("limitMs", ShortProductPolicy.jobMs(entity.kind)).put("action", "kill isolated generation process; no retry")) }
                Process.killProcess(Process.myPid())
            }
        }, ShortProductPolicy.jobMs(entity.kind))
    }
    fun beforeRequest(mode: String, request: String, system: String, limit: Int) {
        val current = job ?: return
        val prefix = File(current.root, "request-${current.requests + 1}")
        write(File(prefix.path + ".json"), request.toByteArray())
        write(File(prefix.path + "-system.txt"), system.toByteArray())
        json(File(prefix.path + "-options.json"), JSONObject().put("mode", mode).put("contextTokens", 8192)
            .put("maxOutputTokens", limit).put("freshConversation", true).put("topK", 1).put("thinking", false)
            .put("actualOutputTokens", JSONObject.NULL).put("stopReason", JSONObject.NULL)
            .put("metricLimitation", "normal synchronous API; no token/TTFT metrics or partial output on native failure"))
        ShortProductPolicy.validateRequest(current.kind, current.requests, mode, request, limit)
        current.pending = prefix
    }
    fun send(conversation: Conversation, request: String): String {
        val current = job ?: return conversation.sendMessage(request).toString()
        val prefix = requireNotNull(current.pending)
        current.pending = null; current.requests++
        val start = SystemClock.elapsedRealtime()
        json(File(prefix.path + "-send-start.json"), JSONObject().put("elapsedRealtimeMs", start))
        try {
            val raw = conversation.sendMessage(request).toString() // same normal API, before production parsing
            write(File(prefix.path + "-raw.txt"), raw.toByteArray())
            json(File(prefix.path + "-returned.json"), JSONObject().put("elapsedMs", SystemClock.elapsedRealtime() - start)
                .put("rawSha256", ShortProductPolicy.hash(raw.toByteArray())))
            return raw
        } catch (error: Throwable) {
            runCatching { json(File(prefix.path + "-failure.json"), JSONObject().put("error", error.stackTraceToString())
                .put("partialOutput", JSONObject.NULL).put("partialReason", "normal synchronous API did not return")) }
            throw error
        }
    }
    fun endJob() {
        val current = job ?: return
        current.timer.cancel(); job = null
        // Optional observations cannot prevent normal service cleanup or erase a committed WAV.
        runCatching {
            write(File(current.root, "proc-status-after.txt"), File("/proc/self/status").readBytes())
            write(File(current.root, "maps-after.txt"), File("/proc/self/maps").readBytes())
            json(File(current.root, "finished.json"), JSONObject().put("logicalSendCalls", current.requests)
                .put("elapsedMs", SystemClock.elapsedRealtime() - current.start).put("serviceFinallyReached", true))
        }
    }
}
