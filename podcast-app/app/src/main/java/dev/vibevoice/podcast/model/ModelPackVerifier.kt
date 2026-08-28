package dev.vibevoice.podcast.model

import org.json.JSONObject
import java.io.File
import java.io.FileInputStream
import java.nio.file.Files
import java.security.MessageDigest

enum class ModelRoute {
    GEMMA_4_E2B_LITERT_GPU,
    SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP,
}

enum class ModelFileRole {
    GEMMA_MODEL,
    GEMMA_TOKENIZER,
    SUPERTONIC_CONFIG,
    SUPERTONIC_DURATION_DESCRIPTOR,
    SUPERTONIC_DURATION_BINARY,
    SUPERTONIC_TEXT_DESCRIPTOR,
    SUPERTONIC_TEXT_BINARY,
    SUPERTONIC_VECTOR_DESCRIPTOR,
    SUPERTONIC_VECTOR_BINARY,
    SUPERTONIC_VOCODER_DESCRIPTOR,
    SUPERTONIC_VOCODER_BINARY,
    SUPERTONIC_TOKENIZER,
    SUPERTONIC_UNICODE_INDEXER,
    SUPERTONIC_VOICE,
    SUPERTONIC_STYLE,
}

data class ModelPackRequirement(
    val route: ModelRoute,
    val expectedId: String,
    val pinnedManifestSha256: String,
    val runtimeApiVersion: Int = 1,
)

data class VerifiedModelFile(
    val role: ModelFileRole,
    val relativePath: String,
    val file: File,
    val byteCount: Long,
    val sha256: String,
)

sealed interface VerifiedModelContract

data class GemmaModelContract(val contextTokens: Int, val runtimeVersion: String) : VerifiedModelContract

data class SupertonicModelContract(
    val textLength: Int,
    val latentLength: Int,
    val latentChannels: Int,
    val diffusionSteps: Int,
    val sampleRateHz: Int,
    val channelCount: Int,
    val pcmBits: Int,
    val runtimeBuildIdentity: String,
) : VerifiedModelContract

data class VerifiedModelPack(
    val id: String,
    val version: String,
    val route: ModelRoute,
    val androidAbi: String,
    val runtimeApiVersion: Int,
    val declaredBackend: String,
    val contract: VerifiedModelContract,
    val manifestSha256: String,
    val root: File,
    val files: List<VerifiedModelFile>,
)

sealed class ModelPackException(message: String) : Exception(message) {
    class Invalid(message: String) : ModelPackException(message)
    class Missing(message: String) : ModelPackException(message)
    class Integrity(message: String) : ModelPackException(message)
}

