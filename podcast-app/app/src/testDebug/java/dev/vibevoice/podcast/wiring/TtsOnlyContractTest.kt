package dev.vibevoice.podcast.wiring

import org.junit.Assert.*
import org.junit.Test
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files

class TtsOnlyContractTest {
    private fun asset(name: String) = requireNotNull(javaClass.classLoader?.getResourceAsStream("tts-only/$name")).use { it.readBytes() }
    @Test fun exactCanonicalAndScopeArePinned() {
        val contract = TtsOnlyContract.parse(::asset)
        assertEquals(226, contract.text.toByteArray(Charsets.UTF_8).size)
        assertEquals(TtsOnlyContract.TEXT_SHA, WiringContract.hash(contract.text.toByteArray(Charsets.UTF_8)))
        assertEquals("M1/SID5", contract.voice)
        assertEquals("canonical-short", contract.chapterId)
        assertEquals(1, contract.json.getInt("ttsRequests"))
        assertEquals(0, contract.json.getInt("gemmaRequests"))
        assertEquals(0, contract.json.getInt("capacityProbes"))
        assertEquals(0, contract.json.getInt("retries"))
        assertEquals(120_000L, contract.deadlineMs("load"))
        assertEquals(90_000L, contract.deadlineMs("render"))
    }
    @Test fun changedInputIsRejectedWithoutTruncation() {
        assertThrows(IllegalArgumentException::class.java) { TtsOnlyContract.parse { name -> if (name == "canonical.txt") asset(name) + '\n'.code.toByte() else asset(name) } }
    }
    @Test fun deterministicReconstructionHasNativeShapesAndHonestProvenance() {
        val root = Files.createTempDirectory("tts-token-test").toFile()
        try {
            val assets = File(root, "assets").apply { mkdir() }
            val indexer = ByteBuffer.allocate(65536 * 4).order(ByteOrder.LITTLE_ENDIAN)
            repeat(65536) { indexer.putInt(it) }
            File(assets, "unicode-indexer.i32").writeBytes(indexer.array())
            File(assets, "voice.bin").writeBytes(byteArrayOf(1, 2, 3))
            val record = TtsOnlyContract.parse(::asset).reconstructedTokens(root)
            assertEquals(235, record.getInt("wrappedCodepoints"))
            assertEquals(239, record.getJSONArray("ids").length())
            assertEquals(239, record.getJSONArray("mask").length())
            assertEquals('<'.code.toLong(), record.getJSONArray("ids").getLong(0))
            assertEquals(0L, record.getJSONArray("ids").getLong(238))
            assertEquals(0.0, record.getJSONArray("mask").getDouble(238), 0.0)
            assertTrue(record.getString("evidenceKind").contains("not native-buffer capture"))
            assertEquals(5, record.getInt("steps"))
            assertEquals(1.0, record.getDouble("speed"), 0.0)
        } finally { root.deleteRecursively() }
    }
    @Test fun runIdsAreExplicitAndBounded() {
        assertTrue(TtsOnlyContract.validRunId("tts-only-first-01"))
        assertFalse(TtsOnlyContract.validRunId("duration-old"))
        assertFalse(TtsOnlyContract.validRunId("tts-only-../../x"))
    }
}
