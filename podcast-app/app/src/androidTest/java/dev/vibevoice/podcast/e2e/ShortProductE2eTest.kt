package dev.vibevoice.podcast.e2e

import android.app.Application
import android.content.Intent
import android.graphics.Bitmap
import android.os.Bundle
import android.os.Process
import android.os.SystemClock
import android.provider.DocumentsContract
import android.view.accessibility.AccessibilityNodeInfo
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.espresso.Espresso
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.vibevoice.podcast.MainActivity
import dev.vibevoice.podcast.PodcastApplication
import dev.vibevoice.podcast.data.*
import dev.vibevoice.podcast.runtime.WavInspector
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

/** ONE real UI/Room/dispatcher/native/SAF workflow. Never seed a draft, import audio, or substitute engines. */
@RunWith(AndroidJUnit4::class)
class ShortProductE2eTest {
    @get:Rule val rule = createEmptyComposeRule()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val app get() = context.applicationContext as PodcastApplication
    private lateinit var root: File
    private var episodeId: String? = null
    private var deadline = 0L
    private fun json(name: String, value: JSONObject) = ShortProductDiagnostics.json(File(root, name), value)
    private fun text(name: String, value: String) = ShortProductDiagnostics.write(File(root, name), value.toByteArray())
    private fun <T> db(block: suspend () -> T): T = runBlocking { block() }
    private fun waitUntil(label: String, millis: Long = 15_000, condition: () -> Boolean) {
        val end = minOf(deadline, SystemClock.elapsedRealtime() + millis)
        while (SystemClock.elapsedRealtime() < end) {
            if (condition()) return
            Thread.sleep(100)
        }
        error("Deadline: $label; no retry")
    }
    private fun readJson(file: File): JSONObject {
        var parsed: JSONObject? = null
        waitUntil("complete evidence ${file.name}", 2_000) { parsed = runCatching { JSONObject(file.readText()) }.getOrNull(); parsed != null }
        return requireNotNull(parsed)
    }
    private fun shown(matcher: SemanticsMatcher) {
        rule.waitUntil(15_000) { rule.onAllNodes(matcher).fetchSemanticsNodes().isNotEmpty() }
    }
    private fun click(label: String) { shown(hasText(label)); rule.onNodeWithText(label).assertIsDisplayed().performClick() }
    private fun icon(label: String) { shown(hasContentDescription(label)); rule.onNodeWithContentDescription(label).assertIsDisplayed().performClick() }
    private fun episode() = db { app.repository.episode(requireNotNull(episodeId)) }
    private fun waitPhase(phase: String, millis: Long) = waitUntil(phase, millis) {
        val value = episode()
        check(value.phase != EpisodePhase.FAILED) { "Owned job failed: ${value.failureMessage}" }
        value.phase == phase
    }
    private fun revision() = db { app.repository.activeRevision(requireNotNull(episodeId)) }
    private fun capture(name: String) {
        // Diagnostic only: not a synthetic-gallery paired-image claim. Failure may contain private UI.
        runCatching {
            val dir = File(root, ".private-ui").apply { mkdirs() }
            val tree = instrumentation.uiAutomation.rootInActiveWindow
            ShortProductDiagnostics.write(File(dir, "$name-tree.txt"), walk(tree).joinToString("\n") {
                "${it.windowId}\t${it.packageName}\t${it.viewIdResourceName}\t${it.text}\t${it.contentDescription}"
            }.toByteArray())
            instrumentation.uiAutomation.takeScreenshot()?.let { image ->
                File(dir, "$name.png").outputStream().use { image.compress(Bitmap.CompressFormat.PNG, 100, it) }
                image.recycle()
            }
        }
    }

