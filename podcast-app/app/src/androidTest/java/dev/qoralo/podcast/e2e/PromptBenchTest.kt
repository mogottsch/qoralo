package dev.qoralo.podcast.e2e

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.qoralo.podcast.PodcastApplication
import dev.qoralo.podcast.data.JobStatus
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * Headless prompt bench: runs ONE real SCRIPT generation through the production coordinator and
 * writes the resulting transcript for inspection.
 *
 * This is a development harness for prompt iteration, not a product test and not a gate. It creates
 * its own episode from supplied text so it never touches an existing one, and it runs the same
 * engine, pack verification and prompts the app uses, so what it produces is what the app produces.
 */
@RunWith(AndroidJUnit4::class)
class PromptBenchTest {
    @Test fun generateOneScriptAndRecordTheTranscript() {
        val args = InstrumentationRegistry.getArguments()
        assumeTrue(args.getString("promptBench") == "script-v1")
        val runId = requireNotNull(args.getString("benchRun"))
        require(Regex("[a-z0-9-]{1,64}").matches(runId))
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val app = context.applicationContext as PodcastApplication
        val sourcePath = requireNotNull(args.getString("sourceFile"))
        val sourceText = File(sourcePath).readText()
        val sourceTitle = args.getString("sourceTitle") ?: "Source"
        val instructions = requireNotNull(args.getString("instructions"))
        val root = File(context.filesDir, "prompt-bench/$runId")
        require(!root.exists()) { "bench run already exists" }
        require(root.mkdirs())

        val started = System.currentTimeMillis()
        val result = JSONObject().put("runId", runId).put("instructions", instructions)
            .put("sourceChars", sourceText.length).put("startedAtEpochMs", started)
        val episodeId = runBlocking {
            val id = app.repository.createEpisode()
            app.repository.addSource(id, sourceTitle, "text/plain", sourceText.byteInputStream())
            app.repository.moveToInstructions(id)
            id
        }
        result.put("episodeId", episodeId)
        try {
            val jobId = runBlocking { app.repository.queueScriptGeneration(episodeId, instructions, true) }
            result.put("jobId", jobId)
            // The app's own dispatcher runs this in the :generation process, exactly as a real tap does.
            // Claiming it here instead would race that dispatcher and kill the job.
            val deadline = System.currentTimeMillis() + 900_000
            var job = runBlocking { app.repository.latestJob(episodeId) }
            while (System.currentTimeMillis() < deadline &&
                (job == null || job.status == JobStatus.QUEUED || job.status == JobStatus.RUNNING)) {
                Thread.sleep(2_000)
                job = runBlocking { app.repository.latestJob(episodeId) }
            }
            result.put("jobStatus", job?.status ?: "none").put("statusText", job?.statusText ?: JSONObject.NULL)
                .put("failureStage", job?.failureStage ?: JSONObject.NULL)
                .put("errorMessage", job?.errorMessage ?: JSONObject.NULL)
            if (job?.status == JobStatus.COMPLETE) {
                val (revision, chapters) = runBlocking { app.repository.activeRevision(episodeId) }
                result.put("title", revision.title).put("chapters", JSONArray(chapters.map {
                    JSONObject().put("position", it.position).put("id", it.stableChapterId)
                        .put("title", it.title).put("text", it.text)
                }))
                result.put("outcome", "complete")
            } else {
                result.put("outcome", "failed")
            }
        } catch (error: Throwable) {
            result.put("outcome", "error")
                .put("safeFailure", dev.qoralo.podcast.runtime.generationFailureMessage(error))
        }
        result.put("elapsedMs", System.currentTimeMillis() - started)
        File(root, "result.json").writeText(result.toString(2))
    }
}
