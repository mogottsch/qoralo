package dev.vibevoice.podcast.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.key
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import dev.vibevoice.podcast.BuildConfig
import dev.vibevoice.podcast.PodcastApplication

@Composable
fun PodcastApp(viewModel: PodcastViewModel = viewModel()) {
    val screen by viewModel.screen.collectAsStateWithLifecycle()
    val episodes by viewModel.episodes.collectAsStateWithLifecycle()
    val libraryPlayback by viewModel.libraryPlayback.collectAsStateWithLifecycle()
    val libraryChapterCounts by viewModel.libraryChapterCounts.collectAsStateWithLifecycle()
    val episode by viewModel.episode.collectAsStateWithLifecycle()
    val sources by viewModel.sources.collectAsStateWithLifecycle()
    val chapters by viewModel.chapters.collectAsStateWithLifecycle()
    val messages by viewModel.messages.collectAsStateWithLifecycle()
    val job by viewModel.job.collectAsStateWithLifecycle()
    val audio by viewModel.audio.collectAsStateWithLifecycle()
    val playback by viewModel.playback.collectAsStateWithLifecycle()
    val agentOpen by viewModel.agentSheetOpen.collectAsState()
    val lockOpen by viewModel.lockDialogOpen.collectAsState()
    val message by viewModel.transientMessage.collectAsState()
    val snackbar = remember { SnackbarHostState() }
    val context = LocalContext.current
    val repository = (context.applicationContext as PodcastApplication).repository

    BackHandler(enabled = screen != AppScreen.Library) {
        when {
            lockOpen -> viewModel.dismissLock()
            agentOpen -> viewModel.closeAgent()
            screen == AppScreen.Instructions -> viewModel.showSources()
            else -> viewModel.showLibrary()
        }
    }

    LaunchedEffect(message) {
        message?.let { snackbar.showSnackbar(it); viewModel.consumeMessage() }
    }

    // Each screen owns system/IME insets; the snackbar host must not add them again.
    Scaffold(contentWindowInsets = WindowInsets(0, 0, 0, 0), snackbarHost = { SnackbarHost(snackbar, Modifier.navigationBarsPadding().imePadding()) }) { outerPadding ->
        androidx.compose.foundation.layout.Box(Modifier.fillMaxSize().padding(outerPadding)) {
            when (screen) {
                AppScreen.Library -> LibraryScreen(episodes, viewModel::newEpisode, viewModel::selectEpisode, viewModel::showSettings,
                    playbackStates = libraryPlayback, chapterCounts = libraryChapterCounts)
                AppScreen.Sources -> episode?.let { current -> key(current.id) {
                    SourcesScreen(
                        sources = sources.filter { it.episodeId == current.id },
                        onBack = viewModel::showLibrary,
                        onPaste = { title, text -> viewModel.addPastedSource(current.id, title, text).await() },
                        onDocument = viewModel::addDocument,
                        onRemove = viewModel::removeSource,
                        onContinue = viewModel::continueToInstructions,
                    )
                } }
                AppScreen.Instructions -> episode?.let {
                    InstructionsScreen(viewModel.instructionDraft(it), viewModel::showSources, viewModel::createScript,
                        onDraftChanged = { text, review -> viewModel.saveInstructionDraft(it.id, text, review) })
                }
                AppScreen.Review -> episode?.let { current -> key(current.id) {
                    ReviewScreen(
                        chapters.filter { it.revisionId == current.activeRevisionId }, messages.filter { it.episodeId == current.id },
                        job?.takeIf { it.episodeId == current.id }, agentOpen, lockOpen,
                        viewModel::showLibrary, viewModel::openAgent, viewModel::closeAgent,
                        { request -> viewModel.requestAgentEdit(current.id, request).await() },
                        viewModel::showLock, viewModel::dismissLock, viewModel::lockAndCreate,
                    )
                } }
                AppScreen.Generating -> GeneratingScreen(episode, job, viewModel::showLibrary)
                AppScreen.Player -> episode?.let { current ->
                    val path = current.finalAudioPath
                    if (path != null) key(current.id) {
                        PlayerScreen(
                            current, chapters, audio, playback?.takeIf { it.episodeId == current.id }, repository.resolveArtifact(path),
                            viewModel::showLibrary,
                            onExport = { destination -> viewModel.exportEpisode(current.id, destination) },
                            onPersist = { position, speed, transcript -> viewModel.savePlayback(current.id, position, speed, transcript) },
                        )
                    }
                }
                AppScreen.Settings -> SettingsScreen(viewModel::showLibrary)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SettingsScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val app = context.applicationContext as PodcastApplication
    val gemmaPresent = app.artifacts.modelPackRoot("gemma-4-e2b").isDirectory && BuildConfig.GEMMA_MANIFEST_SHA256.isNotBlank()
    val supertonicPresent = app.artifacts.modelPackRoot("supertonic-3").isDirectory && BuildConfig.SUPERTONIC_MANIFEST_SHA256.isNotBlank()
    PhoneContent {
        Scaffold(topBar = { TopAppBar(title = { Text("Settings") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back to library") } }) }) { padding ->
            Column(Modifier.fillMaxSize().padding(padding).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("On-device models", style = MaterialTheme.typography.headlineSmall)
                Text("Model data stays outside the APK and must match the manifest hashes pinned into this internal build.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                RuntimeCard("Gemma 4 E2B", "LiteRT GPU · outline + one request per chapter", gemmaPresent)
                RuntimeCard("Supertonic 3", "QNN/HTP · one complete chapter per WAV", supertonicPresent)
                Text("There are no fallback inference routes.", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(top = 8.dp))
            }
        }
    }
}

@Composable
private fun RuntimeCard(title: String, subtitle: String, present: Boolean) {
    Card(
        colors = CardDefaults.cardColors(containerColor = if (present) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.errorContainer),
        shape = RoundedCornerShape(20.dp), modifier = Modifier.fillMaxWidth(),
    ) {
        androidx.compose.foundation.layout.Row(Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Icon(if (present) Icons.Default.CheckCircle else Icons.Default.ErrorOutline, null)
            Column {
                Text(title, style = MaterialTheme.typography.titleSmall)
                Text(subtitle, style = MaterialTheme.typography.bodySmall)
                Text(if (present) "Pack present and hash configured · verified when generation starts" else "Pack missing or hash not configured", style = MaterialTheme.typography.labelSmall, modifier = Modifier.padding(top = 4.dp))
            }
        }
    }
}
