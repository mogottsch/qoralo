package dev.vibevoice.podcast.e2e

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.room.withTransaction
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.vibevoice.podcast.MainActivity
import dev.vibevoice.podcast.PodcastApplication
import dev.vibevoice.podcast.data.*
import dev.vibevoice.podcast.runtime.*
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.flow.first
import org.json.JSONObject
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import java.util.UUID

/** Genuine normal UI lock→AUDIO dispatcher/service→provider HTP→Ready, starting from a labelled copy of a real generated chapter. */
@RunWith(AndroidJUnit4::class)
class ProviderAppIntegrationTest {
    @get:Rule val rule = createEmptyComposeRule()
    private fun <T> db(block: suspend () -> T): T = runBlocking { block() }
    private fun hash(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    @Test fun copiedRealChapterCompletesNormalAudioJob() {
        val args = InstrumentationRegistry.getArguments()
        assumeTrue(args.getString("providerIntegration") == "copied-real-chapter-v1")
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext;val app = context.applicationContext as PodcastApplication
        val run = requireNotNull(args.getString("diagnosticRun"));require(Regex("provider-app-[a-z0-9-]{1,48}").matches(run))
        val parent = File(context.filesDir, "provider-integration").apply { mkdirs() }
        val root = File(parent, "$run-driver");require(root.mkdir())
        fun json(name: String, value: JSONObject) = ShortProductDiagnostics.json(File(root, name), value)
        var scenario: ActivityScenario<MainActivity>? = null
        try {
            val appHash = app.artifacts.sha256(File(context.applicationInfo.sourceDir))
            val testHash = app.artifacts.sha256(File(instrumentation.context.applicationInfo.sourceDir))
            require(appHash == args.getString("appApkSha256") && testHash == args.getString("testApkSha256"))
            require(ProviderAudioPlan.selected)
            require(db { app.repository.runningJobs() }.isEmpty() && db { app.repository.queuedJobs() }.isEmpty())
            require(!File(parent, "active.json").exists())
            val originalId = requireNotNull(args.getString("originalEpisodeId"))
            val originalRevisionId = requireNotNull(args.getString("originalRevisionId"))
            val original = db { app.repository.episode(originalId) }
            val revision = requireNotNull(db { app.database.podcastDao().revision(originalRevisionId) })
            require(revision.episodeId == originalId && revision.contentHash == args.getString("originalRevisionSha256"))
            require(app.artifacts.sha256(app.repository.resolveArtifact(revision.relativePath)) == revision.contentHash)
            val chapter = db { app.repository.chapters(originalRevisionId) }.single { it.stableChapterId == args.getString("originalChapterId") }
            val sourceHash = hash(chapter.text.toByteArray(Charsets.UTF_8))
            require(sourceHash == args.getString("chapterSha256"))
            val oldIds = db { app.database.podcastDao().observeEpisodes().first() }.map { it.id }.toSet()
            // Pure native stochastic/ABI helper check, before model sessions. No model or text substitution.
            NativeAppRuntime.ensureLoaded()
            val noise = ProviderNative.gaussianProbe(2160000)
            val noiseBytes = ByteBuffer.allocate(noise.size * 4).order(ByteOrder.LITTLE_ENDIAN)
            noise.forEach(noiseBytes::putFloat)
            val noiseHash = hash(noiseBytes.array())
            json("native-rng.json", JSONObject().put("draws", noise.size).put("sha256", noiseHash).put("modelCalls", 0))
            require(noiseHash == "7c44878a5b88882b01701839a22b3cfde39078451f15354e7a33d269993b49a8")
            scenario = ActivityScenario.launch(MainActivity::class.java)
            rule.waitUntil(15_000) { rule.onAllNodes(hasContentDescription("New episode")).fetchSemanticsNodes().isNotEmpty() }
            rule.onNodeWithContentDescription("New episode").performClick()
            var owned: EpisodeEntity? = null
            rule.waitUntil(15_000) {
                owned = db { app.database.podcastDao().observeEpisodes().first() }.singleOrNull { it.id !in oldIds }
                owned != null
            }
            val id = requireNotNull(owned).id
            json("identity.json", JSONObject().put("runId", run).put("appApkSha256", appHash).put("testApkSha256", testHash)
                .put("originalEpisodeId", originalId).put("originalRevisionId", revision.id).put("originalRevisionSha256", revision.contentHash)
                .put("originalChapterId", chapter.stableChapterId).put("rawChapterSha256", sourceHash).put("packSha256", ProviderAudioPlan.PACK_SHA256))
            json("ownership.json", JSONObject().put("runId", run).put("episodeId", id).put("createdThroughMainUi", true)
                .put("startPoint", "Test-only copy of one immutable real model-generated chapter; no new SCRIPT inference"))
            val sources = db { app.database.podcastDao().sources(originalId) };require(sources.size == 1)
            val source = sources.single()
            app.repository.resolveArtifact(source.relativePath).inputStream().use { input ->
                db { app.repository.addSource(id, "Copied source for HTP validation", "text/plain", input) }
            }
            val newRevision = UUID.randomUUID().toString();val title = "Provider HTP ${run.takeLast(12)}"
            val contents = listOf(ChapterDraft(chapter.stableChapterId, chapter.title, chapter.text))
            val stored = app.artifacts.writeRevision(id, newRevision, title, contents)
            db { app.database.withTransaction {
                val fresh = app.repository.episode(id)
                require(fresh.phase == EpisodePhase.SOURCES && fresh.activeRevisionId == null)
                app.database.podcastDao().insertRevision(ScriptRevisionEntity(newRevision, id, null, 1, title, stored.sha256, stored.relativePath, System.currentTimeMillis()))
                app.database.podcastDao().insertChapters(listOf(ChapterEntity(UUID.randomUUID().toString(), newRevision, chapter.stableChapterId, 0,
                    chapter.title, chapter.text, chapter.approximateDurationSeconds)))
                app.database.podcastDao().updateEpisode(fresh.copy(title = title, phase = EpisodePhase.SCRIPT_DRAFT, activeRevisionId = newRevision,
                    instructions = "Provider audio integration from a copied real chapter; no new script generation", reviewEnabled = true, updatedAtEpochMs = System.currentTimeMillis()))
            } }
            require(hash(db { app.repository.activeRevision(id) }.second.single().text.toByteArray()) == sourceHash)
            val capability = app.repository.audioTextCapacity(listOf(chapter.text));require(capability.fits && capability.providerPipeline)
            require(capability.chapters.single().segmentCount == 15)
            val control = JSONObject().put("runId", run).put("episodeId", id).put("revisionId", newRevision)
                .put("revisionSha256", stored.sha256).put("appApkSha256", appHash).put("packSha256", ProviderAudioPlan.PACK_SHA256)
            val controlBytes = (control.toString(2) + "\n").toByteArray()
            File(parent, "active.json").writeBytes(controlBytes);File(root, "control-original.json").writeBytes(controlBytes)
            scenario?.close();scenario = ActivityScenario.launch(MainActivity::class.java)
            rule.waitUntil(15_000) { rule.onAllNodes(hasText(title)).fetchSemanticsNodes().isNotEmpty() }
            rule.onNodeWithText(title).performClick()
            rule.waitUntil(15_000) { rule.onAllNodes(hasText("Provider speech pipeline")).fetchSemanticsNodes().isNotEmpty() }
            rule.onNodeWithText("Lock script & create audio").assertIsEnabled().performClick()
            rule.onNodeWithText("Lock & create").performClick()
            var audio: GenerationJobEntity? = null
            rule.waitUntil(15_000) { audio = db { app.repository.latestJob(id) }; audio != null }
            val audioId = requireNotNull(audio).id
            require(audio!!.kind == JobKind.AUDIO && Regex("[a-f0-9]{64}").matches(audioId))
            json("audio-job.json", JSONObject().put("jobId", audioId).put("episodeId", id).put("revisionId", newRevision)
                .put("revisionSha256", stored.sha256).put("kind", audio!!.kind).put("logicalChapters", 1).put("providerSegments", 15))
            val deadline = System.nanoTime() + 600_000_000_000L
            var finished: EpisodeEntity
            while (true) {
                finished = db { app.repository.episode(id) }
                val current = requireNotNull(db { app.repository.latestJob(id) })
                require(current.id == audioId)
                if (finished.phase == EpisodePhase.FROZEN_READY || current.status == JobStatus.FAILED) break
                require(System.nanoTime() < deadline) { "Provider AUDIO terminal-state deadline" }
                Thread.sleep(500)
            }
            require(finished.phase == EpisodePhase.FROZEN_READY) { "Provider AUDIO failed; preserve exact private receipts" }
            val final = app.repository.resolveArtifact(requireNotNull(finished.finalAudioPath))
            val metadata = WavInspector.inspectSupertonicOutput(final)
            require(metadata.sha256 == finished.finalAudioSha256)
            require(original == db { app.repository.episode(originalId) })
            require(app.artifacts.sha256(app.repository.resolveArtifact(revision.relativePath)) == revision.contentHash)
            require(File(parent, "$run/job-identity.json").isFile) { "Provider diagnostic retention was not bound" }
            json("driver-result.json", JSONObject().put("status", "copied_real_chapter_normal_audio_complete")
                .put("appApkSha256", appHash).put("testApkSha256", testHash).put("episodeId", id).put("jobId", audioId)
                .put("revisionId", newRevision).put("revisionSha256", stored.sha256).put("referenceTextSha256", sourceHash)
                .put("finalAudioPath", finished.finalAudioPath).put("wavSha256", metadata.sha256).put("wavBytes", final.length())
                .put("frames", metadata.frameCount).put("sampleRateHz", metadata.sampleRateHz).put("providerSegments", 15)
                .put("newScriptModelCalls", 0).put("newAudioJobs", 1).put("originalEpisodeUnchanged", true)
                .put("playOrExportRequested", false).put("listeningReview", "not_reviewed"))
        } catch (error: Throwable) {
            runCatching { json("private-driver-failure.json", JSONObject().put("error", error.stackTraceToString())) }
            throw AssertionError("Provider integration stopped; inspect private originals; no automatic model retry")
        } finally { runCatching { scenario?.close() } }
    }
}
