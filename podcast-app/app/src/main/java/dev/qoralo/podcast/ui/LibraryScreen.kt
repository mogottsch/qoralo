package dev.qoralo.podcast.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.LibraryBooks
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import dev.qoralo.podcast.data.EpisodeEntity
import dev.qoralo.podcast.data.EpisodePhase
import dev.qoralo.podcast.data.PlaybackStateEntity

@Composable
fun LibraryScreen(
    episodes: List<EpisodeEntity>,
    onNew: () -> Unit,
    onOpen: (EpisodeEntity) -> Unit,
    onSettings: () -> Unit,
    playbackStates: List<PlaybackStateEntity> = emptyList(),
    chapterCounts: Map<String, Int> = emptyMap(),
    episodeActions: @Composable (EpisodeEntity) -> Unit = {},
) {
    val ready = episodes.filter { it.phase == EpisodePhase.FROZEN_READY }
    val resume = playbackStates.sortedByDescending { it.updatedAtEpochMs }.firstOrNull { state ->
        ready.any { it.id == state.episodeId && state.positionMs > 0 && state.positionMs < (it.durationMs ?: Long.MAX_VALUE) }
    }
    val hero = ready.firstOrNull { it.id == resume?.episodeId } ?: ready.firstOrNull()
    val recent = ready.filter { it.id != hero?.id }
    val unfinished = episodes.filter { it.phase != EpisodePhase.FROZEN_READY }
    val stackedAction = LocalDensity.current.fontScale >= 1.4f || LocalConfiguration.current.screenWidthDp < 360
    PhoneContent {
        Scaffold(
            bottomBar = {
                Surface(color = MaterialTheme.colorScheme.surfaceContainer) {
                    Column {
                        if (stackedAction) PrimaryAction("New episode", onNew, icon = Icons.Default.Add,
                            modifier = Modifier.padding(horizontal = 20.dp, vertical = 8.dp))
                        NavigationBar {
                            NavigationBarItem(
                                selected = true, onClick = {},
                                icon = { Icon(Icons.AutoMirrored.Filled.LibraryBooks, contentDescription = null) },
                                label = { Text("Library") },
                            )
                            // Measure the full label intrinsically; do not force a weighted narrow box.
                            if (!stackedAction) ExtendedFloatingActionButton(
                                text = { Text("New episode") },
                                // Material3 clears the animated text's semantics; the icon must name the action.
                                icon = { Icon(Icons.Default.Add, contentDescription = "New episode") },
                                onClick = onNew,
                                containerColor = MaterialTheme.colorScheme.primaryContainer,
                            )
                            NavigationBarItem(
                                selected = false, onClick = onSettings,
                                icon = { Icon(Icons.Default.Settings, contentDescription = null) },
                                label = { Text("Settings") },
                            )
                        }
                    }
                }
            },
        ) { padding ->
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentPadding = PaddingValues(horizontal = 20.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                item {
                    Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text("Library", style = MaterialTheme.typography.headlineMedium, modifier = Modifier.weight(1f))
                        Surface(shape = CircleShape, color = MaterialTheme.colorScheme.primaryContainer, modifier = Modifier.size(44.dp)) {
                            Box(contentAlignment = Alignment.Center) { Text("M", fontWeight = FontWeight.Bold) }
                        }
                    }
                }
                if (hero != null) item { ContinueCard(hero, playbackStates.firstOrNull { it.episodeId == hero.id }, chapterCounts[hero.id], onOpen, episodeActions) }
                if (unfinished.isNotEmpty()) {
                    item { Text("Continue creating", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 8.dp)) }
                    items(unfinished, key = { it.id }) { EpisodeStatusRow(it, onOpen, episodeActions) }
                }
                if (recent.isNotEmpty()) {
                    item { Text("Recent episodes", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 8.dp)) }
                    items(recent, key = { it.id }) { EpisodeRow(it, chapterCounts[it.id], onOpen, episodeActions) }
                }
                if (episodes.isEmpty()) item { EmptyLibrary(onNew) }
            }
        }
    }
}

