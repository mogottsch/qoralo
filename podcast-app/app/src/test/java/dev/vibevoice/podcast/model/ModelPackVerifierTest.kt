package dev.vibevoice.podcast.model

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.nio.file.Files
import java.security.MessageDigest

class ModelPackVerifierTest {
    @get:Rule val temporaryFolder = TemporaryFolder()

    @Test fun verifiesPinnedGemmaDataPack() {
        val pack = pack(ModelRoute.GEMMA_4_E2B_LITERT_GPU)
        val verified = ModelPackVerifier().verify(pack.root, pack.requirement)
        assertEquals("gemma-4-e2b", verified.id)
        assertEquals(setOf(ModelFileRole.GEMMA_MODEL), verified.files.map { it.role }.toSet())
    }

    @Test fun verifiesPinnedSupertonicInventory() {
        val pack = pack(ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP)
        val verified = ModelPackVerifier().verify(pack.root, pack.requirement)
        assertEquals(9, verified.files.map { it.role }.toSet().size)
        assertEquals("QNN_HTP", verified.declaredBackend)
    }

    @Test fun rejectsUnpinnedManifest() {
        val pack = pack(ModelRoute.GEMMA_4_E2B_LITERT_GPU)
        assertThrows(ModelPackException.Missing::class.java) {
            ModelPackVerifier().verify(pack.root, pack.requirement.copy(pinnedManifestSha256 = ""))
        }
    }

    @Test fun rejectsWrongRouteInsteadOfFallingBack() {
        val pack = pack(ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP)
        assertThrows(ModelPackException.Invalid::class.java) {
            ModelPackVerifier().verify(pack.root, pack.requirement.copy(route = ModelRoute.GEMMA_4_E2B_LITERT_GPU))
        }
    }

    @Test fun rejectsTamperedArtifact() {
        val pack = pack(ModelRoute.GEMMA_4_E2B_LITERT_GPU)
        File(pack.root, "data/gemma_model.data").appendText("tampered")
        assertThrows(ModelPackException.Integrity::class.java) { ModelPackVerifier().verify(pack.root, pack.requirement) }
    }

    @Test fun rejectsManifestChangedAfterPinning() {
        val pack = pack(ModelRoute.GEMMA_4_E2B_LITERT_GPU)
        File(pack.root, "manifest.json").appendText(" ")
        assertThrows(ModelPackException.Integrity::class.java) { ModelPackVerifier().verify(pack.root, pack.requirement) }
    }

    @Test fun rejectsUnlistedArtifact() {
        val pack = pack(ModelRoute.GEMMA_4_E2B_LITERT_GPU)
        File(pack.root, "fallback.bin").writeText("must not exist")
        assertThrows(ModelPackException.Invalid::class.java) { ModelPackVerifier().verify(pack.root, pack.requirement) }
    }

    @Test fun rejectsExecutableArtifactEvenWhenPinned() {
        val pack = pack(ModelRoute.GEMMA_4_E2B_LITERT_GPU) { manifest ->
            val file = File(manifestRoot, "data/injected.so").apply { writeText("code") }
            manifest.getJSONArray("files").put(fileEntry(ModelFileRole.GEMMA_TOKENIZER, file, manifestRoot))
        }
        assertThrows(ModelPackException.Invalid::class.java) { ModelPackVerifier().verify(pack.root, pack.requirement) }
    }

    @Test fun rejectsUnsafeParentPath() {
        val pack = pack(ModelRoute.GEMMA_4_E2B_LITERT_GPU) { manifest ->
            manifest.getJSONArray("files").getJSONObject(0).put("path", "../escape.data")
        }
        assertThrows(ModelPackException.Invalid::class.java) { ModelPackVerifier().verify(pack.root, pack.requirement) }
    }

    @Test fun rejectsBackslashPath() {
        val pack = pack(ModelRoute.GEMMA_4_E2B_LITERT_GPU) { manifest ->
            manifest.getJSONArray("files").getJSONObject(0).put("path", "data\\model.data")
        }
        assertThrows(ModelPackException.Invalid::class.java) { ModelPackVerifier().verify(pack.root, pack.requirement) }
    }

    @Test fun rejectsDuplicatePaths() {
        val pack = pack(ModelRoute.GEMMA_4_E2B_LITERT_GPU) { manifest ->
            manifest.getJSONArray("files").put(JSONObject(manifest.getJSONArray("files").getJSONObject(0).toString()).put("role", ModelFileRole.GEMMA_TOKENIZER.name))
        }
        assertThrows(ModelPackException.Invalid::class.java) { ModelPackVerifier().verify(pack.root, pack.requirement) }
    }

    @Test fun rejectsMissingRouteInventory() {
        val pack = pack(ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP) { manifest ->
            val input = manifest.getJSONArray("files")
            val output = JSONArray()
            for (index in 0 until input.length()) if (input.getJSONObject(index).getString("role") != ModelFileRole.SUPERTONIC_VOCODER_CONTEXT.name) output.put(input.getJSONObject(index))
            manifest.put("files", output)
        }
        assertThrows(ModelPackException.Invalid::class.java) { ModelPackVerifier().verify(pack.root, pack.requirement) }
    }

