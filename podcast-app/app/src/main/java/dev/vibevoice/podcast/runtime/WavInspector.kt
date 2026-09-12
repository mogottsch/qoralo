package dev.vibevoice.podcast.runtime

import java.io.File
import java.io.RandomAccessFile
import java.security.MessageDigest
import kotlin.math.abs

object WavInspector {
    fun inspectSupertonicOutput(file: File): AudioMetadata {
        require(file.isFile && file.length() >= 44) { "Chapter WAV is missing or truncated" }
        var format = -1
        var channels = -1
        var sampleRate = -1
        var byteRate = -1L
        var blockAlign = -1
        var bits = -1
        var dataOffset = -1L
        var dataBytes = -1L
        var fmtCount = 0
        var dataCount = 0
        RandomAccessFile(file, "r").use { wav ->
            require(wav.readAscii(4) == "RIFF") { "Chapter output is not RIFF" }
            val riffBytes = wav.readU32()
            require(riffBytes + 8L == wav.length()) { "RIFF size does not match the file" }
            require(wav.readAscii(4) == "WAVE") { "Chapter output is not WAVE" }
            while (wav.filePointer + 8 <= wav.length()) {
                val id = wav.readAscii(4)
                val size = wav.readU32()
                val content = wav.filePointer
                val next = content + size + (size and 1L)
                require(content + size <= wav.length() && next <= wav.length()) { "Invalid WAV chunk" }
                when (id) {
                    "fmt " -> {
                        fmtCount++
                        require(fmtCount == 1 && size >= 16) { "Duplicate or invalid WAV format chunk" }
                        format = wav.readU16()
                        channels = wav.readU16()
                        sampleRate = wav.readU32().toInt()
                        byteRate = wav.readU32()
                        blockAlign = wav.readU16()
                        bits = wav.readU16()
                    }
                    "data" -> {
                        dataCount++
                        require(dataCount == 1) { "Duplicate WAV data chunk" }
                        dataOffset = content
                        dataBytes = size
                    }
                }
                wav.seek(next)
            }
            require(wav.filePointer == wav.length()) { "Trailing or partial WAV chunk" }
            require(fmtCount == 1 && dataCount == 1) { "WAV must have exactly one format and data chunk" }
            require(format == 1) { "Supertonic WAV must be linear PCM" }
            require(channels == 1) { "Supertonic WAV must be mono" }
            require(sampleRate == 44_100) { "Supertonic WAV must be 44.1 kHz" }
            require(bits == 16) { "Supertonic WAV must be PCM16" }
            val expectedBlockAlign = channels * bits / 8
            require(blockAlign == expectedBlockAlign && byteRate == sampleRate.toLong() * expectedBlockAlign) { "WAV rate/alignment fields are inconsistent" }
            require(dataOffset >= 0 && dataBytes > 0 && dataBytes % blockAlign == 0L) { "Supertonic WAV has no valid samples" }

            wav.seek(dataOffset)
            val frames = dataBytes / blockAlign
            var nonZero = 0L
            var clipped = 0L
            var remaining = dataBytes
            val samples = ByteArray(65_536)
            while (remaining > 0) {
                val count = minOf(remaining, samples.size.toLong()).toInt()
                wav.readFully(samples, 0, count)
                var index = 0
                while (index < count) {
                    val sample = ((samples[index].toInt() and 255) or ((samples[index + 1].toInt() and 255) shl 8)).toShort().toInt()
                    if (sample != 0) nonZero++
                    if (abs(sample) >= 32_760) clipped++
                    index += 2
                }
                remaining -= count
            }
            require(nonZero > frames / 100L) { "Supertonic WAV is silent" }
            require(clipped <= frames / 10L) { "Supertonic WAV is heavily clipped" }
        }
        return AudioMetadata(sampleRate, channels, dataBytes / blockAlign, sha256(file))
    }

    private fun sha256(file: File): String {
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

    private fun RandomAccessFile.readAscii(length: Int): String = ByteArray(length).also(::readFully).toString(Charsets.US_ASCII)
    private fun RandomAccessFile.readU16(): Int = readUnsignedByte() or (readUnsignedByte() shl 8)
    private fun RandomAccessFile.readI16(): Short = readU16().toShort()
    private fun RandomAccessFile.readU32(): Long = readU16().toLong() or (readU16().toLong() shl 16)
}
