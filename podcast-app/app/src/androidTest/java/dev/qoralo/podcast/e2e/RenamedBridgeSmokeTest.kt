package dev.qoralo.podcast.e2e

import androidx.test.platform.app.InstrumentationRegistry
import dev.qoralo.podcast.BuildConfig
import dev.qoralo.podcast.PodcastApplication
import dev.qoralo.podcast.model.ModelPackRequirement
import dev.qoralo.podcast.model.ModelPackVerifier
import dev.qoralo.podcast.model.ModelRoute
import dev.qoralo.podcast.runtime.ProviderQnnEngine
import dev.qoralo.podcast.runtime.FrozenChapter
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File
import java.security.MessageDigest

/**
 * Proves the rebuilt JNI bridge resolves its registered classes under the renamed package and that a real
 * HTP segment renders. `JNI_OnLoad` fails closed if any `FindClass` path is wrong, so a class-path mismatch
 * surfaces here as `UnsatisfiedLinkError` at load, separately from any later model or runtime failure.
 */
class RenamedBridgeSmokeTest {
    @Test fun registeredClassPathsResolveAndOneSegmentRendersOnHtp() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val args = InstrumentationRegistry.getArguments()
        assumeTrue(args.getString("renamedBridgeSmoke") == "true")
        val context = instrumentation.targetContext
        val app = context.applicationContext as PodcastApplication
        val receipts = File(context.filesDir, "renamed-bridge-smoke").apply { mkdirs() }
        val receipt = File(receipts, "result.json")
        val stage = JSONObject().put("package", context.packageName)
        var phase = "load"
        try {
            // Loading the library runs JNI_OnLoad, which registers SupertonicNative, the wiring probe and the
            // provider natives. Any stale dev/vibevoice path would abort here rather than during synthesis.
            System.loadLibrary("podcast_runtime")
            stage.put("nativeLibraryLoaded", true).put("registrationFailure", false)
            phase = "verify-pack"
            val pack = ModelPackVerifier().verify(
                app.artifacts.modelPackRoot(BuildConfig.SUPERTONIC_PACK_ID),
                ModelPackRequirement(ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP, BuildConfig.SUPERTONIC_PACK_ID,
                    BuildConfig.SUPERTONIC_MANIFEST_SHA256))
            stage.put("packId", BuildConfig.SUPERTONIC_PACK_ID).put("packManifestSha256", pack.manifestSha256)
            phase = "render"
            val text = requireNotNull(args.getString("segmentText"))
            val chapter = FrozenChapter(id = "renamed-bridge-smoke", title = "Bridge smoke", text = text)
            val output = File(receipts, "segment.wav").also { it.delete() }
            val engine = ProviderQnnEngine()
            val metadata = try {
                runBlocking {
                    engine.load(pack, "M1/SID5")
                    engine.renderChapter(chapter, output) { }
                }
            } finally {
                engine.close()
            }
            val bytes = output.readBytes()
            stage.put("renderedFrames", metadata.frameCount).put("sampleRate", metadata.sampleRateHz)
                .put("channels", metadata.channelCount).put("wavBytes", bytes.size.toLong())
                .put("nativeReportedSha256", metadata.sha256)
                .put("wavSha256", MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) })
                .put("status", "passed")
            require(metadata.frameCount > 0 && bytes.size > 44)
            output.delete()
        } catch (error: UnsatisfiedLinkError) {
            // Distinct from a model failure: the bridge itself did not register.
            stage.put("status", "failed").put("phase", phase).put("registrationFailure", true)
                .put("errorType", error.javaClass.name)
            receipt.writeText(stage.toString(2))
            throw AssertionError("Renamed bridge failed to register its native class paths")
        } catch (error: Throwable) {
            stage.put("status", "failed").put("phase", phase).put("registrationFailure", false)
                .put("errorType", error.javaClass.name)
                .put("causeType", error.cause?.javaClass?.name ?: "none")
            receipt.writeText(stage.toString(2))
            throw AssertionError("Bridge loaded but the $phase phase failed; inspect the private receipt")
        }
        receipt.writeText(stage.toString(2))
    }
}
