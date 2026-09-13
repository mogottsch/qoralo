package dev.vibevoice.podcast.ui

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.SavedStateHandle
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
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
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Suppress("OPT_IN_USAGE")
class PodcastViewModel internal constructor(
    application: Application,
    private val savedState: SavedStateHandle,
    private val repository: dev.vibevoice.podcast.data.PodcastRepository,
) : AndroidViewModel(application) {
    constructor(application: Application, savedState: SavedStateHandle) : this(application, savedState, (application as PodcastApplication).repository)
    private val instructionWrites = Mutex()
    private val selectedEpisodeId = MutableStateFlow<String?>(savedState["livePlayer.episodeId"])
    val selectedLiveJobId = MutableStateFlow<String?>(savedState["livePlayer.jobId"])
    val selectedPlayerEpisodeId: StateFlow<String?> get() = selectedEpisodeId
    private val explicitScreen = MutableStateFlow<AppScreen?>(if (selectedLiveJobId.value != null) AppScreen.Player else null)
    val agentSheetOpen = MutableStateFlow(false)
    val lockDialogOpen = MutableStateFlow(false)
    val transientMessage = MutableStateFlow<String?>(null)
    val deletionTarget = MutableStateFlow<EpisodeDeletionTarget?>(null)
    val deletionBusy = MutableStateFlow(false)
    val deletionError = MutableStateFlow<String?>(null)
    val detailsTarget = MutableStateFlow<EpisodeDeletionTarget?>(null)
    val detailsError = MutableStateFlow<String?>(null)
    val diagnostics = detailsTarget.flatMapLatest { target ->
        kotlinx.coroutines.flow.flow<List<Pair<GenerationJobEntity, org.json.JSONObject?>>?> {
            emit(null)
            if (target != null) try {
                while (true) { emit(repository.episodeDiagnostics(target.id)); kotlinx.coroutines.delay(1_000) }
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (_: Exception) { detailsError.value = "These episode details are no longer available. Return to the library." }
        }.flowOn(Dispatchers.IO)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(0), null)

    fun showDiagnostics(value: EpisodeEntity) {
        detailsError.value = null
        detailsTarget.value = EpisodeDeletionTarget(value.id, value.title)
        explicitScreen.value = AppScreen.Diagnostics
    }
    fun askToDelete(value: EpisodeEntity) {
        if (deletionBusy.value || value.phase == "DELETING") return
        deletionError.value = null; deletionTarget.value = EpisodeDeletionTarget(value.id, value.title)
    }
    fun cancelDeletion() { if (!deletionBusy.value) { deletionTarget.value = null; deletionError.value = null } }
    fun confirmDeletion(id: String): Deferred<Boolean> = viewModelScope.async {
        if (deletionTarget.value?.id != id || deletionBusy.value) return@async false
        deletionBusy.value = true; deletionError.value = null
        try { withContext(Dispatchers.IO) { repository.requestEpisodeDeletion(id) }; true }
        catch (cancelled: CancellationException) { throw cancelled }
        catch (_: Exception) { deletionError.value = "Could not finish requesting deletion. Keep this dialog open and try again."; false }
        finally { deletionBusy.value = false }
    }
    fun deletionAccepted(id: String) {
        if (deletionTarget.value?.id == id) deletionTarget.value = null
        if (selectedEpisodeId.value == id || detailsTarget.value?.id == id) showLibrary()
        transientMessage.value = "Episode deletion requested. Files are removed when they are safely released."
    }

    val episodes = repository.observeEpisodes().stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val libraryPlayback = repository.observeLibraryPlayback().stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
    val libraryChapterCounts = repository.observeLibraryChapterCounts().map { rows -> rows.associate { it.episodeId to it.chapterCount } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyMap())
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

    val liveAudio = combine(selectedEpisodeId, selectedLiveJobId) { id, jobId -> id to jobId }
        .flatMapLatest { (id, jobId) -> if (id == null) flowOf(null) else repository.observeAudioAvailability(id, jobId) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)
    val livePlayback = liveAudio.map { value -> value?.let { repository.streamPlayback(it.binding) } }
        .flowOn(Dispatchers.IO).stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    val screen: StateFlow<AppScreen> = combine(episode, explicitScreen) { current, explicit ->
        explicit ?: screenForPersistedPhase(current?.phase)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), AppScreen.Library)

    fun newEpisode() = launchAction {
        clearLiveSelection()
        selectedEpisodeId.value = repository.createEpisode()
        explicitScreen.value = AppScreen.Sources
    }

    private fun clearLiveSelection() {
        selectedLiveJobId.value = null
        savedState.remove<String>("livePlayer.episodeId"); savedState.remove<String>("livePlayer.jobId")
    }
    fun openLivePlayer(binding: dev.vibevoice.podcast.runtime.AudioAttemptBinding) {
        val available = liveAudio.value
        if (selectedEpisodeId.value != binding.episodeId || available?.binding != binding || !available.canListen) return
        selectedLiveJobId.value = binding.jobId
        savedState["livePlayer.episodeId"] = binding.episodeId; savedState["livePlayer.jobId"] = binding.jobId
        explicitScreen.value = AppScreen.Player
    }
    fun reopenPlayer(episodeId: String, liveBinding: dev.vibevoice.podcast.runtime.AudioAttemptBinding? = null) {
        require(liveBinding == null || liveBinding.episodeId == episodeId)
        selectedEpisodeId.value = episodeId
        selectedLiveJobId.value = liveBinding?.jobId
        if (liveBinding != null) {
            savedState["livePlayer.episodeId"] = episodeId; savedState["livePlayer.jobId"] = liveBinding.jobId
        } else {
            savedState.remove<String>("livePlayer.episodeId"); savedState.remove<String>("livePlayer.jobId")
        }
        agentSheetOpen.value = false; lockDialogOpen.value = false
        explicitScreen.value = AppScreen.Player
    }
    fun selectEpisode(value: EpisodeEntity) {
        clearLiveSelection()
        agentSheetOpen.value = false
        lockDialogOpen.value = false
        selectedEpisodeId.value = value.id
        explicitScreen.value = null
    }

    fun showLibrary() { clearLiveSelection(); selectedEpisodeId.value = null; detailsTarget.value = null; explicitScreen.value = AppScreen.Library }
    fun showSettings() { explicitScreen.value = AppScreen.Settings }
    fun showSources() { explicitScreen.value = AppScreen.Sources }
    fun showInstructions() { explicitScreen.value = AppScreen.Instructions }
    fun closeAgent() { agentSheetOpen.value = false }
    fun openAgent() { agentSheetOpen.value = true }
    fun showLock() { lockDialogOpen.value = true }
    fun dismissLock() { lockDialogOpen.value = false }
    fun consumeMessage() { transientMessage.value = null }

    // Completion means persisted/queued, not merely that a coroutine was launched. Callers await
    // this acknowledgement and render failures inside the originating form, never a replacement.
    fun addPastedSource(episodeId: String, title: String, text: String): Deferred<Unit> = viewModelScope.async(Dispatchers.IO) {
        text.byteInputStream().use { repository.addSource(episodeId, title, "text/plain", it) }
        Unit
    }

    fun addDocument(uri: Uri) = launchAction {
        val resolver = getApplication<Application>().contentResolver
        val title = uri.lastPathSegment?.substringAfterLast('/') ?: "Document"
        val input = requireNotNull(resolver.openInputStream(uri)) { "Could not open the selected document" }
        input.use {
            repository.addSource(requireNotNull(selectedEpisodeId.value), title, resolver.getType(uri) ?: "text/plain", it)
        }
    }

    fun removeSource(source: EpisodeSourceEntity) = launchAction {
        repository.removeSource(source.episodeId, source.id)
    }

    fun continueToInstructions() = launchAction {
        repository.moveToInstructions(requireNotNull(selectedEpisodeId.value))
        explicitScreen.value = AppScreen.Instructions
    }

    fun createScript(instructions: String, review: Boolean) = launchAction {
        val id = requireNotNull(selectedEpisodeId.value)
        repository.queueScriptGeneration(id, instructions, review)
        explicitScreen.value = null
    }

    fun requestAgentEdit(episodeId: String, request: String): Deferred<Unit> = viewModelScope.async {
        repository.queueAgentEdit(episodeId, request)
        Unit
    }

    fun returnToSavedDraft(episodeId: String, failedJobId: String, revisionId: String) = launchAction {
        repository.returnToSavedDraft(episodeId, failedJobId, revisionId)
        // A completed recovery for another selection must not redirect the current screen.
        if (selectedEpisodeId.value == episodeId) {
            agentSheetOpen.value = false
            lockDialogOpen.value = false
            explicitScreen.value = null
        }
    }

    fun lockAndCreate() = launchAction {
        val id = requireNotNull(selectedEpisodeId.value)
        repository.lockAndQueueAudio(id)
        lockDialogOpen.value = false
        agentSheetOpen.value = false
        explicitScreen.value = null
    }

    fun instructionDraft(current: EpisodeEntity): EpisodeEntity =
        if (current.phase == EpisodePhase.SOURCES || current.phase == EpisodePhase.INSTRUCTIONS) current.copy(
            instructions = savedState["instructions.${current.id}"] ?: current.instructions,
            reviewEnabled = savedState["review.${current.id}"] ?: current.reviewEnabled,
        ) else current

    fun saveInstructionDraft(episodeId: String, instructions: String, review: Boolean): kotlinx.coroutines.Job {
        require(instructions.length <= InstructionDraftPolicy.MAX_CHARACTERS)
        savedState["instructions.$episodeId"] = instructions
        savedState["review.$episodeId"] = review
        return viewModelScope.launch {
            try { instructionWrites.withLock { repository.saveInstructionDraft(episodeId, instructions, review) } }
            catch (cancelled: CancellationException) { throw cancelled }
            catch (error: Exception) { transientMessage.value = error.message ?: "Could not save instructions" }
        }
    }

    // Bind writes to the episode being disposed/exported, not a selection that navigation can clear.
    fun saveStreamPlayback(binding: dev.vibevoice.podcast.runtime.AudioAttemptBinding, positionMs: Long, speed: Float, transcriptVisible: Boolean) = viewModelScope.launch(Dispatchers.IO) {
        if (repository.deletionRequested(binding.episodeId)) return@launch
        try { repository.saveStreamPlayback(binding, positionMs, speed, transcriptVisible) }
        catch (cancelled: CancellationException) { throw cancelled }
        catch (_: Exception) { if (!repository.deletionRequested(binding.episodeId)) transientMessage.value = "Could not save this audio attempt's position" }
    }

    fun savePlayback(episodeId: String, positionMs: Long, speed: Float, transcriptVisible: Boolean) = viewModelScope.launch {
        if (repository.deletionRequested(episodeId)) return@launch
        try { repository.savePlayback(episodeId, positionMs, speed, transcriptVisible) }
        catch (cancelled: CancellationException) { throw cancelled }
        catch (error: Exception) { if (!repository.deletionRequested(episodeId)) transientMessage.value = error.message ?: "Could not save playback position" }
    }

    fun exportEpisode(episodeId: String, destination: Uri) = launchAction {
        withContext(Dispatchers.IO) { repository.acquireEpisodeFiles(episodeId).use {
        val current = repository.episode(episodeId)
        require(current.phase == EpisodePhase.FROZEN_READY) { "Export is available only after the complete episode is ready" }
        val source = repository.resolveArtifact(requireNotNull(current.finalAudioPath))
        dev.vibevoice.podcast.runtime.RuntimeDiagnostics.beforeExport(getApplication(), episodeId, destination)
        val output = requireNotNull(getApplication<Application>().contentResolver.openOutputStream(destination, "w")) { "Could not open export destination" }
        output.use { destinationStream -> source.inputStream().use { it.copyTo(destinationStream) } }
        dev.vibevoice.podcast.runtime.RuntimeDiagnostics.exportFinished(episodeId, destination)
        } }
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

enum class AppScreen { Library, Sources, Instructions, Review, Generating, Player, Settings, Diagnostics }

data class EpisodeUiData(
    val episode: EpisodeEntity?,
    val sources: List<EpisodeSourceEntity>,
    val chapters: List<ChapterEntity>,
    val messages: List<AgentMessageEntity>,
    val job: GenerationJobEntity?,
    val audio: List<ChapterAudioEntity>,
    val playback: PlaybackStateEntity?,
)
