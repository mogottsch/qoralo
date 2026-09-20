package dev.qoralo.podcast.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import dev.qoralo.podcast.runtime.AudioAvailabilityState

/** Both player surfaces derive intent from the same session; buffering is not a user pause. */
data class MiniPlayerPresentation(val status: String, val pauseAction: Boolean, val controlsEnabled: Boolean) {
    companion object {
        fun from(isPlaying: Boolean, wantsPlayback: Boolean, waiting: Boolean, state: AudioAvailabilityState?, error: String?, atEnd: Boolean): MiniPlayerPresentation {
            val enabled = state != AudioAvailabilityState.STALE
            return MiniPlayerPresentation(when {
                error != null -> error
                !enabled -> "Audio attempt changed"
                waiting -> "Buffering · waiting for more audio"
                isPlaying -> "Playing"
                wantsPlayback -> "Buffering"
                atEnd && state == AudioAvailabilityState.GENERATING -> "Paused · more audio is generating"
                atEnd && state == AudioAvailabilityState.FAILED -> "End of available audio"
                atEnd -> "Finished"
                else -> "Paused"
            }, enabled && (isPlaying || wantsPlayback), enabled)
        }
    }
}

/** Persistent top surface only: owns no player, timeline, coroutine, or playback lifecycle. */
@Composable
fun MiniPlayer(title: String, session: EpisodePlayerSession, onOpen: () -> Unit, modifier: Modifier = Modifier) {
    val presentation = MiniPlayerPresentation.from(session.isPlaying, session.wantsPlayback, session.waiting,
        session.streamState, session.error, session.durationMs > 0 && session.positionMs >= session.durationMs)
    val largeText = LocalDensity.current.fontScale >= 1.4f
    Surface(color = MaterialTheme.colorScheme.primaryContainer, modifier = modifier.fillMaxWidth()) {
        Column(Modifier.padding(horizontal = 12.dp, vertical = 4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Column(Modifier.weight(1f).heightIn(min = 48.dp)
                    .clickable(role = Role.Button, onClickLabel = "Open player", onClick = onOpen)
                    .semantics { contentDescription = "Open player: $title" }
                    .padding(vertical = 6.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(title, style = MaterialTheme.typography.titleSmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                    Text(presentation.status, style = MaterialTheme.typography.labelSmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                    if (!largeText) Text("${formatDuration(session.positionMs)} · ${session.speed}×", style = MaterialTheme.typography.labelSmall)
                }
                if (!largeText) MiniPlayerControls(session, presentation)
            }
            if (largeText) Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("${formatDuration(session.positionMs)} · ${session.speed}×", style = MaterialTheme.typography.labelSmall, modifier = Modifier.weight(1f))
                MiniPlayerControls(session, presentation)
            }
        }
    }
}

@Composable
private fun RowScope.MiniPlayerControls(session: EpisodePlayerSession, presentation: MiniPlayerPresentation) {
    // A labeled text control matches the full player's 15-second action (no misleading 10s icon).
    TextButton(enabled = presentation.controlsEnabled && session.positionMs > 0,
        onClick = { session.seek((session.positionMs - 15_000L).coerceAtLeast(0)) },
        contentPadding = PaddingValues(horizontal = 8.dp),
        modifier = Modifier.widthIn(min = 48.dp).heightIn(min = 48.dp).semantics { contentDescription = "Back 15 seconds" }) { Text("−15") }
    FilledIconButton(enabled = presentation.controlsEnabled, onClick = session::togglePlay, modifier = Modifier.size(48.dp)) {
        Icon(if (presentation.pauseAction) Icons.Default.Pause else Icons.Default.PlayArrow,
            if (presentation.pauseAction) "Pause" else "Play")
    }
}
