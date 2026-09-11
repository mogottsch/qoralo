package dev.vibevoice.podcast.e2e

import android.app.Application
import android.os.Process
import android.os.SystemClock
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.espresso.Espresso
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.vibevoice.podcast.BuildConfig
import dev.vibevoice.podcast.MainActivity
import dev.vibevoice.podcast.PodcastApplication
import dev.vibevoice.podcast.data.*
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.util.Timer
import java.util.TimerTask

/** One normal-input SCRIPT-only reproduction via real UI. All receipts/input bindings are app-private. */
@RunWith(AndroidJUnit4::class)
class UserScriptReproductionTest {
    @get:Rule val rule = createEmptyComposeRule()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val app get() = context.applicationContext as PodcastApplication
    private fun <T> db(block: suspend () -> T): T = runBlocking { block() }
    private fun hash(file: File) = app.artifacts.sha256(file)
    private fun write(file: File, value: JSONObject) = ShortProductDiagnostics.json(file, value)
    private fun waitFor(label: String, millis: Long = 15_000, condition: () -> Boolean) {
        val end = SystemClock.elapsedRealtime() + millis
        while (SystemClock.elapsedRealtime() < end) { if (condition()) return; Thread.sleep(100) }
        error("Bounded diagnostic wait failed: $label; no retry")
    }
    private fun click(label: String) {
        rule.waitUntil(15_000) { rule.onAllNodes(hasText(label)).fetchSemanticsNodes().isNotEmpty() }
        rule.onNodeWithText(label).assertIsDisplayed().performClick()
    }
    @Test fun reproduceNormalInputScriptOnly() {
        val args = InstrumentationRegistry.getArguments()
        assumeTrue(args.getString("userScriptDiagnostic") == "one-private-script-v1")
        require(Application.getProcessName() == context.packageName && BuildConfig.SHORT_PRODUCT_E2E)
        val run = requireNotNull(args.getString("diagnosticRun")); require(Regex("user-script-[a-z0-9-]{1,48}").matches(run))
        val parent = File(context.filesDir, "user-failure-diagnostics").apply { mkdirs() }
        val root = File(parent, "$run-driver"); require(root.mkdir())
        val capture = File(parent, run); require(!capture.exists())
        val marker = File(parent, "active.json"); require(!marker.exists())
        require(!File(context.filesDir, "short-product-e2e/active.json").exists())
        val appHash = hash(File(context.applicationInfo.sourceDir))
        val testHash = hash(File(instrumentation.context.applicationInfo.sourceDir))
        require(appHash == args.getString("appApkSha256") && testHash == args.getString("testApkSha256"))
        val originalId = requireNotNull(args.getString("originalEpisodeId"))
        val original = db { app.repository.episode(originalId) }
        val originalJob = requireNotNull(db { app.repository.latestJob(originalId) })
        require(original.phase == EpisodePhase.FAILED && originalJob.status == JobStatus.FAILED && originalJob.kind == JobKind.SCRIPT)
        require(originalJob.id == args.getString("originalJobId") && original.reviewEnabled)
        val sources = db { app.database.podcastDao().sources(originalId) }
        require(sources.size == 1) // Exact observed case, not a replacement tiny fixture.
        val source = sources.single(); val sourceFile = app.repository.resolveArtifact(source.relativePath)
        require(sourceFile.length() == source.byteCount && hash(sourceFile) == source.sha256)
        require(source.sha256 == args.getString("originalSourceSha256"))
        val instructionsHash = ShortProductPolicy.hash(original.instructions.toByteArray())
        require(instructionsHash == args.getString("originalInstructionsSha256"))
        require(db { app.repository.runningJobs() }.isEmpty() && db { app.repository.queuedJobs() }.isEmpty())
        write(File(root, "identity.json"), JSONObject().put("appApkSha256", appHash).put("testApkSha256", testHash)
            .put("originalEpisodeId", originalId).put("originalJobId", originalJob.id).put("privateContent", true))
        val before = db { app.repository.observeEpisodes().first() }.map { it.id }.toSet()
        var owned: String? = null; var scenario: ActivityScenario<MainActivity>? = null; var control: ByteArray? = null
        val timer = Timer("user-script-driver-bound", true)
        timer.schedule(object : TimerTask() { override fun run() {
            runCatching { write(File(root, "driver-timeout.json"), JSONObject().put("limitMs", 540_000)) }
            Process.killProcess(Process.myPid())
        } }, 540_000)
        try {
            scenario = ActivityScenario.launch(MainActivity::class.java)
            val createAction = hasClickAction() and (hasContentDescription("New episode") or hasText("New episode"))
            rule.waitUntil(15_000) { rule.onAllNodes(createAction).fetchSemanticsNodes().isNotEmpty() }
            rule.onNode(createAction).assertIsDisplayed().performClick()
            waitFor("one owned episode") { db { app.repository.observeEpisodes().first() }.map { it.id }.toSet().minus(before).size == 1 }
            owned = db { app.repository.observeEpisodes().first() }.map { it.id }.toSet().minus(before).single()
            val id = requireNotNull(owned)
            write(File(root, "ownership.json"), JSONObject().put("runId", run).put("episodeId", owned).put("createdThroughMainUi", true))
            click("Paste text")
            rule.onNode(hasSetTextAction() and hasText("Source name")).performTextReplacement(source.title)
            rule.onNode(hasSetTextAction() and hasText("Source text")).performTextReplacement(sourceFile.readText())
            Espresso.closeSoftKeyboard(); click("Add source")
            waitFor("copied source persistence") { db { app.database.podcastDao().sources(id) }.size == 1 }
            val copied = db { app.database.podcastDao().sources(id) }.single()
            require(copied.sha256 == source.sha256 && copied.byteCount == source.byteCount && copied.title == source.title)
            click("Continue")
            rule.onNode(hasSetTextAction()).performTextReplacement(original.instructions)
            Espresso.closeSoftKeyboard()
            rule.onNode(hasScrollToIndexAction()).performScrollToNode(hasContentDescription("Review script first"))
            val review = rule.onNodeWithContentDescription("Review script first")
            if (review.fetchSemanticsNode().config.getOrElse(androidx.compose.ui.semantics.SemanticsProperties.ToggleableState) { androidx.compose.ui.state.ToggleableState.Off } != androidx.compose.ui.state.ToggleableState.On) review.performClick()
            review.assertIsOn()
            control = JSONObject().put("schemaVersion", 1).put("runId", run).put("episodeId", owned)
                .put("instructionsSha256", instructionsHash).put("sourceSha256s", JSONArray(listOf(source.sha256)))
                .put("gemmaManifestSha256", BuildConfig.GEMMA_MANIFEST_SHA256).put("appApkSha256", appHash).toString().toByteArray()
            ShortProductDiagnostics.write(File(root, "control-original.json"), control)
            ShortProductDiagnostics.write(marker, control)
            click("Create") // Exactly once. Normal dispatcher/service/coordinator, no injected model output.
            waitFor("private capture claimed", 30_000) { File(capture, "identity.json").isFile }
            waitFor("one terminal SCRIPT job", 480_000) {
                db { app.repository.latestJob(id) }?.status in setOf(JobStatus.COMPLETE, JobStatus.FAILED)
            }
            waitFor("normal service finally", 10_000) { File(capture, "finished.json").isFile }
            val job = requireNotNull(db { app.repository.latestJob(id) }); val result = db { app.repository.episode(id) }
            require(job.kind == JobKind.SCRIPT && result.reviewEnabled && result.lockedRevisionId == null && result.finalAudioPath == null)
            require(original == db { app.repository.episode(originalId) } && originalJob == db { app.repository.latestJob(originalId) })
            require(sources == db { app.database.podcastDao().sources(originalId) } && hash(sourceFile) == source.sha256)
            if (job.status == JobStatus.COMPLETE) require(result.phase == EpisodePhase.SCRIPT_DRAFT && result.activeRevisionId != null)
            else require(result.phase == EpisodePhase.FAILED && File(capture, "job-failure.json").isFile)
            write(File(root, "driver-result.json"), JSONObject().put("status", job.status).put("episodeId", owned).put("jobId", job.id)
                .put("currentChapter", job.currentChapter).put("totalChapters", job.totalChapters)
                .put("safeFailureSummary", job.errorMessage ?: JSONObject.NULL).put("originalRowsAndSourceUnchanged", true)
                .put("sameSourceBytesTitleAndInstructions", true).put("ttsRequests", 0).put("agentEdits", 0).put("retryRequested", false))
        } catch (error: Throwable) {
            runCatching { write(File(root, "private-driver-failure.json"), JSONObject().put("error", error.stackTraceToString()).put("episodeId", owned)) }
            // Only this newly created test episode may be stopped. Never overwrite an already-terminal outcome.
            owned?.let { id -> runCatching { db { app.repository.latestJob(id) }?.let { j ->
                if (j.status == JobStatus.RUNNING) db { app.repository.failJob(id, j.id, "Owned diagnostic driver stopped", "diagnostic_driver") }
                else if (j.status == JobStatus.QUEUED) db { app.repository.failQueuedJob(id, j.id, "Owned diagnostic driver stopped", "diagnostic_driver") }
            } } }
            // Runner/logcat must never receive a Compose tree, raw model text, or the private cause chain.
            throw AssertionError("Owned user-script diagnostic stopped; inspect app-private receipts; no retry")
        } finally {
            val cleanup = runCatching {
                scenario?.close()
                if (control != null && marker.isFile && marker.readBytes().contentEquals(control)) check(marker.delete())
            }
            timer.cancel()
            cleanup.exceptionOrNull()?.let { error -> runCatching {
                write(File(root, "private-driver-cleanup-failure.json"), JSONObject().put("error", error.stackTraceToString()))
            } }
        }
    }
}
