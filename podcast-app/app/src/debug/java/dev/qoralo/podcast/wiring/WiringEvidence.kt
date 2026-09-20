package dev.qoralo.podcast.wiring

import android.os.Process
import android.os.SystemClock
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.nio.file.Files
import java.nio.file.StandardOpenOption
import java.security.MessageDigest

/** Private append-only evidence. Terminal status is written once, including before process kill. */
class WiringEvidence(val root: File) {
    @Volatile var terminal = false
        private set

    @Synchronized fun write(name: String, text: String) {
        require(name.matches(Regex("[a-zA-Z0-9._-]+")))
        Files.write(File(root, name).toPath(), text.toByteArray(Charsets.UTF_8), StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)
        FileOutputStream(File(root, name), true).use { it.fd.sync() }
    }

    fun json(name: String, value: JSONObject) = write(name, value.toString(2))

    @Synchronized fun event(kind: String, detail: String) {
        val value = JSONObject().put("kind", kind).put("detail", detail)
            .put("elapsedRealtimeMs", SystemClock.elapsedRealtime()).put("pid", Process.myPid())
        FileOutputStream(File(root, "events.jsonl"), true).use {
            it.write((value.toString() + "\n").toByteArray(Charsets.UTF_8)); it.fd.sync()
        }
    }

    @Synchronized fun finish(status: String, stage: String, error: Throwable? = null) {
        if (terminal) return
        terminal = true
        json("service-result.json", JSONObject().put("status", status).put("stage", stage)
            .put("pid", Process.myPid()).put("elapsedRealtimeMs", SystemClock.elapsedRealtime())
            .put("error", error?.stackTraceToString() ?: JSONObject.NULL)
            .put("claim", "wiring observations only; provider evidence requires separate verification; not product E2E"))
    }

    fun snapshot(label: String) {
        for (name in listOf("maps", "status")) {
            runCatching { write("$label-proc-$name.txt", File("/proc/self/$name").readText()) }
                .onFailure { event("unavailable", "$label /proc/self/$name: $it") }
        }
        runCatching {
            write("$label-fds.txt", File("/proc/self/fd").listFiles().orEmpty().joinToString("\n") { fd ->
                "${fd.name}: ${runCatching { Files.readSymbolicLink(fd.toPath()).toString() }.getOrElse { "unavailable: $it" }}"
            })
        }.onFailure { event("unavailable", "$label fd snapshot: $it") }
    }

    fun inventory(): JSONObject = JSONObject().apply {
        root.walkTopDown().filter { it.isFile && it.name != "inventory.json" }.forEach { file ->
            put(file.relativeTo(root).invariantSeparatorsPath, JSONObject().put("bytes", file.length()).put("sha256", sha256(file)))
        }
    }

    companion object {
        fun sha256(file: File): String {
            val digest = MessageDigest.getInstance("SHA-256")
            file.inputStream().use { input ->
                val bytes = ByteArray(65536)
                while (true) { val n = input.read(bytes); if (n < 0) break; digest.update(bytes, 0, n) }
            }
            return digest.digest().joinToString("") { "%02x".format(it) }
        }
    }
}
