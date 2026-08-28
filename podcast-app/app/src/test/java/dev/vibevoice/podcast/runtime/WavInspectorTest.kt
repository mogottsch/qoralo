package dev.vibevoice.podcast.runtime

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.io.RandomAccessFile
import java.io.IOException

class WavInspectorTest {
    @get:Rule val temporaryFolder = TemporaryFolder()

    @Test fun parsesAndHashesActualPcm16Mono44100() {
        val wav = wav("valid.wav", ShortArray(4_410) { if (it % 2 == 0) 1_000 else -1_000 })
        val result = WavInspector.inspectSupertonicOutput(wav)
        assertTrue(result.sha256.matches(Regex("[0-9a-f]{64}")))
        assertTrue(result.frameCount == 4_410L && result.sampleRateHz == 44_100 && result.channelCount == 1)
    }

    @Test fun rejectsTruncatedWav() {
        val wav = wav("truncated.wav", ShortArray(100) { 100 })
        RandomAccessFile(wav, "rw").use { it.setLength(45) }
        assertThrows(IllegalArgumentException::class.java) { WavInspector.inspectSupertonicOutput(wav) }
    }

    @Test fun rejectsCorruptContainer() {
        val wav = wav("corrupt.wav", ShortArray(100) { 100 })
        RandomAccessFile(wav, "rw").use { it.writeBytes("NOPE") }
        assertThrows(IllegalArgumentException::class.java) { WavInspector.inspectSupertonicOutput(wav) }
    }

    @Test fun rejectsSilentOutput() {
        val wav = wav("silent.wav", ShortArray(1_000))
        assertThrows(IllegalArgumentException::class.java) { WavInspector.inspectSupertonicOutput(wav) }
    }

    @Test fun rejectsHeavilyClippedOutput() {
        val wav = wav("clipped.wav", ShortArray(1_000) { Short.MAX_VALUE })
        assertThrows(IllegalArgumentException::class.java) { WavInspector.inspectSupertonicOutput(wav) }
    }

    @Test fun atomicCommitReplacesStaleDestination() {
        val directory = temporaryFolder.newFolder()
        val temporary = File(directory, ".chapter.wav.tmp").apply { writeBytes(byteArrayOf(1, 2, 3)) }
        val destination = File(directory, "chapter.wav").apply { writeBytes(byteArrayOf(9, 9)) }
        AtomicArtifactCommit.commit(temporary, destination)
        assertFalse(temporary.exists())
        assertArrayEquals(byteArrayOf(1, 2, 3), destination.readBytes())
    }

    @Test fun failedAtomicCommitPreservesStaleDestination() {
        val directory = temporaryFolder.newFolder()
        val temporary = File(directory, ".chapter.wav.tmp").apply { writeBytes(byteArrayOf(1, 2, 3)) }
        val destination = File(directory, "chapter.wav").apply { writeBytes(byteArrayOf(9, 9)) }
        assertThrows(IOException::class.java) {
            AtomicArtifactCommit.commit(temporary, destination) { _, _, _ -> throw IOException("injected commit failure") }
        }
        assertTrue(temporary.exists())
        assertArrayEquals(byteArrayOf(9, 9), destination.readBytes())
    }

    private fun wav(name: String, samples: ShortArray): File {
        val file = File(temporaryFolder.root, name)
        RandomAccessFile(file, "rw").use { out ->
            val dataBytes = samples.size * 2
            out.writeBytes("RIFF"); out.u32(36L + dataBytes); out.writeBytes("WAVEfmt "); out.u32(16)
            out.u16(1); out.u16(1); out.u32(44_100); out.u32(88_200); out.u16(2); out.u16(16)
            out.writeBytes("data"); out.u32(dataBytes.toLong())
            samples.forEach { out.u16(it.toInt() and 0xFFFF) }
        }
        return file
    }

    private fun RandomAccessFile.u16(value: Int) { write(value and 255); write((value ushr 8) and 255) }
    private fun RandomAccessFile.u32(value: Long) { u16((value and 0xFFFF).toInt()); u16(((value ushr 16) and 0xFFFF).toInt()) }
}
