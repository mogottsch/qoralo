package dev.vibevoice.podcast.diagnostics

import android.content.Context
import dev.vibevoice.podcast.BuildConfig
import dev.vibevoice.podcast.PodcastApplication
import dev.vibevoice.podcast.model.VerifiedModelPack
import dev.vibevoice.podcast.runtime.GemmaRequestException
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest

/** Disabled by default, debug-only, ONE exact fresh episode's SCRIPT job. Not a generation controller. */
internal object UserFailureDiagnostics {
    private var receipt: PrivateFailureReceipt? = null

    suspend fun beginJob(context: Context, episodeId: String, jobId: String) {
        receipt = null
        // Optional diagnostics never changes an existing job outcome, including when storage is unavailable.
        runCatching {
            val files = context.filesDir.canonicalFile
            val marker = File(files, "user-failure-diagnostics/active.json")
            if (!marker.isFile || marker.length() > 8192 || marker.canonicalFile != marker.absoluteFile) return
            if (File(files, "short-product-e2e/active.json").exists()) return
            val bytes = marker.readBytes()
            val scope = UserFailureCaptureScope(bytes)
            val control = scope.control
            if (control.getString("episodeId") != episodeId) return
            val root = File(marker.parentFile!!, scope.runId)
            if (root.exists()) return
            require(root.canonicalFile == root.absoluteFile)
            val app = context.applicationContext as PodcastApplication
            val episode = app.repository.episode(episodeId)
            val job = app.repository.latestJob(episodeId) ?: return
            val sources = app.database.podcastDao().sources(episodeId)
            require(job.id == jobId)
            val apkHash = hashFile(File(context.applicationInfo.sourceDir))
            scope.requireOwnership(episodeId, job.episodeId, job.kind, job.status, episode.phase,
                episode.reviewEnabled, episode.activeRevisionId != null, episode.lockedRevisionId != null,
                episode.instructions, sources.map { it.sha256 }, BuildConfig.GEMMA_MANIFEST_SHA256, apkHash)
            // Atomic mkdir in the receipt constructor consumes the one capture. Existing roots are never reused.
            receipt = PrivateFailureReceipt(root, JSONObject().put("schemaVersion", 1).put("runId", scope.runId)
                .put("episodeId", episodeId).put("jobId", jobId).put("jobKind", job.kind)
                .put("pid", android.os.Process.myPid()).put("process", android.app.Application.getProcessName())
                .put("appApkSha256", apkHash).put("versionName", BuildConfig.VERSION_NAME)
                .put("controlSha256", PrivateFailureReceipt.sha256(bytes)).put("control", control)
                .put("privateContent", true).put("noAutomaticRetry", true))
        }
    }

    fun verifiedGemma(pack: VerifiedModelPack) {
        val current = receipt ?: return
        runCatching { current.modelBinding(JSONObject().put("manifestSha256", pack.manifestSha256)
            .put("packId", pack.id).put("packVersion", pack.version).put("route", pack.route.name)
            .put("abi", pack.androidAbi).put("runtimeApiVersion", pack.runtimeApiVersion)
            .put("runtime", "LiteRT-LM 0.16.1").put("backend", "GPU").put("cpuFallback", false)
            .put("files", JSONArray(pack.files.map { f -> JSONObject().put("path", f.relativePath)
                .put("role", f.role.name).put("bytes", f.byteCount).put("sha256", f.sha256) }))) }
    }
    fun beforeRequest(mode: String, request: String, instruction: String, limit: Int, responseSchema: String? = null) {
        receipt?.beforeRequest(mode, request, instruction, limit, responseSchema)
    }
    fun responseReturned(raw: String) { receipt?.responseReturned(raw) }
    fun failed(error: GemmaRequestException) { receipt?.failed(error) }
    fun jobFailed(error: Throwable) { receipt?.jobFailed(error) }
    fun endJob() { val current = receipt; receipt = null; current?.finished() }

    private fun hashFile(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { stream -> val buffer = ByteArray(65536); while (true) {
            val count = stream.read(buffer); if (count < 0) break; digest.update(buffer, 0, count)
        } }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}
