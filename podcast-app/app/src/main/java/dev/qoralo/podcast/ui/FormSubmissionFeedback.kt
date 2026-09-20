package dev.qoralo.podcast.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp

@Composable
internal fun FormSubmissionFeedback(feedback: SubmissionFeedback, rejected: String, retained: String, acceptedOlder: String) {
    Surface(color = if (feedback.accepted) MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.errorContainer,
        shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth().semantics { liveRegion = LiveRegionMode.Polite }) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(if (feedback.accepted) acceptedOlder else if (feedback.newerInput) "Previous submission failed" else rejected, style = MaterialTheme.typography.titleSmall)
            if (!feedback.accepted) {
                Text(feedback.detail.orEmpty(), style = MaterialTheme.typography.bodySmall)
                Text(if (feedback.newerInput) "Your newer text is kept and hasn’t been submitted." else retained, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
