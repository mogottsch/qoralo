package dev.vibevoice.podcast.runtime

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

class ProviderTextFrontendTest {
    private fun hash(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
    @Test fun allSyntheticCasesMatchPinnedPythonSegmentationNormalizationAndIds() {
        val data = JSONObject(requireNotNull(javaClass.getResourceAsStream("/provider-frontend/golden.json")).bufferedReader().use { it.readText() })
        val mapping = data.getJSONObject("indexerEntriesForFixtures")
        val indexer = IntArray(65536) { -1 }
        mapping.keys().forEach { k -> if (k.toInt() in indexer.indices) indexer[k.toInt()] = mapping.getInt(k) }
        val cases = data.getJSONArray("cases")
        repeat(cases.length()) { i ->
            val c = cases.getJSONObject(i); val raw = c.getString("raw")
            assertEquals("normalization case $i", c.getString("normalized"), ProviderTextFrontend.normalize(raw))
            val chunks = c.getJSONArray("chunks")
            assertEquals("segmentation case $i", (0 until chunks.length()).map(chunks::getString), ProviderTextFrontend.segmentRaw(raw))
            val spans=ProviderTextFrontend.segmentSpans(raw)
            assertEquals(ProviderTextFrontend.segmentRaw(raw),spans.map { it.raw })
            spans.forEachIndexed { n, span ->
                assertTrue(span.startUtf16 in 0 until span.endUtf16 && span.endUtf16<=raw.length)
                assertFalse(Character.isLowSurrogate(raw[span.startUtf16]))
                assertFalse(Character.isHighSurrogate(raw[span.endUtf16-1]))
                if(n>0) assertTrue(spans[n-1].endUtf16<=span.startUtf16)
            }
            val valid = runCatching { ProviderTextFrontend.validateOriginal(raw, indexer) }.isSuccess
            assertEquals("character admission case $i", c.getBoolean("validOriginal"), valid)
            if (valid && chunks.length() > 0) {
                val prepared = ProviderTextFrontend.prepare(raw, indexer)
                val expected = c.getJSONArray("processedChunks"); val ids = c.getJSONArray("chunkIds")
                prepared.forEachIndexed { n, segment ->
                    assertEquals("processed chunk $i/$n", expected.getString(n), segment.processed)
                    val expectedIds = ids.getJSONArray(n)
                    assertArrayEquals("IDs $i/$n", LongArray(expectedIds.length()) { expectedIds.getLong(it) }, segment.ids)
                }
            }
        }
    }
    @Test fun passageOffsetsRetainOriginalWhitespaceAndSupplementaryCharacters() {
        val first="😀 First.\t Second."
        val second="word ".repeat(100).trim()+"."
        val original=" \t$first\r\n\r\n$second  "
        val spans=ProviderTextFrontend.segmentSpans(original)
        assertEquals(2,spans.size)
        assertEquals(first,original.substring(spans[0].startUtf16,spans[0].endUtf16))
        assertEquals(second,original.substring(spans[1].startUtf16,spans[1].endUtf16))
        assertTrue(spans[1].raw.codePointCount(0,spans[1].raw.length)>300)
    }
    @Test fun overlongSentencesStayWholeAndNormalizationDoesNotChooseBoundaries() {
        val sentence = "word ".repeat(100).trim()+"."
        assertEquals(listOf(sentence), ProviderTextFrontend.segmentRaw(sentence))
        val raw = "😀".repeat(200)+". End."
        assertEquals(listOf(raw), ProviderTextFrontend.segmentRaw(raw)) // Codepoints, not UTF-16 units.
        assertEquals("<en>. End.</en>", ProviderTextFrontend.normalize(raw))
        assertEquals("a\u0300\u0315", ProviderUnicode14.normalize("a\u0315\u0300"))
        assertTrue(ProviderUnicode14.isWord(0x10781)) // Unicode14, independent of JVM/Android data versions.
    }
    @Test fun exactPrivateAcceptedReferenceMatchesAllFifteenFrozenFrontendChunks() {
        val bundlePath = System.getenv("PODCAST_PROVIDER_REFERENCE_BUNDLE")
        val textPath = System.getenv("PODCAST_PROVIDER_REFERENCE_TEXT")
        val indexerPath = System.getenv("PODCAST_PROVIDER_INDEXER_JSON")
        assumeTrue("Explicit private reference verification only; zero model calls", bundlePath != null && textPath != null && indexerPath != null)
        val bundle = File(requireNotNull(bundlePath)); val text = File(requireNotNull(textPath)).readBytes()
        assertEquals("cbfd5bbef581f0e793b86a568f8d4aa87fe857f413e5c2ea4780b558fc71600b", hash(text))
        val indexerJson = org.json.JSONArray(File(requireNotNull(indexerPath)).readText())
        val prepared = ProviderTextFrontend.prepare(text.toString(Charsets.UTF_8), IntArray(indexerJson.length()) { indexerJson.getInt(it) })
        val manifest = JSONObject(File(bundle, "manifest.json").readText()).getJSONArray("chunks")
        assertEquals(15, prepared.size)
        val spans=ProviderTextFrontend.segmentSpans(text.toString(Charsets.UTF_8))
        assertEquals(prepared.map { it.raw },spans.map { it.raw })
        prepared.forEachIndexed { i, segment ->
            val expected = manifest.getJSONObject(i)
            assertEquals("raw chunk hash $i", expected.getString("raw_chunk_sha256"), hash(segment.raw.toByteArray()))
            assertEquals("processed hash $i", expected.getString("processed_sha256"), hash(segment.processed.toByteArray()))
            val bytes = ByteBuffer.allocate(segment.ids.size * 8).order(ByteOrder.LITTLE_ENDIAN)
            segment.ids.forEach(bytes::putLong)
            assertEquals("token IDs hash $i", expected.getString("ids_sha256"), hash(bytes.array()))
            assertEquals(expected.getInt("text_extent"), segment.textExtent)
        }
    }
}
