package dev.qoralo.podcast.runtime

import dev.qoralo.podcast.BuildConfig
import dev.qoralo.podcast.data.ArtifactStore
import dev.qoralo.podcast.data.ChapterDraft
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.security.MessageDigest

/** Non-neural admission and immutable content-addressed AUDIO plan. Legacy data/schema stay unchanged. */
object ProviderAudioPlan {
    const val PACK_ID = "supertonic-3-provider"
    const val PACK_SHA256 = "423429c6642da131ac62511e3b233f1a121b97975aa5b6e9aa755bb13a927670"
    val selected: Boolean get() = BuildConfig.SUPERTONIC_PACK_ID == PACK_ID && BuildConfig.SUPERTONIC_MANIFEST_SHA256 == PACK_SHA256
    private fun hash(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
    fun idsHash(ids: LongArray): String {
        val bytes = ByteBuffer.allocate(ids.size * 8).order(ByteOrder.LITTLE_ENDIAN)
        ids.forEach(bytes::putLong); return hash(bytes.array())
    }

    /** Manifest/indexer identity and file extents only. Full neural-file hashes/ABI are checked again at runtime load. */
    fun indexer(artifacts: ArtifactStore): IntArray {
        require(selected) { "Provider pack is not selected" }
        val root = artifacts.modelPackRoot(PACK_ID)
        require(root.isDirectory && !Files.isSymbolicLink(root.toPath()))
        val manifest = File(root, "manifest.json")
        require(manifest.isFile && manifest.length() in 1..1_048_576 && !Files.isSymbolicLink(manifest.toPath()))
        val bytes = manifest.readBytes(); require(hash(bytes) == PACK_SHA256) { "Provider capability manifest changed" }
        val value = JSONObject(bytes.toString(Charsets.UTF_8))
        val files = value.getJSONArray("files")
        var table: IntArray? = null
        repeat(files.length()) { i ->
            val item = files.getJSONObject(i); val path = File(root, item.getString("path"))
            require(path.canonicalFile.toPath().startsWith(root.canonicalFile.toPath()) && !Files.isSymbolicLink(path.toPath()))
            require(path.isFile && path.length() == item.getLong("bytes")) { "Provider asset is unavailable" }
            if (item.getString("role") == "SUPERTONIC_UNICODE_INDEXER") {
                val raw = path.readBytes()
                require(raw.size == 65536 * 4 && hash(raw) == item.getString("sha256")) { "Provider indexer changed" }
                val view = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN);table = IntArray(65536) { view.int }
            }
        }
        return requireNotNull(table)
    }

    fun assess(artifacts: ArtifactStore, texts: List<String>): ScriptTextCapacity {
        if (!selected) return SupertonicTextCapacity.configured(texts)
        val indexer = runCatching { indexer(artifacts) }.getOrElse {
            return ScriptTextCapacity(320, emptyList(), true, "The provider voice pack is unavailable or failed its capability integrity check. Your complete draft stays editable.")
        }
        val chapters = texts.mapIndexed { i, text ->
            val segments = runCatching { ProviderTextFrontend.prepare(text, indexer) }.getOrNull()
            val max = segments?.maxOfOrNull { it.textExtent }
            ChapterTextCapacity(i, segments?.sumOf { it.textExtent - 9 }, segments?.sumOf { it.textExtent },
                segments != null && segments.isNotEmpty() && max != null && max <= 320, segments?.size ?: 0, max)
        }
        return ScriptTextCapacity(320, chapters, true)
    }

    private fun encoded(artifacts: ArtifactStore, episode: String, revision: String, revisionHash: String, nonce: String, chapters: List<ChapterDraft>): ByteArray {
        val indexer = indexer(artifacts)
        val rows = chapters.map { chapter ->
            val segments = ProviderTextFrontend.prepare(chapter.text, indexer)
            require(segments.isNotEmpty() && segments.all { it.textExtent <= 320 }) { "Provider sentence segment cannot be submitted" }
            JSONObject().put("id", chapter.stableId).put("titleSha256", hash(chapter.title.toByteArray(Charsets.UTF_8)))
                .put("textSha256", hash(chapter.text.toByteArray(Charsets.UTF_8)))
                .put("segments", JSONArray(segments.map { segment -> JSONObject()
                    .put("rawSha256", hash(segment.raw.toByteArray(Charsets.UTF_8)))
                    .put("processedSha256", hash(segment.processed.toByteArray(Charsets.UTF_8)))
                    .put("idsSha256", idsHash(segment.ids)).put("nativeTextLength", segment.textExtent) }))
        }
        return JSONObject().put("schemaVersion", 1).put("nonce", nonce).put("episodeId", episode)
            .put("revisionId", revision).put("revisionSha256", revisionHash).put("packSha256", PACK_SHA256)
            .put("frontendVersion", ProviderTextFrontend.VERSION).put("unicodeTableSha256", ProviderUnicode14.TABLE_SHA256)
            .put("textBucket", 320).put("nativeLatentLimit", 512).put("steps", 8).put("speedHundredths", 105)
            .put("seedPerChapter", 20260911).put("gapFrames", 13230).put("waveExtent", "FULL_NATIVE_VOCODER")
            .put("nativeDurationCheckedDuringRender", true).put("chapters", JSONArray(rows)).toString().toByteArray(Charsets.UTF_8)
    }
    data class Saved(val jobId: String, val file: File)

    /** SHA256 of the plan is the AUDIO job ID: durable pack/revision/frontend binding without reusing mutable fields. */
    fun save(artifacts: ArtifactStore, episode: String, revision: String, revisionHash: String, nonce: String, chapters: List<ChapterDraft>): Saved {
        val bytes = encoded(artifacts, episode, revision, revisionHash, nonce, chapters)
        val id = hash(bytes);val file = artifacts.resolveEpisodeFile("$episode/audio-plans/$id.json")
        val temporary = File(file.parentFile, ".${file.name}.tmp")
        require(bytes.size <= 8_388_608 && !file.exists() && !temporary.exists()) { "Audio plan target or size is invalid" }
        try { artifacts.writeAtomically(file, bytes) }
        catch (error: Throwable) { file.delete(); temporary.delete(); throw error }
        return Saved(id, file)
    }

    fun verify(artifacts: ArtifactStore, episode: String, job: String, revision: String, revisionHash: String, packHash: String, chapters: List<ChapterDraft>) {
        require(selected && packHash == PACK_SHA256 && Regex("[a-f0-9]{64}").matches(job)) { "Audio job is not bound to the current provider pack" }
        val file = artifacts.resolveEpisodeFile("$episode/audio-plans/$job.json")
        require(file.isFile && file.length() in 1..8_388_608 && !Files.isSymbolicLink(file.toPath())) { "Audio plan is missing" }
        val bytes = file.readBytes();require(hash(bytes) == job) { "Audio plan integrity mismatch" }
        val nonce = JSONObject(bytes.toString(Charsets.UTF_8)).getString("nonce")
        val expected = encoded(artifacts, episode, revision, revisionHash, nonce, chapters)
        require(bytes.contentEquals(expected)) { "Audio plan no longer matches the exact revision/pack/frontend" }
    }
}
