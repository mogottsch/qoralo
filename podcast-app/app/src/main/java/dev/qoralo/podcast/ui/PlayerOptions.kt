package dev.qoralo.podcast.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ClosedCaption
import androidx.compose.material.icons.filled.Speed
import androidx.compose.material.icons.filled.Timer
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp

/** Secondary actions share equal, centered slots, without competing with the Play button. */
@Composable
internal fun PlayerOptions(
    speed: Float,
    sleepMinutes: Int?,
    onSpeedClick: () -> Unit,
    onTranscriptClick: () -> Unit,
    onSleepClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val labels = listOf("${speed}×", "Transcript", sleepMinutes?.let { "$it min" } ?: "Sleep")
    val textStyle = MaterialTheme.typography.labelLarge
    val textMeasurer = rememberTextMeasurer()
    val widestLabel = labels.maxOf { textMeasurer.measure(it, style = textStyle, softWrap = false).size.width }
    val minimumSlotWidth = with(LocalDensity.current) { widestLabel.toDp() } + 16.dp

    BoxWithConstraints(modifier.fillMaxWidth()) {
        // Reflow based on real label/font measurements, not truncation or a smaller font.
        val stacked = maxWidth < minimumSlotWidth * 3 + 16.dp
        @Composable fun Options(slotModifier: Modifier) {
            PlayerOption(labels[0], Icons.Default.Speed, onSpeedClick, stacked, slotModifier,
                active = speed != 1f, state = "Playback speed ${speed}×")
            PlayerOption(labels[1], Icons.Default.ClosedCaption, onTranscriptClick, stacked, slotModifier)
            PlayerOption(labels[2], Icons.Default.Timer, onSleepClick, stacked, slotModifier,
                active = sleepMinutes != null, state = sleepMinutes?.let { "Sleep timer: $it minutes" } ?: "Sleep timer off")
        }
        if (stacked) {
            Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Options(Modifier.fillMaxWidth())
            }
        } else {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Options(Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun PlayerOption(
    label: String,
    icon: ImageVector,
    onClick: () -> Unit,
    stacked: Boolean,
    modifier: Modifier,
    active: Boolean = false,
    state: String? = null,
) {
    TextButton(
        onClick = onClick,
        modifier = modifier.heightIn(min = if (stacked) 48.dp else 64.dp)
            .semantics { if (state != null) stateDescription = state },
        colors = ButtonDefaults.textButtonColors(
            contentColor = if (active) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
        ),
        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 8.dp),
    ) {
        if (stacked) {
            Icon(icon, contentDescription = null, modifier = Modifier.size(20.dp))
            Spacer(Modifier.width(8.dp))
            Text(label, style = MaterialTheme.typography.labelLarge)
        } else {
            Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Icon(icon, contentDescription = null, modifier = Modifier.size(20.dp))
                Text(label, style = MaterialTheme.typography.labelLarge)
            }
        }
    }
}