/** Validates a data-only pack against an identity pinned into the installed app. */
class ModelPackVerifier {
    fun verify(root: File, requirement: ModelPackRequirement): VerifiedModelPack {
        if (!PINNED_SHA.matches(requirement.pinnedManifestSha256.lowercase())) {
            throw ModelPackException.Missing("No trusted manifest hash is configured for ${requirement.route}")
        }
        if (!root.isDirectory || Files.isSymbolicLink(root.toPath())) {
            throw ModelPackException.Missing("Model-pack directory is missing or unsafe: ${root.path}")
        }
        root.walkTopDown().forEach {
            if (Files.isSymbolicLink(it.toPath())) throw ModelPackException.Invalid("Symbolic links are not allowed in model packs")
        }
        val manifestFile = File(root, MANIFEST)
        if (!manifestFile.isFile) throw ModelPackException.Missing("Model pack has no $MANIFEST")
        if (manifestFile.length() !in 1..MAX_MANIFEST_BYTES) throw ModelPackException.Invalid("Model-pack manifest has an invalid size")
        val manifestSha = sha256(manifestFile)
        if (!constantEquals(manifestSha, requirement.pinnedManifestSha256.lowercase())) {
            throw ModelPackException.Integrity("Model-pack manifest is not the app-pinned manifest")
        }

        val json = try {
            JSONObject(manifestFile.readText(Charsets.UTF_8))
        } catch (error: Exception) {
            throw ModelPackException.Invalid("Model-pack manifest is not valid JSON: ${error.message}")
        }
        requireExactKeys(json, setOf("schemaVersion", "id", "version", "route", "androidAbi", "runtime", "contract", "files"), "manifest")
        if (json.requireInt("schemaVersion") != SCHEMA_VERSION) throw ModelPackException.Invalid("Unsupported model-pack schema")
        val id = safeIdentifier(json.requireString("id"), "id")
        val version = safeIdentifier(json.requireString("version"), "version")
        if (id != requirement.expectedId) throw ModelPackException.Invalid("Expected pack ${requirement.expectedId}, found $id")
        val route = enumValue<ModelRoute>(json.requireString("route"), "model route")
        if (route != requirement.route) throw ModelPackException.Invalid("Expected route ${requirement.route} but pack declares $route")
        val abi = json.requireString("androidAbi")
        if (abi != REQUIRED_ABI) throw ModelPackException.Invalid("Model pack must target $REQUIRED_ABI")

        val runtime = json.requireObject("runtime")
        requireExactKeys(runtime, setOf("apiVersion", "backend", "cpuFallbackAllowed", "buildIdentity"), "runtime")
        val runtimeApi = runtime.requireInt("apiVersion")
        if (runtimeApi != requirement.runtimeApiVersion) throw ModelPackException.Invalid("Runtime API mismatch")
        val backend = runtime.requireString("backend")
        val expectedBackend = if (route == ModelRoute.GEMMA_4_E2B_LITERT_GPU) "LITERT_GPU" else "QNN_HTP"
        if (backend != expectedBackend) throw ModelPackException.Invalid("Pack backend must be $expectedBackend")
        if (runtime.requireBoolean("cpuFallbackAllowed")) throw ModelPackException.Invalid("CPU fallback must be disabled")
        val buildIdentity = runtime.requireString("buildIdentity")
        val expectedBuildIdentity = if (route == ModelRoute.GEMMA_4_E2B_LITERT_GPU) "LiteRT-LM 0.16.1" else "ONNX Runtime 1.27.1 + QAIRT 2.49.0.260730"
        if (buildIdentity != expectedBuildIdentity) throw ModelPackException.Invalid("Runtime build identity mismatch")
        val contract = validateContract(route, json.requireObject("contract"), buildIdentity)

        val fileArray = json.requireArray("files")
        if (fileArray.length() !in 1..MAX_FILES) throw ModelPackException.Invalid("Invalid model-pack file count")
        val seen = mutableSetOf<String>()
        val files = ArrayList<VerifiedModelFile>(fileArray.length())
        for (index in 0 until fileArray.length()) {
            val item = try { fileArray.getJSONObject(index) } catch (_: Exception) {
                throw ModelPackException.Invalid("files[$index] must be an object")
            }
            requireExactKeys(item, setOf("role", "path", "bytes", "sha256"), "files[$index]")
            val role = enumValue<ModelFileRole>(item.requireString("role"), "file role")
            val relativePath = safeRelativePath(item.requireString("path"))
            if (EXECUTABLE_EXTENSIONS.any(relativePath.lowercase()::endsWith)) {
                throw ModelPackException.Invalid("Model packs must contain data only: $relativePath")
            }
            if (!seen.add(relativePath)) throw ModelPackException.Invalid("Duplicate file: $relativePath")
            val expectedBytes = item.requireLong("bytes")
            if (expectedBytes <= 0) throw ModelPackException.Invalid("Invalid size for $relativePath")
            val expectedSha = item.requireString("sha256").lowercase()
            if (!PINNED_SHA.matches(expectedSha)) throw ModelPackException.Invalid("Invalid SHA-256 for $relativePath")
            val file = resolveContainedFile(root, relativePath)
            if (!file.isFile || Files.isSymbolicLink(file.toPath())) throw ModelPackException.Missing("Missing or unsafe model file: $relativePath")
            if (file.length() != expectedBytes) throw ModelPackException.Integrity("Size mismatch: $relativePath")
            val actualSha = sha256(file)
            if (!constantEquals(actualSha, expectedSha)) throw ModelPackException.Integrity("SHA-256 mismatch: $relativePath")
            files += VerifiedModelFile(role, relativePath, file, expectedBytes, expectedSha)
        }
        validateInventory(route, files)

        val listed = seen + MANIFEST
        val actual = root.walkTopDown().filter(File::isFile).map { it.relativeTo(root).invariantSeparatorsPath }.toSet()
        val unlisted = actual - listed
        if (unlisted.isNotEmpty()) throw ModelPackException.Invalid("Unlisted model-pack files: ${unlisted.sorted().joinToString()}")

        return VerifiedModelPack(id, version, route, abi, runtimeApi, backend, contract, manifestSha, root, files)
    }

