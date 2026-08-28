package dev.vibevoice.podcast.ui

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
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import dev.vibevoice.podcast.data.EpisodeEntity
import dev.vibevoice.podcast.data.EpisodePhase

@Composable
fun LibraryScreen(
    episodes: List<EpisodeEntity>,
    onNew: () -> Unit,
    onOpen: (EpisodeEntity) -> Unit,
    onSettings: () -> Unit,
) {
    val ready = episodes.filter { it.phase == EpisodePhase.FROZEN_READY }
    val hero = ready.firstOrNull()
    PhoneContent {
        Scaffold(
            bottomBar = {
                NavigationBar {
                    NavigationBarItem(
                        selected = true,
                        onClick = {},
                        icon = { Icon(Icons.AutoMirrored.Filled.LibraryBooks, contentDescription = "Library") },
                        label = { Text("Library", maxLines = 1) },
                    )
                    Box(Modifier.weight(1.25f), contentAlignment = Alignment.Center) {
                        ExtendedFloatingActionButton(
                            text = { Text("New episode", maxLines = 1) },
                            icon = { Icon(Icons.Default.Add, contentDescription = null) },
                            onClick = onNew,
                            containerColor = MaterialTheme.colorScheme.primaryContainer,
                        )
                    }
                    NavigationBarItem(
                        selected = false,
                        onClick = onSettings,
                        icon = { Icon(Icons.Default.Settings, contentDescription = "Settings") },
                        label = { Text("Settings", maxLines = 1) },
                    )
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
                if (hero != null) {
                    item { ContinueCard(hero, onOpen) }
                    item { Text("Recent episodes", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 8.dp)) }
                    items(ready.drop(1), key = { it.id }) { EpisodeRow(it, onOpen) }
                } else {
                    item {
                        EmptyLibrary(onNew)
                    }
                }
            }
        }
    }
}

@Composable
private fun ContinueCard(episode: EpisodeEntity, onOpen: (EpisodeEntity) -> Unit) {
    Surface(
        color = MaterialTheme.colorScheme.primaryContainer,
        shape = RoundedCornerShape(28.dp),
        modifier = Modifier.fillMaxWidth().clickable(onClick = { onOpen(episode) }).semantics { role = Role.Button },
    ) {
        Row(Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            VibeArtwork(Modifier.size(width = 116.dp, height = 148.dp), compact = true)
            Column(Modifier.weight(1f)) {
                Text("CONTINUE LISTENING", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                Text(episode.title, style = MaterialTheme.typography.titleLarge, maxLines = 3, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 4.dp))
                Text("${episode.durationMs?.let(::formatDuration) ?: "Ready"}", style = MaterialTheme.typography.labelMedium, modifier = Modifier.padding(top = 6.dp))
                Spacer(Modifier.weight(1f))
                LinearProgressIndicator(progress = { 0f }, modifier = Modifier.fillMaxWidth())
                Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("Start listening", style = MaterialTheme.typography.labelMedium, modifier = Modifier.weight(1f))
                    Surface(shape = CircleShape, color = MaterialTheme.colorScheme.primary, modifier = Modifier.size(40.dp)) {
                        Box(contentAlignment = Alignment.Center) { Icon(Icons.Default.PlayArrow, "Play ${episode.title}", tint = MaterialTheme.colorScheme.onPrimary) }
                    }
                }
            }
        }
    }
}

@Composable
private fun EpisodeRow(episode: EpisodeEntity, onOpen: (EpisodeEntity) -> Unit) {
    Surface(
        color = MaterialTheme.colorScheme.surfaceContainerLow,
        shape = RoundedCornerShape(20.dp),
        modifier = Modifier.fillMaxWidth().clickable { onOpen(episode) },
    ) {
        Row(Modifier.padding(10.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            VibeArtwork(Modifier.size(60.dp), compact = true)
            Column(Modifier.weight(1f)) {
                Text(episode.title, style = MaterialTheme.typography.titleSmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                Text(episode.durationMs?.let(::formatDuration) ?: "Ready", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            IconButton(onClick = { onOpen(episode) }) { Icon(Icons.Default.PlayArrow, "Play") }
        }
    }
}

@Composable
private fun EmptyLibrary(onNew: () -> Unit) {
    Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = RoundedCornerShape(28.dp), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(28.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            VibeArtwork(Modifier.fillMaxWidth().height(210.dp), compact = true)
            Text("Turn your sources into an episode", style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(top = 24.dp))
            Text("Everything stays on this device.", color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 8.dp))
            ExtendedFloatingActionButton(onClick = onNew, icon = { Icon(Icons.Default.Add, null) }, text = { Text("Create an episode") }, modifier = Modifier.padding(top = 24.dp))
        }
    }
}
