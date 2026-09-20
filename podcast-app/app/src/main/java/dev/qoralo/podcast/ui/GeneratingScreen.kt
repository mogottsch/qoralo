package dev.qoralo.podcast.ui

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
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.statusBarsPadding
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
import dev.qoralo.podcast.data.EpisodeEntity
import dev.qoralo.podcast.data.EpisodePhase
import dev.qoralo.podcast.data.GenerationJobEntity

@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@Composable
fun GeneratingScreen(episode: EpisodeEntity?, job: GenerationJobEntity?, onClose: () -> Unit, onReturnToDraft: (() -> Unit)? = null,
    availableAudio: dev.qoralo.podcast.runtime.AudioAvailability? = null, onOpenAudio: (() -> Unit)? = null) {
    val failed = episode?.phase == EpisodePhase.FAILED
    val restore = onReturnToDraft?.takeIf { dev.qoralo.podcast.data.canReturnToSavedDraft(episode, job) }
    PhoneContent {
        Scaffold(topBar = {
            // Let wrapped large-font titles determine height instead of clipping inside the
            // fixed-height small TopAppBar. This bar alone owns the status-bar inset.
            Surface(color = MaterialTheme.colorScheme.surface) {
                Row(Modifier.fillMaxWidth().statusBarsPadding().heightIn(min = 64.dp)
                    .padding(start = 4.dp, end = 16.dp, top = 8.dp, bottom = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = onClose) { Icon(Icons.Default.Close, "Return to library") }
                    Text(if (failed) "Episode stopped" else "Creating episode", style = MaterialTheme.typography.titleLarge,
                        softWrap = true, modifier = Modifier.weight(1f))
                }
            }
        }) { padding ->
            LazyColumn(
                Modifier.fillMaxSize().padding(padding),
                contentPadding = PaddingValues(horizontal = 24.dp, vertical = 20.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                item {
                    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
                        if (failed) FailurePanel(episode, onClose, restore) else GenerationPanel(episode, job)
                        if (availableAudio?.canListen == true && onOpenAudio != null) {
                            Text("${formatDuration(availableAudio.availableMs)} of audio available", style = MaterialTheme.typography.titleMedium,
                                textAlign = TextAlign.Center, modifier = Modifier.padding(top = 20.dp))
                            Text(if (failed) "Generation stopped. You can listen to the completed portion; export is unavailable."
                                else "You can listen now. Playback will wait if it catches up with generation.",
                                style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.Center, modifier = Modifier.padding(top = 6.dp))
                            PrimaryAction("Listen", onOpenAudio, modifier = Modifier.padding(top = 12.dp))
                            Text("Opens the player paused. Press Play when you are ready.", style = MaterialTheme.typography.bodySmall,
                                textAlign = TextAlign.Center, modifier = Modifier.padding(top = 6.dp))
                        }
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
private fun FailurePanel(episode: EpisodeEntity, onClose: () -> Unit, onReturnToDraft: (() -> Unit)?) {
    Surface(color = MaterialTheme.colorScheme.errorContainer, shape = RoundedCornerShape(28.dp), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(Icons.Default.ErrorOutline, null, modifier = Modifier.size(48.dp), tint = MaterialTheme.colorScheme.error)
            Text(if (onReturnToDraft != null) "The chat edit couldn’t finish" else "Generation couldn’t finish", style = MaterialTheme.typography.headlineSmall, textAlign = TextAlign.Center, modifier = Modifier.padding(top = 16.dp))
            Text(
                episode.failureMessage ?: "The selected on-device runtime stopped.",
                style = MaterialTheme.typography.bodyMedium,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 10.dp),
            )
            Text(
                if (dev.qoralo.podcast.runtime.ProviderAudioPlan.selected && episode.lockedRevisionId != null)
                    "This voice uses provider sentence segments. No alternate model, CPU fallback, script rewriting or forced duration was attempted."
                else "No alternate model, CPU fallback, or hidden chapter splitting was attempted.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onErrorContainer,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 12.dp),
            )
            if (onReturnToDraft != null) {
                Text("Your saved script is still intact. Return to it without retrying generation or deleting the failed chat request.",
                    style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.Center, modifier = Modifier.padding(top = 16.dp))
                PrimaryAction("Return to saved draft", onReturnToDraft, modifier = Modifier.padding(top = 16.dp))
            }
            PrimaryAction("Return to library", onClose, modifier = Modifier.padding(top = 22.dp))
        }
    }
}
