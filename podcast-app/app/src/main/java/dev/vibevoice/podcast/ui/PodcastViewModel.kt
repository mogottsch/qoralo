package dev.vibevoice.podcast.ui

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import dev.vibevoice.podcast.PodcastApplication
import dev.vibevoice.podcast.data.AgentMessageEntity
import dev.vibevoice.podcast.data.ChapterAudioEntity
import dev.vibevoice.podcast.data.ChapterEntity
import dev.vibevoice.podcast.data.EpisodeEntity
import dev.vibevoice.podcast.data.EpisodePhase
import dev.vibevoice.podcast.data.EpisodeSourceEntity
import dev.vibevoice.podcast.data.GenerationJobEntity
import dev.vibevoice.podcast.data.PlaybackStateEntity
import dev.vibevoice.podcast.generation.GenerationService
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

@Suppress("OPT_IN_USAGE")
class PodcastViewModel(application: Application) : AndroidViewModel(application) {
    private val app = application as PodcastApplication
    private val repository = app.repository
    private val selectedEpisodeId = MutableStateFlow<String?>(null)
    private val explicitScreen = MutableStateFlow<AppScreen?>(null)
    val agentSheetOpen = MutableStateFlow(false)
    val lockDialogOpen = MutableStateFlow(false)
    val transientMessage = MutableStateFlow<String?>(null)

    val episodes = repository.observeEpisodes().stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val episode = selectedEpisodeId.flatMapLatest { it?.let(repository::observeEpisode) ?: flowOf(null) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)
    val sources = selectedEpisodeId.flatMapLatest { it?.let(repository::observeSources) ?: flowOf(emptyList()) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val chapters = selectedEpisodeId.flatMapLatest { it?.let(repository::observeChapters) ?: flowOf(emptyList()) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val messages = selectedEpisodeId.flatMapLatest { it?.let(repository::observeMessages) ?: flowOf(emptyList()) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val job = selectedEpisodeId.flatMapLatest { it?.let(repository::observeJob) ?: flowOf(null) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)
    val audio = selectedEpisodeId.flatMapLatest { it?.let(repository::observeAudio) ?: flowOf(emptyList()) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val playback = selectedEpisodeId.flatMapLatest { it?.let(repository::observePlayback) ?: flowOf(null) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    val screen: StateFlow<AppScreen> = combine(episode, explicitScreen) { current, explicit ->
        explicit ?: when (current?.phase) {
            null -> AppScreen.Library
            EpisodePhase.SOURCES -> AppScreen.Sources
            EpisodePhase.INSTRUCTIONS -> AppScreen.Instructions
            EpisodePhase.GENERATING_SCRIPT, EpisodePhase.LOCKED, EpisodePhase.GENERATING_AUDIO, EpisodePhase.FAILED -> AppScreen.Generating
            EpisodePhase.SCRIPT_DRAFT -> AppScreen.Review
            EpisodePhase.FROZEN_READY -> AppScreen.Player
            else -> AppScreen.Library
        }
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), AppScreen.Library)

    fun newEpisode() = launchAction {
        selectedEpisodeId.value = repository.createEpisode()
        explicitScreen.value = AppScreen.Sources
    }

    fun selectEpisode(value: EpisodeEntity) {
        selectedEpisodeId.value = value.id
        explicitScreen.value = null
    }

    fun showLibrary() { selectedEpisodeId.value = null; explicitScreen.value = AppScreen.Library }
    fun showSettings() { explicitScreen.value = AppScreen.Settings }
    fun showSources() { explicitScreen.value = AppScreen.Sources }
    fun showInstructions() { explicitScreen.value = AppScreen.Instructions }
    fun closeAgent() { agentSheetOpen.value = false }
    fun openAgent() { agentSheetOpen.value = true }
    fun showLock() { lockDialogOpen.value = true }
    fun dismissLock() { lockDialogOpen.value = false }
    fun consumeMessage() { transientMessage.value = null }

    fun addPastedSource(title: String, text: String) = launchAction {
        val id = requireNotNull(selectedEpisodeId.value)
        repository.addSource(id, title, "text/plain", text.byteInputStream())
    }

    fun addDocument(uri: Uri) = launchAction {
        val resolver = getApplication<Application>().contentResolver
        val title = uri.lastPathSegment?.substringAfterLast('/') ?: "Document"
        resolver.openInputStream(uri).use { input ->
            repository.addSource(requireNotNull(selectedEpisodeId.value), title, resolver.getType(uri) ?: "text/plain", requireNotNull(input))
        }
    }

    fun removeSource(source: EpisodeSourceEntity) = launchAction {
        repository.removeSource(requireNotNull(selectedEpisodeId.value), source.id)
    }

    fun continueToInstructions() = launchAction {
        repository.moveToInstructions(requireNotNull(selectedEpisodeId.value))
        explicitScreen.value = AppScreen.Instructions
    }

    fun createScript(instructions: String, review: Boolean) = launchAction {
        val id = requireNotNull(selectedEpisodeId.value)
        val jobId = repository.queueScriptGeneration(id, instructions, review)
        explicitScreen.value = null
        GenerationService.startScript(getApplication(), id, jobId)
    }

    fun requestAgentEdit(request: String) = launchAction {
        val id = requireNotNull(selectedEpisodeId.value)
        val jobId = repository.queueAgentEdit(id, request)
        GenerationService.startEdit(getApplication(), id, jobId)
    }

    fun lockAndCreate() = launchAction {
        val id = requireNotNull(selectedEpisodeId.value)
        val jobId = repository.lockAndQueueAudio(id)
        lockDialogOpen.value = false
        agentSheetOpen.value = false
        explicitScreen.value = null
        GenerationService.startAudio(getApplication(), id, jobId)
    }

    fun savePlayback(positionMs: Long, speed: Float, transcriptVisible: Boolean) = launchAction(showFailure = false) {
        repository.savePlayback(requireNotNull(selectedEpisodeId.value), positionMs, speed, transcriptVisible)
    }

    fun exportEpisode(destination: Uri) = launchAction {
        val current = requireNotNull(episode.value)
        val source = repository.resolveArtifact(requireNotNull(current.finalAudioPath))
        getApplication<Application>().contentResolver.openOutputStream(destination, "w").use { output ->
            source.inputStream().use { it.copyTo(requireNotNull(output)) }
        }
        transientMessage.value = "Episode exported"
    }

    private fun launchAction(showFailure: Boolean = true, block: suspend () -> Unit) {
        viewModelScope.launch {
            try { block() } catch (error: Throwable) {
                if (showFailure) transientMessage.value = error.message ?: "Something went wrong"
            }
        }
    }
}

enum class AppScreen { Library, Sources, Instructions, Review, Generating, Player, Settings }

data class EpisodeUiData(
    val episode: EpisodeEntity?,
    val sources: List<EpisodeSourceEntity>,
    val chapters: List<ChapterEntity>,
    val messages: List<AgentMessageEntity>,
    val job: GenerationJobEntity?,
    val audio: List<ChapterAudioEntity>,
    val playback: PlaybackStateEntity?,
)
