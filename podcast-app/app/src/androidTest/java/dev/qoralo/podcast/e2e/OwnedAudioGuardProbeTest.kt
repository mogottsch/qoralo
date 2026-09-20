package dev.qoralo.podcast.e2e

import android.app.ActivityManager
import android.content.Intent
import android.database.sqlite.SQLiteDatabase
import androidx.compose.material3.Text
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.core.content.ContextCompat
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.qoralo.podcast.PodcastApplication
import dev.qoralo.podcast.runtime.OwnedAudioGuardProbeService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.util.UUID

@RunWith(AndroidJUnit4::class)
class OwnedAudioGuardProbeTest {
    @get:Rule val rule=createComposeRule()
    @Test fun boundNonNeuralBlockedWorkerPersistsFailureThenTerminatesOnlyItself() {
        val args=InstrumentationRegistry.getArguments()
        assumeTrue(args.getString("ownedGuardProbe")=="true")
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        val app=context.applicationContext as PodcastApplication
        val run=requireNotNull(args.getString("diagnosticRun"));require(Regex("provider-app-[a-z0-9-]{1,48}").matches(run))
        val hash=requireNotNull(args.getString("appApkSha256"))
        require(app.artifacts.sha256(File(context.applicationInfo.sourceDir))==hash)
        val testHash=requireNotNull(args.getString("testApkSha256"))
        require(app.artifacts.sha256(File(InstrumentationRegistry.getInstrumentation().context.applicationInfo.sourceDir))==testHash)
        require(runBlocking(Dispatchers.IO) {app.database.podcastDao().activeJobCount()}==0)
        val root=File(context.filesDir,"owned-guard-probe/$run");require(root.mkdirs())
        File(root,"plan.json").writeText(JSONObject().put("runId",run).put("nonce",UUID.randomUUID()).put("appApkSha256",hash).put("nonNeural",true).toString(2))
        rule.setContent {Text("Owned guard test · synthetic worker · no models")}
        try {
            rule.runOnIdle { ContextCompat.startForegroundService(context,Intent(context,OwnedAudioGuardProbeService::class.java).putExtra("run",run)) }
            rule.waitUntil(15_000) {File(root,"blocked-worker.json").isFile || File(root,"private-failure.json").isFile}
            require(!File(root,"private-failure.json").isFile)
            require(JSONObject(File(root,"blocked-worker.json").readText()).getString("phase")=="managed_unwind_blocked_teardown")
            val identity=JSONObject(File(root,"worker-identity.json").readText())
            val pid=identity.getInt("pid")
            rule.waitUntil(8000) { context.getSystemService(ActivityManager::class.java).runningAppProcesses.orEmpty().none {it.pid==pid && it.processName==context.packageName+":guard_probe"} }
            val goneNs=System.nanoTime()
            val events=File(root,"guard-events.jsonl").readLines().filter {it.isNotBlank()}.map(::JSONObject)
            val stop=events.single {it.getString("event")=="stop_requested"}
            val kill=events.single {it.getString("event")=="owned_failure_durable_terminating_self"}
            require(stop.getString("reason")=="LOW_MEMORY" && kill.getLong("monotonicNs")>=stop.getLong("monotonicNs"))
            val failed=JSONObject(File(root,"failure-durable.json").readText())
            require(failed.getBoolean("workerWasBlocked") && failed.getString("planSha256")==identity.getString("planSha256") && failed.getInt("pid")==pid && failed.getLong("startTicks")==identity.getLong("startTicks"))
            require(failed.getLong("monotonicNs")<=kill.getLong("monotonicNs"))
            SQLiteDatabase.openDatabase(File(root,"worker.db").path,null,SQLiteDatabase.OPEN_READONLY).use { database ->
                database.rawQuery("SELECT state FROM worker",null).use { require(it.moveToFirst() && it.getString(0)=="FAILED" && !it.moveToNext()) }
            }
            val latencyMs=(goneNs-stop.getLong("monotonicNs"))/1_000_000.0
            require(latencyMs in 0.0..3000.0) {"Owned stop/cleanup latency outside provisional bound"}
            require(runBlocking(Dispatchers.IO) {app.database.podcastDao().activeJobCount()}==0)
            File(root,"probe-result.json").writeText(JSONObject().put("status","owned_non_neural_guard_passed").put("appApkSha256",hash).put("testApkSha256",testHash).put("pid",pid).put("startTicks",identity.getLong("startTicks"))
                .put("planSha256",identity.getString("planSha256")).put("stopToObservedProcessAbsentMs",latencyMs)
                .put("modelCalls",0).put("modelConstructions",0).put("newUserAudioJobs",0).put("syntheticPrivateWorkerRows",1)
                .put("wholeStartFloorKiB",dev.qoralo.podcast.runtime.AudioGuardPolicy.WHOLE_START_KIB)
                .put("preContextFloorKiB",dev.qoralo.podcast.runtime.AudioGuardPolicy.PRE_CONTEXT_KIB).put("startupMemoryCreditKiB",0)
                .put("failureDurableBeforeTermination",true).put("managedUnwindBlockedTeardown",true).put("inFlightQnnCancellationProven",false).toString(2))
        } catch(error:Throwable) {
            File(root,"private-test-failure.txt").writeText(error.stackTraceToString())
            throw AssertionError("Owned non-neural guard probe failed; retain private state, no model entry")
        }
    }
}
