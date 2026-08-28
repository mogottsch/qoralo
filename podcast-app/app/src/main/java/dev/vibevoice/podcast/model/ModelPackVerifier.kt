package dev.vibevoice.podcast.model

import org.json.JSONObject
import java.io.File
import java.io.FileInputStream
import java.security.MessageDigest

enum class ModelRoute {
    GEMMA_4_E2B_LITERT_GPU,
    SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP,
}

data class VerifiedModelFile(
    val relativePath: String,
    val file: File,
    val byteCount: Long,
    val sha256: String,
)

data class VerifiedModelPack(
    val id: String,
    val version: String,
    val route: ModelRoute,
    val androidAbi: String,
    val entrypoint: File,
    val root: File,
    val files: List<VerifiedModelFile>,
)

sealed class ModelPackException(message: String) : Exception(message) {
    class Invalid(message: String) : ModelPackException(message)
    class Missing(message: String) : ModelPackException(message)
    class Integrity(message: String) : ModelPackException(message)
}

/** Strict, fail-closed validation for licensed model packs installed outside the APK. */
class ModelPackVerifier {
    fun verify(root: File, expectedRoute: ModelRoute): VerifiedModelPack {
        if (!root.isDirectory) throw ModelPackException.Missing("Model-pack directory is missing: ${root.path}")
        val manifestFile = File(root, MANIFEST)
        if (!manifestFile.isFile) throw ModelPackException.Missing("Model pack has no $MANIFEST")
        if (manifestFile.length() !in 1..MAX_MANIFEST_BYTES) {
            throw ModelPackException.Invalid("Model-pack manifest has an invalid size")
        }

        val json = try {
            JSONObject(manifestFile.readText(Charsets.UTF_8))
        } catch (error: Exception) {
            throw ModelPackException.Invalid("Model-pack manifest is not valid JSON: ${error.message}")
        }
        requireExactKeys(json, setOf("schemaVersion", "id", "version", "route", "androidAbi", "entrypoint", "files"), "manifest")
        if (json.getInt("schemaVersion") != SCHEMA_VERSION) {
            throw ModelPackException.Invalid("Unsupported model-pack schema")
        }
        val id = safeIdentifier(json.getString("id"), "id")
        val version = safeIdentifier(json.getString("version"), "version")
        val route = try {
            ModelRoute.valueOf(json.getString("route"))
        } catch (_: IllegalArgumentException) {
            throw ModelPackException.Invalid("Unknown model route")
        }
        if (route != expectedRoute) {
            throw ModelPackException.Invalid("Expected route $expectedRoute but pack declares $route")
        }
        val abi = json.getString("androidAbi")
        if (abi != REQUIRED_ABI) throw ModelPackException.Invalid("Model pack must target $REQUIRED_ABI")
        val entrypointPath = safeRelativePath(json.getString("entrypoint"))

        val fileArray = json.getJSONArray("files")
        if (fileArray.length() !in 1..MAX_FILES) throw ModelPackException.Invalid("Invalid model-pack file count")
        val seen = mutableSetOf<String>()
        val files = ArrayList<VerifiedModelFile>(fileArray.length())
        for (index in 0 until fileArray.length()) {
            val item = fileArray.getJSONObject(index)
            requireExactKeys(item, setOf("path", "bytes", "sha256"), "files[$index]")
            val relativePath = safeRelativePath(item.getString("path"))
            if (!seen.add(relativePath)) throw ModelPackException.Invalid("Duplicate file: $relativePath")
            val expectedBytes = item.getLong("bytes")
            if (expectedBytes < 0) throw ModelPackException.Invalid("Negative size for $relativePath")
            val expectedSha = item.getString("sha256").lowercase()
            if (!SHA256.matches(expectedSha)) throw ModelPackException.Invalid("Invalid SHA-256 for $relativePath")
            val file = resolveContainedFile(root, relativePath)
            if (!file.isFile) throw ModelPackException.Missing("Missing model file: $relativePath")
            if (file.length() != expectedBytes) throw ModelPackException.Integrity("Size mismatch: $relativePath")
            val actualSha = sha256(file)
            if (!MessageDigest.isEqual(actualSha.toByteArray(), expectedSha.toByteArray())) {
                throw ModelPackException.Integrity("SHA-256 mismatch: $relativePath")
            }
            files += VerifiedModelFile(relativePath, file, expectedBytes, expectedSha)
        }
        if (entrypointPath !in seen || !entrypointPath.endsWith(".so")) {
            throw ModelPackException.Invalid("Entrypoint must be a listed shared library")
        }

        val listed = seen + MANIFEST
        val actual = root.walkTopDown().filter(File::isFile).map { it.relativeTo(root).invariantSeparatorsPath }.toSet()
        val unlisted = actual - listed
        if (unlisted.isNotEmpty()) throw ModelPackException.Invalid("Unlisted model-pack files: ${unlisted.sorted().joinToString()}")

        return VerifiedModelPack(id, version, route, abi, resolveContainedFile(root, entrypointPath), root, files)
    }

    private fun requireExactKeys(json: JSONObject, expected: Set<String>, label: String) {
        val actual = json.keys().asSequence().toSet()
        if (actual != expected) throw ModelPackException.Invalid("Unexpected keys in $label")
    }

    private fun safeIdentifier(value: String, field: String): String {
        if (!IDENTIFIER.matches(value)) throw ModelPackException.Invalid("Invalid model-pack $field")
        return value
    }

    private fun safeRelativePath(value: String): String {
        if (value.isBlank() || value.contains('\\')) throw ModelPackException.Invalid("Unsafe model-pack path")
        val candidate = File(value)
        if (candidate.isAbsolute || candidate.toPath().normalize().toString() != value) {
            throw ModelPackException.Invalid("Unsafe model-pack path: $value")
        }
        return value
    }

    private fun resolveContainedFile(root: File, relativePath: String): File {
        val canonicalRoot = root.canonicalFile
        val file = File(canonicalRoot, relativePath).canonicalFile
        if (!file.toPath().startsWith(canonicalRoot.toPath())) {
            throw ModelPackException.Invalid("Model file escapes pack root")
        }
        return file
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { input ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private companion object {
        const val MANIFEST = "manifest.json"
        const val SCHEMA_VERSION = 1
        const val MAX_MANIFEST_BYTES = 1_048_576L
        const val MAX_FILES = 512
        const val REQUIRED_ABI = "arm64-v8a"
        val IDENTIFIER = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
        val SHA256 = Regex("[0-9a-f]{64}")
    }
}
