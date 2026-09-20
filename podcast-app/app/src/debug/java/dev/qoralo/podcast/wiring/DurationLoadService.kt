package dev.qoralo.podcast.wiring

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.IBinder
import android.os.Process
import androidx.core.app.NotificationCompat
import dev.qoralo.podcast.BuildConfig
import dev.qoralo.podcast.PodcastApplication
import dev.qoralo.podcast.R
import dev.qoralo.podcast.model.ModelPackRequirement
import dev.qoralo.podcast.model.ModelPackVerifier
import dev.qoralo.podcast.model.ModelRoute
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import java.io.File
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/** One debug duration-session LOAD ONLY. No LLM, no tensors, no neural execution. */
class DurationLoadService : Service() {
    private val worker = Executors.newSingleThreadExecutor()
    private val timer = Executors.newScheduledThreadPool(2)
    @Volatile private var log: WiringEvidence? = null
    @Volatile private var stage = "dispatch"

    override fun onBind(intent: Intent?): IBinder? = null
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (log != null) return START_NOT_STICKY
        val run = intent?.getStringExtra("runId").orEmpty()
        if (!validRunId(run) || intent?.getStringExtra("contractSha256") != CONTRACT_SHA) { stopSelf(); return START_NOT_STICKY }
        check(Application.getProcessName() == "$packageName:generation")
        val root = File(filesDir, "duration-load/$run")
        check(root.isDirectory && !File(root, "service-started.json").exists()) { "New run directory required" }
        val evidence = WiringEvidence(root).also { log = it }
        evidence.json("service-started.json", JSONObject().put("pid", Process.myPid()).put("uid", Process.myUid())
            .put("process", Application.getProcessName()).put("contractSha256", CONTRACT_SHA))
        getSystemService(NotificationManager::class.java).createNotificationChannel(NotificationChannel("duration-load", "Debug QNN load-only", NotificationManager.IMPORTANCE_LOW))
        startForeground(4200, NotificationCompat.Builder(this, "duration-load").setSmallIcon(R.drawable.ic_notification)
            .setContentTitle("Debug duration load-only").setContentText("No Gemma or neural execution").setOngoing(true).build(), ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        worker.execute {
            try {
                val contract = contract(this)
                timer.schedule({ abort("total_deadline", IllegalStateException("Load-only total deadline exceeded")) }, contract.getLong("serviceDeadlineSeconds"), TimeUnit.SECONDS)
                timer.scheduleWithFixedDelay({
                    if (root.walkTopDown().filter(File::isFile).sumOf(File::length) > contract.getLong("maxEvidenceBytes")) {
                        abort("evidence_quota", IllegalStateException("Load-only evidence limit exceeded"))
                    }
                }, 1, 1, TimeUnit.SECONDS)
                stage = "verify-supertonic-pack"
                val verifyTimeout = timer.schedule({ if (stage == "verify-supertonic-pack") abort(stage, IllegalStateException("Verification deadline exceeded")) }, contract.getLong("verifyDeadlineSeconds"), TimeUnit.SECONDS)
                val app = application as PodcastApplication
                runBlocking { check(app.repository.runningJobs().isEmpty() && app.repository.queuedJobs().isEmpty()) { "Product jobs active" } }
                require(BuildConfig.SUPERTONIC_MANIFEST_SHA256 == contract.getString("manifestSha256"))
                val pack = ModelPackVerifier().verify(app.artifacts.modelPackRoot("supertonic-3"), ModelPackRequirement(
                    ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP, "supertonic-3", BuildConfig.SUPERTONIC_MANIFEST_SHA256))
                val descriptor = File(pack.root, contract.getString("descriptor"))
                require(WiringEvidence.sha256(descriptor) == contract.getString("descriptorSha256"))
                evidence.json("verified-pack.json", JSONObject().put("manifestSha256", pack.manifestSha256).put("contract", pack.contract.toString()))
                stage = "duration-load"
                verifyTimeout.cancel(false)
                val loadTimeout = timer.schedule({ if (stage == "duration-load") abort(stage, IllegalStateException("Duration load/close deadline exceeded")) }, contract.getLong("loadDeadlineSeconds"), TimeUnit.SECONDS)
                evidence.snapshot("before-duration-load")
                evidence.json("environment.json", environmentSnapshot(this))
                NativeStdioCapture(root).use {
                    evidence.event("duration_load_begin", "one constructor, zero Run calls; original options and ADSP path; verbose logs only")
                    try {
                        System.loadLibrary("podcast_runtime")
                        val profiles = File(root, "profiles").apply { check(mkdir()) }
                        val result = DurationLoadNative.probe(pack.root.absolutePath, profiles.absolutePath)
                        evidence.write("native-return.txt", result ?: error("Native load probe returned no result"))
                        evidence.event("duration_load_return", result)
                    } catch (error: Throwable) {
                        evidence.write("load-error.txt", error.stackTraceToString())
                        throw error
                    } finally { evidence.snapshot("after-duration-load") }
                }
                stage = "completed-without-run"
                loadTimeout.cancel(false)
                evidence.json("inventory.json", evidence.inventory())
                evidence.finish("duration_session_created_no_run", stage)
            } catch (error: Throwable) {
                evidence.finish("duration_load_failed", stage, error)
            } finally {
                timer.shutdownNow()
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
        }
        return START_NOT_STICKY
    }

    private fun abort(where: String, error: Throwable) {
        try { log?.finish("timeout_or_limit", where, error) }
        finally { if (Application.getProcessName() == "$packageName:generation") Process.killProcess(Process.myPid()) }
    }
    override fun onTimeout(startId: Int, fgsType: Int) = abort("android_fgs_timeout", IllegalStateException("Android FGS timeout"))
    override fun onDestroy() { timer.shutdownNow(); worker.shutdownNow(); super.onDestroy() }

    companion object {
        const val CONTRACT_SHA = "51edc271c52b43e14f901169315136f29298c29f7e8954eb6b99d6fe21954f02"
        const val DRIVER_TIMEOUT_MS = 135_000L
        fun validRunId(value: String) = value.matches(Regex("duration-[a-z0-9-]{1,64}"))
        fun contract(context: Context): JSONObject {
            val bytes = context.assets.open("duration-load/contract.json").use { it.readBytes() }
            require(WiringContract.hash(bytes) == CONTRACT_SHA)
            return JSONObject(bytes.toString(Charsets.UTF_8))
        }

        private fun environmentSnapshot(context: Context): JSONObject = JSONObject().apply {
            put("uid", Process.myUid()); put("pid", Process.myPid()); put("nativeLibraryDir", context.applicationInfo.nativeLibraryDir)
            put("targetSdk", context.applicationInfo.targetSdkVersion)
            put("LD_LIBRARY_PATH", System.getenv("LD_LIBRARY_PATH") ?: JSONObject.NULL)
            put("ADSP_LIBRARY_PATH_before_native", System.getenv("ADSP_LIBRARY_PATH") ?: JSONObject.NULL)
            put("namespaceLimitation", "maps, SELinux context and loader logs are observations; filesystem readability is not namespace visibility; no explicit vendor dlopen probe")
            for (path in listOf("/proc/self/attr/current", "/linkerconfig/ld.config.txt", "/vendor/etc/public.libraries.txt", "/system/etc/public.libraries.txt")) {
                put(path, runCatching { File(path).readText() }.getOrElse { "UNAVAILABLE: $it" })
            }
            put("packagedLibraries", JSONObject().apply {
                File(context.applicationInfo.nativeLibraryDir).listFiles().orEmpty().filter { it.extension == "so" }.forEach {
                    put(it.name, JSONObject().put("bytes", it.length()).put("sha256", WiringEvidence.sha256(it)))
                }
            })
        }
    }
}

internal object DurationLoadNative {
    @JvmStatic external fun probe(packRoot: String, evidenceDirectory: String): String?
}
