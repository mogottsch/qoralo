package dev.vibevoice.podcast.ui

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import dev.vibevoice.podcast.data.EpisodeEntity
import dev.vibevoice.podcast.data.EpisodePhase
import dev.vibevoice.podcast.data.GenerationJobEntity

@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@Composable
fun GeneratingScreen(episode: EpisodeEntity?, job: GenerationJobEntity?, onClose: () -> Unit) {
    val failed = episode?.phase == EpisodePhase.FAILED
    PhoneContent {
        Scaffold(topBar = {
            TopAppBar(
                title = { Text(if (failed) "Episode stopped" else "Creating episode") },
                navigationIcon = { IconButton(onClick = onClose) { Icon(Icons.Default.Close, "Return to library") } },
            )
        }) { padding ->
            LazyColumn(
                Modifier.fillMaxSize().padding(padding),
                contentPadding = PaddingValues(horizontal = 24.dp, vertical = 20.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                item {
                    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
                        if (failed) FailurePanel(episode, onClose) else GenerationPanel(episode, job)
                    }
                }
            }
        }
    }
}

@Composable
private fun GenerationPanel(episode: EpisodeEntity?, job: GenerationJobEntity?) {
    val transition = rememberInfiniteTransition(label = "generation")
    val pulse by transition.animateFloat(0.94f, 1.04f, infiniteRepeatable(tween(1_100), RepeatMode.Reverse), label = "pulse")
    Surface(
        color = MaterialTheme.colorScheme.primaryContainer,
        shape = RoundedCornerShape(64.dp),
        modifier = Modifier.size(if (LocalDensity.current.fontScale >= 1.4f) 140.dp else 218.dp).scale(pulse),
    ) { VibeArtwork(Modifier.fillMaxSize(), compact = true) }
    val total = job?.totalChapters ?: 0
    val current = job?.currentChapter ?: 0
    val completed = if (total > 0) (current - 1).coerceIn(0, total) else 0
    val assembling = total > 0 && current > total
    Text(
        if (assembling) "ASSEMBLING EPISODE" else if (total > 0) "CHAPTER ${current.coerceIn(1, total)} OF $total" else "ON-DEVICE GENERATION",
        style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(top = 34.dp),
    )
    Text(
        job?.statusText ?: "Preparing your episode",
        style = MaterialTheme.typography.headlineMedium,
        textAlign = TextAlign.Center,
        modifier = Modifier.padding(top = 8.dp),
    )
    Text(
        episode?.title?.takeUnless { it == "Untitled episode" } ?: "Your script and audio stay on this device",
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        textAlign = TextAlign.Center,
        modifier = Modifier.padding(top = 8.dp),
    )
    if (total > 0) {
        LinearProgressIndicator(progress = { completed.toFloat() / total.coerceAtLeast(1) }, modifier = Modifier.fillMaxWidth().padding(top = 28.dp).height(7.dp))
        Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("$completed complete", style = MaterialTheme.typography.labelMedium)
            Text("${(total - completed).coerceAtLeast(0)} remaining", style = MaterialTheme.typography.labelMedium)
        }
    } else LinearProgressIndicator(Modifier.fillMaxWidth().padding(top = 28.dp))
    if (episode?.lockedRevisionId != null) Text("Script locked", style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(top = 16.dp))
    Text("The selected inference route must succeed; no fallback will be used.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center, modifier = Modifier.padding(top = 24.dp))
}

@Composable
private fun FailurePanel(episode: EpisodeEntity, onClose: () -> Unit) {
    Surface(color = MaterialTheme.colorScheme.errorContainer, shape = RoundedCornerShape(28.dp), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(Icons.Default.ErrorOutline, null, modifier = Modifier.size(48.dp), tint = MaterialTheme.colorScheme.error)
            Text("Generation couldn’t finish", style = MaterialTheme.typography.headlineSmall, textAlign = TextAlign.Center, modifier = Modifier.padding(top = 16.dp))
            Text(
                episode.failureMessage ?: "The selected on-device runtime stopped.",
                style = MaterialTheme.typography.bodyMedium,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 10.dp),
            )
            Text(
                "No alternate model, CPU fallback, or hidden chapter splitting was attempted.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onErrorContainer,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 12.dp),
            )
            PrimaryAction("Return to library", onClose, modifier = Modifier.padding(top = 22.dp))
        }
    }
}
