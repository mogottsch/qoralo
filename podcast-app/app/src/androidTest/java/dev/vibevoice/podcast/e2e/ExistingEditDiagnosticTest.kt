package dev.vibevoice.podcast.e2e

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.room.withTransaction
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.ai.edge.litertlm.Conversation
import dev.vibevoice.podcast.BuildConfig
import dev.vibevoice.podcast.MainActivity
import dev.vibevoice.podcast.PodcastApplication
import dev.vibevoice.podcast.data.*
import dev.vibevoice.podcast.diagnostics.PrivateFailureReceipt
import dev.vibevoice.podcast.generation.agentEditRequest
import dev.vibevoice.podcast.model.ModelPackRequirement
import dev.vibevoice.podcast.model.ModelPackVerifier
import dev.vibevoice.podcast.model.ModelRoute
import dev.vibevoice.podcast.runtime.*
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/** One reconstructed real EDIT request; no new jobs/revisions or committed episode writes. Not product E2E. */
@RunWith(AndroidJUnit4::class)
class ExistingEditDiagnosticTest {
    @get:Rule val rule = createEmptyComposeRule()
    private fun <T> db(block: suspend () -> T): T = runBlocking { block() }
    private class ProbeRollback(val reopened: Boolean) : RuntimeException("Intentional draft-recovery rollback")

