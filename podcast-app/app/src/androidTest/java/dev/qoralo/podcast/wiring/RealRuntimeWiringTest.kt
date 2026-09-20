package dev.qoralo.podcast.wiring

import android.app.Application
import android.content.Intent
import android.os.Process
import android.os.SystemClock
import androidx.core.content.ContextCompat
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.qoralo.podcast.MainActivity
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/** Opt-in real hardware wiring. Never included implicitly in UI/fake benchmark evidence. */
@RunWith(AndroidJUnit4::class)
class RealRuntimeWiringTest {
    @Test fun realGpuAndQnnWiringWithExpectedChapterCapacityRejection() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val args = InstrumentationRegistry.getArguments()
        assumeTrue("Explicit phone assignment and exact host preflight required", args.getString("wiringApproved") == WiringContract.SHA256)
        val runId = requireNotNull(args.getString("wiringRunId"))
        require(WiringContract.validRunId(runId))
        val context = instrumentation.targetContext
        check(Application.getProcessName() == context.packageName) { "Driver must remain in UI process" }
        val root = File(context.filesDir, "wiring/$runId")
        require(!root.exists() && root.mkdirs()) { "Run ID reused; never overwrite an earlier failure" }
        val log = WiringEvidence(root)
        val start = SystemClock.elapsedRealtime()
        try {
            val contract = WiringContract.load(context)
            log.write("contract.json", context.assets.open("wiring/contract.json").bufferedReader().use { it.readText() })
            contract.inputs.forEach { (name, text) -> log.write(name, text) }
            val appHash = WiringEvidence.sha256(File(context.applicationInfo.sourceDir))
            val testHash = WiringEvidence.sha256(File(instrumentation.context.applicationInfo.sourceDir))
            log.json("driver-identity.json", JSONObject().put("appApkSha256", appHash).put("testApkSha256", testHash)
                .put("driverPid", Process.myPid()).put("contractSha256", WiringContract.SHA256)
                .put("device", android.os.Build.MODEL).put("fingerprint", android.os.Build.FINGERPRINT)
                .put("expectedAppHash", args.getString("appApkSha256")).put("expectedTestHash", args.getString("testApkSha256")))
            require(appHash == args.getString("appApkSha256") && testHash == args.getString("testApkSha256")) { "Installed APK identity differs from host preflight" }
            ActivityScenario.launch(MainActivity::class.java).use {
                val dispatchStart = SystemClock.elapsedRealtime()
                ContextCompat.startForegroundService(context, Intent(context, RuntimeWiringService::class.java)
                    .putExtra("runId", runId).putExtra("contractSha256", WiringContract.SHA256))
                val started = File(root, "service-started.json")
                while (!started.isFile && SystemClock.elapsedRealtime() - dispatchStart < WiringContract.ACK_TIMEOUT_MS) Thread.sleep(200)
                require(started.isFile) { "Wiring service did not acknowledge within 30 seconds; no retry" }
                // JSON writes are bounded tiny files; wait until complete, never treat partial write as a new attempt.
                val identity = readJson(started)
                assertEquals("${context.packageName}:generation", identity.getString("process"))
                assertNotEquals(Process.myPid(), identity.getInt("pid"))
                val terminal = File(root, "service-result.json")
                while (!terminal.isFile && SystemClock.elapsedRealtime() - start < WiringContract.INSTRUMENTATION_TIMEOUT_MS) Thread.sleep(500)
                require(terminal.isFile) { "No terminal service evidence by driver deadline; inspect logcat for crash; no retry" }
                val outcome = readJson(terminal)
                assertEquals(outcome.toString(), "observations_complete", outcome.getString("status"))
                require(File(root, "canonical-short.wav").isFile)
                require(!File(root, "capacity-output/chapter.wav").exists())
                log.json("driver-result.json", JSONObject().put("status", "observations_complete_provider_review_required")
                    .put("elapsedMs", SystemClock.elapsedRealtime() - start)
                    .put("productE2e", false).put("runtimeProof", "Host review of preserved maps/RPC/QNN profiles required"))
            }
        } catch (error: Throwable) {
            if (!File(root, "driver-result.json").exists()) log.json("driver-result.json", JSONObject().put("status", "failed")
                .put("error", error.stackTraceToString()).put("elapsedMs", SystemClock.elapsedRealtime() - start))
            throw error
        } finally {
            // Host controller also force-stops only this scoped app on failure; JNI may ignore stopService.
            context.stopService(Intent(context, RuntimeWiringService::class.java))
        }
    }

    private fun readJson(file: File): JSONObject {
        val end = SystemClock.elapsedRealtime() + 2000
        var failure: Throwable? = null
        while (SystemClock.elapsedRealtime() < end) {
            try { return JSONObject(file.readText()) } catch (error: Exception) { failure = error; Thread.sleep(50) }
        }
        throw IllegalStateException("Incomplete evidence file: ${file.name}", failure)
    }
}
