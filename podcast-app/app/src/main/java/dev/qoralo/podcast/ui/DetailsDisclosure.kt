package dev.qoralo.podcast.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.dp

/** Secondary explanations stay available without interrupting the main task. */
@Composable
internal fun DetailsDisclosure(title: String, identity: Any? = title, content: @Composable () -> Unit) {
    var expanded by rememberSaveable(identity) { mutableStateOf(false) }
    Column(Modifier.fillMaxWidth()) {
        TextButton(onClick = { expanded = !expanded }, contentPadding = PaddingValues(horizontal = 0.dp),
            modifier = Modifier.heightIn(min = 48.dp).semantics { stateDescription = if (expanded) "Expanded" else "Collapsed" }) {
            Text(title, Modifier.weight(1f), softWrap = true)
            Icon(if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore, null)
        }
        if (expanded) Column(Modifier.fillMaxWidth().padding(bottom = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            ProvideTextStyle(MaterialTheme.typography.bodySmall) { content() }
        }
    }
}
