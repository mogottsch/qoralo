package dev.qoralo.podcast.e2e

import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.qoralo.podcast.MainActivity
import dev.qoralo.podcast.PodcastApplication
import dev.qoralo.podcast.data.*
import dev.qoralo.podcast.runtime.*
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/** Finishes the exact already-rendered owned chapter. Does not instantiate a voice/Gemma engine or replay synthesis. */
@RunWith(AndroidJUnit4::class)
class ProviderPublicationRecoveryTest {
    private fun <T> db(block: suspend () -> T): T = runBlocking { block() }
    @Test fun publishExactCompletedChapterWithoutInference() {
        val args=InstrumentationRegistry.getArguments()
        assumeTrue(args.getString("providerRecovery")=="non-neural-v1")
        val instrumentation=InstrumentationRegistry.getInstrumentation();val context=instrumentation.targetContext
        val app=context.applicationContext as PodcastApplication
        val run=requireNotNull(args.getString("diagnosticRun"));require(Regex("provider-app-[a-z0-9-]{1,48}").matches(run))
        val root=File(context.filesDir,"provider-integration/$run-driver");require(root.mkdirs())
        fun json(name:String,value:JSONObject)=ShortProductDiagnostics.json(File(root,name),value)
        var scenario:ActivityScenario<MainActivity>?=null
        try {
            val appHash=app.artifacts.sha256(File(context.applicationInfo.sourceDir));val testHash=app.artifacts.sha256(File(instrumentation.context.applicationInfo.sourceDir))
            require(appHash==args.getString("appApkSha256") && testHash==args.getString("testApkSha256"))
            val id=requireNotNull(args.getString("ownedEpisodeId"));val sourceJob=requireNotNull(args.getString("sourceJobId"))
            val revisionId=requireNotNull(args.getString("revisionId"));val hash=requireNotNull(args.getString("wavSha256"))
            val path=requireNotNull(args.getString("completedWavePath"))
            val before=db { app.repository.episode(id) };val failed=requireNotNull(db { app.repository.latestJob(id) })
            require(before.phase==EpisodePhase.FAILED && before.lockedRevisionId==revisionId && failed.id==sourceJob && failed.status==JobStatus.FAILED)
            require(before.lockedContentHash==args.getString("revisionSha256"))
            val revision=db { app.repository.activeRevision(id) }
            val source=app.repository.resolveArtifact(path);require(ProviderPublication.hash(source)==hash)
            require(db { app.repository.runningJobs() }.isEmpty() && db { app.repository.queuedJobs() }.isEmpty())
            json("identity.json",JSONObject().put("runId",run).put("appApkSha256",appHash).put("testApkSha256",testHash)
                .put("episodeId",id).put("sourceJobId",sourceJob).put("revisionId",revisionId).put("revisionSha256",before.lockedContentHash)
                .put("wavSha256",hash).put("nonNeuralPublicationRecovery",true))
            json("ownership.json",JSONObject().put("runId",run).put("episodeId",id).put("sourceJobId",sourceJob).put("existingOwnedRecovery",true))
            scenario=ActivityScenario.launch(MainActivity::class.java)
            val newJob=db { app.repository.queueProviderPublicationRecovery(id,sourceJob,revisionId,listOf(path to hash)) }
            require(newJob!=sourceJob)
            json("recovery-job.json",JSONObject().put("jobId",newJob).put("sourceJobId",sourceJob).put("episodeId",id).put("neuralCalls",0))
            val deadline=System.nanoTime()+90_000_000_000L
            var current:EpisodeEntity
            while(true) {
                current=db { app.repository.episode(id) };val job=requireNotNull(db { app.repository.latestJob(id) });require(job.id==newJob)
                if(current.phase==EpisodePhase.FROZEN_READY || job.status==JobStatus.FAILED) break
                require(System.nanoTime()<deadline) { "Publication deadline" };Thread.sleep(200)
            }
            require(current.phase==EpisodePhase.FROZEN_READY)
            val final=app.repository.resolveArtifact(requireNotNull(current.finalAudioPath));val metadata=WavInspector.inspectSupertonicOutput(final)
            require(metadata.sha256==hash && current.finalAudioSha256==hash && ProviderPublication.hash(source)==hash)
            require(failed==db { app.database.podcastDao().job(sourceJob) })
            require(revision==db { app.repository.activeRevision(id) } && current.lockedRevisionId==before.lockedRevisionId && current.lockedAtEpochMs==before.lockedAtEpochMs)
            json("driver-result.json",JSONObject().put("status","exact_completed_audio_published_without_inference")
                .put("appApkSha256",appHash).put("testApkSha256",testHash).put("episodeId",id).put("sourceJobId",sourceJob).put("jobId",newJob)
                .put("revisionId",revisionId).put("revisionSha256",current.lockedContentHash).put("wavSha256",hash)
                .put("frames",metadata.frameCount).put("wavBytes",final.length()).put("finalAudioPath",current.finalAudioPath)
                .put("failedJobUnchanged",true).put("completedSourceUnchanged",true).put("neuralCalls",0).put("playOrExportRequested",false))
        } catch(error:Throwable) {
            runCatching { json("private-driver-failure.json",JSONObject().put("error",error.stackTraceToString())) }
            throw AssertionError("Publication recovery stopped; inspect private evidence; no synthesis retry")
        } finally { runCatching { scenario?.close() } }
    }
}
