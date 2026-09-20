package dev.qoralo.podcast.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import dev.qoralo.podcast.data.EpisodeEntity

@Composable
internal fun EpisodeOverflow(episode: EpisodeEntity, onDiagnostics: ((EpisodeEntity) -> Unit)?, onDelete: ((EpisodeEntity) -> Unit)?) {
    if (onDiagnostics == null && onDelete == null) return
    var expanded by remember(episode.id) { mutableStateOf(false) }
    Box {
        IconButton(onClick = { expanded = true }) { Icon(Icons.Default.MoreVert, "Episode actions: ${episode.title}") }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            if (onDiagnostics != null) DropdownMenuItem(text = { Text("Episode details") }, enabled = episode.phase != "DELETING",
                onClick = { expanded = false; onDiagnostics(episode) })
            if (onDelete != null) DropdownMenuItem(text = { Text(if (episode.phase == "DELETING") "Deletion pending" else "Delete episode", color = MaterialTheme.colorScheme.error) },
                enabled = episode.phase != "DELETING", onClick = { expanded = false; onDelete(episode) })
        }
    }
}

data class EpisodeDeletionTarget(val id: String, val title: String)

@Composable
internal fun DeleteEpisodeConfirmation(target: EpisodeDeletionTarget, busy: Boolean, error: String?, onCancel: () -> Unit, onDelete: () -> Unit) {
    AlertDialog(
        onDismissRequest = { if (!busy) onCancel() },
        title = { Text("Delete episode?") },
        text = {
            Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(target.title, style = MaterialTheme.typography.titleMedium)
                Text("This removes this episode's draft, audio, history and diagnostics from this device. It cannot be undone.")
                Text("If generation is running, it will be cancelled. Deletion waits until the worker and player have released their files. Other episodes, shared sources, model packs and exported copies stay unchanged.")
                if (busy) Text("Requesting deletion…")
                if (error != null) Text(error, color = MaterialTheme.colorScheme.error)
            }
        },
        confirmButton = { TextButton(enabled = !busy, onClick = onDelete, colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error)) { Text("Delete episode") } },
        dismissButton = { TextButton(enabled = !busy, onClick = onCancel) { Text("Keep episode") } },
    )
}
