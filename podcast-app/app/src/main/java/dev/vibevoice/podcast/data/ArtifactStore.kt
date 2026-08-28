package dev.vibevoice.podcast.data

import android.content.Context
import org.json.JSONObject
import java.io.File
import java.io.InputStream
import java.security.MessageDigest
import java.text.Normalizer

class ArtifactStore(context: Context) {
    val episodesRoot = File(context.filesDir, "episodes")
    val modelPacksRoot = File(context.noBackupFilesDir, "model-packs")

    fun writeSource(episodeId: String, sourceId: String, input: InputStream): StoredText {
        val raw = input.bufferedReader(Charsets.UTF_8).use { it.readText() }
        val normalized = normalizeSource(raw)
        require(normalized.isNotBlank()) { "Source is empty" }
        require(normalized.toByteArray().size <= MAX_SOURCE_BYTES) { "Source exceeds the 5 MB MVP limit" }
        val relative = "$episodeId/sources/$sourceId.txt"
        val file = File(episodesRoot, relative)
        writeAtomically(file, normalized.toByteArray(Charsets.UTF_8))
        return StoredText(relative, normalized, file.length(), sha256(file))
    }

    fun readText(relativePath: String): String = resolveEpisodeFile(relativePath).readText(Charsets.UTF_8)

    fun writeRevision(episodeId: String, revisionId: String, title: String, chapters: List<ChapterDraft>): StoredFile {
        val relative = "$episodeId/script/$revisionId.json"
        val bytes = ScriptCodec.encode(title, chapters).toByteArray(Charsets.UTF_8)
        val file = File(episodesRoot, relative)
        writeAtomically(file, bytes)
        return StoredFile(relative, file.length(), sha256(file))
    }

    fun chapterWav(episodeId: String, position: Int): File =
        File(episodesRoot, "$episodeId/chapters/chapter-${position.toString().padStart(3, '0')}.wav")

    fun finalWav(episodeId: String): File = File(episodesRoot, "$episodeId/final/episode.wav")
    fun timeline(episodeId: String): File = File(episodesRoot, "$episodeId/final/chapter-timeline.json")

    fun relativeToEpisodes(file: File): String = file.canonicalFile.relativeTo(episodesRoot.canonicalFile).invariantSeparatorsPath

    fun resolveEpisodeFile(relativePath: String): File {
        val root = episodesRoot.canonicalFile
        val file = File(root, relativePath).canonicalFile
        require(file.toPath().startsWith(root.toPath())) { "Artifact path escapes episode store" }
        return file
    }

    fun modelPackRoot(routeDirectory: String): File = File(modelPacksRoot, "$routeDirectory/current")

    fun writeAtomically(destination: File, bytes: ByteArray) {
        destination.parentFile?.mkdirs()
        val temp = File(destination.parentFile, ".${destination.name}.tmp")
        temp.outputStream().use { output -> output.write(bytes); output.fdSync() }
        if (destination.exists() && !destination.delete()) error("Could not replace ${destination.name}")
        if (!temp.renameTo(destination)) error("Could not commit ${destination.name}")
    }

    fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun java.io.FileOutputStream.fdSync() = fd.sync()

    companion object {
        const val MAX_SOURCE_BYTES = 5 * 1024 * 1024

        fun normalizeSource(value: String): String = Normalizer.normalize(value.replace("\r\n", "\n").replace('\r', '\n'), Normalizer.Form.NFC)
            .filter { it == '\n' || it == '\t' || !Character.isISOControl(it) }
            .lineSequence().joinToString("\n") { it.trimEnd() }.trim()
    }
}

data class StoredText(val relativePath: String, val text: String, val byteCount: Long, val sha256: String)
data class StoredFile(val relativePath: String, val byteCount: Long, val sha256: String)
data class ChapterDraft(val stableId: String, val title: String, val text: String)

object ScriptCodec {
    fun encode(title: String, chapters: List<ChapterDraft>): String = buildString {
        append("{\"schemaVersion\":1,\"title\":")
        append(JSONObject.quote(title))
        append(",\"chapters\":[")
        chapters.forEachIndexed { index, chapter ->
            if (index > 0) append(',')
            append("{\"id\":").append(JSONObject.quote(chapter.stableId))
            append(",\"title\":").append(JSONObject.quote(chapter.title))
            append(",\"text\":").append(JSONObject.quote(chapter.text)).append('}')
        }
        append("]}")
    }
}