@Composable
private fun ContinueCard(episode: EpisodeEntity, playback: PlaybackStateEntity?, chapterCount: Int?, onOpen: (EpisodeEntity) -> Unit, actions: @Composable (EpisodeEntity) -> Unit) {
    val position = playback?.positionMs?.coerceIn(0, episode.durationMs ?: Long.MAX_VALUE) ?: 0L
    val finished = episode.durationMs?.let { it > 0 && position >= it } ?: false
    val stacked = LocalDensity.current.fontScale >= 1.4f || LocalConfiguration.current.screenWidthDp < 360
    Surface(
        color = MaterialTheme.colorScheme.primaryContainer,
        shape = RoundedCornerShape(28.dp),
        modifier = Modifier.fillMaxWidth().clickable(onClick = { onOpen(episode) }).semantics { role = Role.Button },
    ) {
        if (stacked) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                VibeArtwork(Modifier.fillMaxWidth().height(72.dp), compact = true)
                ContinueDetails(episode, position, finished, chapterCount, actions)
            }
        } else {
            Row(Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                VibeArtwork(Modifier.size(width = 116.dp, height = 148.dp), compact = true)
                ContinueDetails(episode, position, finished, chapterCount, actions, Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun ContinueDetails(episode: EpisodeEntity, position: Long, finished: Boolean, chapterCount: Int?, actions: @Composable (EpisodeEntity) -> Unit, modifier: Modifier = Modifier) {
    Column(modifier) {
        Text(if (finished) "FINISHED" else if (position > 0) "CONTINUE LISTENING" else "READY TO LISTEN", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
        Text(episode.title, style = MaterialTheme.typography.titleLarge, maxLines = 3, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 4.dp))
        Text(listOfNotNull(chapterCount?.takeIf { it > 0 }?.let { "$it chapters" }, episode.durationMs?.let(::formatDuration)).joinToString(" · "), style = MaterialTheme.typography.labelMedium, modifier = Modifier.padding(top = 6.dp))
        Spacer(Modifier.height(12.dp))
        LinearProgressIndicator(progress = { (position.toFloat() / (episode.durationMs ?: 1L).coerceAtLeast(1)).coerceIn(0f, 1f) }, modifier = Modifier.fillMaxWidth())
        Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(if (finished) "Play again" else if (position > 0) "Resume at ${formatDuration(position)}" else "Start listening", style = MaterialTheme.typography.labelMedium, modifier = Modifier.weight(1f))
            Surface(shape = CircleShape, color = MaterialTheme.colorScheme.primary, modifier = Modifier.size(40.dp)) {
                Box(contentAlignment = Alignment.Center) { Icon(Icons.Default.PlayArrow, "Play ${episode.title}", tint = MaterialTheme.colorScheme.onPrimary) }
            }
            actions(episode)
        }
    }
}

@Composable
private fun EpisodeRow(episode: EpisodeEntity, chapterCount: Int?, onOpen: (EpisodeEntity) -> Unit, actions: @Composable (EpisodeEntity) -> Unit) {
    Surface(
        color = MaterialTheme.colorScheme.surfaceContainerLow,
        shape = RoundedCornerShape(20.dp),
        modifier = Modifier.fillMaxWidth().clickable { onOpen(episode) },
    ) {
        Row(Modifier.padding(10.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            VibeArtwork(Modifier.size(60.dp), compact = true)
            Column(Modifier.weight(1f)) {
                Text(episode.title, style = MaterialTheme.typography.titleSmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                Text(listOfNotNull(chapterCount?.takeIf { it > 0 }?.let { "$it chapters" }, episode.durationMs?.let(::formatDuration)).joinToString(" · "), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            IconButton(onClick = { onOpen(episode) }) { Icon(Icons.Default.PlayArrow, "Play") }
            actions(episode)
        }
    }
}

@Composable
private fun EpisodeStatusRow(episode: EpisodeEntity, onOpen: (EpisodeEntity) -> Unit, actions: @Composable (EpisodeEntity) -> Unit) {
    val status = when (episode.phase) {
        EpisodePhase.SOURCES -> "Add sources"
        EpisodePhase.INSTRUCTIONS -> "Add instructions"
        EpisodePhase.GENERATING_SCRIPT -> "Creating script"
        EpisodePhase.SCRIPT_DRAFT -> "Draft ready"
        EpisodePhase.LOCKED -> "Audio queued"
        EpisodePhase.GENERATING_AUDIO -> "Creating audio"
        EpisodePhase.FAILED -> "Generation stopped"
        "DELETING" -> "Deletion pending"
        else -> episode.phase.lowercase().replace('_', ' ')
    }
    Surface(
        color = if (episode.phase == EpisodePhase.FAILED) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.surfaceContainerLow,
        shape = RoundedCornerShape(20.dp),
        modifier = Modifier.fillMaxWidth().clickable(enabled = episode.phase != "DELETING") { onOpen(episode) },
    ) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            VibeArtwork(Modifier.size(56.dp), compact = true)
            Column(Modifier.weight(1f)) {
                Text(episode.title, style = MaterialTheme.typography.titleSmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                Text(status, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            actions(episode)
            if (episode.phase != "DELETING") Text("›", style = MaterialTheme.typography.titleLarge)
        }
    }
}

@Composable
private fun EmptyLibrary(onNew: () -> Unit) {
    val largeText = LocalDensity.current.fontScale >= 1.4f
    Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = RoundedCornerShape(28.dp), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            VibeArtwork(Modifier.fillMaxWidth().height(if (largeText) 96.dp else 180.dp), compact = true)
            Text("Your first episode", style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(top = 20.dp))
            Text("Everything stays on this device.", color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 8.dp))
            PrimaryAction("Create an episode", onNew, modifier = Modifier.padding(top = 20.dp))
        }
    }
}