    @Test fun captureOneExistingEditAndVerifyDraftRecovery() {
        val args = InstrumentationRegistry.getArguments()
        assumeTrue(args.getString("editDiagnostic") == "existing-failed-edit-v1")
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val app = context.applicationContext as PodcastApplication
        val run = requireNotNull(args.getString("diagnosticRun"))
        require(Regex("edit-probe-[a-z0-9-]{1,48}").matches(run))
        val parent = File(context.filesDir, "user-failure-diagnostics").apply { mkdirs() }
        val root = File(parent, "$run-driver"); require(root.mkdir())
        fun json(name: String, data: JSONObject) = ShortProductDiagnostics.json(File(root, name), data)
        var scenario: ActivityScenario<MainActivity>? = null
        var engine: GemmaLiteRtGpuEngine? = null
        var receipt: PrivateFailureReceipt? = null
        try {
            val appHash = app.artifacts.sha256(File(context.applicationInfo.sourceDir))
            val testHash = app.artifacts.sha256(File(instrumentation.context.applicationInfo.sourceDir))
            require(appHash == args.getString("appApkSha256") && testHash == args.getString("testApkSha256"))
            require(!File(parent, "active.json").exists() && !File(context.filesDir, "short-product-e2e/active.json").exists())
            val id = requireNotNull(args.getString("originalEpisodeId"))
            val before = db { app.repository.episode(id) }
            val revision = db { app.repository.activeRevision(id) }
            val job = requireNotNull(db { app.repository.latestJob(id) })
            require(canReturnToSavedDraft(before, job))
            require(job.id == args.getString("originalJobId"))
            require(revision.first.id == args.getString("revisionId") && revision.first.contentHash == args.getString("revisionSha256"))
            val message = requireNotNull(db { app.database.podcastDao().message(requireNotNull(job.requestMessageId)) })
            require(message.episodeId == id && message.role == AgentRole.USER && message.baseRevisionId == revision.first.id)
            val instructionHash = PrivateFailureReceipt.sha256(message.text.toByteArray(Charsets.UTF_8))
            require(instructionHash == args.getString("editInstructionSha256"))
            require(db { app.repository.runningJobs() }.isEmpty() && db { app.repository.queuedJobs() }.isEmpty())
            val artifact = app.repository.resolveArtifact(revision.first.relativePath)
            val fileHash = app.artifacts.sha256(artifact); require(fileHash == revision.first.contentHash)
            val request = agentEditRequest(revision.first, revision.second, message)
            val requestHash = PrivateFailureReceipt.sha256(request.toByteArray(Charsets.UTF_8))
            val identity = JSONObject().put("schemaVersion", 1).put("runId", run)
                .put("appApkSha256", appHash).put("testApkSha256", testHash)
                .put("originalEpisodeId", id).put("originalJobId", job.id)
                .put("revisionId", revision.first.id).put("revisionSha256", fileHash)
                .put("instructionSha256", instructionHash).put("requestSha256", requestHash)
                .put("requestReconstructedFromSavedRows", true).put("originalRequestWasNotCaptured", true)
                .put("pid", android.os.Process.myPid()).put("privateContent", true).put("noDatabaseWrites", true)
            json("identity.json", identity)
            val currentReceipt = PrivateFailureReceipt(File(parent, run), identity)
            receipt = currentReceipt
            val observer = object : GemmaRequestObserver {
                override fun beforeRequest(mode: String, request: String, systemInstruction: String, outputLimit: Int) =
                    currentReceipt.beforeRequest(mode, request, systemInstruction, outputLimit)
                override fun responseReturned(raw: String) = currentReceipt.responseReturned(raw)
                override fun requestFailed(error: GemmaRequestException) = currentReceipt.failed(error)
                @OptIn(com.google.ai.edge.litertlm.ExperimentalApi::class)
                override fun conversationReturned(conversation: Conversation) {
                    // Raw output has already been offered to the private receipt. Optional counters never gate it.
                    val metrics = JSONObject().put("scope", "SDK counters after one synchronous edit send; not a benchmark campaign")
                    runCatching { conversation.getTokenCount() }.fold(
                        { metrics.put("conversationKvTokenCount", it) },
                        { metrics.put("conversationKvTokenCount", JSONObject.NULL).put("kvCounterUnavailableType", it.javaClass.name) })
                    runCatching { conversation.getBenchmarkInfo() }.fold(
                        { metrics.put("lastPrefillTokenCount", it.lastPrefillTokenCount).put("lastDecodeTokenCount", it.lastDecodeTokenCount) },
                        { metrics.put("lastPrefillTokenCount", JSONObject.NULL).put("lastDecodeTokenCount", JSONObject.NULL)
                            .put("benchmarkCountersUnavailableType", it.javaClass.name) })
                    metrics.put("stopReason", JSONObject.NULL).put("stopReasonUnavailable", "Synchronous Message API does not expose finish reason here")
                    json("sdk-token-observation.json", metrics)
                }
            }
            val pack = ModelPackVerifier().verify(app.artifacts.modelPackRoot("gemma-4-e2b"),
                ModelPackRequirement(ModelRoute.GEMMA_4_E2B_LITERT_GPU, "gemma-4-e2b", BuildConfig.GEMMA_MANIFEST_SHA256))
            currentReceipt.modelBinding(JSONObject().put("manifestSha256", pack.manifestSha256).put("packId", pack.id)
                .put("packVersion", pack.version).put("runtime", "LiteRT-LM 0.16.1").put("backend", "GPU")
                .put("samplerAndSystemInstructionUnchanged", true).put("cpuFallback", false))
            val concrete = GemmaLiteRtGpuEngine(observer); engine = concrete
            val started = System.nanoTime()
            db { concrete.load(pack) }
            val ready = System.nanoTime()
            var syntaxAccepted = false
            var parseFailure: GemmaRequestException? = null
            try {
                val parsed = db { concrete.editScript(request) } // Exactly one call; never retries or commits the response.
                syntaxAccepted = true
                ShortProductDiagnostics.json(File(root, "private-parsed-response.json"), JSONObject(parsed))
            } catch (error: GemmaRequestException) {
                parseFailure = error
            } finally {
                concrete.close(); engine = null
                currentReceipt.finished(); receipt = null
            }
            val completed = System.nanoTime()
            json("model-result.json", JSONObject().put("status", if (syntaxAccepted) "json_syntax_accepted" else "request_failed")
                .put("safeFailure", parseFailure?.message ?: JSONObject.NULL)
                .put("failurePhase", parseFailure?.failurePhase?.name ?: JSONObject.NULL)
                .put("requestSha256", requestHash).put("modelCallsRequested", 1)
                .put("loadWallMs", (ready-started)/1_000_000.0).put("requestAndCloseWallMs", (completed-ready)/1_000_000.0)
                .put("responseCommitted", false).put("instructionFulfillmentNotAutomaticallyAccepted", true))
            // Prove existing-draft recovery under an unconditional outer rollback. No original episode transition commits.
            val reopened = db {
                try {
                    app.database.withTransaction {
                        app.repository.returnToSavedDraft(id, job.id, revision.first.id)
                        val restored = app.repository.episode(id)
                        throw ProbeRollback(restored.phase == EpisodePhase.SCRIPT_DRAFT && restored.activeRevisionId == revision.first.id)
                    }
                } catch (rollback: ProbeRollback) { rollback.reopened }
            }
            require(reopened)
            require(before == db { app.repository.episode(id) } && job == db { app.repository.latestJob(id) })
            scenario = ActivityScenario.launch(MainActivity::class.java)
            rule.waitUntil(15_000) { rule.onAllNodes(hasText(before.title)).fetchSemanticsNodes().isNotEmpty() }
            rule.onNodeWithText(before.title).performClick()
            rule.waitUntil(15_000) { rule.onAllNodes(hasText("Return to saved draft")).fetchSemanticsNodes().isNotEmpty() }
            rule.onNodeWithText("Return to saved draft").performScrollTo().assertIsDisplayed().assertIsEnabled() // Deliberately NOT clicked.
            require(before == db { app.repository.episode(id) } && revision == db { app.repository.activeRevision(id) })
            require(job == db { app.repository.latestJob(id) } && fileHash == app.artifacts.sha256(artifact))
            require(db { app.repository.runningJobs() }.isEmpty() && db { app.repository.queuedJobs() }.isEmpty())
            json("driver-result.json", JSONObject().put("status", "one_existing_edit_observed_and_recovery_ui_verified")
                .put("appApkSha256", appHash).put("testApkSha256", testHash).put("episodeId", id)
                .put("revisionId", revision.first.id).put("revisionSha256", fileHash).put("requestSha256", requestHash)
                .put("jsonSyntaxAccepted", syntaxAccepted).put("failurePhase", parseFailure?.failurePhase?.name ?: JSONObject.NULL)
                .put("recoveryButtonAvailable", true).put("recoveryButtonClicked", false)
                .put("recoveryTransactionAlwaysRolledBack", true).put("originalDraftAndJobUnchanged", true)
                .put("modelCallsRequested", 1).put("newJobs", 0).put("newRevisions", 0).put("ttsPlayExport", false))
        } catch (error: Throwable) {
            runCatching { json("private-driver-failure.json", JSONObject().put("error", error.stackTraceToString())) }
            throw AssertionError("Existing edit diagnostic stopped; inspect private receipts; no automatic retry")
        } finally {
            runCatching { engine?.close() }
            runCatching { receipt?.finished() }
            runCatching { scenario?.close() }.exceptionOrNull()?.let { error -> runCatching {
                json("private-driver-cleanup-failure.json", JSONObject().put("error", error.stackTraceToString()))
            } }
        }
    }
}