    private fun validateContract(route: ModelRoute, contract: JSONObject, buildIdentity: String): VerifiedModelContract {
        return when (route) {
            ModelRoute.GEMMA_4_E2B_LITERT_GPU -> {
                requireExactKeys(contract, setOf("generationPlan", "completeChapterPerRequest", "contextTokens", "runtimeVersion"), "contract")
                val contextTokens = contract.requireInt("contextTokens")
                val runtimeVersion = contract.requireString("runtimeVersion")
                if (contract.requireString("generationPlan") != "OUTLINE_THEN_CHAPTERS" || !contract.requireBoolean("completeChapterPerRequest") ||
                    contextTokens != 8_192 || runtimeVersion != "0.16.1"
                ) throw ModelPackException.Invalid("Gemma pack does not declare the complete-chapter contract")
                GemmaModelContract(contextTokens, runtimeVersion)
            }
            ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP -> {
                requireExactKeys(contract, setOf("synthesisUnit", "externalContextCount", "sampleRateHz", "channelCount", "pcmBits", "textLength", "latentLength", "latentChannels", "diffusionSteps"), "contract")
                val textLength = contract.requireInt("textLength")
                val latentLength = contract.requireInt("latentLength")
                val sampleRate = contract.requireInt("sampleRateHz")
                val channels = contract.requireInt("channelCount")
                val bits = contract.requireInt("pcmBits")
                val latentChannels = contract.requireInt("latentChannels")
                val steps = contract.requireInt("diffusionSteps")
                if (contract.requireString("synthesisUnit") != "COMPLETE_CHAPTER" || contract.requireInt("externalContextCount") != 4 ||
                    sampleRate != 44_100 || channels != 1 || bits != 16 || textLength !in 10..16_384 || latentLength !in 1..10_000 ||
                    latentChannels != 144 || steps != 5
                ) throw ModelPackException.Invalid("Supertonic pack does not match the chapter WAV/shape contract")
                SupertonicModelContract(textLength, latentLength, latentChannels, steps, sampleRate, channels, bits, buildIdentity)
            }
        }
    }

