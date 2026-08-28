package dev.vibevoice.podcast.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import java.util.Locale

@Composable
fun PhoneContent(content: @Composable () -> Unit) {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.TopCenter) {
        Box(Modifier.fillMaxSize().widthIn(max = 600.dp)) { content() }
    }
}

@Composable
fun VibeArtwork(
    modifier: Modifier = Modifier,
    title: String? = null,
    compact: Boolean = false,
) {
    Box(
        modifier.clip(RoundedCornerShape(if (compact) 16.dp else 28.dp))
            .semantics { contentDescription = "Abstract episode artwork" },
    ) {
        Canvas(Modifier.fillMaxSize()) {
            drawRect(Color(0xFFC4AFE9))
            drawCircle(Color(0xFFFF9EB8), radius = size.minDimension * .46f, center = Offset(size.width * .9f, size.height * .08f))
            rotate(-16f, pivot = Offset(size.width * .34f, size.height * .72f)) {
                drawOval(
                    color = Color(0xFF4B3B72),
                    topLeft = Offset(-size.width * .25f, size.height * .54f),
                    size = Size(size.width * 1.15f, size.height * .38f),
                    style = Stroke(width = size.minDimension * .10f),
                )
            }
        }
        if (title != null && !compact) {
            Text(
                title,
                style = MaterialTheme.typography.headlineMedium,
                color = Color(0xFF211047),
                maxLines = 3,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.align(Alignment.BottomStart).padding(24.dp),
            )
        }
    }
}

@Composable
fun WizardProgress(step: Int, modifier: Modifier = Modifier) {
    Row(modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        StepLine(active = step >= 1)
        StepLine(active = step >= 2)
    }
}

@Composable
private fun RowScope.StepLine(active: Boolean) {
    Surface(
        color = if (active) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceContainerHighest,
        shape = RoundedCornerShape(8.dp),
        modifier = Modifier.weight(1f).padding(horizontal = 3.dp).height(4.dp),
        content = {},
    )
}

fun formatDuration(milliseconds: Long): String {
    val seconds = (milliseconds.coerceAtLeast(0) / 1_000)
    return String.format(Locale.US, "%02d:%02d", seconds / 60, seconds % 60)
}
