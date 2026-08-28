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
import androidx.compose.material3.Switch
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import dev.vibevoice.podcast.data.EpisodeEntity
import dev.vibevoice.podcast.data.EpisodeSourceEntity

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SourcesScreen(
    sources: List<EpisodeSourceEntity>,
    onBack: () -> Unit,
    onPaste: (String, String) -> Unit,
    onDocument: (android.net.Uri) -> Unit,
    onRemove: (EpisodeSourceEntity) -> Unit,
    onContinue: () -> Unit,
) {
    var pasteDialog by remember { mutableStateOf(false) }
    val document = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let(onDocument) }
    PhoneContent {
        Scaffold(
            topBar = { TopAppBar(title = { Text("New episode") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back to library") } }) },
            bottomBar = {
                Button(
                    onClick = onContinue,
                    enabled = sources.isNotEmpty(),
                    modifier = Modifier.fillMaxWidth().navigationBarsPadding().padding(20.dp).height(52.dp),
                ) { Text("Continue") }
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
    if (pasteDialog) PasteSourceDialog(onDismiss = { pasteDialog = false }) { title, body -> onPaste(title, body); pasteDialog = false }
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
private fun PasteSourceDialog(onDismiss: () -> Unit, onAdd: (String, String) -> Unit) {
    var title by remember { mutableStateOf("") }
    var text by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Paste text") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(title, { title = it }, label = { Text("Source name") }, singleLine = true)
                OutlinedTextField(text, { text = it }, label = { Text("Source text") }, minLines = 8, maxLines = 14)
            }
        },
        confirmButton = { TextButton(onClick = { onAdd(title, text) }, enabled = text.isNotBlank()) { Text("Add source") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun InstructionsScreen(
    episode: EpisodeEntity,
    onBack: () -> Unit,
    onCreate: (String, Boolean) -> Unit,
) {
    var instructions by remember(episode.id) { mutableStateOf(episode.instructions) }
    var review by remember(episode.id) { mutableStateOf(episode.reviewEnabled) }
    val hints = listOf(
        "Length" to "Keep it under five minutes.",
        "Focus" to "Focus on the practical consequences.",
        "Questions to answer" to "Answer these questions: ",
        "Things to drop" to "Leave out: ",
        "Audience" to "Explain it for someone new to the topic.",
    )
    PhoneContent {
        Scaffold(
            topBar = { TopAppBar(title = { Text("New episode") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back to sources") } }) },
            bottomBar = {
                Button(
                    onClick = { onCreate(instructions, review) },
                    enabled = instructions.isNotBlank(),
                    modifier = Modifier.fillMaxWidth().navigationBarsPadding().padding(20.dp).height(52.dp),
                ) { Text("Create") }
            },
        ) { padding ->
            LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(horizontal = 20.dp, vertical = 8.dp)) {
                item { WizardProgress(2, Modifier.padding(bottom = 18.dp)) }
                item { Text("Shape your episode", style = MaterialTheme.typography.displaySmall) }
                item {
                    OutlinedTextField(
                        value = instructions,
                        onValueChange = { if (it.length <= 2_000) instructions = it },
                        label = { Text("Initial instructions") },
                        supportingText = { Text("${instructions.length} / 2,000") },
                        placeholder = { Text("Make it about 10 minutes. Focus on the questions that matter most.") },
                        minLines = 7,
                        maxLines = 11,
                        modifier = Modifier.fillMaxWidth().padding(top = 18.dp),
                    )
                }
                item { Text("Things you could mention", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 16.dp, bottom = 4.dp)) }
                item {
                    androidx.compose.foundation.layout.FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        hints.forEach { (label, value) -> AssistChip(onClick = {
                            instructions = listOf(instructions.trim(), value).filter(String::isNotBlank).joinToString("\n")
                        }, label = { Text(label) }) }
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
                            Switch(checked = review, onCheckedChange = { review = it })
                        }
                    }
                }
                item { Spacer(Modifier.height(24.dp)) }
            }
        }
    }
}
