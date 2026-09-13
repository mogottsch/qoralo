package dev.vibevoice.podcast.ui

import android.content.Context
import android.content.ContextWrapper
import android.os.Looper
import androidx.compose.material3.Text
import androidx.compose.runtime.remember
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.media3.common.Player
import androidx.media3.common.Timeline
import androidx.room.Room
import androidx.room.withTransaction
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.vibevoice.podcast.PodcastApplication
import dev.vibevoice.podcast.data.ArtifactStore
import dev.vibevoice.podcast.data.EpisodePhase
import dev.vibevoice.podcast.data.JobStatus
import dev.vibevoice.podcast.data.PodcastDatabase
import dev.vibevoice.podcast.data.PodcastRepository
import dev.vibevoice.podcast.runtime.AudioAvailabilityState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest
import java.util.concurrent.atomic.AtomicBoolean

/** Opt-in 0NN replay of retained media; never a claim of playback concurrent with HTP. */
@RunWith(AndroidJUnit4::class)
class LiveCollectorRegressionTest {
    @get:Rule val rule = createComposeRule()

    @Test fun productionIoCollectorReplaysRetainedChunksOnMain() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val app = context.applicationContext as PodcastApplication
        val args = InstrumentationRegistry.getArguments()
        val run = requireNotNull(args.getString("diagnosticRun")).also { require(it.matches(Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,159}"))) }
        val episodeId = requireNotNull(args.getString("sourceEpisodeId")).also { require(it.matches(Regex("[A-Za-z0-9-]{1,80}"))) }
        val jobId = requireNotNull(args.getString("sourceJobId")).also { require(it.matches(Regex("[a-f0-9]{64}"))) }
        val expectedMaster = requireNotNull(args.getString("expectedMasterSha256")).also { require(it.matches(Regex("[a-f0-9]{64}"))) }
        val receiptDir = File(context.filesDir, "player-ui-captures/$run/live-collector/.private-ui").also { check(it.mkdirs()) }
        val receipt = File(receiptDir, "replay.json")
        val failure = File(receiptDir, "replay-failure.json")
        val cache = File(context.cacheDir, "live-collector-$run-${System.nanoTime()}").also { check(it.mkdirs()) }
        val artifacts = ArtifactStore(File(cache, "episodes"), File(cache, "models"))
        val database = Room.inMemoryDatabaseBuilder(context, PodcastDatabase::class.java).allowMainThreadQueries().build()
        val repository = PodcastRepository(database, artifacts, providerAdmission = false)
        // Keep RuntimeDiagnostics away from the real attempt's active marker/first-failure receipts.
        val isolatedContext = object : ContextWrapper(context) {
            override fun getApplicationContext(): Context = this
            override fun getFilesDir(): File = File(cache, "private-context").also { it.mkdirs() }
        }
        val originals = linkedMapOf<String, String>()
        val stages = JSONArray()
        var host: PlaybackHost? = null
        var passed = false
        var producerWasOffMain = false
        val wrongListenerThread = AtomicBoolean(false)
        fun <T> io(block: suspend () -> T): T = runBlocking(Dispatchers.IO) { block() }
        fun copyArtifact(relative: String) {
            check(Looper.myLooper() != Looper.getMainLooper())
            producerWasOffMain = true
            val original = app.artifacts.resolveEpisodeFile(relative)
            val digest = sha256(original)
            originals[original.absolutePath]?.let { check(it == digest) }
            originals[original.absolutePath] = digest
            val target = artifacts.resolveEpisodeFile(relative)
            check(!target.exists()); check(target.parentFile!!.mkdirs() || target.parentFile!!.isDirectory)
            val temporary = File(target.parentFile, ".${target.name}.stage")
            check(!temporary.exists())
            FileOutputStream(temporary).use { output -> original.inputStream().use { it.copyTo(output) }; output.fd.sync() }
            check(sha256(temporary) == digest && temporary.renameTo(target))
        }
        try {
            val sourceEpisode = io { app.repository.episode(episodeId) }
            val sourceJob = io { requireNotNull(app.database.podcastDao().job(jobId)) }
            val sourcePlayback = io { app.repository.observePlayback(episodeId).first() }
            require(sourceEpisode.phase == EpisodePhase.FROZEN_READY && sourceEpisode.finalAudioSha256 == expectedMaster)
            require(sourceJob.episodeId == episodeId && sourceJob.status == JobStatus.COMPLETE)
            val masterPath = requireNotNull(sourceEpisode.finalAudioPath)
            val masterHash = io { sha256(app.artifacts.resolveEpisodeFile(masterPath)) }
            require(masterHash == expectedMaster)
            val sourceRevision = io { requireNotNull(app.database.podcastDao().revision(requireNotNull(sourceEpisode.lockedRevisionId))) }
            val chapters = io { app.database.podcastDao().chapters(sourceRevision.id) }
            val sourceAvailability = io { withTimeout(15_000) { app.repository.observeAudioAvailability(episodeId, jobId).filterNotNull().first() } }
            require(sourceAvailability.state == AudioAvailabilityState.COMPLETE && sourceAvailability.chunks.size == 15)
            val streamRoot = "$episodeId/audio-stream/$jobId"
            val replayEpisode = sourceEpisode.copy(phase = EpisodePhase.GENERATING_AUDIO, finalAudioPath = null,
                finalAudioSha256 = null, finalAudioByteCount = null, durationMs = null, timelinePath = null, timelineSha256 = null, timelineByteCount = null)
            val replayJob = sourceJob.copy(status = JobStatus.RUNNING, terminalAtEpochMs = null)
            io {
                require(app.repository.runningJobs().isEmpty() && app.repository.queuedJobs().isEmpty())
                database.podcastDao().insertEpisode(replayEpisode)
                database.podcastDao().insertRevision(sourceRevision)
                database.podcastDao().insertChapters(chapters)
                database.podcastDao().insertJob(replayJob)
                copyArtifact(sourceRevision.relativePath)
                copyArtifact("$episodeId/audio-plans/$jobId.json")
                copyArtifact("$streamRoot/binding.json")
                // Media first, closed metadata last: the production reader sees only durable prefixes.
                copyArtifact("$streamRoot/000000.wav")
                copyArtifact("$streamRoot/000000.json")
            }
            val initial = io { withTimeout(15_000) { repository.observeAudioAvailability(episodeId, jobId).filterNotNull().first() } }
            require(initial.chunks.size == 1 && initial.state == AudioAvailabilityState.GENERATING)
            rule.setContent {
                val currentHost = remember { PlaybackHost(isolatedContext) }
                host = currentHost
                PlaybackHostEffects(currentHost, repository)
                Text("Retained audio · background collector replay · no synthesis")
            }
            rule.runOnIdle { requireNotNull(host).open(replayEpisode, chapters, emptyList(), jobId, null, initial, null) { _, _, _ -> } }
            val session = requireNotNull(host?.active).session
            val player = session.player
            rule.runOnIdle {
                assertSame(Looper.getMainLooper(), player.applicationLooper)
                player.volume = 0f
                player.addListener(object : Player.Listener {
                    override fun onTimelineChanged(timeline: Timeline, reason: Int) {
                        if (Looper.myLooper() != player.applicationLooper) wrongListenerThread.set(true)
                    }
                })
                session.seek(500); session.changeSpeed(1.25f)
            }
            fun snapshot(stage: String) = rule.runOnIdle {
                assertSame(Looper.getMainLooper(), Looper.myLooper())
                assertSame(player, requireNotNull(host.active).session.player)
                assertFalse(wrongListenerThread.get()); assertNull(session.error)
                JSONObject().put("stage", stage).put("playerIdentity", System.identityHashCode(player))
                    .put("collectorChunks", session.availableChunks.size).put("mediaItems", player.mediaItemCount)
                    .put("absolutePositionMs", session.positionMs).put("availableMs", session.durationMs)
                    .put("playing", session.isPlaying).put("wantsPlayback", session.wantsPlayback)
                    .put("state", session.streamState?.name).put("muted", player.volume == 0f)
                    .put("speed", session.speed.toDouble()).put("applicationLooper", player.applicationLooper.thread.name)
            }
            stages.put(snapshot("initial-paused"))
            var published = 1
            for (count in listOf(2, 5, 15)) {
                io {
                    delay(150) // Real IO dispatcher publication, not main-thread session.update injection.
                    for (index in published until count) {
                        val stem = index.toString().padStart(6, '0')
                        copyArtifact("$streamRoot/$stem.wav")
                        copyArtifact("$streamRoot/$stem.json")
                    }
                }
                published = count
                rule.waitUntil(15_000) { session.availableChunks.size == count }
                val event = snapshot("io-prefix-$count")
                require(!event.getBoolean("playing") && !event.getBoolean("wantsPlayback") && event.getBoolean("muted"))
                require(event.getLong("absolutePositionMs") == 500L && event.getDouble("speed") == 1.25)
                require(event.getInt("mediaItems") == count)
                stages.put(event)
            }
            rule.runOnIdle { session.togglePlay() }
            rule.waitUntil(15_000) { session.isPlaying && session.positionMs > 900 }
            stages.put(snapshot("replay-advanced-before-fixture-complete"))
            val positionBeforeComplete = rule.runOnIdle { session.positionMs }
            io {
                copyArtifact(masterPath)
                sourceEpisode.timelinePath?.let(::copyArtifact)
                copyArtifact("$streamRoot/completion.json")
                // Only the isolated in-memory copies change phase. Real Ready/job stay untouched.
                database.withTransaction {
                    database.podcastDao().updateJob(sourceJob)
                    database.podcastDao().updateEpisode(sourceEpisode)
                }
            }
            rule.waitUntil(15_000) { session.streamState == AudioAvailabilityState.COMPLETE && session.isPlaying && session.positionMs > positionBeforeComplete + 300 }
            stages.put(snapshot("same-player-after-fixture-complete"))
            rule.runOnIdle { session.pause(); requireNotNull(host).close() }
            rule.waitForIdle()
            io {
                require(app.repository.episode(episodeId) == sourceEpisode)
                require(app.database.podcastDao().job(jobId) == sourceJob)
                require(app.repository.observePlayback(episodeId).first() == sourcePlayback)
                originals.forEach { (path, digest) -> require(sha256(File(path)) == digest) }
                require(sha256(app.artifacts.resolveEpisodeFile(masterPath)) == masterHash)
                writeJson(receipt, JSONObject().put("status", "passed").put("realRepoIO", true)
                    .put("sourceEpisodeId", episodeId).put("sourceJobId", jobId).put("sourceMasterSha256", masterHash)
                    .put("newModelCalls", 0).put("newAudioJobs", 0).put("replay", true).put("htpConcurrency", false)
                    .put("producerOffMain", producerWasOffMain).put("playerApplicationLooper", "main")
                    .put("sourceDataUnchanged", true).put("sourceFilesChecked", originals.size).put("stages", stages)
                    .put("appApkSha256", sha256(File(context.applicationInfo.sourceDir)))
                    .put("testApkSha256", sha256(File(instrumentation.context.applicationInfo.sourceDir))))
            }
            passed = true
        } catch (error: Throwable) {
            io { writeJson(failure, JSONObject().put("status", "failed").put("replay", true).put("newModelCalls", 0)
                .put("sourceEpisodeId", episodeId).put("sourceJobId", jobId).put("sourceMasterSha256", expectedMaster)
                .put("cacheFixtureRetained", cache.absolutePath).put("stages", stages).put("error", error.stackTraceToString())) }
            throw AssertionError("Retained-audio collector replay failed; inspect its private receipt. No model retry.")
        } finally {
            runCatching { rule.runOnIdle { host?.close() }; rule.waitForIdle() }
            database.close()
            if (passed) cache.deleteRecursively()
        }
    }

    private fun sha256(file: File): String {
        val hash = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input -> val buffer = ByteArray(65536); while (true) { val n = input.read(buffer); if (n < 0) break; hash.update(buffer, 0, n) } }
        return hash.digest().joinToString("") { "%02x".format(it) }
    }

    private fun writeJson(file: File, value: JSONObject) {
        check(!file.exists())
        FileOutputStream(file).use { it.write(value.toString(2).toByteArray()); it.fd.sync() }
    }
}
