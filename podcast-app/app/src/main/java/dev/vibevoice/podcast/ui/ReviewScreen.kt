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
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import dev.vibevoice.podcast.data.AgentMessageEntity
import dev.vibevoice.podcast.data.AgentRole
import dev.vibevoice.podcast.data.ChapterEntity
import dev.vibevoice.podcast.data.GenerationJobEntity
import dev.vibevoice.podcast.data.JobKind
import dev.vibevoice.podcast.data.JobStatus

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReviewScreen(
    chapters: List<ChapterEntity>,
    messages: List<AgentMessageEntity>,
    job: GenerationJobEntity?,
    agentOpen: Boolean,
    lockOpen: Boolean,
    onBack: () -> Unit,
    onOpenAgent: () -> Unit,
    onCloseAgent: () -> Unit,
    onRequestEdit: (String) -> Unit,
    onShowLock: () -> Unit,
    onDismissLock: () -> Unit,
    onLock: () -> Unit,
) {
    var expanded by remember(chapters) { mutableStateOf(setOf(chapters.firstOrNull()?.stableChapterId).filterNotNull().toSet()) }
    PhoneContent {
        Scaffold(
            topBar = { TopAppBar(title = { Text("Review script") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back to library") } }) },
            floatingActionButton = {
                ExtendedFloatingActionButton(
                    onClick = onOpenAgent,
                    icon = { Icon(Icons.Default.AutoAwesome, null) },
                    text = { Text("Edit with agent") },
                    containerColor = MaterialTheme.colorScheme.tertiaryContainer,
                    modifier = Modifier.navigationBarsPadding().padding(bottom = 64.dp),
                )
            },
            bottomBar = {
                Surface(color = MaterialTheme.colorScheme.surfaceContainer, tonalElevation = 3.dp) {
                    Button(onClick = onShowLock, modifier = Modifier.fillMaxWidth().navigationBarsPadding().padding(16.dp).height(52.dp)) {
                        Icon(Icons.Default.Lock, null); Text("Lock script & create audio", Modifier.padding(start = 8.dp))
                    }
                }
            },
        ) { padding ->
            LazyColumn(
                Modifier.fillMaxSize().padding(padding),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                item {
                    Surface(color = MaterialTheme.colorScheme.secondaryContainer, shape = RoundedCornerShape(14.dp), modifier = Modifier.fillMaxWidth()) {
                        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text("Draft", fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                            Text("${chapters.size} chapters")
                        }
                    }
                }
                items(chapters, key = { it.rowId }) { chapter ->
                    val open = chapter.stableChapterId in expanded
                    Card(
                        shape = RoundedCornerShape(20.dp),
                        colors = CardDefaults.cardColors(containerColor = if (open) MaterialTheme.colorScheme.surfaceContainerLowest else MaterialTheme.colorScheme.surfaceContainerLow),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Row(
                            Modifier.fillMaxWidth().clickable {
                                expanded = if (open) expanded - chapter.stableChapterId else expanded + chapter.stableChapterId
                            }.padding(14.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = RoundedCornerShape(10.dp), modifier = Modifier.size(36.dp)) {
                                Box(contentAlignment = Alignment.Center) { Text("${chapter.position + 1}", fontWeight = FontWeight.Bold) }
                            }
                            Column(Modifier.weight(1f).padding(horizontal = 12.dp)) {
                                Text(chapter.title, style = MaterialTheme.typography.titleSmall)
                                Text("About ${((chapter.approximateDurationSeconds + 30) / 60).coerceAtLeast(1)} min", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            Icon(if (open) Icons.Default.ExpandLess else Icons.Default.ExpandMore, if (open) "Collapse chapter" else "Expand chapter")
                        }
                        if (open) {
                            HorizontalDivider(Modifier.padding(horizontal = 14.dp))
                            Text(chapter.text, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(16.dp))
                        }
                    }
                }
                item { Spacer(Modifier.height(88.dp)) }
            }
        }
    }

    if (agentOpen) AgentEditorSheet(messages, job, onCloseAgent, onRequestEdit)
    if (lockOpen) AlertDialog(
        onDismissRequest = onDismissLock,
        icon = { Icon(Icons.Default.Lock, null, tint = MaterialTheme.colorScheme.tertiary) },
        title = { Text("Ready to create audio?") },
        text = { Text("These ${chapters.size} chapters can’t be changed once audio generation starts.") },
        confirmButton = { Button(onClick = onLock) { Text("Lock & create") } },
        dismissButton = { TextButton(onClick = onDismissLock) { Text("Cancel") } },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AgentEditorSheet(
    messages: List<AgentMessageEntity>,
    job: GenerationJobEntity?,
    onClose: () -> Unit,
    onRequest: (String) -> Unit,
) {
    var request by remember { mutableStateOf("") }
    val working = job?.kind == JobKind.AGENT_EDIT && job.status in setOf(JobStatus.QUEUED, JobStatus.RUNNING)
    ModalBottomSheet(onDismissRequest = onClose, modifier = Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp).navigationBarsPadding()) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text("Edit the script", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                IconButton(onClick = onClose) { Icon(Icons.Default.Close, "Close agent editor") }
            }
            Text("I can rewrite, shorten, remove, split, combine, or rename chapters.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            LazyColumn(
                modifier = Modifier.fillMaxWidth().weight(1f).padding(top = 16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                if (messages.isEmpty()) item { AgentBubble("What should I change?", false) }
                items(messages, key = { it.id }) { message -> AgentBubble(message.text, message.role == AgentRole.USER) }
                if (working) item { LinearProgressIndicator(Modifier.fillMaxWidth()); Text(job.statusText, style = MaterialTheme.typography.labelMedium) }
                val changed = messages.lastOrNull { it.role == AgentRole.AGENT && it.resultRevisionId != null }
                if (changed != null) item {
                    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer), shape = RoundedCornerShape(16.dp)) {
                        Column(Modifier.padding(14.dp)) {
                            Text("Changes ready", fontWeight = FontWeight.Bold)
                            Text(changed.text, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 4.dp))
                            TextButton(onClick = onClose) { Text("Review changes") }
                        }
                    }
                }
            }
            OutlinedTextField(
                value = request,
                onValueChange = { request = it },
                enabled = !working,
                placeholder = { Text("Ask for a change…") },
                trailingIcon = {
                    IconButton(onClick = { onRequest(request); request = "" }, enabled = request.isNotBlank() && !working) {
                        Icon(Icons.AutoMirrored.Filled.Send, "Send change request")
                    }
                },
                modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp),
                shape = RoundedCornerShape(28.dp),
            )
        }
    }
}

@Composable
private fun AgentBubble(text: String, user: Boolean) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = if (user) Arrangement.End else Arrangement.Start) {
        Surface(
            color = if (user) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceContainerHighest,
            contentColor = if (user) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface,
            shape = RoundedCornerShape(18.dp),
            modifier = Modifier.fillMaxWidth(.84f),
        ) { Text(text, Modifier.padding(12.dp), style = MaterialTheme.typography.bodyMedium) }
    }
}
