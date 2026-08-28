package dev.vibevoice.podcast.runtime

import dev.vibevoice.podcast.data.ArtifactStore
import org.json.JSONObject
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.io.IOException
import java.io.RandomAccessFile

class WavAssemblerTest {
    @get:Rule val temporary = TemporaryFolder()

    @Test fun assemblesTwoChaptersWithExact700msTimelineOffset() {
        val store = store()
        val first = wav("first.wav", 1_000, 700)
        val second = wav("second.wav", 2_000, -700)
        val result = WavAssembler(store).assemble("episode", "job-1", listOf(
            WavAssembler.Input("one", "One", first), WavAssembler.Input("two", "Two", second),
        ))
        assertEquals(33_870L, result.totalFrames)
        assertEquals(33_870L, WavInspector.inspectSupertonicOutput(result.audioFile).frameCount)
        val timeline = JSONObject(result.timelineFile.readText()).getJSONArray("chapters")
        assertEquals(0L, timeline.getJSONObject(0).getLong("startFrame"))
        assertEquals(1_000L, timeline.getJSONObject(0).getLong("endFrame"))
        assertEquals(31_870L, timeline.getJSONObject(1).getLong("startFrame"))
        assertEquals(33_870L, timeline.getJSONObject(1).getLong("endFrame"))
    }

    @Test fun rejectsCorruptChapterBeforePublishingGeneration() {
        val store = store()
        val corrupt = temporary.newFile("corrupt.wav").apply { writeText("not wav") }
        assertThrows(IllegalArgumentException::class.java) {
            WavAssembler(store).assemble("episode", "job-corrupt", listOf(WavAssembler.Input("one", "One", corrupt)))
        }
        assertFalse(store.finalGenerationDir("episode", "job-corrupt").exists())
    }

    @Test fun staleGenerationDestinationIsNeverDestroyed() {
        val store = store()
        val destination = store.finalGenerationDir("episode", "job-stale").apply { mkdirs() }
        val marker = File(destination, "old").apply { writeBytes(byteArrayOf(9, 8, 7)) }
        assertThrows(IllegalArgumentException::class.java) {
            WavAssembler(store).assemble("episode", "job-stale", listOf(WavAssembler.Input("one", "One", wav("stale.wav", 100, 10))))
        }
        assertArrayEquals(byteArrayOf(9, 8, 7), marker.readBytes())
    }

    @Test fun failedSingleDirectoryCommitPublishesNeitherAudioNorTimeline() {
        val store = store()
        val assembler = WavAssembler(store) { _, _ -> throw IOException("injected directory commit failure") }
        assertThrows(IOException::class.java) {
            assembler.assemble("episode", "job-fail", listOf(WavAssembler.Input("one", "One", wav("failure.wav", 100, 10))))
        }
        assertFalse(store.finalGenerationDir("episode", "job-fail").exists())
        assertTrue(store.finalGenerationDir("episode", "job-fail").parentFile!!.listFiles().orEmpty().none { it.name.contains("job-fail") })
    }

    private fun store() = ArtifactStore(temporary.newFolder(), temporary.newFolder())

    private fun wav(name: String, frames: Int, sample: Int): File {
        val file = File(temporary.root, name)
        RandomAccessFile(file, "rw").use { out ->
            val bytes = frames * 2L
            out.writeBytes("RIFF"); out.u32(36 + bytes); out.writeBytes("WAVEfmt "); out.u32(16)
            out.u16(1); out.u16(1); out.u32(44_100); out.u32(88_200); out.u16(2); out.u16(16)
            out.writeBytes("data"); out.u32(bytes)
            repeat(frames) { out.u16(sample and 0xFFFF) }
        }
        return file
    }

    private fun RandomAccessFile.u16(value: Int) { write(value and 255); write((value ushr 8) and 255) }
    private fun RandomAccessFile.u32(value: Long) { u16((value and 0xFFFF).toInt()); u16(((value ushr 16) and 0xFFFF).toInt()) }
}
