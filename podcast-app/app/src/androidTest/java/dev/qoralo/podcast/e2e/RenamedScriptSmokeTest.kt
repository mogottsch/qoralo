package dev.qoralo.podcast.e2e

import androidx.test.platform.app.InstrumentationRegistry
import dev.qoralo.podcast.BuildConfig
import dev.qoralo.podcast.PodcastApplication
import dev.qoralo.podcast.model.ModelPackRequirement
import dev.qoralo.podcast.model.ModelPackVerifier
import dev.qoralo.podcast.model.ModelRoute
import dev.qoralo.podcast.runtime.GemmaLiteRtGpuEngine
import dev.qoralo.podcast.runtime.EpisodeOutline
import dev.qoralo.podcast.runtime.OutlineChapter
import dev.qoralo.podcast.runtime.SourceMaterial
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File

/**
 * Exercises the LiteRT GPU script path under the renamed application id: pack verification, engine load, one
 * real outline request and one real chapter request. Nothing is written to the user's library; only a private
 * receipt is produced, and it records word counts and stage rather than the generated text.
 */
class RenamedScriptSmokeTest {
    @Test fun gemmaLoadsAndWritesOneChapterUnderTheRenamedId() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val args = InstrumentationRegistry.getArguments()
        assumeTrue(args.getString("renamedScriptSmoke") == "true")
        val context = instrumentation.targetContext
        val app = context.applicationContext as PodcastApplication
        val receipts = File(context.filesDir, "renamed-script-smoke").apply { mkdirs() }
        val receipt = File(receipts, "result.json")
        val stage = JSONObject().put("package", context.packageName)
        var phase = "verify-pack"
        try {
            val pack = ModelPackVerifier().verify(
                app.artifacts.modelPackRoot("gemma-4-e2b"),
                ModelPackRequirement(ModelRoute.GEMMA_4_E2B_LITERT_GPU, "gemma-4-e2b", BuildConfig.GEMMA_MANIFEST_SHA256))
            stage.put("packManifestSha256", pack.manifestSha256)
            val source = SourceMaterial("renamed-script-smoke", "Tram works",
                requireNotNull(args.getString("sourceText")).replace('+', ' '))
            val engine = GemmaLiteRtGpuEngine()
            try {
                runBlocking {
                    phase = "load"
                    engine.load(pack)
                    stage.put("backend", engine.provenance?.backend ?: "unknown")
                        .put("runtimeVersion", engine.provenance?.runtimeVersion ?: "unknown")
                    phase = "outline"
                    val outline: EpisodeOutline = engine.createOutline(listOf(source), "One short chapter for a test.")
                    stage.put("outlineChapters", outline.chapters.size)
                    phase = "chapter"
                    val target: OutlineChapter = outline.chapters.first()
                    val chapter = engine.createChapter(outline, target, listOf(source), "Keep it short.")
                    val words = chapter.text.split(Regex("\\s+")).count { it.isNotBlank() }
                    stage.put("chapterWords", words).put("chapterTitleLength", chapter.title.length)
                    require(words > 0)
                }
            } finally {
                engine.close()
            }
            stage.put("status", "passed")
        } catch (error: UnsatisfiedLinkError) {
            stage.put("status", "failed").put("phase", phase).put("registrationFailure", true)
                .put("errorType", error.javaClass.name)
            receipt.writeText(stage.toString(2))
            throw AssertionError("LiteRT native registration failed under the renamed id")
        } catch (error: Throwable) {
            stage.put("status", "failed").put("phase", phase).put("registrationFailure", false)
                .put("errorType", error.javaClass.name).put("causeType", error.cause?.javaClass?.name ?: "none")
            receipt.writeText(stage.toString(2))
            throw AssertionError("Script path failed in the $phase phase; inspect the private receipt")
        }
        receipt.writeText(stage.toString(2))
    }
}
