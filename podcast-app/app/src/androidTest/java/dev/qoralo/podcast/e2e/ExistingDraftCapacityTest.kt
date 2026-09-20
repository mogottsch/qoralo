package dev.qoralo.podcast.e2e

import android.os.Process
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.room.withTransaction
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.qoralo.podcast.MainActivity
import dev.qoralo.podcast.PodcastApplication
import dev.qoralo.podcast.data.EpisodePhase
import dev.qoralo.podcast.runtime.AudioTextCapacityException
import dev.qoralo.podcast.runtime.SupertonicTextCapacity
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.util.Timer
import java.util.TimerTask

/** Reuses the genuine persisted full draft. ZERO model calls/jobs/edits/locks/playback. */
@RunWith(AndroidJUnit4::class)
class ExistingDraftCapacityTest {
    @get:Rule val rule = createEmptyComposeRule()
    private fun <T> db(block: suspend () -> T): T = runBlocking { block() }
    private class ProbeRollback(val observed: Throwable?) : RuntimeException("Intentional read-only guard probe rollback")

    @Test fun fullDraftCannotLockOrDispatchAudio() {
        val args = InstrumentationRegistry.getArguments()
        assumeTrue(args.getString("capacityDiagnostic") == "existing-draft-no-model-v1")
        val instrumentation = InstrumentationRegistry.getInstrumentation(); val context = instrumentation.targetContext
        val app = context.applicationContext as PodcastApplication
        val run = requireNotNull(args.getString("diagnosticRun")); require(Regex("capacity-ui-[a-z0-9-]{1,48}").matches(run))
        val root = File(context.filesDir, "user-failure-diagnostics/$run-driver"); require(root.mkdirs())
        fun json(name: String, value: JSONObject) = ShortProductDiagnostics.json(File(root, name), value)
        val appHash = app.artifacts.sha256(File(context.applicationInfo.sourceDir))
        val testHash = app.artifacts.sha256(File(instrumentation.context.applicationInfo.sourceDir))
        require(appHash == args.getString("appApkSha256") && testHash == args.getString("testApkSha256"))
        val id = requireNotNull(args.getString("originalEpisodeId"))
        var scenario: ActivityScenario<MainActivity>? = null
        val timer = Timer("capacity-ui-bound", true)
        timer.schedule(object : TimerTask() { override fun run() {
            runCatching { json("driver-timeout.json", JSONObject().put("limitMs", 90_000)) }
            Process.killProcess(Process.myPid())
        } },90_000)
        try {
            val before = db { app.repository.episode(id) }
            val revision = db { app.repository.activeRevision(id) }
            val job = db { app.repository.latestJob(id) }
            require(before.phase == EpisodePhase.SCRIPT_DRAFT && before.lockedRevisionId == null)
            require(revision.first.id == args.getString("revisionId") && revision.first.contentHash == args.getString("revisionSha256"))
            require(db { app.repository.runningJobs() }.isEmpty() && db { app.repository.queuedJobs() }.isEmpty())
            val artifact = app.repository.resolveArtifact(revision.first.relativePath)
            val fileHash = app.artifacts.sha256(artifact)
            require(fileHash == revision.first.contentHash) // Existing bytes must match the pinned genuine revision, not just remain unchanged.
            val capacity = SupertonicTextCapacity.configured(revision.second.map { it.text })
            require(capacity.textLength == 239 && capacity.maxNormalizedCodePoints == 230 && !capacity.fits)
            // Rollback even if a regression mistakenly queues work: no AUDIO row can become visible/dispatchable.
            val rejected = db {
                try {
                    app.database.withTransaction {
                        val observed = runCatching { app.repository.lockAndQueueAudio(id) }.exceptionOrNull()
                        throw ProbeRollback(observed)
                    }
                } catch (rollback: ProbeRollback) { rollback.observed }
            }
            require(rejected is AudioTextCapacityException && !rejected.capacity.fits)
            require(before == db { app.repository.episode(id) } && job == db { app.repository.latestJob(id) })
            scenario = ActivityScenario.launch(MainActivity::class.java)
            rule.waitUntil(15_000) { rule.onAllNodes(hasText(before.title)).fetchSemanticsNodes().isNotEmpty() }
            rule.onNodeWithText(before.title).performClick()
            rule.waitUntil(15_000) { rule.onAllNodes(hasText("Audio unavailable for this draft")).fetchSemanticsNodes().isNotEmpty() }
            rule.onNodeWithText("Audio unavailable for this draft").assertIsDisplayed()
            rule.onNodeWithText("Lock script & create audio").assertIsNotEnabled()
            rule.onNodeWithText("Edit with agent").assertIsEnabled()
            require(before == db { app.repository.episode(id) } && revision == db { app.repository.activeRevision(id) })
            require(job == db { app.repository.latestJob(id) } && fileHash == app.artifacts.sha256(artifact))
            require(!File(context.filesDir, "user-failure-diagnostics/active.json").exists())
            require(!File(context.filesDir, "short-product-e2e/active.json").exists())
            json("driver-result.json", JSONObject().put("status", "existing_full_draft_capacity_block_verified")
                .put("appApkSha256", appHash).put("testApkSha256", testHash)
                .put("episodeId", id).put("revisionId", revision.first.id).put("revisionSha256", fileHash)
                .put("textLength", capacity.textLength).put("maxNormalizedCodePoints", capacity.maxNormalizedCodePoints)
                .put("chapters", JSONArray(capacity.chapters.map { c -> JSONObject().put("position", c.position)
                    .put("normalizedCodePoints", c.normalizedCodePoints).put("activeCodePointsWithLanguageTags", c.activeCodePoints).put("fits", c.fits) }))
                .put("repositoryRejectedBeforeCommit", true).put("outerProbeTransactionAlwaysRolledBack", true)
                .put("lockDisabled", true).put("agentEditStillAvailable", true).put("draftRowsAndFileUnchanged", true)
                .put("newModelCalls", 0).put("newJobs", 0).put("playOrExportRequested", false))
        } catch (error: Throwable) {
            runCatching { json("private-driver-failure.json", JSONObject().put("error", error.stackTraceToString())) }
            throw AssertionError("Capacity guard diagnostic stopped; inspect private receipts; no model retry")
        } finally {
            runCatching { scenario?.close() }.exceptionOrNull()?.let { error -> runCatching {
                json("private-driver-cleanup-failure.json", JSONObject().put("error", error.stackTraceToString()))
            } }
            timer.cancel()
        }
    }
}
