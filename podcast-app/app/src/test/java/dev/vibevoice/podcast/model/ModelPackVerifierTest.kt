package dev.vibevoice.podcast.model

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.security.MessageDigest

class ModelPackVerifierTest {
    @get:Rule val temporaryFolder = TemporaryFolder()

    @Test fun verifiesExactRouteSizeHashAndEntrypoint() {
        val root = pack(ModelRoute.GEMMA_4_E2B_LITERT_GPU)
        val verified = ModelPackVerifier().verify(root, ModelRoute.GEMMA_4_E2B_LITERT_GPU)
        assertEquals("gemma-4-e2b", verified.id)
        assertEquals(1, verified.files.size)
    }

    @Test fun rejectsWrongRouteInsteadOfFallingBack() {
        val root = pack(ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP)
        assertThrows(ModelPackException.Invalid::class.java) {
            ModelPackVerifier().verify(root, ModelRoute.GEMMA_4_E2B_LITERT_GPU)
        }
    }

    @Test fun rejectsTamperedArtifact() {
        val root = pack(ModelRoute.GEMMA_4_E2B_LITERT_GPU)
        File(root, "runtime/libentry.so").appendText("tampered")
        assertThrows(ModelPackException.Integrity::class.java) {
            ModelPackVerifier().verify(root, ModelRoute.GEMMA_4_E2B_LITERT_GPU)
        }
    }

    @Test fun rejectsUnlistedArtifact() {
        val root = pack(ModelRoute.GEMMA_4_E2B_LITERT_GPU)
        File(root, "fallback.bin").writeText("must not exist")
        assertThrows(ModelPackException.Invalid::class.java) {
            ModelPackVerifier().verify(root, ModelRoute.GEMMA_4_E2B_LITERT_GPU)
        }
    }

    private fun pack(route: ModelRoute): File {
        val root = temporaryFolder.newFolder()
        val entrypoint = File(root, "runtime/libentry.so").apply { parentFile!!.mkdirs(); writeText("jni") }
        val digest = MessageDigest.getInstance("SHA-256").digest(entrypoint.readBytes()).joinToString("") { "%02x".format(it) }
        val manifest = JSONObject()
            .put("schemaVersion", 1)
            .put("id", if (route == ModelRoute.GEMMA_4_E2B_LITERT_GPU) "gemma-4-e2b" else "supertonic-3")
            .put("version", "test-1")
            .put("route", route.name)
            .put("androidAbi", "arm64-v8a")
            .put("entrypoint", "runtime/libentry.so")
            .put("files", JSONArray().put(JSONObject().put("path", "runtime/libentry.so").put("bytes", entrypoint.length()).put("sha256", digest)))
        File(root, "manifest.json").writeText(manifest.toString())
        return root
    }
}
