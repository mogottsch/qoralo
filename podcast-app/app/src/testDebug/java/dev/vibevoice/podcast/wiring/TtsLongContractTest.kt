package dev.vibevoice.podcast.wiring

import dev.vibevoice.podcast.model.ModelPackRequirement
import dev.vibevoice.podcast.model.ModelPackVerifier
import dev.vibevoice.podcast.model.ModelRoute
import dev.vibevoice.podcast.model.SupertonicModelContract
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File

class TtsLongContractTest {
    private fun asset(name: String) = requireNotNull(javaClass.classLoader?.getResourceAsStream("tts-long/$name")).use { it.readBytes() }
    private fun contract() = TtsOnlyContract.parseVariant(TtsOnlyContract.LONG_SHA256, ::asset)

    @Test fun longInputIsPinnedWholeNoncanonicalAndNaturallyTimed() {
        val c = contract()
        assertTrue(c.isLongProbe)
        assertEquals("supertonic-3-t2048-l2048-parity", c.packId)
        assertEquals("long-library-01.wav", c.outputName)
        assertEquals(1327, c.text.toByteArray(Charsets.UTF_8).size)
        assertEquals(1324, c.json.getJSONObject("input").getInt("normalizedCodepoints"))
        assertFalse(c.json.getJSONObject("input").getBoolean("canonical"))
        assertFalse(c.json.getJSONObject("input").getBoolean("durationForced"))
        assertEquals(90, c.json.getJSONObject("input").getInt("targetAudioSeconds"))
        assertEquals(1, c.json.getInt("ttsRequests"))
        assertEquals(1, c.json.getInt("capacityProbes"))
        assertEquals(0, c.json.getInt("gemmaRequests"))
        assertEquals(0, c.json.getInt("retries"))
        assertEquals(5, c.json.getInt("steps"))
        assertEquals(1.0, c.json.getDouble("speed"), 0.0)
        assertEquals("M1/SID5", c.voice)
        assertEquals(60_000L, c.deadlineMs("verify"))
        assertEquals(120_000L, c.deadlineMs("load"))
        assertEquals(180_000L, c.deadlineMs("render"))
        assertEquals(30_000L, c.deadlineMs("close"))
        assertEquals(420, c.json.getInt("serviceSeconds"))
        assertEquals(435_000L, c.driverMs)
        assertEquals(450, c.json.getInt("hostSeconds"))
    }

    @Test fun changedTextAndCrossVariantApprovalsAreRejected() {
        assertThrows(IllegalArgumentException::class.java) {
            TtsOnlyContract.parseVariant(TtsOnlyContract.LONG_SHA256) { name ->
                if (name == "narration.txt") asset(name) + '\n'.code.toByte() else asset(name)
            }
        }
        assertTrue(TtsOnlyContract.validRunId("tts-long-first-01", TtsOnlyContract.LONG_SHA256))
        assertFalse(TtsOnlyContract.validRunId("tts-only-first-01", TtsOnlyContract.LONG_SHA256))
        assertFalse(TtsOnlyContract.validRunId("tts-long-first-01", TtsOnlyContract.SHA256))
        assertFalse(TtsOnlyContract.validRunId("tts-long-../../x", TtsOnlyContract.LONG_SHA256))
        assertFalse(TtsOnlyContract.approvedHash("unreviewed"))
    }

    @Test fun explicitLocalPackPassesProductionVerifierAndFullReconstruction() {
        val path = System.getenv("PODCAST_TTS_LONG_PACK")
        assumeTrue("Explicit host data-pack verification only; never a model/session load", path != null)
        val c = contract()
        val root = File(requireNotNull(path))
        val pack = ModelPackVerifier().verify(root, ModelPackRequirement(
            ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP, c.packId, c.manifestSha))
        val shape = pack.contract as SupertonicModelContract
        assertEquals(2048, shape.textLength)
        assertEquals(2048, shape.latentLength)
        assertEquals(144, shape.latentChannels)
        assertEquals(5, shape.diffusionSteps)
        assertEquals(13, pack.files.size)
        val r = c.reconstructedTokens(root)
        assertEquals(1333, r.getInt("wrappedCodepoints"))
        assertEquals(2048, r.getJSONArray("ids").length())
        val mask = r.getJSONArray("mask")
        assertEquals(2048, mask.length())
        repeat(2048) { i ->
            assertEquals(if (i < 1333) 1.0 else 0.0, mask.getDouble(i), 0.0)
            if (i >= 1333) assertEquals(0L, r.getJSONArray("ids").getLong(i))
        }
        assertEquals("8402ca48e5189a8950138580b0fff64db6f072f24ac07cd54ba8b2fbb9883b30", r.getString("indexerSha256"))
        assertEquals("b6d15b9e1fbb4a8efca004427bd05963a2b01ce11b780f3843956d82605d076a", r.getString("voiceSha256"))
        assertTrue(r.getString("evidenceKind").contains("not native-buffer capture"))
    }
}