    @Test fun rejectsCpuFallbackDeclaration() {
        val pack = pack(ModelRoute.GEMMA_4_E2B_LITERT_GPU) { it.getJSONObject("runtime").put("cpuFallbackAllowed", true) }
        assertThrows(ModelPackException.Invalid::class.java) { ModelPackVerifier().verify(pack.root, pack.requirement) }
    }

    @Test fun rejectsExtraSchemaField() {
        val pack = pack(ModelRoute.GEMMA_4_E2B_LITERT_GPU) { it.put("fallbackModel", "other") }
        assertThrows(ModelPackException.Invalid::class.java) { ModelPackVerifier().verify(pack.root, pack.requirement) }
    }

    @Test fun rejectsWrongTypedSchemaField() {
        val pack = pack(ModelRoute.GEMMA_4_E2B_LITERT_GPU) { it.put("schemaVersion", "2") }
        assertThrows(ModelPackException.Invalid::class.java) { ModelPackVerifier().verify(pack.root, pack.requirement) }
    }

    @Test fun rejectsSymlinkedArtifact() {
        val pack = pack(ModelRoute.GEMMA_4_E2B_LITERT_GPU)
        val model = File(pack.root, "data/gemma_model.data")
        val outside = temporaryFolder.newFile("outside-model").apply { writeText(model.readText()) }
        assertTrue(model.delete())
        Files.createSymbolicLink(model.toPath(), outside.toPath())
        assertThrows(ModelPackException.Invalid::class.java) { ModelPackVerifier().verify(pack.root, pack.requirement) }
    }

    private lateinit var manifestRoot: File

    private fun pack(route: ModelRoute, mutate: (JSONObject) -> Unit = {}): PackFixture {
        val root = temporaryFolder.newFolder().also { manifestRoot = it }
        val roles = if (route == ModelRoute.GEMMA_4_E2B_LITERT_GPU) {
            listOf(ModelFileRole.GEMMA_MODEL)
        } else {
            listOf(
                ModelFileRole.SUPERTONIC_CONFIG,
                ModelFileRole.SUPERTONIC_DURATION_CONTEXT,
                ModelFileRole.SUPERTONIC_TEXT_CONTEXT,
                ModelFileRole.SUPERTONIC_VECTOR_CONTEXT,
                ModelFileRole.SUPERTONIC_VOCODER_CONTEXT,
                ModelFileRole.SUPERTONIC_TOKENIZER,
                ModelFileRole.SUPERTONIC_UNICODE_INDEXER,
                ModelFileRole.SUPERTONIC_VOICE,
                ModelFileRole.SUPERTONIC_STYLE,
            )
        }
        val files = roles.map { role ->
            File(root, "data/${role.name.lowercase()}.data").apply { parentFile!!.mkdirs(); writeText("fixture-${role.name}") }
        }
        val contract = if (route == ModelRoute.GEMMA_4_E2B_LITERT_GPU) {
            JSONObject().put("generationPlan", "OUTLINE_THEN_CHAPTERS").put("completeChapterPerRequest", true)
        } else {
            JSONObject().put("synthesisUnit", "COMPLETE_CHAPTER").put("externalContextCount", 4)
                .put("sampleRateHz", 44_100).put("channelCount", 1).put("pcmBits", 16)
        }
        val manifest = JSONObject()
            .put("schemaVersion", 2)
            .put("id", if (route == ModelRoute.GEMMA_4_E2B_LITERT_GPU) "gemma-4-e2b" else "supertonic-3")
            .put("version", "test-1")
            .put("route", route.name)
            .put("androidAbi", "arm64-v8a")
            .put("runtime", JSONObject().put("apiVersion", 1).put("backend", if (route == ModelRoute.GEMMA_4_E2B_LITERT_GPU) "LITERT_GPU" else "QNN_HTP").put("cpuFallbackAllowed", false))
            .put("contract", contract)
            .put("files", JSONArray().apply { roles.zip(files).forEach { (role, file) -> put(fileEntry(role, file, root)) } })
        mutate(manifest)
        val manifestFile = File(root, "manifest.json").apply { writeText(manifest.toString()) }
        val pinned = sha256(manifestFile)
        val requirement = ModelPackRequirement(route, if (route == ModelRoute.GEMMA_4_E2B_LITERT_GPU) "gemma-4-e2b" else "supertonic-3", pinned)
        return PackFixture(root, requirement)
    }

    private fun fileEntry(role: ModelFileRole, file: File, root: File) = JSONObject()
        .put("role", role.name)
        .put("path", file.relativeTo(root).invariantSeparatorsPath)
        .put("bytes", file.length())
        .put("sha256", sha256(file))

    private fun sha256(file: File): String = MessageDigest.getInstance("SHA-256").digest(file.readBytes()).joinToString("") { "%02x".format(it) }
    private data class PackFixture(val root: File, val requirement: ModelPackRequirement)
}
