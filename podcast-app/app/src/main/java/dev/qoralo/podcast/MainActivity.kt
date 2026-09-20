package dev.qoralo.podcast

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import dev.qoralo.podcast.ui.PodcastApp
import dev.qoralo.podcast.ui.theme.QoraloTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { QoraloTheme { PodcastApp() } }
    }
}
