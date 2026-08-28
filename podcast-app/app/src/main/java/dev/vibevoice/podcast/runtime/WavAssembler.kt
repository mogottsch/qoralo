package dev.vibevoice.podcast.runtime

import dev.vibevoice.podcast.data.ArtifactStore
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.RandomAccessFile

class WavAssembler(private val artifacts: ArtifactStore) {
    data class Input(val chapterId: String, val title: String, val file: File)
    data class Result(val file: File, val totalFrames: Long, val durationMs: Long)

    fun assemble(episodeId: String, chapters: List<Input>, pauseMs: Int = 700): Result {
        require(chapters.isNotEmpty()) { "No chapter audio to assemble" }
        val destination = artifacts.finalWav(episodeId)
        destination.parentFile?.mkdirs()
        val temporary = File(destination.parentFile, ".${destination.name}.tmp")
        temporary.delete()
        val pauseFrames = 44_100L * pauseMs / 1_000L
        val timeline = JSONArray()
        var cursor = 0L

        try {
            RandomAccessFile(temporary, "rw").use { output ->
                output.setLength(0)
                output.write(ByteArray(44))
                chapters.forEachIndexed { index, chapter ->
                    val parsed = pcmData(chapter.file)
                    require(parsed.sampleRate == 44_100 && parsed.channels == 1 && parsed.bits == 16) { "Chapter WAV formats do not match" }
                    val start = cursor
                    RandomAccessFile(chapter.file, "r").use { input ->
                        input.seek(parsed.offset)
                        var remaining = parsed.bytes
                        val buffer = ByteArray(64 * 1024)
                        while (remaining > 0) {
                            val count = input.read(buffer, 0, minOf(buffer.size.toLong(), remaining).toInt())
                            require(count > 0) { "Unexpected end of chapter WAV" }
                            output.write(buffer, 0, count)
                            remaining -= count
                        }
                    }
                    cursor += parsed.bytes / 2L
                    timeline.put(JSONObject()
                        .put("chapterId", chapter.chapterId)
                        .put("title", chapter.title)
                        .put("startFrame", start)
                        .put("endFrame", cursor)
                        .put("startMs", start * 1_000L / 44_100L)
                        .put("endMs", cursor * 1_000L / 44_100L))
                    if (index < chapters.lastIndex) {
                        writeSilence(output, pauseFrames)
                        cursor += pauseFrames
                    }
                }
                val dataBytes = cursor * 2L
                require(dataBytes <= 0xFFFF_FFFFL - 36L) { "Episode WAV exceeds RIFF size limit" }
                output.seek(0)
                writeHeader(output, dataBytes)
                output.fd.sync()
            }
            WavInspector.inspectSupertonicOutput(temporary)
            if (destination.exists() && !destination.delete()) error("Could not replace final WAV")
            if (!temporary.renameTo(destination)) error("Could not commit final WAV")
            val timelineBytes = JSONObject()
                .put("schemaVersion", 1)
                .put("sampleRateHz", 44_100)
                .put("chapters", timeline)
                .toString().toByteArray(Charsets.UTF_8)
            artifacts.writeAtomically(artifacts.timeline(episodeId), timelineBytes)
            return Result(destination, cursor, cursor * 1_000L / 44_100L)
        } catch (error: Throwable) {
            temporary.delete()
            throw error
        }
    }

    private fun pcmData(file: File): PcmData {
        RandomAccessFile(file, "r").use { wav ->
            require(wav.readAscii(4) == "RIFF")
            wav.readU32()
            require(wav.readAscii(4) == "WAVE")
            var format = -1
            var channels = -1
            var sampleRate = -1
            var bits = -1
            var data: PcmData? = null
            while (wav.filePointer + 8 <= wav.length()) {
                val id = wav.readAscii(4)
                val size = wav.readU32()
                val content = wav.filePointer
                require(content + size <= wav.length())
                if (id == "fmt ") {
                    format = wav.readU16()
                    channels = wav.readU16()
                    sampleRate = wav.readU32().toInt()
                    wav.readU32(); wav.readU16(); bits = wav.readU16()
                } else if (id == "data") {
                    data = PcmData(content, size, sampleRate, channels, bits)
                }
                wav.seek(content + size + (size and 1L))
            }
            require(format == 1)
            return requireNotNull(data).copy(sampleRate = sampleRate, channels = channels, bits = bits)
        }
    }

    private fun writeSilence(output: RandomAccessFile, frames: Long) {
        var remaining = frames * 2L
        val zeroes = ByteArray(16 * 1024)
        while (remaining > 0) {
            val count = minOf(remaining, zeroes.size.toLong()).toInt()
            output.write(zeroes, 0, count)
            remaining -= count
        }
    }

    private fun writeHeader(output: RandomAccessFile, dataBytes: Long) {
        output.writeBytes("RIFF")
        output.writeU32(36L + dataBytes)
        output.writeBytes("WAVEfmt ")
        output.writeU32(16)
        output.writeU16(1)
        output.writeU16(1)
        output.writeU32(44_100)
        output.writeU32(88_200)
        output.writeU16(2)
        output.writeU16(16)
        output.writeBytes("data")
        output.writeU32(dataBytes)
    }

    private data class PcmData(val offset: Long, val bytes: Long, val sampleRate: Int, val channels: Int, val bits: Int)
    private fun RandomAccessFile.readAscii(length: Int): String = ByteArray(length).also(::readFully).toString(Charsets.US_ASCII)
    private fun RandomAccessFile.readU16(): Int = readUnsignedByte() or (readUnsignedByte() shl 8)
    private fun RandomAccessFile.readU32(): Long = readU16().toLong() or (readU16().toLong() shl 16)
    private fun RandomAccessFile.writeU16(value: Int) { write(value and 255); write((value ushr 8) and 255) }
    private fun RandomAccessFile.writeU32(value: Long) { writeU16((value and 0xFFFF).toInt()); writeU16(((value ushr 16) and 0xFFFF).toInt()) }
}
