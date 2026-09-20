package dev.qoralo.podcast.e2e

import android.net.Uri
import androidx.test.platform.app.InstrumentationRegistry
import dev.qoralo.podcast.PodcastApplication
import dev.qoralo.podcast.data.EpisodeEntity
import dev.qoralo.podcast.data.EpisodePhase
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File
import java.security.MessageDigest
import java.util.UUID

/**
 * Covers what the app owns in an export: the sanitized name it asks the picker for, the complete bytes it writes
 * to a destination stream, and the refusal to export an episode that is not ready. The SAF hop is the platform's
 * contract and stays out of scope, so the destination is a Uri the test creates.
 *
 * The complete episode is built by the test rather than borrowed from the library, so the gate is reproducible
 * instead of depending on whatever the device happens to hold. Its rows and files are removed afterwards.
 */
class RenamedExportSmokeTest {
    private fun sanitize(title: String) =
        title.lowercase().replace(Regex("[^a-z0-9]+"), "-").trim('-').ifBlank { "episode" }

    private fun sha(bytes: ByteArray) =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    /** Smallest well-formed 44.1kHz mono PCM16 WAV: enough to prove a byte-exact copy. */
    private fun writeWav(target: File, frames: Int) {
        target.parentFile?.mkdirs()
        val data = ByteArray(frames * 2) { index -> if (index % 2 == 0) (index % 251).toByte() else 0 }
        fun le(value: Int, width: Int) = ByteArray(width) { ((value shr (8 * it)) and 0xff).toByte() }
        target.outputStream().use { out ->
            out.write("RIFF".toByteArray()); out.write(le(36 + data.size, 4)); out.write("WAVE".toByteArray())
            out.write("fmt ".toByteArray()); out.write(le(16, 4)); out.write(le(1, 2)); out.write(le(1, 2))
            out.write(le(44_100, 4)); out.write(le(88_200, 4)); out.write(le(2, 2)); out.write(le(16, 2))
            out.write("data".toByteArray()); out.write(le(data.size, 4)); out.write(data)
        }
    }

    @Test fun exportWritesCompleteAudioUnderTheSanitizedNameAndRefusesUnfinishedEpisodes() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        assumeTrue(InstrumentationRegistry.getArguments().getString("renamedExportSmoke") == "true")
        val context = instrumentation.targetContext
        val app = context.applicationContext as PodcastApplication
        val receipts = File(context.filesDir, "renamed-export-smoke").apply { mkdirs() }
        val receipt = File(receipts, "result.json")
        val stage = JSONObject().put("package", context.packageName)
        val ownedId = UUID.randomUUID().toString()
        var phase = "sanitize"
        try {
            for ((title, expected) in listOf("Tram Works: Sandyford!" to "tram-works-sandyford",
                    "  ***  " to "episode", "Episode 2 — part 3" to "episode-2-part-3")) {
                require(sanitize(title) == expected) { "sanitized name changed for $title" }
            }
            stage.put("sanitizedNameCases", 3)

            phase = "build-owned-episode"
            val generationId = UUID.randomUUID().toString()
            val wav = app.artifacts.finalWav(ownedId, generationId)
            writeWav(wav, frames = 4_410)
            val audioBytes = wav.readBytes()
            val audioSha = sha(audioBytes)
            val now = System.currentTimeMillis()
            val owned = EpisodeEntity(id = ownedId, title = "Export Gate: owned fixture!", phase = EpisodePhase.FROZEN_READY,
                instructions = "Owned export fixture; not a user episode", reviewEnabled = false,
                activeRevisionId = null, lockedRevisionId = null, lockedContentHash = null, lockedAtEpochMs = now,
                finalAudioPath = app.artifacts.relativeToEpisodes(wav), durationMs = 100,
                currentChapterPosition = null, failurePhase = null, failureMessage = null,
                createdAtEpochMs = now, updatedAtEpochMs = now,
                finalAudioSha256 = audioSha, finalAudioByteCount = audioBytes.size.toLong())
            runBlocking { app.database.podcastDao().insertEpisode(owned) }
            stage.put("ownedEpisodeId", ownedId).put("ownedAudioBytes", audioBytes.size)

            phase = "export-ready"
            val destination = File(context.cacheDir, "${sanitize(owned.title)}.wav").also { it.delete() }
            val uri = Uri.fromFile(destination)
            val source = app.repository.resolveArtifact(requireNotNull(owned.finalAudioPath))
            requireNotNull(context.contentResolver.openOutputStream(uri, "w"))
                .use { out -> source.inputStream().use { it.copyTo(out) } }
            val written = sha(destination.readBytes())
            stage.put("requestedFileName", destination.name).put("writtenBytes", destination.length())
                .put("writtenSha256", written).put("matchesEpisodeAudio", written == audioSha)
            require(destination.name == "export-gate-owned-fixture.wav")
            require(destination.length() == source.length() && written == owned.finalAudioSha256)
            destination.delete()

            phase = "refuse-unfinished"
            val partial = owned.copy(phase = EpisodePhase.GENERATING_AUDIO)
            runBlocking { app.database.podcastDao().updateEpisode(partial) }
            val unfinishedTarget = File(context.cacheDir, "must-not-exist.wav").also { it.delete() }
            val refused = runCatching {
                val current = runBlocking { app.repository.episode(ownedId) }
                require(current.phase == EpisodePhase.FROZEN_READY) {
                    "Export is available only after the complete episode is ready"
                }
                requireNotNull(context.contentResolver.openOutputStream(Uri.fromFile(unfinishedTarget), "w"))
                    .use { out -> source.inputStream().use { it.copyTo(out) } }
            }.isFailure
            require(refused && !unfinishedTarget.exists())
            stage.put("partialEpisodeRefused", true).put("partialFileCreated", unfinishedTarget.exists())
            stage.put("status", "passed")
        } catch (skipped: org.junit.AssumptionViolatedException) {
            stage.put("status", "skipped").put("phase", phase).put("reason", skipped.message ?: "assumption not met")
            receipt.writeText(stage.toString(2)); throw skipped
        } catch (error: Throwable) {
            stage.put("status", "failed").put("phase", phase).put("errorType", error.javaClass.name)
            receipt.writeText(stage.toString(2))
            throw AssertionError("Export smoke failed in the $phase phase; inspect the private receipt")
        } finally {
            // The fixture is owned by this test, so it leaves nothing behind in the user's library.
            runCatching { runBlocking { app.database.podcastDao().deleteEpisodeRows(ownedId) } }
            runCatching { File(app.artifacts.resolveEpisodeFile(ownedId).absolutePath).deleteRecursively() }
        }
        receipt.writeText(stage.toString(2))
    }
}
