package dev.vibevoice.podcast.runtime

import dev.vibevoice.podcast.model.SupertonicModelContract
import org.junit.Assert.assertThrows
import org.junit.Assert.assertEquals
import org.junit.Test

class SupertonicContractTest {
    private val contract = SupertonicModelContract(239, 238, 144, 5, 44_100, 1, 16,
        "ONNX Runtime 1.27.1 + QAIRT 2.49.0.260730")
    private val provenance = RuntimeProvenance(
        1, "SUPERTONIC_3_EXTERNAL_CONTEXT", "QNN_HTP", "ONNX Runtime 1.27.1 / QAIRT 2.49.0.260730", false,
        setOf("duration_context", "text_context", "vector_context", "vocoder_context", "htp",
            "text_length=239", "latent_length=238", "latent_channels=144", "diffusion_steps=5",
            "sample_rate_hz=44100", "channel_count=1", "pcm_bits=16"),
    )

    @Test fun acceptsExactAuthenticatedContractAndNativeReadiness() {
        assertEquals(provenance, requireMatchingSupertonicContract(contract, provenance))
    }

    @Test fun rejectsAnyNativeShapeMismatch() {
        val mismatch = provenance.copy(readyComponents = provenance.readyComponents - "text_length=239" + "text_length=240")
        assertThrows(IllegalArgumentException::class.java) { requireMatchingSupertonicContract(contract, mismatch) }
    }

    @Test fun rejectsImpreciseRuntimeBuildIdentity() {
        assertThrows(IllegalArgumentException::class.java) {
            requireMatchingSupertonicContract(contract, provenance.copy(runtimeVersion = "ONNX Runtime 1.27.1 / QNN 2.49"))
        }
    }
}
