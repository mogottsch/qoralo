package dev.qoralo.podcast.runtime

import dev.qoralo.podcast.data.ArtifactStore
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.io.RandomAccessFile

class WavAssembler(
    private val artifacts: ArtifactStore,
    private val commitGeneration: (File, File) -> Unit = AtomicArtifactCommit::commitDirectory,
) {
    data class Input(val chapterId: String, val title: String, val file: File)
    data class Result(
        val audioFile: File,
        val audioSha256: String,
        val audioByteCount: Long,
        val timelineFile: File,
        val timelineSha256: String,
        val timelineByteCount: Long,
        val totalFrames: Long,
        val durationMs: Long,
    )

    fun assemble(episodeId: String, generationId: String, chapters: List<Input>, pauseMs: Int = 700): Result {
        require(chapters.isNotEmpty()) { "No chapter audio to assemble" }
        require(generationId.matches(Regex("[A-Za-z0-9._-]+"))) { "Unsafe generation ID" }
        val generationDestination = artifacts.finalGenerationDir(episodeId, generationId)
        val finalRoot = generationDestination.parentFile.also { it?.mkdirs() }
        val stagedGeneration = File(finalRoot, ".$generationId.tmp")
        require(!generationDestination.exists()) { "Generation destination already exists" }
        stagedGeneration.deleteRecursively()
        require(stagedGeneration.mkdirs()) { "Could not stage final episode generation" }
        val temporary = File(stagedGeneration, "episode.wav")
        val timelineTemporary = File(stagedGeneration, "chapter-timeline.json")
        val pauseFrames = 44_100L * pauseMs / 1_000L
        val timeline = JSONArray()
        var cursor = 0L

        try {
            RandomAccessFile(temporary, "rw").use { output ->
                output.setLength(0); output.write(ByteArray(44))
                chapters.forEachIndexed { index, chapter ->
                    WavInspector.inspectSupertonicOutput(chapter.file)
                    val parsed = pcmData(chapter.file)
                    val start = cursor
                    RandomAccessFile(chapter.file, "r").use { input ->
                        input.seek(parsed.offset)
                        var remaining = parsed.bytes
                        val buffer = ByteArray(64 * 1024)
                        while (remaining > 0) {
                            val count = input.read(buffer, 0, minOf(buffer.size.toLong(), remaining).toInt())
                            require(count > 0) { "Unexpected end of chapter WAV" }
                            output.write(buffer, 0, count); remaining -= count
                        }
                    }
                    cursor += parsed.bytes / 2L
                    timeline.put(JSONObject().put("chapterId", chapter.chapterId).put("title", chapter.title)
                        .put("startFrame", start).put("endFrame", cursor)
                        .put("startMs", start * 1_000L / 44_100L).put("endMs", cursor * 1_000L / 44_100L))
                    if (index < chapters.lastIndex) { writeSilence(output, pauseFrames); cursor += pauseFrames }
                }
                val dataBytes = cursor * 2L
                require(dataBytes <= 0xFFFF_FFFFL - 36L) { "Episode WAV exceeds RIFF size limit" }
                output.seek(0); writeHeader(output, dataBytes); output.fd.sync()
            }
            WavInspector.inspectSupertonicOutput(temporary)

            val timelineJson = JSONObject().put("schemaVersion", 1).put("sampleRateHz", 44_100)
                .put("totalFrames", cursor).put("chapters", timeline).toString()
            FileOutputStream(timelineTemporary).use { stream ->
                stream.write(timelineJson.toByteArray(Charsets.UTF_8)); stream.fd.sync()
            }
            validateTimeline(timelineTemporary, chapters.size, cursor)

            commitGeneration(stagedGeneration, generationDestination)
            val destination = artifacts.finalWav(episodeId, generationId)
            val timelineDestination = artifacts.timeline(episodeId, generationId)
            return Result(
                destination, artifacts.sha256(destination), destination.length(),
                timelineDestination, artifacts.sha256(timelineDestination), timelineDestination.length(),
                cursor, cursor * 1_000L / 44_100L,
            )
        } catch (error: Throwable) {
            stagedGeneration.deleteRecursively()
            throw error
        }
    }

    private fun validateTimeline(file: File, expectedChapters: Int, expectedFrames: Long) {
        val json = JSONObject(file.readText(Charsets.UTF_8))
        require(json.getInt("schemaVersion") == 1 && json.getInt("sampleRateHz") == 44_100)
        require(json.getLong("totalFrames") == expectedFrames)
        val chapters = json.getJSONArray("chapters")
        require(chapters.length() == expectedChapters)
        var previousEnd = 0L
        for (index in 0 until chapters.length()) {
            val chapter = chapters.getJSONObject(index)
            val start = chapter.getLong("startFrame")
            val end = chapter.getLong("endFrame")
            require(start >= previousEnd && end > start)
            previousEnd = end
        }
    }

    private fun pcmData(file: File): PcmData {
        RandomAccessFile(file, "r").use { wav ->
            wav.seek(12)
            var data: PcmData? = null
            while (wav.filePointer + 8 <= wav.length()) {
                val id = wav.readAscii(4); val size = wav.readU32(); val content = wav.filePointer
                require(content + size <= wav.length())
                if (id == "data") { require(data == null); data = PcmData(content, size) }
                wav.seek(content + size + (size and 1L))
            }
            return requireNotNull(data)
        }
    }

    private fun writeSilence(output: RandomAccessFile, frames: Long) {
        var remaining = frames * 2L; val zeroes = ByteArray(16 * 1024)
        while (remaining > 0) { val count = minOf(remaining, zeroes.size.toLong()).toInt(); output.write(zeroes, 0, count); remaining -= count }
    }

    private fun writeHeader(output: RandomAccessFile, dataBytes: Long) {
        output.writeBytes("RIFF"); output.writeU32(36L + dataBytes); output.writeBytes("WAVEfmt "); output.writeU32(16)
        output.writeU16(1); output.writeU16(1); output.writeU32(44_100); output.writeU32(88_200); output.writeU16(2); output.writeU16(16)
        output.writeBytes("data"); output.writeU32(dataBytes)
    }

    private data class PcmData(val offset: Long, val bytes: Long)
    private fun RandomAccessFile.readAscii(length: Int): String = ByteArray(length).also(::readFully).toString(Charsets.US_ASCII)
    private fun RandomAccessFile.readU16(): Int = readUnsignedByte() or (readUnsignedByte() shl 8)
    private fun RandomAccessFile.readU32(): Long = readU16().toLong() or (readU16().toLong() shl 16)
    private fun RandomAccessFile.writeU16(value: Int) { write(value and 255); write((value ushr 8) and 255) }
    private fun RandomAccessFile.writeU32(value: Long) { writeU16((value and 0xFFFF).toInt()); writeU16(((value ushr 16) and 0xFFFF).toInt()) }
}
