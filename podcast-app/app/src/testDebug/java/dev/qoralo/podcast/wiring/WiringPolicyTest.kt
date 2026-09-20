package dev.qoralo.podcast.wiring

import dev.qoralo.podcast.runtime.SupertonicTextNormalizer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class WiringPolicyTest {
    private fun bytes(name: String) = requireNotNull(javaClass.getResourceAsStream("/wiring/$name")).use { it.readBytes() }

    @Test fun exactInputsAndCeilingsArePinnedAndNonBenchmark() {
        val contract = WiringContract.parse(::bytes)
        assertEquals(256, contract.outputTokens("outline"))
        assertEquals(768, contract.outputTokens("chapter"))
        assertEquals(4, contract.inputs.size)
        assertTrue(contract.json.getBoolean("noAutomaticInferenceRetries"))
        assertEquals(300_000L, contract.deadlineMs("gemma-chapter"))
        assertTrue(contract.totalMs < WiringContract.INSTRUMENTATION_TIMEOUT_MS)
        assertThrows(IllegalStateException::class.java) { contract.outputTokens("source_notes") }
    }

    @Test fun sameSizeInputMutationIsRejected() {
        assertThrows(IllegalArgumentException::class.java) {
            WiringContract.parse { name -> bytes(name).also { if (name == "source.txt") it[0] = (it[0].toInt() xor 1).toByte() } }
        }
    }

    @Test fun deadlineMutationCannotSelfAuthorize() {
        assertThrows(IllegalArgumentException::class.java) {
            WiringContract.parse { name -> bytes(name).let { if (name == "contract.json") it + ' '.code.toByte() else it } }
        }
    }

    @Test fun canonicalShortFitsAndRealisticChapterRequiresAnActualNativeRejection() {
        val inputs = WiringContract.parse(::bytes).inputs
        assertEquals("424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67", WiringContract.hash(bytes("canonical-short.txt")))
        val short = SupertonicTextNormalizer.normalize(inputs.getValue("canonical-short.txt"))
        val realistic = SupertonicTextNormalizer.normalize(inputs.getValue("realistic-chapter.txt"))
        assertTrue(short.codePointCount(0, short.length) + 9 <= 239)
        assertTrue(realistic.codePointCount(0, realistic.length) + 9 > 239)
        assertTrue(realistic.split(Regex("\\s+")).size >= 120)
    }

    @Test fun runIdentifiersCannotEscapeEvidenceDirectory() {
        assertTrue(WiringContract.validRunId("wiring-20260910-a"))
        listOf("../wiring-a", "wiring-../../a", "wiring-", "a", "wiring-A", "wiring-a/b").forEach { assertFalse(WiringContract.validRunId(it)) }
    }
}
