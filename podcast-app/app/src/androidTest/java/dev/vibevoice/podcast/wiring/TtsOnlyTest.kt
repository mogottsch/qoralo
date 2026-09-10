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
class TtsOnlyTest {
    @Test fun oneWholeRequestRetainsOutputOrFirstFailure() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val args = InstrumentationRegistry.getArguments()
        val approval = args.getString("ttsOnlyApproved")
        assumeTrue("Explicit exact TTS slot required", TtsOnlyContract.approvedHash(approval))
        val approvedSha = requireNotNull(approval)
        val run = requireNotNull(args.getString("ttsOnlyRunId")); require(TtsOnlyContract.validRunId(run, approvedSha))
        val context = instrumentation.targetContext
        require(Application.getProcessName() == context.packageName)
        val contract = TtsOnlyContract.load(context, approvedSha)
        val root = File(context.filesDir, "${contract.evidenceDirectory}/$run"); require(!root.exists() && root.mkdirs())
        val log = WiringEvidence(root)
        val start = SystemClock.elapsedRealtime()
        try {
            log.write("contract.json", context.assets.open("${contract.assetDirectory}/contract.json").bufferedReader().use { it.readText() })
            val appHash = WiringEvidence.sha256(File(context.applicationInfo.sourceDir))
            val testHash = WiringEvidence.sha256(File(instrumentation.context.applicationInfo.sourceDir))
            log.json("driver-identity.json", JSONObject().put("appApkSha256", appHash).put("testApkSha256", testHash)
                .put("pid", Process.myPid()).put("contractSha256", contract.sha256).put("deviceFingerprint", android.os.Build.FINGERPRINT)
                .put("inputSha256", WiringContract.hash(contract.text.toByteArray(Charsets.UTF_8)))
                .put("inputUtf8Bytes", contract.text.toByteArray(Charsets.UTF_8).size).put("canonical", !contract.isLongProbe))
            require(appHash == args.getString("appApkSha256") && testHash == args.getString("testApkSha256"))
            ActivityScenario.launch(MainActivity::class.java).use {
                val dispatch = SystemClock.elapsedRealtime()
                ContextCompat.startForegroundService(context, Intent(context, TtsOnlyService::class.java)
                    .putExtra("runId", run).putExtra("contractSha256", contract.sha256))
                val started = File(root, "service-started.json"); waitFor(started, dispatch + 15_000)
                val identity = readJson(started)
                assertEquals("${context.packageName}:generation", identity.getString("process"))
                assertNotEquals(Process.myPid(), identity.getInt("pid"))
                val terminal = File(root, "service-result.json"); waitFor(terminal, start + contract.driverMs)
                val result = readJson(terminal)
                require(result.getString("status") in setOf("tts_complete", "tts_failed", "timeout_or_limit"))
                log.json("driver-result.json", JSONObject().put("collection", "terminal_record_received")
                    .put("nativeOutcome", result.getString("status")).put("stage", result.getString("stage"))
                    .put("wavPresent", File(root, contract.outputName).isFile).put("providerExecutionApproved", false)
                    .put("gemmaRequested", false).put("capacityProbeRequested", contract.isLongProbe).put("elapsedMs", SystemClock.elapsedRealtime() - start))
            }
        } catch (error: Throwable) {
            if (!File(root, "driver-result.json").exists()) log.json("driver-result.json", JSONObject().put("collection", "failed").put("error", error.stackTraceToString()))
            throw error
        } finally { context.stopService(Intent(context, TtsOnlyService::class.java)) }
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
