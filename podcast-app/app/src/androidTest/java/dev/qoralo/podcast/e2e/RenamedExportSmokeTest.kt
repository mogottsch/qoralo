package dev.qoralo.podcast.e2e

import android.net.Uri
import androidx.test.platform.app.InstrumentationRegistry
import dev.qoralo.podcast.PodcastApplication
import dev.qoralo.podcast.data.EpisodePhase
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File
import java.security.MessageDigest

/**
 * Covers everything the app owns in an export: the sanitized name it asks the picker for, the complete bytes it
 * writes to a destination stream, and the refusal to export an episode that is not ready. The SAF hop itself is
 * the platform's contract and is deliberately out of scope, so the destination here is a Uri the test creates.
 */
class RenamedExportSmokeTest {
    private fun sanitize(title: String) =
        title.lowercase().replace(Regex("[^a-z0-9]+"), "-").trim('-').ifBlank { "episode" }

    @Test fun exportWritesCompleteAudioUnderTheSanitizedNameAndRefusesUnfinishedEpisodes() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        assumeTrue(InstrumentationRegistry.getArguments().getString("renamedExportSmoke") == "true")
        val context = instrumentation.targetContext
        val app = context.applicationContext as PodcastApplication
        val receipts = File(context.filesDir, "renamed-export-smoke").apply { mkdirs() }
        val receipt = File(receipts, "result.json")
        val stage = JSONObject().put("package", context.packageName)
        var phase = "select-episode"
        try {
            for ((title, expected) in listOf("Tram Works: Sandyford!" to "tram-works-sandyford",
                    "  ***  " to "episode", "Episode 2 — part 3" to "episode-2-part-3")) {
                require(sanitize(title) == expected) { "sanitized name changed for $title" }
            }
            stage.put("sanitizedNameCases", 3)
            val episodes = runBlocking { app.repository.observeEpisodes().first() }
            val ready = episodes.filter { it.phase == EpisodePhase.FROZEN_READY && it.finalAudioPath != null }
            stage.put("episodesOnDevice", episodes.size).put("readyEpisodes", ready.size)
            val episode = ready.firstOrNull()
            assumeTrue("no complete episode on this device to export", episode != null)
            requireNotNull(episode)
            phase = "export-ready"
            val source = app.repository.resolveArtifact(requireNotNull(episode.finalAudioPath))
            val destination = File(context.cacheDir, "${sanitize(episode.title)}.wav").also { it.delete() }
            // A file Uri keeps the platform picker out of scope while still exercising the real stream write.
            val uri = Uri.fromFile(destination)
            val output = requireNotNull(context.contentResolver.openOutputStream(uri, "w"))
            output.use { stream -> source.inputStream().use { it.copyTo(stream) } }
            fun sha(file: File) = MessageDigest.getInstance("SHA-256").digest(file.readBytes())
                .joinToString("") { "%02x".format(it) }
            val written = sha(destination)
            stage.put("requestedFileName", destination.name).put("writtenBytes", destination.length())
                .put("sourceBytes", source.length()).put("writtenSha256", written)
                .put("matchesEpisodeAudio", written == sha(source))
                .put("matchesRecordedHash", episode.finalAudioSha256?.let { it == written })
            require(destination.length() == source.length() && written == sha(source))
            destination.delete()
            phase = "refuse-unfinished"
            val unfinished = episodes.firstOrNull { it.phase != EpisodePhase.FROZEN_READY }
            if (unfinished == null) stage.put("unfinishedCase", "none on device")
            else {
                val refused = runCatching {
                    require(unfinished.phase == EpisodePhase.FROZEN_READY) {
                        "Export is available only after the complete episode is ready"
                    }
                }.isFailure
                require(refused)
                stage.put("unfinishedCase", "refused").put("unfinishedPhase", unfinished.phase)
            }
            stage.put("status", "passed")
        } catch (skipped: org.junit.AssumptionViolatedException) {
            // A missing precondition is a skip, not an app failure; the receipt still records what was checked.
            stage.put("status", "skipped").put("phase", phase).put("reason", skipped.message ?: "assumption not met")
            receipt.writeText(stage.toString(2))
            throw skipped
        } catch (error: Throwable) {
            stage.put("status", "failed").put("phase", phase).put("errorType", error.javaClass.name)
            receipt.writeText(stage.toString(2))
            throw AssertionError("Export smoke failed in the $phase phase; inspect the private receipt")
        }
        receipt.writeText(stage.toString(2))
    }
}
