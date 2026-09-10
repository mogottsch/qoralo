package dev.vibevoice.podcast.e2e

import android.content.Context
import dev.vibevoice.podcast.BuildConfig
import dev.vibevoice.podcast.runtime.SupertonicTextNormalizer
import org.json.JSONObject
import java.security.MessageDigest

/** Fixed short plumbing scenario, never a global product word-count policy. */
internal object ShortProductPolicy {
    const val CONTRACT_SHA = "a39106380003a3a4c7b83c2f45066399e204d8aefade77ec88866f9062eccfc4"
    const val DIRECTORY = "short-product-e2e"
    const val DRIVER_MS = 900_000L
    const val SHORT_MANIFEST = "dc4ac737924d7d62e57ff5e166707198095c49e51d77cfed04a44d9e9435952d"
    val chapterIds = listOf("chapter-1", "chapter-2")
    fun hash(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
    fun validRun(run: String) = run.matches(Regex("short-product-[a-z0-9-]{1,64}"))
    fun load(context: Context): JSONObject {
        check(BuildConfig.SHORT_PRODUCT_E2E && BuildConfig.SUPERTONIC_PACK_ID == "supertonic-3")
        check(BuildConfig.SUPERTONIC_MANIFEST_SHA256 == SHORT_MANIFEST)
        val bytes = context.assets.open("$DIRECTORY/contract.json").use { it.readBytes() }
        check(hash(bytes) == CONTRACT_SHA)
        val value = JSONObject(bytes.toString(Charsets.UTF_8))
        check(BuildConfig.GEMMA_MANIFEST_SHA256 == value.getString("gemmaManifestSha256"))
        val files = value.getJSONObject("files")
        files.keys().forEach { name -> check(hash(context.assets.open("$DIRECTORY/$name").use { it.readBytes() }) == files.getString(name)) }
        return value
    }
    fun asset(context: Context, name: String) = context.assets.open("$DIRECTORY/$name").bufferedReader().use { it.readText() }
    fun modes(kind: String): List<String> = when (kind) {
        "SCRIPT" -> listOf("source_notes", "outline", "chapter", "chapter")
        "AGENT_EDIT" -> listOf("edit")
        "AUDIO" -> emptyList()
        else -> error("Unknown owned job kind")
    }
    fun jobMs(kind: String): Long = when (kind) {
        "SCRIPT" -> 420_000L
        "AGENT_EDIT" -> 180_000L
        "AUDIO" -> 150_000L
        else -> error("Unknown owned job kind")
    }
    fun validateRequest(kind: String, index: Int, mode: String, request: String, limit: Int) {
        require(modes(kind).getOrNull(index) == mode) { "Outside scoped logical request sequence; no extra inference" }
        require(limit == if (mode in setOf("source_notes", "outline")) 1200 else 4096)
        if (mode == "chapter") {
            val json = JSONObject(request)
            val chapters = json.getJSONObject("outline").getJSONArray("chapters")
            require(List(chapters.length()) { chapters.getJSONObject(it).getString("id") } == chapterIds) { "Outline differs from scoped two chapters" }
            require(json.getString("requestedChapterId") == chapterIds[index - 2])
        }
    }
    fun validateFinal(chapters: List<Pair<String, String>>, enforceWordTarget: Boolean = true) {
        require(chapters.map { it.first } == chapterIds) { "Final scoped chapter IDs/order differ" }
        chapters.forEach { (_, text) ->
            require(text.isNotBlank()) { "Empty chapter is not valid narration" }
            if (enforceWordTarget) require(text.trim().split(Regex("\\s+")).size in 20..25) { "Final draft misses scoped20–25word target; preserve it without lock/retry" }
            val normalized = SupertonicTextNormalizer.normalize(text)
            require(normalized.codePointCount(0, normalized.length) <= 190) { "Final chapter exceeds scoped short input capacity" }
        }
    }
}