    @Test fun oneOwnedShortEpisodeThroughRealProductionWorkflow() {
        val args = InstrumentationRegistry.getArguments()
        assumeTrue("Exact separate short-product slot required", args.getString("shortProductApproved") == ShortProductPolicy.CONTRACT_SHA)
        val run = requireNotNull(args.getString("shortProductRunId")); require(ShortProductPolicy.validRun(run))
        require(Application.getProcessName() == context.packageName)
        val contract = ShortProductPolicy.load(context)
        root = File(context.filesDir, "${ShortProductPolicy.DIRECTORY}/$run"); check(!root.exists() && root.mkdirs())
        deadline = SystemClock.elapsedRealtime() + ShortProductPolicy.DRIVER_MS
        val timer = Timer("short-product-driver-bound", true)
        timer.schedule(object : TimerTask() { override fun run() {
            runCatching { json("driver-timeout.json", JSONObject().put("limitMs", ShortProductPolicy.DRIVER_MS)) }
            Process.killProcess(Process.myPid())
        } }, ShortProductPolicy.DRIVER_MS)
        var scenario: ActivityScenario<MainActivity>? = null
        val marker = File(root.parentFile, "active.json")
        var controlBytes: ByteArray? = null
        try {
            check(!marker.exists()) { "Existing diagnostic control is not ours; stop without removal" }
            json("contract.json", contract)
            val appHash = ShortProductPolicy.hash(File(context.applicationInfo.sourceDir).readBytes())
            val testHash = ShortProductPolicy.hash(File(instrumentation.context.applicationInfo.sourceDir).readBytes())
            json("identity.json", JSONObject().put("appApkSha256", appHash).put("testApkSha256", testHash)
                .put("pid", Process.myPid()).put("process", Application.getProcessName()).put("fingerprint", android.os.Build.FINGERPRINT))
            require(appHash == args.getString("appApkSha256") && testHash == args.getString("testApkSha256"))
            val before = db { app.repository.observeEpisodes().first() }.map { it.id }.toSet()
            scenario = ActivityScenario.launch(MainActivity::class.java)
            val createAction = hasClickAction() and (hasContentDescription("New episode") or hasText("New episode"))
            rule.waitUntil(15_000) { rule.onAllNodes(createAction).fetchSemanticsNodes().isNotEmpty() }
            rule.onNode(createAction).assertIsDisplayed().performClick()
            waitUntil("one newly created episode") { db { app.repository.observeEpisodes().first() }.map { it.id }.toSet().minus(before).size == 1 }
            episodeId = db { app.repository.observeEpisodes().first() }.map { it.id }.toSet().minus(before).single()
            json("ownership.json", JSONObject().put("runId", run).put("episodeId", episodeId).put("createdThroughMainUi", true))
            val title = "Short plumbing ${requireNotNull(episodeId).take(8)}"
            val control = JSONObject().put("runId", run).put("episodeId", episodeId).put("contractSha256", ShortProductPolicy.CONTRACT_SHA)
            controlBytes = control.toString().toByteArray()
            ShortProductDiagnostics.write(File(root, "control-original.json"), controlBytes)
            ShortProductDiagnostics.write(marker, controlBytes)
            rule.runOnIdle { ShortProductDiagnostics.enableUi(root, requireNotNull(episodeId)) }
            click("Paste text")
            rule.onNode(hasSetTextAction() and hasText("Source name")).performTextReplacement("Short shelf source")
            val source = ShortProductPolicy.asset(context, "source.txt")
            rule.onNode(hasSetTextAction() and hasText("Source text")).performTextReplacement(source)
            Espresso.closeSoftKeyboard(); click("Add source")
            waitUntil("source persistence") { db { app.repository.observeSources(requireNotNull(episodeId)).first() }.size == 1 }
            capture("source-added"); click("Continue")
            val instructions = ShortProductPolicy.asset(context, "instructions.txt").replace("{TITLE}", title)
            text("actual-instructions.txt", instructions)
            rule.onNode(hasSetTextAction()).performTextReplacement(instructions)
            Espresso.closeSoftKeyboard()
            rule.onNode(hasScrollToIndexAction()).performScrollToNode(hasContentDescription("Review script first"))
            val review = rule.onNodeWithContentDescription("Review script first")
            if (review.fetchSemanticsNode().config.getOrElse(androidx.compose.ui.semantics.SemanticsProperties.ToggleableState) { androidx.compose.ui.state.ToggleableState.Off } != androidx.compose.ui.state.ToggleableState.On) review.performClick()
            review.assertIsOn(); click("Create")
            waitUntil("production generation started", 30_000) { File(root, "jobs").listFiles().orEmpty().any { File(it, "started.json").isFile } }
            val started = File(root, "jobs").listFiles().orEmpty().single().resolve("started.json")
            val generationPid = readJson(started).getInt("pid")
            assertNotEquals(Process.myPid(), generationPid)
            // Real Home/reopen, without force-stop, data/task clear, or a second Create action.
            shell("input keyevent KEYCODE_HOME")
            Thread.sleep(1_200)
            val generationName = File("/proc/$generationPid/cmdline").readBytes().toString(Charsets.UTF_8).trimEnd('\u0000')
            assertEquals("${context.packageName}:generation", generationName)
            context.startActivity(Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT))
            json("background-reopen.json", JSONObject().put("generationPid", generationPid).put("generationNameAfterHome", generationName).put("homeAndReopen", true)
                .put("forceStopOrTaskClear", false).put("redispatchRequested", false))
            waitPhase(EpisodePhase.SCRIPT_DRAFT, 430_000)
            waitUntil("script terminal") { db { app.repository.latestJob(requireNotNull(episodeId)) }?.status == JobStatus.COMPLETE }
            val (first, firstChapters) = revision()
            assertEquals(ShortProductPolicy.chapterIds, firstChapters.map { it.stableChapterId })
            assertTrue(firstChapters.all { it.text.isNotBlank() }) // brief target does not prevent initial review/ONE planned edit
            val firstBytes = app.repository.resolveArtifact(first.relativePath).readBytes()
            text("first-revision.json", firstBytes.toString(Charsets.UTF_8)); capture("initial-review")
            click("Edit with agent")
            val edit = ShortProductPolicy.asset(context, "agent.txt").replace("{TITLE}", title)
            text("actual-agent-request.txt", edit)
            rule.onNode(hasSetTextAction()).performTextReplacement(edit)
            Espresso.closeSoftKeyboard(); icon("Send change request")
            waitUntil("one agent revision", 190_000) {
                val latest = db { app.repository.latestJob(requireNotNull(episodeId)) }
                check(latest?.status != JobStatus.FAILED) { "Agent edit failed: ${latest?.errorMessage}" }
                latest?.kind == JobKind.AGENT_EDIT && latest.status == JobStatus.COMPLETE && episode().activeRevisionId != first.id
            }
            val (final, chapters) = revision()
            assertEquals(first.id, final.baseRevisionId); assertEquals(first.revisionNumber + 1, final.revisionNumber)
            assertEquals("$title checked", final.title) // verify the planned model edit, not merely queue/new-row acceptance
            assertNotEquals(first.contentHash, final.contentHash)
            assertArrayEquals(firstBytes, app.repository.resolveArtifact(first.relativePath).readBytes())
            text("final-revision.json", app.repository.resolveArtifact(final.relativePath).readText())
            ShortProductPolicy.validateFinal(chapters.map { it.stableChapterId to it.text })
            icon("Close agent editor"); capture("final-review")
            click("Lock script & create audio"); click("Cancel")
            assertNull(episode().lockedRevisionId)
            assertTrue(db { app.repository.observeAudio(requireNotNull(episodeId)).first() }.isEmpty())
            click("Lock script & create audio"); click("Lock & create")
            waitPhase(EpisodePhase.FROZEN_READY, 165_000)
            val ready = episode()
            assertEquals(final.id, ready.lockedRevisionId); assertEquals(final.contentHash, ready.lockedContentHash)
            val audio = db { app.repository.observeAudio(requireNotNull(episodeId)).first() }
            verifyAssembly(ready, chapters, audio)
            waitUntil("silent paused player") { var ok = false; rule.runOnIdle { ok = ShortProductDiagnostics.player?.let { it.volume == 0f && !it.playWhenReady } == true }; ok }
            rule.runOnIdle { assertEquals(0f, requireNotNull(ShortProductDiagnostics.player).volume) }
            icon("Play")
            waitUntil("real silent playback position", 10_000) { var ok = false; rule.runOnIdle { ok = ShortProductDiagnostics.player?.let { it.isPlaying && it.currentPosition > 200 && it.volume == 0f } == true }; ok }
            icon("Pause"); icon("Next chapter")
            val boundary = audio[1].startFrame * 1000 / 44100
            waitUntil("chapter boundary") { var ok = false; rule.runOnIdle { ok = ShortProductDiagnostics.player?.currentPosition?.let { kotlin.math.abs(it - boundary) < 100 } == true }; ok }
            click("1.0× Speed"); click("Transcript")
            shown(hasText("Chapter 2 · ${chapters[1].title}"))
            rule.onNodeWithText("Chapter 2 · ${chapters[1].title}").assertIsDisplayed()
            val paragraphs = chapters[1].text.split(Regex("(?<=[.!?])\\s+(?=[A-Z])")).filter(String::isNotBlank)
            paragraphs.groupingBy { it }.eachCount().forEach { (paragraph, count) -> rule.onAllNodesWithText(paragraph).assertCountEquals(count) }
            capture("chapter-two-transcript")
            val previousPlayer = rule.runOnIdle { requireNotNull(ShortProductDiagnostics.player) }
            scenario.recreate() // disposal saves visibility while the ViewModel survives configuration change
            waitUntil("playback persistence after disposal") { db { app.repository.observePlayback(requireNotNull(episodeId)).first() }?.let { it.speed == 1.25f && it.transcriptVisible } == true }
            waitUntil("new player after recreation") { var ok = false; rule.runOnIdle { ok = ShortProductDiagnostics.player?.let { it !== previousPlayer && it.volume == 0f && !it.playWhenReady } == true }; ok }
            val recreatedPlayer = rule.runOnIdle { requireNotNull(ShortProductDiagnostics.player) }
            scenario.close()
            scenario = ActivityScenario.launch(MainActivity::class.java) // fresh Activity/ViewModel; select through Library
            rule.waitUntil(15_000) { rule.onAllNodesWithText(final.title).fetchSemanticsNodes().isNotEmpty() }
            click(final.title)
            waitUntil("restored silent paused player") { var ok = false; rule.runOnIdle { ok = ShortProductDiagnostics.player?.let { it !== recreatedPlayer && it !== previousPlayer && !it.playWhenReady && it.volume == 0f && it.playbackParameters.speed == 1.25f && kotlin.math.abs(it.currentPosition - boundary) < 500 } == true }; ok }
            shown(hasText("Chapter 2 · ${chapters[1].title}"))
            rule.onNodeWithText("Chapter 2 · ${chapters[1].title}").assertIsDisplayed()
            json("player-proof.json", JSONObject().put("episodeId", episodeId).put("volume", 0).put("actualSilentPlayback", true)
                .put("boundaryMs", boundary).put("activityRecreated", true).put("restoredSpeed", 1.25).put("restoredTranscript", true)
                .put("restoredPaused", true).put("systemVolumeChanged", false).put("freshPlayerIdentityChecked", true).put("freshViewModelFromLibrary", true))
            icon("Close transcript"); icon("Export episode")
            saveThroughLocalDocumentsUi("podcast-$run.wav")
            waitUntil("real export callback", 30_000) { ShortProductDiagnostics.exportedUri != null }
            val uri = requireNotNull(ShortProductDiagnostics.exportedUri)
            require(uri.authority in setOf("com.android.providers.downloads.documents", "com.android.externalstorage.documents"))
            val bytes = context.contentResolver.openInputStream(uri)!!.use { it.readBytes() }
            assertEquals(ready.finalAudioSha256, ShortProductPolicy.hash(bytes)); assertEquals(ready.finalAudioByteCount, bytes.size.toLong())
            json("export-proof.json", JSONObject().put("uri", uri.toString()).put("sha256", ShortProductPolicy.hash(bytes))
                .put("bytes", bytes.size).put("realCreateDocument", true).put("newOwnedFilename", "podcast-$run.wav"))
            waitUntil("all service-finally records", 15_000) { File(root, "jobs").listFiles().orEmpty().count { File(it, "finished.json").isFile } == 3 }
            val sends = File(root, "jobs").walkTopDown().count { it.name.endsWith("-send-start.json") }
            assertEquals(5, sends)
            json("driver-result.json", JSONObject().put("status", "short_product_plumbing_complete").put("episodeId", episodeId)
                .put("logicalGemmaSends", sends).put("chapterWavs", 2).put("longReadiness", false).put("listening", "not_reviewed")
                .put("profileEvidence", "UNAVAILABLE_BY_DESIGN").put("elapsedMs", ShortProductPolicy.DRIVER_MS - (deadline - SystemClock.elapsedRealtime())))
        } catch (error: Throwable) {
            runCatching { json("driver-failure.json", JSONObject().put("error", error.stackTraceToString()).put("episodeId", episodeId)); capture("failure") }
            // Terminalize only this test's active job via normal guarded failure APIs; no deletion/retry/repair.
            episodeId?.let { id -> runCatching { db {
                app.repository.latestJob(id)?.let { job ->
                    app.repository.failQueuedJob(id, job.id, "Short plumbing driver stopped; no retry", "short_product_driver")
                    app.repository.failJob(id, job.id, "Short plumbing driver stopped; no retry", "short_product_driver")
                }
            } } }
            throw error
        } finally {
            runCatching { rule.runOnIdle { ShortProductDiagnostics.player?.pause() } }
            runCatching { scenario?.close() }
            runCatching { rule.runOnIdle { ShortProductDiagnostics.disableUi() } }
            if (controlBytes != null && marker.isFile && marker.readBytes().contentEquals(controlBytes)) {
                val removed = marker.delete()
                runCatching { json("control-disarmed.json", JSONObject().put("removedOwnedControlOnly", removed).put("sha256", ShortProductPolicy.hash(controlBytes))) }
            }
            timer.cancel()
        }
    }

    @Test fun continueOwnedReviewToAudioAndExport() {
        val args = InstrumentationRegistry.getArguments()
        assumeTrue("Exact continuation release required", args.getString("shortProductApproved") == ShortContinuationPolicy.CONTRACT_SHA)
        val run = requireNotNull(args.getString("shortProductRunId")); require(ShortProductPolicy.validRun(run))
        require(Application.getProcessName() == context.packageName)
        val contract = ShortContinuationPolicy.load(context)
        root = File(context.filesDir, "${ShortProductPolicy.DIRECTORY}/$run"); check(!root.exists() && root.mkdirs())
        episodeId = ShortContinuationPolicy.EPISODE_ID
        deadline = SystemClock.elapsedRealtime() + ShortContinuationPolicy.DRIVER_MS
        val timer = Timer("short-continuation-driver-bound", true)
        timer.schedule(object : TimerTask() { override fun run() {
            runCatching { json("driver-timeout.json", JSONObject().put("limitMs", ShortContinuationPolicy.DRIVER_MS)) }
            Process.killProcess(Process.myPid())
        } }, ShortContinuationPolicy.DRIVER_MS)
        var scenario: ActivityScenario<MainActivity>? = null
        val marker = File(root.parentFile, "active.json"); var controlBytes: ByteArray? = null
        try {
            check(!marker.exists()) { "Existing control is not ours" }
            json("contract.json", contract)
            val appHash = ShortProductPolicy.hash(File(context.applicationInfo.sourceDir).readBytes())
            val testHash = ShortProductPolicy.hash(File(instrumentation.context.applicationInfo.sourceDir).readBytes())
            json("identity.json", JSONObject().put("appApkSha256", appHash).put("testApkSha256", testHash)
                .put("pid", Process.myPid()).put("process", Application.getProcessName()).put("fingerprint", android.os.Build.FINGERPRINT))
            require(appHash == args.getString("appApkSha256") && testHash == args.getString("testApkSha256"))
            val (final, chapters) = db { ShortContinuationPolicy.validateStored(context, locked = false) }
            require(db { app.repository.observeAudio(requireNotNull(episodeId)).first() }.isEmpty())
            json("ownership.json", JSONObject().put("runId", run).put("episodeId", episodeId).put("revisionId", final.id)
                .put("contentHash", final.contentHash).put("priorRunId", contract.getString("priorRunId"))
                .put("multiStageRealWorkflow", true).put("newGemmaRequestsAuthorized", 0).put("seededOrImported", false))
            json("word-target-report.json", JSONObject().put("chapters", ShortContinuationPolicy.wordReport(chapters))
                .put("capacityAndExactContentVerified", true).put("wordTargetIsValidityGate", false))
            controlBytes = JSONObject().put("runId", run).put("episodeId", episodeId).put("contractSha256", ShortContinuationPolicy.CONTRACT_SHA).toString().toByteArray()
            ShortProductDiagnostics.write(File(root, "control-original.json"), controlBytes)
            ShortProductDiagnostics.write(marker, controlBytes)
            rule.runOnIdle { ShortProductDiagnostics.enableUi(root, requireNotNull(episodeId)) }
            scenario = ActivityScenario.launch(MainActivity::class.java)
            click(final.title); shown(hasText("Review script")); capture("real-existing-review")
            click("Lock script & create audio"); click("Cancel")
            assertNull(episode().lockedRevisionId)
            assertEquals(final.contentHash, revision().first.contentHash)
            click("Lock script & create audio"); click("Lock & create")
            waitPhase(EpisodePhase.FROZEN_READY, 165_000)
            val ready = episode()
            assertEquals(final.id, ready.lockedRevisionId); assertEquals(final.contentHash, ready.lockedContentHash)
            val audio = db { app.repository.observeAudio(requireNotNull(episodeId)).first() }
            verifyAssembly(ready, chapters, audio)
            waitUntil("silent paused continuation player") { var ok = false; rule.runOnIdle { ok = ShortProductDiagnostics.player?.let { it.volume == 0f && !it.playWhenReady } == true }; ok }
            icon("Play")
            waitUntil("real silent continuation playback", 10_000) { var ok = false; rule.runOnIdle { ok = ShortProductDiagnostics.player?.let { it.isPlaying && it.currentPosition > 200 && it.volume == 0f } == true }; ok }
            icon("Pause"); icon("Next chapter")
            val boundary = audio[1].startFrame * 1000 / 44100
            waitUntil("continuation chapter boundary") { var ok = false; rule.runOnIdle { ok = ShortProductDiagnostics.player?.currentPosition?.let { kotlin.math.abs(it - boundary) < 100 } == true }; ok }
            click("1.0× Speed"); click("Transcript")
            shown(hasText("Chapter 2 · ${chapters[1].title}"))
            chapters[1].text.split(Regex("(?<=[.!?])\\s+(?=[A-Z])")).filter(String::isNotBlank).groupingBy { it }.eachCount().forEach { (paragraph, count) -> rule.onAllNodesWithText(paragraph).assertCountEquals(count) }
            capture("continued-chapter-two-transcript")
            val previousPlayer = rule.runOnIdle { requireNotNull(ShortProductDiagnostics.player) }
            scenario.recreate()
            waitUntil("continuation persisted playback after disposal") { db { app.repository.observePlayback(requireNotNull(episodeId)).first() }?.let { it.speed == 1.25f && it.transcriptVisible } == true }
            waitUntil("continuation new player") { var ok = false; rule.runOnIdle { ok = ShortProductDiagnostics.player?.let { it !== previousPlayer && it.volume == 0f && !it.playWhenReady } == true }; ok }
            val recreatedPlayer = rule.runOnIdle { requireNotNull(ShortProductDiagnostics.player) }
            scenario.close(); scenario = ActivityScenario.launch(MainActivity::class.java)
            click(final.title)
            waitUntil("continuation restored from Library") { var ok = false; rule.runOnIdle { ok = ShortProductDiagnostics.player?.let { it !== previousPlayer && it !== recreatedPlayer && !it.playWhenReady && it.volume == 0f && it.playbackParameters.speed == 1.25f && kotlin.math.abs(it.currentPosition - boundary) < 500 } == true }; ok }
            shown(hasText("Chapter 2 · ${chapters[1].title}"))
            json("player-proof.json", JSONObject().put("episodeId", episodeId).put("volume", 0).put("actualSilentPlayback", true)
                .put("boundaryMs", boundary).put("restoredSpeed", 1.25).put("restoredTranscript", true).put("restoredPaused", true)
                .put("freshPlayerIdentityChecked", true).put("freshViewModelFromLibrary", true).put("systemVolumeChanged", false))
            icon("Close transcript"); icon("Export episode")
            saveThroughLocalDocumentsUi("podcast-$run.wav")
            waitUntil("continuation real export callback", 30_000) { ShortProductDiagnostics.exportedUri != null }
            val uri = requireNotNull(ShortProductDiagnostics.exportedUri)
            val bytes = context.contentResolver.openInputStream(uri)!!.use { it.readBytes() }
            assertEquals(ready.finalAudioSha256, ShortProductPolicy.hash(bytes)); assertEquals(ready.finalAudioByteCount, bytes.size.toLong())
            json("export-proof.json", JSONObject().put("uri", uri.toString()).put("sha256", ShortProductPolicy.hash(bytes))
                .put("bytes", bytes.size).put("realCreateDocument", true).put("newOwnedFilename", "podcast-$run.wav"))
            waitUntil("one AUDIO finally", 15_000) { File(root, "jobs").listFiles().orEmpty().count { File(it, "finished.json").isFile } == 1 }
            val jobRoot = File(root, "jobs").listFiles().orEmpty().single()
            assertEquals("AUDIO", readJson(File(jobRoot, "started.json")).getString("kind"))
            assertEquals(0, readJson(File(jobRoot, "finished.json")).getInt("logicalSendCalls"))
            assertEquals(0, jobRoot.walkTopDown().count { it.name.endsWith("-send-start.json") })
            json("driver-result.json", JSONObject().put("status", "short_product_continuation_complete").put("episodeId", episodeId)
                .put("newGemmaSends", 0).put("newWholeTtsChapters", 2).put("priorRunId", contract.getString("priorRunId"))
                .put("multiStageRealWorkflow", true).put("singleFreshSourceToAudioPass", false).put("longReadiness", false)
                .put("wordTargetReport", ShortContinuationPolicy.wordReport(chapters)).put("listening", "not_reviewed")
                .put("profileEvidence", "UNAVAILABLE_BY_DESIGN").put("elapsedMs", ShortContinuationPolicy.DRIVER_MS - (deadline - SystemClock.elapsedRealtime())))
        } catch (error: Throwable) {
            runCatching { json("driver-failure.json", JSONObject().put("error", error.stackTraceToString()).put("episodeId", episodeId)); capture("failure") }
            runCatching { db { app.repository.latestJob(requireNotNull(episodeId))?.takeIf { it.kind == JobKind.AUDIO }?.let {
                app.repository.failQueuedJob(requireNotNull(episodeId), it.id, "Continuation stopped; no retry", "continuation_driver")
                app.repository.failJob(requireNotNull(episodeId), it.id, "Continuation stopped; no retry", "continuation_driver")
            } } }
            throw error
        } finally {
            runCatching { rule.runOnIdle { ShortProductDiagnostics.player?.pause() } }; runCatching { scenario?.close() }
            runCatching { rule.runOnIdle { ShortProductDiagnostics.disableUi() } }
            if (controlBytes != null && marker.isFile && marker.readBytes().contentEquals(controlBytes)) {
                val removed = marker.delete(); runCatching { json("control-disarmed.json", JSONObject().put("removedOwnedControlOnly", removed).put("sha256", ShortProductPolicy.hash(controlBytes))) }
            }
            timer.cancel()
        }
    }

    private fun verifyAssembly(ready: EpisodeEntity, chapters: List<ChapterEntity>, audio: List<ChapterAudioEntity>) {
        assertEquals(2, audio.size); assertEquals(chapters.map { it.stableChapterId }, audio.map { it.stableChapterId })
        val parts = audio.map { item ->
            val file = app.repository.resolveArtifact(item.relativePath)
            val metadata = WavInspector.inspectSupertonicOutput(file)
            assertEquals(item.sha256, ShortProductPolicy.hash(file.readBytes())); assertEquals(item.frameCount, metadata.frameCount)
            file.readBytes().drop(44).toByteArray()
        }
        assertEquals(0L, audio[0].startFrame); assertEquals(audio[0].frameCount + 30_870, audio[1].startFrame)
        val master = app.repository.resolveArtifact(requireNotNull(ready.finalAudioPath))
        val expected = parts[0] + ByteArray(30_870 * 2) + parts[1]
        assertArrayEquals(expected, master.readBytes().drop(44).toByteArray())
        assertEquals(ready.finalAudioSha256, ShortProductPolicy.hash(master.readBytes()))
        val timelineFile = app.repository.resolveArtifact(requireNotNull(ready.timelinePath))
        assertEquals(ready.timelineSha256, ShortProductPolicy.hash(timelineFile.readBytes()))
        val timeline = JSONObject(timelineFile.readText())
        assertEquals(expected.size / 2L, timeline.getLong("totalFrames"))
        for (i in 0..1) {
            val row = timeline.getJSONArray("chapters").getJSONObject(i)
            assertEquals(audio[i].stableChapterId, row.getString("chapterId")); assertEquals(audio[i].startFrame, row.getLong("startFrame")); assertEquals(audio[i].endFrame, row.getLong("endFrame"))
        }
        json("assembly-proof.json", JSONObject().put("masterSha256", ready.finalAudioSha256).put("timelineSha256", ready.timelineSha256)
            .put("chapterFrames", JSONArray(audio.map { it.frameCount })).put("gapFrames", 30_870).put("pcmConcatenationExact", true)
            .put("audioSeconds", expected.size / 2.0 / 44100).put("notLongReadiness", true))
    }
    private fun shell(command: String): String = android.os.ParcelFileDescriptor.AutoCloseInputStream(instrumentation.uiAutomation.executeShellCommand(command)).use { it.readBytes().toString(Charsets.UTF_8) }
    private fun walk(node: AccessibilityNodeInfo?): List<AccessibilityNodeInfo> = if (node == null) emptyList() else listOf(node) + (0 until node.childCount).flatMap { walk(node.getChild(it)) }
    private fun clickNative(node: AccessibilityNodeInfo) {
        var target: AccessibilityNodeInfo? = node
        while (target != null && !target.isClickable) target = target.parent
        require(target?.performAction(AccessibilityNodeInfo.ACTION_CLICK) == true)
    }
    private fun saveThroughLocalDocumentsUi(filename: String) {
        waitUntil("local DocumentsUI", 15_000) { instrumentation.uiAutomation.rootInActiveWindow?.packageName?.toString() in setOf("com.google.android.documentsui", "com.android.documentsui") }
        var nodes = walk(instrumentation.uiAutomation.rootInActiveWindow)
        val drawer = nodes.firstOrNull { it.contentDescription?.toString() in setOf("Show roots", "Show navigation drawer") }
        if (drawer != null) clickNative(drawer)
        waitUntil("Downloads root") { walk(instrumentation.uiAutomation.rootInActiveWindow).any { it.text?.toString() == "Downloads" } }
        nodes = walk(instrumentation.uiAutomation.rootInActiveWindow)
        val downloads = nodes.filter { it.text?.toString() == "Downloads" }
        // With a drawer open choose its root row, never a cloud provider or an existing document.
        if (drawer != null) clickNative(downloads.first { it.parent?.isClickable == true || it.isClickable })
        Thread.sleep(500)
        nodes = walk(instrumentation.uiAutomation.rootInActiveWindow)
        val input = nodes.filter { it.isEditable }.single()
        require(input.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, Bundle().apply { putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, filename) }))
        Thread.sleep(300)
        val save = walk(instrumentation.uiAutomation.rootInActiveWindow).single {
            it.isEnabled && (it.viewIdResourceName?.endsWith(":id/button1") == true || it.text?.toString()?.lowercase() in setOf("save", "speichern"))
        }
        clickNative(save)
    }
}
