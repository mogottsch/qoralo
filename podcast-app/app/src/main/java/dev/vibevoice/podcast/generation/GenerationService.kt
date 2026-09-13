package dev.vibevoice.podcast.generation

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import dev.vibevoice.podcast.MainActivity
import dev.vibevoice.podcast.PodcastApplication
import dev.vibevoice.podcast.R
import dev.vibevoice.podcast.data.GenerationJobEntity
import dev.vibevoice.podcast.data.JobKind
import dev.vibevoice.podcast.runtime.generationFailureMessage
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.withContext

class GenerationService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private lateinit var coordinator: GenerationCoordinator
    private val commandGate = SingleActiveGenerationGate()
    @Volatile private var activeJobId: String? = null
    @Volatile private var activeEpisodeId: String? = null

    override fun onCreate() {
        super.onCreate()
        val app = application as PodcastApplication
        coordinator = GenerationCoordinator(app.repository, app.artifacts, audioGuardFactory = { binding ->
            dev.vibevoice.podcast.runtime.RuntimeDiagnostics.createOwnedAudioGuard(this, binding) {
                activeJobId == binding.jobId && activeEpisodeId == binding.episodeId
            }
        })
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(CHANNEL_ID, getString(R.string.generation_channel_name), NotificationManager.IMPORTANCE_LOW).apply {
                description = getString(R.string.generation_channel_description)
            },
        )
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val episodeId = intent?.getStringExtra(EXTRA_EPISODE_ID)
        val jobId = intent?.getStringExtra(EXTRA_JOB_ID)
        val action = intent?.action
        if (episodeId == null || jobId == null || action !in SUPPORTED_ACTIONS) {
            stopSelf(startId)
            return START_NOT_STICKY
        }
        if (!commandGate.tryAcquire()) return START_NOT_STICKY
        activeJobId = jobId
        activeEpisodeId = episodeId
        startAsForeground("Preparing on-device generation")
        scope.launch {
            var failureJob = jobId
            try {
                dev.vibevoice.podcast.runtime.RuntimeDiagnostics.beginJob(this@GenerationService, episodeId, jobId)
                val progress: suspend (String) -> Unit = { updateNotification(it) }
                when (action) {
                    ACTION_SCRIPT -> {
                        val audioJob = coordinator.generateScript(episodeId, jobId, progress)
                        if (audioJob != null) {
                            activeJobId = audioJob
                            failureJob = audioJob
                            coordinator.generateAudio(episodeId, audioJob, progress)
                        }
                    }
                    ACTION_EDIT -> coordinator.editDraft(episodeId, jobId, progress)
                    ACTION_AUDIO -> coordinator.generateAudio(episodeId, jobId, progress)
                }
            } catch (cancelled: CancellationException) {
                withContext(NonCancellable) {
                    runCatching { (application as PodcastApplication).repository.failJob(episodeId, failureJob,
                        "Generation was cancelled. Any completed audio is retained; the episode is not complete.", "cancelled") }
                }
                throw cancelled
            } catch (error: Throwable) {
                val safeMessage = generationFailureMessage(error)
                runCatching { dev.vibevoice.podcast.runtime.RuntimeDiagnostics.jobFailed(error) }
                runCatching {
                    (application as PodcastApplication).repository.failJob(
                        episodeId,
                        failureJob,
                        safeMessage,
                    )
                }
                updateNotification("Generation stopped: $safeMessage")
            } finally {
                dev.vibevoice.podcast.runtime.RuntimeDiagnostics.endJob()
                activeJobId = null
                activeEpisodeId = null
                commandGate.release()
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf(startId)
            }
        }
        return START_NOT_STICKY
    }

    override fun onTimeout(startId: Int, fgsType: Int) {
        val jobId = activeJobId
        val episodeId = activeEpisodeId
        if (jobId != null && episodeId != null) {
            scope.launch {
                runCatching { (application as PodcastApplication).repository.failJob(episodeId, jobId, "Android ended the long-running generation service", "android_fgs_timeout") }
                scope.cancel()
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf(startId)
            }
        } else stopSelf(startId)
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun startAsForeground(status: String) {
        val notification = notification(status)
        startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
    }

    private fun updateNotification(status: String) {
        getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, notification(status))
    }

    private fun notification(status: String): Notification {
        val contentIntent = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle("Creating episode")
            .setContentText(status)
            .setContentIntent(contentIntent)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setCategory(NotificationCompat.CATEGORY_PROGRESS)
            .build()
    }

    companion object {
        private const val CHANNEL_ID = "episode-generation"
        private const val NOTIFICATION_ID = 4102
        private const val EXTRA_EPISODE_ID = "episode-id"
        private const val EXTRA_JOB_ID = "job-id"
        private const val ACTION_SCRIPT = "dev.vibevoice.podcast.GENERATE_SCRIPT"
        private const val ACTION_EDIT = "dev.vibevoice.podcast.EDIT_SCRIPT"
        private const val ACTION_AUDIO = "dev.vibevoice.podcast.GENERATE_AUDIO"
        private val SUPPORTED_ACTIONS = setOf(ACTION_SCRIPT, ACTION_EDIT, ACTION_AUDIO)

        fun startScript(context: Context, episodeId: String, jobId: String) = start(context, ACTION_SCRIPT, episodeId, jobId)
        fun startEdit(context: Context, episodeId: String, jobId: String) = start(context, ACTION_EDIT, episodeId, jobId)
        fun startAudio(context: Context, episodeId: String, jobId: String) = start(context, ACTION_AUDIO, episodeId, jobId)
        fun start(context: Context, job: GenerationJobEntity) = when (job.kind) {
            JobKind.SCRIPT -> startScript(context, job.episodeId, job.id)
            JobKind.AGENT_EDIT -> startEdit(context, job.episodeId, job.id)
            JobKind.AUDIO -> startAudio(context, job.episodeId, job.id)
            else -> error("Unsupported durable job kind")
        }

        private fun start(context: Context, action: String, episodeId: String, jobId: String) {
            ContextCompat.startForegroundService(context, Intent(context, GenerationService::class.java).apply {
                this.action = action
                putExtra(EXTRA_EPISODE_ID, episodeId)
                putExtra(EXTRA_JOB_ID, jobId)
            })
        }
    }
}
