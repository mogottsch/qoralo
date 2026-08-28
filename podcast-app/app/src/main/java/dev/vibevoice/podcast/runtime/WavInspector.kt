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
        var bits = -1
        var dataOffset = -1L
        var dataBytes = -1L
        RandomAccessFile(file, "r").use { wav ->
            require(wav.readAscii(4) == "RIFF") { "Chapter output is not RIFF" }
            wav.readU32()
            require(wav.readAscii(4) == "WAVE") { "Chapter output is not WAVE" }
            while (wav.filePointer + 8 <= wav.length()) {
                val id = wav.readAscii(4)
                val size = wav.readU32()
                val content = wav.filePointer
                require(size >= 0 && content + size <= wav.length()) { "Invalid WAV chunk" }
                when (id) {
                    "fmt " -> {
                        require(size >= 16) { "Invalid WAV format chunk" }
                        format = wav.readU16()
                        channels = wav.readU16()
                        sampleRate = wav.readU32().toInt()
                        wav.readU32()
                        wav.readU16()
                        bits = wav.readU16()
                    }
                    "data" -> {
                        dataOffset = content
                        dataBytes = size
                    }
                }
                wav.seek(content + size + (size and 1L))
            }
            require(format == 1) { "Supertonic WAV must be linear PCM" }
            require(channels == 1) { "Supertonic WAV must be mono" }
            require(sampleRate == 44_100) { "Supertonic WAV must be 44.1 kHz" }
            require(bits == 16) { "Supertonic WAV must be PCM16" }
            require(dataOffset >= 0 && dataBytes > 0 && dataBytes % 2L == 0L) { "Supertonic WAV has no valid samples" }

            wav.seek(dataOffset)
            val frames = dataBytes / 2L
            var nonZero = 0L
            var clipped = 0L
            var index = 0L
            while (index < frames) {
                val sample = wav.readI16()
                if (sample != 0.toShort()) nonZero++
                if (abs(sample.toInt()) >= 32_760) clipped++
                index++
            }
            require(nonZero > frames / 100L) { "Supertonic WAV is silent" }
            require(clipped <= frames / 10L) { "Supertonic WAV is heavily clipped" }
        }
        return AudioMetadata(sampleRate, channels, dataBytes / 2L, sha256(file))
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
