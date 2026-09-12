package dev.vibevoice.podcast.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ContentPaste
import androidx.compose.material.icons.filled.Description
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import android.view.WindowManager
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import kotlinx.coroutines.launch
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.compose.ui.window.DialogWindowProvider
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import dev.vibevoice.podcast.data.EpisodeEntity
import dev.vibevoice.podcast.data.EpisodeSourceEntity

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SourcesScreen(
    sources: List<EpisodeSourceEntity>,
    onBack: () -> Unit,
    onPaste: suspend (String, String) -> Unit,
    onDocument: (android.net.Uri) -> Unit,
    onRemove: (EpisodeSourceEntity) -> Unit,
    onContinue: () -> Unit,
) {
    var pasteDialog by rememberSaveable { mutableStateOf(false) }
    val document = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let(onDocument) }
    PhoneContent {
        Scaffold(
            modifier = Modifier.imePadding(),
            topBar = { TopAppBar(title = { Text("New episode") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back to library") } }) },
            bottomBar = {
                PrimaryAction("Continue", onContinue, enabled = sources.isNotEmpty(),
                    modifier = Modifier.navigationBarsPadding().padding(horizontal = 20.dp, vertical = 12.dp))
            },
        ) { padding ->
            LazyColumn(
                Modifier.fillMaxSize().padding(padding),
                contentPadding = PaddingValues(horizontal = 20.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                item { WizardProgress(1, Modifier.padding(bottom = 18.dp)) }
                item { Text("Add sources", style = MaterialTheme.typography.displaySmall, modifier = Modifier.padding(bottom = 10.dp)) }
                item {
                    SourceChoice(Icons.Default.ContentPaste, "Paste text", "Article, notes, or anything copied") { pasteDialog = true }
                }
                item {
                    SourceChoice(Icons.Default.AttachFile, "Choose a file", "Plain text or Markdown document") {
                        document.launch(arrayOf("text/plain", "text/markdown", "application/json"))
                    }
                }
                item {
                    Row(Modifier.fillMaxWidth().padding(top = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text("Added sources", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                        TextButton(onClick = { pasteDialog = true }) { Icon(Icons.Default.Add, null); Text("Add") }
                    }
                }
                if (sources.isEmpty()) item {
                    Text("Add at least one source to continue.", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
                }
                items(sources, key = { it.id }) { source ->
                    ListItem(
                        headlineContent = { Text(source.title, maxLines = 2, overflow = TextOverflow.Ellipsis) },
                        supportingContent = { Text("${source.wordCount} words · ${source.mimeType}") },
                        leadingContent = { Icon(Icons.Default.Description, null, tint = MaterialTheme.colorScheme.tertiary) },
                        trailingContent = { IconButton(onClick = { onRemove(source) }) { Icon(Icons.Default.Close, "Remove ${source.title}") } },
                        tonalElevation = 1.dp,
                    )
                }
            }
        }
    }
    if (pasteDialog) PasteSourceDialog(onDismiss = { pasteDialog = false }, onAdd = onPaste, onAdded = { pasteDialog = false })
}

@Composable
private fun SourceChoice(icon: androidx.compose.ui.graphics.vector.ImageVector, title: String, subtitle: String, onClick: () -> Unit) {
    OutlinedButton(onClick = onClick, shape = RoundedCornerShape(18.dp), contentPadding = PaddingValues(16.dp), modifier = Modifier.fillMaxWidth()) {
        Icon(icon, null, Modifier.size(32.dp), tint = MaterialTheme.colorScheme.primary)
        Column(Modifier.weight(1f).padding(horizontal = 16.dp), horizontalAlignment = Alignment.Start) {
            Text(title, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurface)
            Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Text("›", style = MaterialTheme.typography.titleLarge)
    }
}

@Composable
internal fun PasteSourceDialog(onDismiss: () -> Unit, onAdd: suspend (String, String) -> Unit) =
    PasteSourceDialog(onDismiss, onAdd, onAdded = onDismiss)

@Composable
internal fun PasteSourceDialog(onDismiss: () -> Unit, onAdd: suspend (String, String) -> Unit, onAdded: () -> Unit) {
    var title by rememberSaveable { mutableStateOf("") }
    var text by rememberSaveable { mutableStateOf("") }
    val submission = rememberFormSubmission()
    val scope = rememberCoroutineScope()
    val bodyScroll = rememberScrollState()
    LaunchedEffect(submission.feedback) { if (submission.feedback != null) bodyScroll.scrollTo(0) }
    val dismiss = { submission.dispose(); onDismiss() }
    // Compose 1.7's custom-width DialogLayout measures against configuration height instead
    // of the incoming window constraint. Let the platform own IME resizing here; do not also
    // subtract IME/system padding in the content. Header/action are measured before the body.
    Dialog(onDismissRequest = dismiss, properties = DialogProperties(usePlatformDefaultWidth = true, decorFitsSystemWindows = true)) {
        val focus = LocalFocusManager.current
        val keyboard = LocalSoftwareKeyboardController.current
        val window = (LocalView.current.parent as? DialogWindowProvider)?.window
        DisposableEffect(window) {
            val previous = window?.attributes?.softInputMode
            if (window != null && previous != null) window.setSoftInputMode(
                (previous and WindowManager.LayoutParams.SOFT_INPUT_MASK_ADJUST.inv()) or WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE)
            onDispose { if (window != null && previous != null) window.setSoftInputMode(previous) }
        }
        val largeText = LocalDensity.current.fontScale >= 1.5f
        BoxWithConstraints(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
            Surface(shape = RoundedCornerShape(28.dp), color = MaterialTheme.colorScheme.surfaceContainerHigh,
                modifier = Modifier.fillMaxWidth().heightIn(max = maxHeight)) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text("Paste text", style = MaterialTheme.typography.headlineSmall, modifier = Modifier.weight(1f))
                        IconButton(onClick = dismiss) { Icon(Icons.Default.Close, if (submission.submitting) "Close paste" else "Cancel paste") }
                    }
                    Column(Modifier.weight(1f, fill = false).verticalScroll(bodyScroll),
                        verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        submission.feedback?.let { feedback ->
                            FormSubmissionFeedback(feedback, "Source wasn’t added", "Your text is still here.", "Previous source added. Newer text hasn’t been added.")
                        }
                        OutlinedTextField(title, { title = it; submission.edited() }, label = { Text("Source name") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                        OutlinedTextField(text, { text = it; submission.edited() }, label = { Text("Source text") }, minLines = 3,
                            maxLines = if (largeText) 3 else 8, modifier = Modifier.fillMaxWidth())
                    }
                    PrimaryAction(if (submission.submitting) "Adding source…" else "Add source", {
                        val ticket = submission.begin()
                        if (ticket != null) {
                            val submittedTitle = title
                            val submittedText = text
                            val submit = onAdd
                            val accepted = onAdded
                            scope.launch {
                                when (submission.await(ticket) { submit(submittedTitle, submittedText) }) {
                                    SubmissionCompletion.ACCEPTED_CURRENT -> { submission.dispose(); accepted() }
                                    SubmissionCompletion.REJECTED -> if (submission.feedback?.newerInput == false) { focus.clearFocus(); keyboard?.hide() }
                                    else -> Unit
                                }
                            }
                        }
                    }, enabled = text.isNotBlank() && !submission.submitting)
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun InstructionsScreen(
    episode: EpisodeEntity,
    onBack: () -> Unit,
    onCreate: (String, Boolean) -> Unit,
    onDraftChanged: (String, Boolean) -> Unit = { _, _ -> },
) {
    var instructions by rememberSaveable(episode.id) { mutableStateOf(episode.instructions) }
    var review by rememberSaveable(episode.id) { mutableStateOf(episode.reviewEnabled) }
    val largeText = LocalDensity.current.fontScale >= 1.5f
    val hints = listOf(
        "Length" to "Keep it under five minutes.",
        "Focus" to "Focus on the practical consequences.",
        "Questions to answer" to "Answer these questions: ",
        "Things to drop" to "Leave out: ",
        "Audience" to "Explain it for someone new to the topic.",
    )
    PhoneContent {
        Scaffold(
            modifier = Modifier.imePadding(),
            topBar = { TopAppBar(title = { Text("New episode") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back to sources") } }) },
            bottomBar = {
                PrimaryAction("Create", { onCreate(instructions, review) }, enabled = instructions.isNotBlank(),
                    modifier = Modifier.navigationBarsPadding().padding(horizontal = 20.dp, vertical = 12.dp))
            },
        ) { padding ->
            LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(horizontal = 20.dp, vertical = 8.dp)) {
                item { WizardProgress(2, Modifier.padding(bottom = 18.dp)) }
                item { Text("Shape your episode", style = MaterialTheme.typography.displaySmall) }
                item {
                    OutlinedTextField(
                        value = instructions,
                        onValueChange = { text ->
                            if (text.length <= InstructionDraftPolicy.MAX_CHARACTERS) {
                                instructions = text
                                onDraftChanged(instructions, review)
                            }
                        },
                        label = { Text("Initial instructions") },
                        supportingText = { Text("${instructions.length} / 2,000") },
                        placeholder = { Text("Make it about 10 minutes. Focus on the questions that matter most.") },
                        minLines = if (largeText) 3 else 5,
                        maxLines = if (largeText) 4 else 8,
                        modifier = Modifier.fillMaxWidth().padding(top = 18.dp),
                    )
                }
                item {
                    val limit = dev.vibevoice.podcast.runtime.SupertonicTextCapacity.textLengthForManifest(dev.vibevoice.podcast.BuildConfig.SUPERTONIC_MANIFEST_SHA256)
                        ?.minus(dev.vibevoice.podcast.runtime.SupertonicTextCapacity.LANGUAGE_TAG_CODEPOINTS)
                    Text(if (dev.vibevoice.podcast.runtime.ProviderAudioPlan.selected) "Full chapters use the provider's sentence-grouped HTP speech pipeline. Long individual sentences are never forcibly split; segment limits are checked before locking. Your instructions and script remain intact."
                        else if (limit != null) "Current voice input limit: $limit normalized characters per chapter. Longer scripts can still be generated and reviewed, but cannot be locked for audio with this voice. Your instructions are not changed."
                        else "Voice input capacity is not configured. Scripts can still be generated and reviewed; audio locking is unavailable.",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 12.dp))
                }
                item { Text("Things you could mention", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 16.dp, bottom = 4.dp)) }
                item {
                    androidx.compose.foundation.layout.FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        hints.forEach { (label, value) ->
                            val appended = InstructionDraftPolicy.appendedHint(instructions, value)
                            AssistChip(enabled = appended != null, onClick = {
                                if (appended != null) {
                                    instructions = appended
                                    onDraftChanged(instructions, review)
                                }
                            }, label = { Text(label) })
                        }
                    }
                }
                item {
                    Card(
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer),
                        shape = RoundedCornerShape(18.dp),
                        modifier = Modifier.fillMaxWidth().padding(top = 20.dp),
                    ) {
                        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text("Review script first", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                                Text("See the chapters before audio.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            Switch(checked = review, onCheckedChange = {
                                review = it
                                onDraftChanged(instructions, review)
                            }, modifier = Modifier.semantics { contentDescription = "Review script first" })
                        }
                    }
                }
                item { Spacer(Modifier.height(24.dp)) }
            }
        }
    }
}
