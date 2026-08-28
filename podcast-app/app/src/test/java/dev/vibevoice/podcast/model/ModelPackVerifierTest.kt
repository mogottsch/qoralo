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
        assertEquals(setOf(ModelFileRole.GEMMA_MODEL, ModelFileRole.GEMMA_TOKENIZER), verified.files.map { it.role }.toSet())
    }

    @Test fun verifiesPinnedSupertonicInventory() {
        val pack = pack(ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP)
        val verified = ModelPackVerifier().verify(pack.root, pack.requirement)
        assertEquals(13, verified.files.map { it.role }.toSet().size)
        assertEquals("QNN_HTP", verified.declaredBackend)
        assertEquals(SupertonicModelContract(239, 238, 144, 5, 44_100, 1, 16,
            "ONNX Runtime 1.27.1 + QAIRT 2.49.0.260730"), verified.contract)
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
        File(pack.root, "models/gemma-4-e2b.litertlm").appendText("tampered")
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
            val file = File(manifestRoot, "data/injected.so").apply { parentFile!!.mkdirs(); writeText("code") }
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

    @Test fun rejectsDuplicateRoleWithDifferentFiles() {
        val pack = pack(ModelRoute.GEMMA_4_E2B_LITERT_GPU) { manifest ->
            val file = File(manifestRoot, "data/second-tokenizer.data").apply { parentFile!!.mkdirs(); writeText("duplicate role") }
            manifest.getJSONArray("files").put(fileEntry(ModelFileRole.GEMMA_TOKENIZER, file, manifestRoot))
        }
        assertThrows(ModelPackException.Invalid::class.java) { ModelPackVerifier().verify(pack.root, pack.requirement) }
    }

    @Test fun rejectsMissingRouteInventory() {
        val pack = pack(ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP) { manifest ->
            val input = manifest.getJSONArray("files")
            val output = JSONArray()
            for (index in 0 until input.length()) if (input.getJSONObject(index).getString("role") != ModelFileRole.SUPERTONIC_VOCODER_BINARY.name) output.put(input.getJSONObject(index))
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
        val model = File(pack.root, "models/gemma-4-e2b.litertlm")
        val outside = temporaryFolder.newFile("outside-model").apply { writeText(model.readText()) }
        assertTrue(model.delete())
        Files.createSymbolicLink(model.toPath(), outside.toPath())
        assertThrows(ModelPackException.Invalid::class.java) { ModelPackVerifier().verify(pack.root, pack.requirement) }
    }

    private lateinit var manifestRoot: File

    private fun pack(route: ModelRoute, mutate: (JSONObject) -> Unit = {}): PackFixture {
        val root = temporaryFolder.newFolder().also { manifestRoot = it }
        val roles = if (route == ModelRoute.GEMMA_4_E2B_LITERT_GPU) {
            listOf(ModelFileRole.GEMMA_MODEL, ModelFileRole.GEMMA_TOKENIZER)
        } else {
            listOf(
                ModelFileRole.SUPERTONIC_CONFIG,
                ModelFileRole.SUPERTONIC_DURATION_DESCRIPTOR,
                ModelFileRole.SUPERTONIC_DURATION_BINARY,
                ModelFileRole.SUPERTONIC_TEXT_DESCRIPTOR,
                ModelFileRole.SUPERTONIC_TEXT_BINARY,
                ModelFileRole.SUPERTONIC_VECTOR_DESCRIPTOR,
                ModelFileRole.SUPERTONIC_VECTOR_BINARY,
                ModelFileRole.SUPERTONIC_VOCODER_DESCRIPTOR,
                ModelFileRole.SUPERTONIC_VOCODER_BINARY,
                ModelFileRole.SUPERTONIC_TOKENIZER,
                ModelFileRole.SUPERTONIC_UNICODE_INDEXER,
                ModelFileRole.SUPERTONIC_VOICE,
                ModelFileRole.SUPERTONIC_STYLE,
            )
        }
        val files = roles.map { role ->
            File(root, pathFor(role)).apply { parentFile!!.mkdirs(); writeText("fixture-${role.name}") }
        }
        val contract = if (route == ModelRoute.GEMMA_4_E2B_LITERT_GPU) {
            JSONObject().put("generationPlan", "OUTLINE_THEN_CHAPTERS").put("completeChapterPerRequest", true)
                .put("contextTokens", 8_192).put("runtimeVersion", "0.16.1")
        } else {
            JSONObject().put("synthesisUnit", "COMPLETE_CHAPTER").put("externalContextCount", 4)
                .put("sampleRateHz", 44_100).put("channelCount", 1).put("pcmBits", 16)
                .put("textLength", 239).put("latentLength", 238).put("latentChannels", 144).put("diffusionSteps", 5)
        }
        val manifest = JSONObject()
            .put("schemaVersion", 2)
            .put("id", if (route == ModelRoute.GEMMA_4_E2B_LITERT_GPU) "gemma-4-e2b" else "supertonic-3")
            .put("version", "test-1")
            .put("route", route.name)
            .put("androidAbi", "arm64-v8a")
            .put("runtime", JSONObject().put("apiVersion", 1).put("backend", if (route == ModelRoute.GEMMA_4_E2B_LITERT_GPU) "LITERT_GPU" else "QNN_HTP")
                .put("cpuFallbackAllowed", false).put("buildIdentity", if (route == ModelRoute.GEMMA_4_E2B_LITERT_GPU) "LiteRT-LM 0.16.1" else "ONNX Runtime 1.27.1 + QAIRT 2.49.0.260730"))
            .put("contract", contract)
            .put("files", JSONArray().apply { roles.zip(files).forEach { (role, file) -> put(fileEntry(role, file, root)) } })
        mutate(manifest)
        val manifestFile = File(root, "manifest.json").apply { writeText(manifest.toString()) }
        val pinned = sha256(manifestFile)
        val requirement = ModelPackRequirement(route, if (route == ModelRoute.GEMMA_4_E2B_LITERT_GPU) "gemma-4-e2b" else "supertonic-3", pinned)
        return PackFixture(root, requirement)
    }

    private fun pathFor(role: ModelFileRole): String = when (role) {
        ModelFileRole.GEMMA_MODEL -> "models/gemma-4-e2b.litertlm"
        ModelFileRole.GEMMA_TOKENIZER -> "models/tokenizer.model"
        ModelFileRole.SUPERTONIC_CONFIG -> "assets/config.json"
        ModelFileRole.SUPERTONIC_DURATION_DESCRIPTOR -> "contexts/duration-context.onnx"
        ModelFileRole.SUPERTONIC_DURATION_BINARY -> "contexts/duration-context_qnn.bin"
        ModelFileRole.SUPERTONIC_TEXT_DESCRIPTOR -> "contexts/text-context.onnx"
        ModelFileRole.SUPERTONIC_TEXT_BINARY -> "contexts/text-context_qnn.bin"
        ModelFileRole.SUPERTONIC_VECTOR_DESCRIPTOR -> "contexts/vector-context.onnx"
        ModelFileRole.SUPERTONIC_VECTOR_BINARY -> "contexts/vector-context_qnn.bin"
        ModelFileRole.SUPERTONIC_VOCODER_DESCRIPTOR -> "contexts/vocoder-context.onnx"
        ModelFileRole.SUPERTONIC_VOCODER_BINARY -> "contexts/vocoder-context_qnn.bin"
        ModelFileRole.SUPERTONIC_TOKENIZER -> "assets/tokenizer.json"
        ModelFileRole.SUPERTONIC_UNICODE_INDEXER -> "assets/unicode-indexer.i32"
        ModelFileRole.SUPERTONIC_VOICE -> "assets/voice.bin"
        ModelFileRole.SUPERTONIC_STYLE -> "assets/voice-style.json"
    }

    private fun fileEntry(role: ModelFileRole, file: File, root: File) = JSONObject()
        .put("role", role.name)
        .put("path", file.relativeTo(root).invariantSeparatorsPath)
        .put("bytes", file.length())
        .put("sha256", sha256(file))

    private fun sha256(file: File): String = MessageDigest.getInstance("SHA-256").digest(file.readBytes()).joinToString("") { "%02x".format(it) }
    private data class PackFixture(val root: File, val requirement: ModelPackRequirement)
}
