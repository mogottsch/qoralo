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
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
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
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.rememberModalBottomSheetState
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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.rememberCoroutineScope
import kotlinx.coroutines.launch
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
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
    onRequestEdit: suspend (String) -> Unit,
    onShowLock: () -> Unit,
    onDismissLock: () -> Unit,
    onLock: () -> Unit,
) {
    var expanded by remember(chapters) { mutableStateOf(setOf(chapters.firstOrNull()?.stableChapterId).filterNotNull().toSet()) }
    PhoneContent {
        Scaffold(
            topBar = { TopAppBar(title = { Text("Review script") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back to library") } }) },
            bottomBar = {
                Surface(color = MaterialTheme.colorScheme.surfaceContainer, tonalElevation = 3.dp) {
                    Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        FilledTonalButton(onClick = onOpenAgent, modifier = Modifier.align(Alignment.End).heightIn(min = 48.dp)) {
                            Icon(Icons.Default.AutoAwesome, null)
                            Text("Edit with agent", Modifier.padding(start = 8.dp), softWrap = true)
                        }
                        PrimaryAction("Lock script & create audio", onShowLock, icon = Icons.Default.Lock)
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
internal fun AgentEditorSheet(
    messages: List<AgentMessageEntity>,
    job: GenerationJobEntity?,
    onClose: () -> Unit,
    onRequest: suspend (String) -> Unit,
) {
    var request by rememberSaveable { mutableStateOf("") }
    val submission = rememberFormSubmission()
    val scope = rememberCoroutineScope()
    val history = rememberLazyListState()
    val close = { submission.dispose(); onClose() }
    LaunchedEffect(submission.feedback) { if (submission.feedback != null) history.scrollToItem(0) }
    val working = job?.kind == JobKind.AGENT_EDIT && job.status in setOf(JobStatus.QUEUED, JobStatus.RUNNING)
    ModalBottomSheet(onDismissRequest = close, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true), modifier = Modifier.fillMaxSize()) {
        val focus = LocalFocusManager.current
        val keyboard = LocalSoftwareKeyboardController.current
        Column(Modifier.fillMaxSize().padding(horizontal = 16.dp).navigationBarsPadding().imePadding()) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text("Edit the script", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                IconButton(onClick = close) { Icon(Icons.Default.Close, "Close agent editor") }
            }
            Text("I can rewrite, shorten, remove, split, combine, or rename chapters.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            LazyColumn(
                modifier = Modifier.fillMaxWidth().weight(1f).padding(top = 16.dp),
                state = history,
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                submission.feedback?.let { feedback -> item {
                    FormSubmissionFeedback(feedback, "Request wasn’t sent", "Your request is still here.", "Previous request sent. Newer text hasn’t been sent.")
                } }
                if (job?.kind == JobKind.AGENT_EDIT && job.status == JobStatus.FAILED) item {
                    Surface(color = MaterialTheme.colorScheme.errorContainer, shape = RoundedCornerShape(16.dp)) {
                        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text("Change wasn’t applied", style = MaterialTheme.typography.titleSmall)
                            Text(job.errorMessage ?: "The editing request could not finish.", style = MaterialTheme.typography.bodyMedium)
                            Text("Your draft is unchanged.", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
                if (messages.isEmpty()) item { AgentBubble("What should I change?", false) }
                items(messages, key = { it.id }) { message -> AgentBubble(message.text, message.role == AgentRole.USER) }
                if (working) item { LinearProgressIndicator(Modifier.fillMaxWidth()); Text(job.statusText, style = MaterialTheme.typography.labelMedium) }
                val changed = messages.lastOrNull { it.role == AgentRole.AGENT && it.resultRevisionId != null }
                if (changed != null && job?.status != JobStatus.FAILED && submission.feedback?.accepted != false) item {
                    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer), shape = RoundedCornerShape(16.dp)) {
                        Column(Modifier.padding(14.dp)) {
                            Text("Changes ready", fontWeight = FontWeight.Bold)
                            Text(changed.text, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 4.dp))
                            TextButton(onClick = close) { Text("Review changes") }
                        }
                    }
                }
            }
            OutlinedTextField(
                value = request,
                onValueChange = { request = it; submission.edited() },
                enabled = !working,
                minLines = 1,
                maxLines = 4,
                placeholder = { Text("Ask for a change…") },
                supportingText = if (submission.submitting) { { Text("Sending request…") } } else null,
                trailingIcon = {
                    IconButton(onClick = {
                        val ticket = submission.begin()
                        if (ticket != null) {
                            val submittedRequest = request
                            val submit = onRequest
                            scope.launch {
                                when (submission.await(ticket) { submit(submittedRequest) }) {
                                    SubmissionCompletion.ACCEPTED_CURRENT -> request = ""
                                    SubmissionCompletion.REJECTED -> if (submission.feedback?.newerInput == false) { focus.clearFocus(); keyboard?.hide() }
                                    else -> Unit
                                }
                            }
                        }
                    }, enabled = request.isNotBlank() && !working && !submission.submitting) {
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
