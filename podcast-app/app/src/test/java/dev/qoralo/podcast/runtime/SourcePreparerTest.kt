package dev.qoralo.podcast.runtime

import dev.qoralo.podcast.data.ArtifactStore
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.io.InputStream

class SourcePreparerTest {
    @get:Rule val temporary = TemporaryFolder()

    @Test fun chunksEveryGemmaNotesRequestWithinBudgetAndReducesNotes() = runTest {
        val engine = NotesEngine()
        val source = SourceMaterial("source", "Large", "word ".repeat(120_000))
        val notes = SourcePreparer().prepare(listOf(source), engine)
        assertTrue(engine.requestLengths.isNotEmpty())
        assertTrue(engine.requestLengths.all { it <= SourcePreparer.MAX_REQUEST_CHARS })
        assertTrue(notes.sumOf { it.text.length } <= SourcePreparer.MAX_PREPARED_CHARS)
        assertTrue(engine.requestLengths.size > SourcePreparer().chunk(source.text).size)
    }

    @Test fun chunkingPreservesNormalizedTextWithoutTruncation() {
        val text = ("paragraph words here\n\n".repeat(2_000)).trim()
        val chunks = SourcePreparer().chunk(text)
        assertTrue(chunks.all { it.length <= SourcePreparer.MAX_REQUEST_CHARS })
        assertEquals(text.replace(Regex("\\s+"), " "), chunks.joinToString(" ").replace(Regex("\\s+"), " "))
    }

    @Test fun sourceByteLimitIsEnforcedDuringStreaming() {
        val store = ArtifactStore(temporary.newFolder(), temporary.newFolder())
        val input = RepeatingInputStream(ArtifactStore.MAX_SOURCE_BYTES.toLong() + 1L)
        assertThrows(IllegalArgumentException::class.java) { store.writeSource("episode", "source", input) }
        assertTrue(input.readCount <= ArtifactStore.MAX_SOURCE_BYTES.toLong() + DEFAULT_BUFFER_SIZE)
        assertTrue(store.episodesRoot.walkTopDown().none(File::isFile))
    }

    private class NotesEngine : LlmEngine {
        val requestLengths = mutableListOf<Int>()
        override val provenance: RuntimeProvenance? = null
        override suspend fun load(pack: dev.qoralo.podcast.model.VerifiedModelPack) = Unit
        override suspend fun createSourceNotes(source: SourceMaterial, chunkIndex: Int, chunkCount: Int): SourceMaterial {
            requestLengths += source.text.length
            return SourceMaterial("notes-$chunkIndex-${requestLengths.size}", source.title, source.text.take(SourcePreparer.MAX_NOTE_CHARS))
        }
        override suspend fun createOutline(sources: List<SourceMaterial>, instructions: String) = error("unused")
        override suspend fun createChapter(outline: EpisodeOutline, chapter: OutlineChapter, sources: List<SourceMaterial>, instructions: String, preceding: List<ChapterRecap>) = error("unused")
        override suspend fun editScript(requestJson: String) = error("unused")
        override fun close() = Unit
    }

    private class RepeatingInputStream(private val length: Long) : InputStream() {
        var readCount = 0L
        override fun read(): Int = if (readCount++ < length) 'a'.code else -1
        override fun read(buffer: ByteArray, offset: Int, len: Int): Int {
            if (readCount >= length) return -1
            val count = minOf(len.toLong(), length - readCount).toInt()
            buffer.fill('a'.code.toByte(), offset, offset + count)
            readCount += count
            return count
        }
    }
}
