package dev.vibevoice.podcast.wiring

import dev.vibevoice.podcast.runtime.RuntimeDiagnostics
import org.junit.Assert.*
import org.junit.Test
import java.nio.file.Files

class TtsProfileOffContractTest {
    private fun asset(directory: String, name: String) = requireNotNull(javaClass.classLoader?.getResourceAsStream("$directory/$name")).use { it.readBytes() }
    private fun contract(hash: String, directory: String) = TtsOnlyContract.parseVariant(hash) { asset(directory, it) }

    @Test fun onlyPinnedObservabilityChangesAndOriginalContractsDefaultOn() {
        val previous = contract(TtsOnlyContract.LONG_SHA256, "tts-long")
        val off = contract(TtsOnlyContract.PROFILE_OFF_SHA256, "tts-long-profile-off")
        val canonical = contract(TtsOnlyContract.SHA256, "tts-only")
        assertTrue(previous.collectProfiles); assertTrue(canonical.collectProfiles); assertFalse(off.collectProfiles)
        assertEquals(previous.text, off.text)
        assertEquals(previous.chapterId, off.chapterId)
        assertEquals("long-library-01", off.chapterId)
        assertEquals(previous.packId, off.packId)
        assertEquals(previous.driverMs, off.driverMs)
        assertEquals(TtsOnlyContract.PROFILE_OFF_SHA256, off.sha256)
        assertEquals("tts-long-profile-off", off.assetDirectory)
        assertEquals("tts-long", off.evidenceDirectory)
        val labels = setOf("id", "benchmarkScope")
        previous.json.keys().forEach { key ->
            if (key !in labels) assertEquals(key, previous.json.get(key).toString(), off.json.get(key).toString())
        }
        assertTrue(off.json.getString("profilingEvidence").startsWith("UNAVAILABLE_BY_DESIGN"))
    }

    @Test fun profileOffUsesItsOwnExactApprovalAndPreservesLongRunNamespace() {
        assertTrue(TtsOnlyContract.approvedHash(TtsOnlyContract.PROFILE_OFF_SHA256))
        assertTrue(TtsOnlyContract.isLongHash(TtsOnlyContract.PROFILE_OFF_SHA256))
        assertTrue(TtsOnlyContract.validRunId("tts-long-profile-off-once", TtsOnlyContract.PROFILE_OFF_SHA256))
        assertFalse(TtsOnlyContract.validRunId("tts-only-once", TtsOnlyContract.PROFILE_OFF_SHA256))
        assertThrows(IllegalArgumentException::class.java) {
            contract(TtsOnlyContract.LONG_SHA256, "tts-long-profile-off")
        }
        assertThrows(IllegalArgumentException::class.java) {
            TtsOnlyContract.parseVariant(TtsOnlyContract.PROFILE_OFF_SHA256) { name ->
                if (name == "narration.txt") asset("tts-long-profile-off", name) + 'x'.code.toByte() else asset("tts-long-profile-off", name)
            }
        }
    }

    @Test fun existingDisabledHookReturnsEmptyWithoutCreatingProfileDirectory() {
        val root = Files.createTempDirectory("tts-profile-switch-").toFile()
        try {
            RuntimeDiagnostics.disable()
            val off = contract(TtsOnlyContract.PROFILE_OFF_SHA256, "tts-long-profile-off")
            if (off.collectProfiles) RuntimeDiagnostics.enableTtsOnly(WiringEvidence(root))
            assertEquals("", RuntimeDiagnostics.qnnProfileDirectory())
            assertFalse(root.resolve("qnn-profiles").exists())
            // Positive control: the unchanged hook still enables the original profiled mode.
            RuntimeDiagnostics.enableTtsOnly(WiringEvidence(root))
            assertEquals(root.resolve("qnn-profiles").absolutePath, RuntimeDiagnostics.qnnProfileDirectory())
            assertTrue(root.resolve("qnn-profiles").isDirectory)
            RuntimeDiagnostics.disable()
            assertEquals("", RuntimeDiagnostics.qnnProfileDirectory())
        } finally {
            RuntimeDiagnostics.disable()
            root.deleteRecursively()
        }
    }
}
