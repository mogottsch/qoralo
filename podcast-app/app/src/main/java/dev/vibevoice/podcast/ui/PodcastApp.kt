package dev.vibevoice.podcast.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.ui.Alignment
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
import androidx.compose.runtime.rememberCoroutineScope
import kotlinx.coroutines.launch
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import dev.vibevoice.podcast.BuildConfig
import dev.vibevoice.podcast.PodcastApplication
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

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
    val liveAudio by viewModel.liveAudio.collectAsStateWithLifecycle()
    val livePlayback by viewModel.livePlayback.collectAsStateWithLifecycle()
    val selectedLiveJob by viewModel.selectedLiveJobId.collectAsStateWithLifecycle()
    val selectedPlayerEpisodeId by viewModel.selectedPlayerEpisodeId.collectAsStateWithLifecycle()
    val agentOpen by viewModel.agentSheetOpen.collectAsState()
    val lockOpen by viewModel.lockDialogOpen.collectAsState()
    val message by viewModel.transientMessage.collectAsState()
    val deletionTarget by viewModel.deletionTarget.collectAsState()
    val deletionBusy by viewModel.deletionBusy.collectAsState()
    val deletionError by viewModel.deletionError.collectAsState()
    val detailsTarget by viewModel.detailsTarget.collectAsState()
    val detailsError by viewModel.detailsError.collectAsState()
    val diagnostics by viewModel.diagnostics.collectAsStateWithLifecycle()
    val actionsScope = rememberCoroutineScope()
    val snackbar = remember { SnackbarHostState() }
    val context = LocalContext.current
    val repository = (context.applicationContext as PodcastApplication).repository
    val playbackHost = remember(repository) { PlaybackHost(context.applicationContext) }
    PlaybackHostEffects(playbackHost, repository)
    deletionTarget?.let { target ->
        DeleteEpisodeConfirmation(target, deletionBusy, deletionError, viewModel::cancelDeletion) {
            actionsScope.launch {
                if (viewModel.confirmDeletion(target.id).await()) {
                    try {
                        playbackHost.closeIfEpisodeAndAwait(target.id)
                        viewModel.deletionAccepted(target.id)
                    } catch (cancelled: kotlinx.coroutines.CancellationException) { throw cancelled }
                    catch (_: Exception) { viewModel.deletionReleasePending(target.id) }
                }
            }
        }
    }
    val activePlayback = playbackHost.active
    val showMiniPlayer = activePlayback != null && screen != AppScreen.Player
    LaunchedEffect(screen, episode, selectedPlayerEpisodeId, selectedLiveJob, liveAudio, playback, livePlayback) {
        if (screen != AppScreen.Player) return@LaunchedEffect
        val current = episode?.takeIf { it.id == selectedPlayerEpisodeId } ?: return@LaunchedEffect
        val requestedJob = selectedLiveJob
        val available = liveAudio?.takeIf { it.binding.episodeId == current.id && it.binding.jobId == requestedJob }
        val binding = available?.binding
        withContext(Dispatchers.Main.immediate) {
            if (screen != AppScreen.Player || selectedPlayerEpisodeId != current.id || selectedLiveJob != requestedJob) return@withContext
            playbackHost.open(current, chapters, audio, requestedJob,
                current.finalAudioPath?.let(repository::resolveArtifact), available,
                if (requestedJob != null) livePlayback else playback) { position, speed, transcript ->
                if (binding != null) viewModel.saveStreamPlayback(binding, position, speed, transcript)
                else viewModel.savePlayback(current.id, position, speed, transcript)
            }
        }
    }

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
        Column(Modifier.fillMaxSize().padding(outerPadding).then(
            if (showMiniPlayer) Modifier.windowInsetsPadding(WindowInsets.statusBars) else Modifier
        )) {
            if (showMiniPlayer) Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.TopCenter) {
                MiniPlayer(activePlayback.episode.title, activePlayback.session,
                    onOpen = { viewModel.reopenPlayer(activePlayback.identity.episodeId, activePlayback.identity.liveBinding) },
                    modifier = Modifier.widthIn(max = 600.dp))
            }
            Box(Modifier.fillMaxWidth().weight(1f)) {
            when (screen) {
                AppScreen.Library -> LibraryScreen(episodes, viewModel::newEpisode, viewModel::selectEpisode, viewModel::showSettings,
                    playbackStates = libraryPlayback, chapterCounts = libraryChapterCounts,
                    episodeActions = { current -> EpisodeOverflow(current, viewModel::showDiagnostics, viewModel::askToDelete) })
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
                        audioCapacity = repository::audioTextCapacity,
                    )
                } }
                AppScreen.Generating -> {
                    val current = episode
                    val failedJob = job
                    val returnToDraft: (() -> Unit)? = if (dev.vibevoice.podcast.data.canReturnToSavedDraft(current, failedJob)) {
                        val episodeId = requireNotNull(current).id
                        val revisionId = requireNotNull(current.activeRevisionId)
                        val jobId = requireNotNull(failedJob).id
                        val action: () -> Unit = { viewModel.returnToSavedDraft(episodeId, jobId, revisionId) }
                        action
                    } else null
                    val available = liveAudio?.takeIf { it.binding.episodeId == current?.id }
                    GeneratingScreen(current, failedJob, viewModel::showLibrary, returnToDraft,
                        available, { available?.let { viewModel.openLivePlayer(it.binding) } })
                }
                AppScreen.Player -> {
                    val active = activePlayback?.takeIf {
                        it.identity.episodeId == selectedPlayerEpisodeId && it.identity.episodeId == episode?.id &&
                            (selectedLiveJob == null || it.identity.liveBinding?.jobId == selectedLiveJob)
                    }
                    if (active != null) PlayerScreen(active.episode, active.chapters, active.audio, null, null,
                        onBack = viewModel::showLibrary,
                        onExport = { destination -> viewModel.exportEpisode(active.identity.episodeId, destination) },
                        onPersist = { _, _, _ -> }, liveAudio = active.stream, sharedPlayback = active)
                    else Column(Modifier.fillMaxSize().padding(24.dp)) {
                        Text("Checking available audio…")
                        androidx.compose.material3.TextButton(onClick = viewModel::showLibrary) { Text("Return to library") }
                    }
                }
                AppScreen.Diagnostics -> EpisodeDiagnosticsScreen(detailsTarget?.title ?: "Episode", diagnostics, detailsError, viewModel::showLibrary)
                AppScreen.Settings -> SettingsScreen(viewModel::showLibrary)
            }
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
    val supertonicPresent = app.artifacts.modelPackRoot(BuildConfig.SUPERTONIC_PACK_ID).isDirectory && BuildConfig.SUPERTONIC_MANIFEST_SHA256.isNotBlank()
    PhoneContent {
        Scaffold(topBar = { TopAppBar(title = { Text("Settings") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back to library") } }) }) { padding ->
            Column(Modifier.fillMaxSize().padding(padding).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("On-device models", style = MaterialTheme.typography.headlineSmall)
                Text("Model data stays outside the APK and must match the manifest hashes pinned into this internal build.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                RuntimeCard("Gemma 4 E2B", "LiteRT GPU · outline + one request per chapter", gemmaPresent)
                val provider = dev.vibevoice.podcast.runtime.ProviderAudioPlan.selected
                RuntimeCard(if (provider) "Supertonic 3 · provider pipeline" else if (BuildConfig.SHORT_PRODUCT_E2E) "Supertonic 3 · short plumbing" else "Supertonic 3 · experimental",
                    if (provider) "QNN/HTP · sentence segments · 8 steps · speed 1.05" else if (BuildConfig.SHORT_PRODUCT_E2E) "QNN/HTP · brief chapters only" else "QNN/HTP · speech coverage unverified", supertonicPresent)
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
