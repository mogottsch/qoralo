package dev.vibevoice.podcast

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import dev.vibevoice.podcast.ui.PodcastApp
import dev.vibevoice.podcast.ui.theme.VibeVoiceTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { VibeVoiceTheme { PodcastApp() } }
    }
}
