package dev.vibevoice.podcast.generation

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.IBinder
import dev.vibevoice.podcast.R

class GenerationService : Service() {
    override fun onCreate() {
        super.onCreate()
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, getString(R.string.generation_channel_name), NotificationManager.IMPORTANCE_LOW).apply {
                description = getString(R.string.generation_channel_description)
            },
        )
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val notification = Notification.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_launcher)
            .setContentTitle("Creating episode")
            .setContentText("Preparing the selected on-device runtimes")
            .setOngoing(true)
            .build()
        startForeground(NOTIFICATION_ID, notification)
        // Slice 0 intentionally performs no fake inference. A durable episode command is required.
        stopSelf(startId)
        return START_NOT_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private companion object {
        const val CHANNEL_ID = "episode-generation"
        const val NOTIFICATION_ID = 4102
    }
}
