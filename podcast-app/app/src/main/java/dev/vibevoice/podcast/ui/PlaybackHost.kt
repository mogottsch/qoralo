package dev.vibevoice.podcast.ui

import android.content.Context
import androidx.compose.runtime.*
import dev.vibevoice.podcast.data.*
import dev.vibevoice.podcast.runtime.AudioAttemptBinding
import dev.vibevoice.podcast.runtime.AudioAvailability
import dev.vibevoice.podcast.runtime.AudioAvailabilityState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

/** Active audio identity is independent of the episode currently being browsed/edited. */
data class PlaybackIdentity(val episodeId: String, val liveBinding: AudioAttemptBinding?, val masterPath: String?) {
    fun canReuse(episodeId: String, requestedJobId: String?, masterPath: String?): Boolean =
        this.episodeId == episodeId && when {
            // A live session remains authoritative through completion and library reopen.
            liveBinding != null -> requestedJobId == null || liveBinding.jobId == requestedJobId
            else -> requestedJobId == null && this.masterPath == masterPath
        }
}

class ActivePlayback(
    val identity: PlaybackIdentity,
    val session: EpisodePlayerSession,
    episode: EpisodeEntity,
    chapters: List<ChapterEntity>,
    audio: List<ChapterAudioEntity>,
    stream: AudioAvailability?,
) {
    val revisionId = identity.liveBinding?.revisionId ?: episode.lockedRevisionId ?: episode.activeRevisionId
    var episode by mutableStateOf(episode)
    var chapters by mutableStateOf(chapters.filter { it.revisionId == revisionId })
    var audio by mutableStateOf(audio.filter { it.episodeId == identity.episodeId && it.lockedRevisionId == revisionId })
    var stream by mutableStateOf(stream)
    var verifiedPassages by mutableStateOf<List<dev.vibevoice.podcast.runtime.TranscriptPassage>>(emptyList())
}

/** The app calls this above its navigation switch, so collapsing a screen cannot dispose audio. */
class PlaybackHost(private val context: Context) {
    var active by mutableStateOf<ActivePlayback?>(null)
        private set

    fun open(episode: EpisodeEntity, chapters: List<ChapterEntity>, audio: List<ChapterAudioEntity>,
             requestedJobId: String?, file: File?, stream: AudioAvailability?, saved: PlaybackStateEntity?,
             persist: (Long, Float, Boolean) -> Unit) {
        val previous = active
        if (previous?.identity?.canReuse(episode.id, requestedJobId, file?.absolutePath) == true &&
            (previous.identity.liveBinding == null || previous.identity.liveBinding.revisionId == episode.lockedRevisionId) &&
            (previous.session.streamState != AudioAvailabilityState.STALE || requestedJobId != null)) return
        if (requestedJobId != null && (stream?.binding?.episodeId != episode.id || stream.binding.jobId != requestedJobId || !stream.canListen)) return
        if (requestedJobId == null && file == null) return
        val selectedStream = stream.takeIf { requestedJobId != null }
        // Close before constructing its replacement: never two live ExoPlayers.
        active?.session?.close()
        active = null
        val identity = PlaybackIdentity(episode.id, selectedStream?.binding, file?.absolutePath)
        val session = EpisodePlayerSession(context.applicationContext, episode.id, file, selectedStream,
            saved?.takeIf { it.episodeId == episode.id }, episode.durationMs ?: 0, persist)
        active = ActivePlayback(identity, session, episode, chapters, audio, selectedStream)
    }

    fun close() { active?.session?.close(); active = null }
}

@Composable
fun PlaybackHostEffects(host: PlaybackHost, repository: PodcastRepository) {
    val active = host.active
    DisposableEffect(host) { onDispose { host.close() } }
    LaunchedEffect(active) {
        val current = active ?: return@LaunchedEffect
        val session = current.session
        launch { repository.observeEpisode(session.episodeId).collect { episode ->
            if (host.active !== current) return@collect
            if (episode != null) current.episode = episode else session.pause(PlaybackStopReason.STALE_ATTEMPT)
        } }
        launch { repository.observeChapters(session.episodeId).collect { if (host.active === current) current.chapters = it.filter { row -> row.revisionId == current.revisionId } } }
        launch { repository.observeAudio(session.episodeId).collect { if (host.active === current) current.audio = it.filter { row -> row.episodeId == session.episodeId && row.lockedRevisionId == current.revisionId } } }
        val binding = session.liveBinding
        if (binding != null) {
            launch {
                val saved = withContext(Dispatchers.IO) { repository.streamPlayback(binding) }
                if (host.active !== current) return@launch
                session.restore(saved)
                repository.observeAudioAvailability(session.episodeId, binding.jobId).collect { value ->
                    if (host.active !== current) return@collect
                    val next = value ?: current.stream?.copy(state = AudioAvailabilityState.STALE, problem = "Audio attempt is no longer available")
                    if (next != null) { current.stream = next; session.update(next) }
                }
            }
        } else {
            launch { repository.observePlayback(session.episodeId).collect { if (host.active === current) session.restore(it) } }
            launch {
                current.verifiedPassages = try { withContext(Dispatchers.IO) { repository.verifiedTranscriptPassages(session.episodeId) } }
                catch (cancelled: kotlinx.coroutines.CancellationException) { throw cancelled }
                catch (_: Exception) { emptyList() } // Unavailable alignment must not stop playback.
            }
        }
        var ticks = 0
        while (host.active === current) {
            session.tick()
            if (session.isPlaying && ++ticks % 10 == 0) session.checkpoint()
            delay(300)
        }
    }
}