    private fun validateInventory(route: ModelRoute, files: List<VerifiedModelFile>) {
        val actual = files.map { it.role }.toSet()
        val required = when (route) {
            ModelRoute.GEMMA_4_E2B_LITERT_GPU -> setOf(ModelFileRole.GEMMA_MODEL, ModelFileRole.GEMMA_TOKENIZER)
            ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP -> setOf(
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
        val counts = files.groupingBy { it.role }.eachCount()
        val duplicateRoles = counts.filterValues { it != 1 }.keys
        if (duplicateRoles.isNotEmpty()) throw ModelPackException.Invalid("Model-pack roles must have exact cardinality one: ${duplicateRoles.sortedBy { it.name }}")
        if (actual != required) throw ModelPackException.Invalid("Model pack must contain exactly the required ${route.name} assets: missing=${(required - actual).sortedBy { it.name }}, extra=${(actual - required).sortedBy { it.name }}")
        files.forEach { file ->
            val expectedPath = REQUIRED_PATHS.getValue(file.role)
            if (file.relativePath != expectedPath) throw ModelPackException.Invalid("${file.role} must use path $expectedPath")
        }
        val wrongRouteRoles = actual.filter { role -> route == ModelRoute.GEMMA_4_E2B_LITERT_GPU && role.name.startsWith("SUPERTONIC") || route == ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP && role.name.startsWith("GEMMA") }
        if (wrongRouteRoles.isNotEmpty()) throw ModelPackException.Invalid("Pack contains assets for another inference route")
    }

    private fun requireExactKeys(json: JSONObject, expected: Set<String>, label: String) {
        val actual = json.keys().asSequence().toSet()
        if (actual != expected) throw ModelPackException.Invalid("Unexpected or missing keys in $label")
    }

    private fun safeIdentifier(value: String, field: String): String {
        if (!IDENTIFIER.matches(value)) throw ModelPackException.Invalid("Invalid model-pack $field")
        return value
    }

    private fun safeRelativePath(value: String): String {
        if (value.isBlank() || value.contains('\\')) throw ModelPackException.Invalid("Unsafe model-pack path")
        val candidate = File(value)
        if (candidate.isAbsolute || candidate.toPath().normalize().toString().replace(File.separatorChar, '/') != value) {
            throw ModelPackException.Invalid("Unsafe model-pack path: $value")
        }
        return value
    }

    private fun resolveContainedFile(root: File, relativePath: String): File {
        val canonicalRoot = root.canonicalFile
        val file = File(canonicalRoot, relativePath).canonicalFile
        if (!file.toPath().startsWith(canonicalRoot.toPath())) throw ModelPackException.Invalid("Model file escapes pack root")
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

    private inline fun <reified T : Enum<T>> enumValue(value: String, label: String): T =
        try { enumValueOf<T>(value) } catch (_: IllegalArgumentException) { throw ModelPackException.Invalid("Unknown $label") }

    private fun JSONObject.requireString(key: String): String = try {
        get(key).let { if (it is String) it else throw IllegalArgumentException() }
    } catch (_: Exception) { throw ModelPackException.Invalid("$key must be a string") }
    private fun JSONObject.requireInt(key: String): Int = try {
        get(key).let { if (it is Int) it else throw IllegalArgumentException() }
    } catch (_: Exception) { throw ModelPackException.Invalid("$key must be an integer") }
    private fun JSONObject.requireLong(key: String): Long = try {
        get(key).let { if (it is Number && it.toLong().toDouble() == it.toDouble()) it.toLong() else throw IllegalArgumentException() }
    } catch (_: Exception) { throw ModelPackException.Invalid("$key must be an integer") }
    private fun JSONObject.requireBoolean(key: String): Boolean = try {
        get(key).let { if (it is Boolean) it else throw IllegalArgumentException() }
    } catch (_: Exception) { throw ModelPackException.Invalid("$key must be a boolean") }
    private fun JSONObject.requireObject(key: String): JSONObject = try { getJSONObject(key) } catch (_: Exception) { throw ModelPackException.Invalid("$key must be an object") }
    private fun JSONObject.requireArray(key: String) = try { getJSONArray(key) } catch (_: Exception) { throw ModelPackException.Invalid("$key must be an array") }
    private fun constantEquals(a: String, b: String) = MessageDigest.isEqual(a.toByteArray(Charsets.US_ASCII), b.toByteArray(Charsets.US_ASCII))

    private companion object {
        const val MANIFEST = "manifest.json"
        const val SCHEMA_VERSION = 2
        const val MAX_MANIFEST_BYTES = 1_048_576L
        const val MAX_FILES = 512
        const val REQUIRED_ABI = "arm64-v8a"
        val IDENTIFIER = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
        val PINNED_SHA = Regex("[0-9a-f]{64}")
        val EXECUTABLE_EXTENSIONS = setOf(".so", ".dex", ".jar", ".apk")
        val REQUIRED_PATHS = mapOf(
            ModelFileRole.GEMMA_MODEL to "models/gemma-4-e2b.litertlm",
            ModelFileRole.GEMMA_TOKENIZER to "models/tokenizer.model",
            ModelFileRole.SUPERTONIC_CONFIG to "assets/config.json",
            ModelFileRole.SUPERTONIC_DURATION_DESCRIPTOR to "contexts/duration-context.onnx",
            ModelFileRole.SUPERTONIC_DURATION_BINARY to "contexts/duration-context_qnn.bin",
            ModelFileRole.SUPERTONIC_TEXT_DESCRIPTOR to "contexts/text-context.onnx",
            ModelFileRole.SUPERTONIC_TEXT_BINARY to "contexts/text-context_qnn.bin",
            ModelFileRole.SUPERTONIC_VECTOR_DESCRIPTOR to "contexts/vector-context.onnx",
            ModelFileRole.SUPERTONIC_VECTOR_BINARY to "contexts/vector-context_qnn.bin",
            ModelFileRole.SUPERTONIC_VOCODER_DESCRIPTOR to "contexts/vocoder-context.onnx",
            ModelFileRole.SUPERTONIC_VOCODER_BINARY to "contexts/vocoder-context_qnn.bin",
            ModelFileRole.SUPERTONIC_TOKENIZER to "assets/tokenizer.json",
            ModelFileRole.SUPERTONIC_UNICODE_INDEXER to "assets/unicode-indexer.i32",
            ModelFileRole.SUPERTONIC_VOICE to "assets/voice.bin",
            ModelFileRole.SUPERTONIC_STYLE to "assets/voice-style.json",
        )
    }
}
