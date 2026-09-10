package dev.vibevoice.podcast.wiring

import android.app.Application
import android.content.Intent
import android.os.Process
import android.os.SystemClock
import androidx.core.content.ContextCompat
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.vibevoice.podcast.MainActivity
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

@RunWith(AndroidJUnit4::class)
class DurationLoadOnlyTest {
    @Test fun baselineDurationConstructorOnlyRetainsSuccessOrFailure() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val args = InstrumentationRegistry.getArguments()
        assumeTrue("Explicit separate duration-load phone slot required", args.getString("durationLoadApproved") == DurationLoadService.CONTRACT_SHA)
        val run = requireNotNull(args.getString("durationLoadRunId"))
        require(DurationLoadService.validRunId(run))
        val context = instrumentation.targetContext
        require(Application.getProcessName() == context.packageName)
        val root = File(context.filesDir, "duration-load/$run")
        require(!root.exists() && root.mkdirs())
        val log = WiringEvidence(root)
        val start = SystemClock.elapsedRealtime()
        try {
            DurationLoadService.contract(context)
            log.write("contract.json", context.assets.open("duration-load/contract.json").bufferedReader().use { it.readText() })
            val appHash = WiringEvidence.sha256(File(context.applicationInfo.sourceDir))
            val testHash = WiringEvidence.sha256(File(instrumentation.context.applicationInfo.sourceDir))
            log.json("driver-identity.json", JSONObject().put("appApkSha256", appHash).put("testApkSha256", testHash)
                .put("pid", Process.myPid()).put("contractSha256", DurationLoadService.CONTRACT_SHA)
                .put("deviceFingerprint", android.os.Build.FINGERPRINT))
            require(appHash == args.getString("appApkSha256") && testHash == args.getString("testApkSha256"))
            ActivityScenario.launch(MainActivity::class.java).use {
                val dispatch = SystemClock.elapsedRealtime()
                ContextCompat.startForegroundService(context, Intent(context, DurationLoadService::class.java)
                    .putExtra("runId", run).putExtra("contractSha256", DurationLoadService.CONTRACT_SHA))
                val started = File(root, "service-started.json")
                waitFor(started, dispatch + 15_000)
                val identity = readJson(started)
                assertEquals("${context.packageName}:generation", identity.getString("process"))
                assertNotEquals(Process.myPid(), identity.getInt("pid"))
                val terminal = File(root, "service-result.json")
                waitFor(terminal, start + DurationLoadService.DRIVER_TIMEOUT_MS)
                val result = readJson(terminal)
                // A load failure is a retained diagnostic result, NOT a successful backend.
                val status = result.getString("status")
                require(status in setOf("duration_session_created_no_run", "duration_load_failed", "timeout_or_limit"))
                log.json("driver-result.json", JSONObject().put("collection", "terminal_record_received")
                    .put("nativeOutcome", status).put("stage", result.getString("stage"))
                    .put("backendApproved", false).put("neuralInferenceRequested", false)
                    .put("gemmaRequested", false).put("elapsedMs", SystemClock.elapsedRealtime() - start))
            }
        } catch (error: Throwable) {
            if (!File(root, "driver-result.json").exists()) log.json("driver-result.json", JSONObject().put("collection", "failed")
                .put("error", error.stackTraceToString()))
            throw error
        } finally { context.stopService(Intent(context, DurationLoadService::class.java)) }
    }

    private fun waitFor(file: File, deadline: Long) {
        while (!file.isFile && SystemClock.elapsedRealtime() < deadline) Thread.sleep(100)
        require(file.isFile) { "Evidence deadline: ${file.name}; no retry" }
    }
    private fun readJson(file: File): JSONObject {
        val deadline = SystemClock.elapsedRealtime() + 2000
        while (true) {
            try { return JSONObject(file.readText()) }
            catch (error: Exception) { if (SystemClock.elapsedRealtime() >= deadline) throw error; Thread.sleep(25) }
        }
    }
}
