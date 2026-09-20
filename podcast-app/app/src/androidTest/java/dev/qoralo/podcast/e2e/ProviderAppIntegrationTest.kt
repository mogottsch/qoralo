package dev.qoralo.podcast.e2e

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.room.withTransaction
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.qoralo.podcast.MainActivity
import dev.qoralo.podcast.PodcastApplication
import dev.qoralo.podcast.data.*
import dev.qoralo.podcast.runtime.*
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
import androidx.compose.ui.test.onLast
import androidx.compose.ui.test.onAllNodesWithText

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
        val progressive = args.getString("progressivePlayback") == "true"
        val ownedGuard = args.getString("ownedMemoryGuard") == "true"
        val run = requireNotNull(args.getString("diagnosticRun"));require(Regex("provider-app-[a-z0-9-]{1,48}").matches(run))
        val parent = File(context.filesDir, "provider-integration").apply { mkdirs() }
        val root = File(parent, "$run-driver");require(root.mkdir())
        fun json(name: String, value: JSONObject) = ShortProductDiagnostics.json(File(root, name), value)
        var scenario: ActivityScenario<MainActivity>? = null
        var retainedEpisodeId: String? = null
        var retainedAudioJobId: String? = null
        var audioDeadlineNs: Long? = null
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
                .put("progressivePlayback", progressive).put("mutePlayer", progressive).put("ownedMemoryGuard",ownedGuard)
            val controlBytes = (control.toString(2) + "\n").toByteArray()
            File(parent, "active.json").writeBytes(controlBytes);File(root, "control-original.json").writeBytes(controlBytes)
            scenario?.close();scenario = ActivityScenario.launch(MainActivity::class.java)
            rule.waitUntil(15_000) { rule.onAllNodes(hasText(title)).fetchSemanticsNodes().isNotEmpty() }
            rule.onNodeWithText(title).performClick()
            rule.waitUntil(15_000) { rule.onAllNodes(hasText("Create audio") and isEnabled()).fetchSemanticsNodes().isNotEmpty() }
            rule.onNodeWithText("Create audio").assertIsEnabled().performClick()
            retainedEpisodeId=id
            val lockRequestedNs = System.nanoTime()
            audioDeadlineNs=lockRequestedNs+600_000_000_000L
            rule.onAllNodesWithText("Create audio").onLast().performClick()
            var audio: GenerationJobEntity? = null
            rule.waitUntil(15_000) { audio = db { app.repository.latestJob(id) }; audio != null }
            val audioId = requireNotNull(audio).id
            retainedAudioJobId=audioId
            require(audio!!.kind == JobKind.AUDIO && Regex("[a-f0-9]{64}").matches(audioId))
            json("audio-job.json", JSONObject().put("jobId", audioId).put("episodeId", id).put("revisionId", newRevision)
                .put("revisionSha256", stored.sha256).put("kind", audio!!.kind).put("logicalChapters", 1).put("providerSegments", 15))
            var observedPlayerId: Int? = null
            var pausedPosition: Long? = null
            fun playerEvents(): List<JSONObject> {
                val file = File(parent, "$run/player-events.jsonl")
                if (!file.isFile) return emptyList()
                return file.readLines().mapNotNull { line -> runCatching { JSONObject(line) }.getOrNull() }
            }
            if (progressive) {
                rule.waitUntil(90_000) {
                    val current=db { app.repository.latestJob(id) }
                    when(OwnedAudioWaitPolicy.listen(id,audioId,current,rule.onAllNodes(hasText("Open player")).fetchSemanticsNodes().isNotEmpty())) {
                        OwnedListenDecision.WAIT -> false
                        OwnedListenDecision.LISTEN -> true
                        else -> {
                            json("listen-stopped-original-cause.json",JSONObject().put("episodeId",id).put("expectedJobId",audioId)
                                .put("observedJobId",current?.id).put("status",current?.status).put("failureStage",current?.failureStage)
                                .put("originalErrorMessage",current?.errorMessage).put("monotonicNs",System.nanoTime()))
                            error("Owned AUDIO ended or changed before the player opened; inspect its bound original cause")
                        }
                    }
                }
                val firstListenObservedNs = System.nanoTime()
                require(db { app.repository.latestJob(id) }?.status == JobStatus.RUNNING)
                rule.onNodeWithText("Open player").performScrollTo().performClick()
                rule.waitUntil(15_000) { rule.onAllNodes(hasContentDescription("Play")).fetchSemanticsNodes().isNotEmpty() && playerEvents().isNotEmpty() }
                val beforePlay = playerEvents().last()
                require(beforePlay.getBoolean("muted") && !beforePlay.getBoolean("playing") && !beforePlay.getBoolean("wantsPlayback") && beforePlay.getLong("absolutePositionMs") == 0L)
                val playRequestedNs = System.nanoTime()
                rule.onNodeWithContentDescription("Play", useUnmergedTree = true).performClick()
                rule.waitUntil(15_000) { playerEvents().any { it.getBoolean("playing") && it.getLong("absolutePositionMs") >= 1000 } }
                val advanced = playerEvents().first { it.getBoolean("playing") && it.getLong("absolutePositionMs") >= 1000 }
                require(advanced.getBoolean("muted") && db { app.repository.latestJob(id) }?.status == JobStatus.RUNNING && db { app.repository.episode(id) }.phase != EpisodePhase.FROZEN_READY)
                val firstAdvancement = playerEvents().first { it.getBoolean("playing") && it.getLong("absolutePositionMs") > 0 }
                observedPlayerId = advanced.getInt("playerIdentity")
                json("progressive-before-ready.json", JSONObject().put("lockRequestedNs", lockRequestedNs).put("firstListenObservedNs", firstListenObservedNs)
                    .put("playRequestedNs", playRequestedNs).put("firstObservedAdvancement", firstAdvancement).put("sustainedAdvancement", advanced)
                    .put("listenAvailableBeforeGenerationComplete", true).put("playerAdvancedBeforeGenerationComplete", true)
                    .put("firstListenObservedMsFromLock", (firstListenObservedNs-lockRequestedNs)/1_000_000.0)
                    .put("firstObservedPlayerAdvanceMsFromLock", (firstAdvancement.getLong("monotonicNs")-lockRequestedNs)/1_000_000.0)
                    .put("audiblePlaybackMeasured", false).put("muted", true))
                fun capture(name: String) {
                    // Optional visual evidence is never a reason to abandon functional checks.
                    runCatching {
                        val value=OwnedWindowCapturePolicy.capture(context.packageName,root,name,
                            readWindowDump={android.os.ParcelFileDescriptor.AutoCloseInputStream(instrumentation.uiAutomation.executeShellCommand("dumpsys window displays")).bufferedReader().use {it.readText()}},
                            takeScreenshot={instrumentation.uiAutomation.takeScreenshot()})
                        json("$name-state.json",value.put("episodeId",id).put("jobId",audioId).put("player",playerEvents().last())
                            .put("phase",db { app.repository.episode(id) }.phase))
                    }
                }
                fun atTail(event: JSONObject?) = event != null && event.getBoolean("wantsPlayback") && !event.getBoolean("playing") &&
                    event.getInt("playbackState")==4 && event.getLong("absolutePositionMs")>=event.getLong("availableMs")-2
                fun seekAvailableFrontier(): JSONObject {
                    repeat(8) {
                        if (!atTail(playerEvents().lastOrNull())) {
                            val forward=rule.onNodeWithContentDescription("Forward 15 seconds",useUnmergedTree=true)
                            if (!forward.fetchSemanticsNode().config.contains(SemanticsProperties.Disabled)) forward.performClick()
                            Thread.sleep(150)
                        }
                    }
                    rule.waitUntil(15_000) { atTail(playerEvents().lastOrNull()) }
                    return playerEvents().last()
                }
                val firstTail=seekAvailableFrontier();json("live-tail-before-pause.json",firstTail)
                capture("live-tail")
                rule.onNodeWithContentDescription("Pause", useUnmergedTree = true).performClick()
                rule.waitUntil(10_000) { playerEvents().lastOrNull()?.let { !it.getBoolean("playing") && !it.getBoolean("wantsPlayback") } == true }
                pausedPosition = playerEvents().last().getLong("absolutePositionMs")
                rule.waitUntil(30_000) { (playerEvents().lastOrNull()?.getLong("availableMs") ?: 0L) > firstTail.getLong("availableMs") }
                val afterArrival = playerEvents().last()
                require(!afterArrival.getBoolean("playing") && !afterArrival.getBoolean("wantsPlayback") && kotlin.math.abs(afterArrival.getLong("absolutePositionMs")-requireNotNull(pausedPosition)) <= 50)
                json("pause-survives-new-audio.json", afterArrival)
                rule.onNodeWithContentDescription("Play",useUnmergedTree=true).performClick()
                rule.waitUntil(10_000) { playerEvents().lastOrNull()?.let { it.getBoolean("playing") && it.getLong("absolutePositionMs")>firstTail.getLong("availableMs")+350 } == true }
                val secondTail=seekAvailableFrontier();json("live-tail-before-auto-resume.json",secondTail)
                rule.waitUntil(30_000) { playerEvents().lastOrNull()?.let { it.getBoolean("playing") && it.getLong("absolutePositionMs")>secondTail.getLong("availableMs")+350 } == true }
                val resumed=playerEvents().last();require(resumed.getInt("playerIdentity")==observedPlayerId)
                json("live-tail-auto-resumed.json",resumed)
                rule.onNodeWithContentDescription("Minimize player").performClick()
                rule.onNodeWithContentDescription("Open player: $title").assertIsDisplayed()
                rule.onNodeWithText("Settings").performClick()
                val beforeNavigation=playerEvents().last().getLong("absolutePositionMs")
                rule.waitUntil(10_000) { (playerEvents().lastOrNull()?.getLong("absolutePositionMs") ?: 0L) > beforeNavigation+500 }
                capture("mini-settings")
                rule.onNodeWithContentDescription("Open player: $title").performClick()
                rule.onNodeWithText("1.0×").performClick()
                rule.waitUntil(10_000) { playerEvents().lastOrNull()?.optDouble("speed")==1.25 }
                require(playerEvents().last().getInt("playerIdentity")==observedPlayerId)
                json("mini-navigation-reopen-speed.json",playerEvents().last())
                rule.onNodeWithText("Transcript").performClick()
                rule.waitUntil(10_000) { rule.onAllNodes(hasTestTag("Transcript passages")).fetchSemanticsNodes().isNotEmpty() }
                rule.onNodeWithTag("Transcript passages").performTouchInput { swipeUp() }
                rule.onNodeWithText("Follow playback").assertIsDisplayed()
                val scrollBefore=rule.onNodeWithTag("Transcript passages").fetchSemanticsNode().config[SemanticsProperties.VerticalScrollAxisRange].value()
                val itemBefore=playerEvents().last().getInt("mediaItemIndex")
                rule.waitUntil(25_000) { (playerEvents().lastOrNull()?.getInt("mediaItemIndex") ?: 0) > itemBefore }
                val scrollAfter=rule.onNodeWithTag("Transcript passages").fetchSemanticsNode().config[SemanticsProperties.VerticalScrollAxisRange].value()
                require(kotlin.math.abs(scrollBefore-scrollAfter)<0.02f)
                capture("transcript-manual")
                json("manual-transcript-kept-position.json",JSONObject().put("before",scrollBefore).put("after",scrollAfter).put("passageAdvanced",true))
                rule.onNodeWithText("Follow playback").performClick()
                rule.waitUntil(5000) { rule.onAllNodes(hasText("Current passage")).fetchSemanticsNodes().isNotEmpty() }
                capture("transcript-following")
                rule.onNodeWithContentDescription("Close transcript").performClick()
                require(playerEvents().last().getBoolean("wantsPlayback"))
            }
            var lastLivePosition=if(progressive) playerEvents().last().getLong("absolutePositionMs") else 0L
            val deadline = requireNotNull(audioDeadlineNs)
            var finished: EpisodeEntity
            while (true) {
                finished = db { app.repository.episode(id) }
                val current = requireNotNull(db { app.repository.latestJob(id) })
                require(current.id == audioId)
                if(progressive) {
                    val event=playerEvents().last()
                    require(event.getInt("playerIdentity")==observedPlayerId && event.getLong("absolutePositionMs")>=lastLivePosition)
                    lastLivePosition=event.getLong("absolutePositionMs")
                }
                if (finished.phase == EpisodePhase.FROZEN_READY || current.status == JobStatus.FAILED) break
                require(System.nanoTime() < deadline) { "Provider AUDIO terminal-state deadline" }
                Thread.sleep(500)
            }
            require(finished.phase == EpisodePhase.FROZEN_READY) { "Provider AUDIO failed; preserve exact private receipts" }
            if (progressive) {
                val atReady=lastLivePosition
                rule.waitUntil(15_000) { playerEvents().lastOrNull()?.let { it.getLong("availableMs")==finished.durationMs && it.getBoolean("playing") && it.getLong("absolutePositionMs")>atReady+300 } == true }
                val last = playerEvents().last()
                require(last.getInt("playerIdentity") == observedPlayerId && last.getBoolean("playing") && last.getBoolean("wantsPlayback"))
                json("finalization-same-player.json", last.put("samePlayerNoReset", true).put("generationComplete", true).put("playingAcrossReady",true).put("positionObservedAtReady",atReady))
                rule.onNodeWithContentDescription("Pause",useUnmergedTree=true).performClick()
                rule.waitUntil(10_000) { playerEvents().lastOrNull()?.let { !it.getBoolean("playing") && !it.getBoolean("wantsPlayback") } == true }
                json("final-player-paused.json",playerEvents().last())
            }
            val final = app.repository.resolveArtifact(requireNotNull(finished.finalAudioPath))
            val metadata = WavInspector.inspectSupertonicOutput(final)
            require(metadata.sha256 == finished.finalAudioSha256)
            require(original == db { app.repository.episode(originalId) })
            require(app.artifacts.sha256(app.repository.resolveArtifact(revision.relativePath)) == revision.contentHash)
            require(File(parent, "$run/job-identity.json").isFile) { "Provider diagnostic retention was not bound" }
            if(ownedGuard) {
                val guardIdentity=JSONObject(File(parent,"$run/guard-identity.json").readText())
                require(guardIdentity.getString("planSha256")==audioId && guardIdentity.getLong("wholeStartFloorKiB")==3072L*1024)
                require(guardIdentity.getLong("preContextFloorKiB")==2648L*1024 && guardIdentity.getLong("startupMemoryCreditKiB")==0L)
                val events=File(parent,"$run/guard-events.jsonl").readLines().filter {it.isNotBlank()}.map(::JSONObject)
                require(events.any {it.getString("event")=="sample"} && events.any {it.getString("event")=="closed"})
                require(events.none {it.getString("event")=="stop_requested"})
            }
            json("driver-result.json", JSONObject().put("status", "copied_real_chapter_normal_audio_complete")
                .put("appApkSha256", appHash).put("testApkSha256", testHash).put("episodeId", id).put("jobId", audioId)
                .put("revisionId", newRevision).put("revisionSha256", stored.sha256).put("referenceTextSha256", sourceHash)
                .put("finalAudioPath", finished.finalAudioPath).put("wavSha256", metadata.sha256).put("wavBytes", final.length())
                .put("frames", metadata.frameCount).put("sampleRateHz", metadata.sampleRateHz).put("providerSegments", 15)
                .put("newScriptModelCalls", 0).put("newAudioJobs", 1).put("originalEpisodeUnchanged", true)
                .put("playRequested", progressive).put("mutedPlayer", progressive).put("exportRequested", false)
                .put("progressivePlaybackVerified", progressive).put("ownedMemoryGuardVerified",ownedGuard).put("listeningReview", "not_reviewed"))
        } catch (error: Throwable) {
            runCatching { json("private-driver-failure.json", JSONObject().put("error", error.stackTraceToString())) }
            // A UI assertion is not a reason to throw away the one already-requested neural run.
            // Close only our player, retain the first failure, and await this same owned job's
            // terminal result within the original bounded deadline. Never queue a retry.
            runCatching { scenario?.close();scenario=null }
            if(progressive) runCatching {
                val owned=retainedEpisodeId ?: return@runCatching
                val until=audioDeadlineNs ?: return@runCatching
                val expected=retainedAudioJobId ?: return@runCatching
                while(System.nanoTime()<until) {
                    val job=db { app.repository.latestJob(owned) }
                    if(!OwnedAudioWaitPolicy.retainRunning(owned,expected,job)) {
                        json("audio-retained-after-ui-failure.json",JSONObject().put("episodeId",owned).put("jobId",job?.id).put("jobStatus",job?.status)
                            .put("phase",db { app.repository.episode(owned) }.phase).put("newModelRetry",false));break
                    }
                    Thread.sleep(500)
                }
            }
            throw AssertionError("Provider integration stopped; inspect private originals; no automatic model retry")
        } finally { runCatching { scenario?.close() } }
    }
}
