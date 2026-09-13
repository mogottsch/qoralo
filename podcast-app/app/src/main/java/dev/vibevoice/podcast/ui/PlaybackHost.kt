package dev.vibevoice.podcast.ui

import android.content.Context
import android.os.Looper
import androidx.compose.runtime.*
import dev.vibevoice.podcast.data.*
import dev.vibevoice.podcast.runtime.AudioAttemptBinding
import dev.vibevoice.podcast.runtime.AudioAvailability
import dev.vibevoice.podcast.runtime.AudioAvailabilityState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
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
class PlaybackHost(private val context: Context, private val acquireFiles: (String) -> java.io.Closeable = { id ->
    (context.applicationContext as dev.vibevoice.podcast.PodcastApplication).repository.acquireEpisodeFiles(id)
}, private val releaseSession: (EpisodePlayerSession) -> Unit = { it.close() }) {
    private var fileLease: java.io.Closeable? = null
    var active by mutableStateOf<ActivePlayback?>(null)
        private set

    fun open(episode: EpisodeEntity, chapters: List<ChapterEntity>, audio: List<ChapterAudioEntity>,
             requestedJobId: String?, file: File?, stream: AudioAvailability?, saved: PlaybackStateEntity?,
             persist: (Long, Float, Boolean) -> Unit) {
        check(Looper.myLooper() == Looper.getMainLooper()) { "PlaybackHost.open requires the main player looper" }
        val previous = active
        if (previous?.identity?.canReuse(episode.id, requestedJobId, file?.absolutePath) == true &&
            (previous.identity.liveBinding == null || previous.identity.liveBinding.revisionId == episode.lockedRevisionId) &&
            (previous.session.streamState != AudioAvailabilityState.STALE || requestedJobId != null)) return
        if (requestedJobId != null && (stream?.binding?.episodeId != episode.id || stream.binding.jobId != requestedJobId || !stream.canListen)) return
        if (requestedJobId == null && file == null) return
        val selectedStream = stream.takeIf { requestedJobId != null }
        // Close before constructing its replacement: never two live ExoPlayers.
        val lease = try { acquireFiles(episode.id) } catch (_: dev.vibevoice.podcast.episode.EpisodeDeletedException) { return }
        try {
            close()
            val identity = PlaybackIdentity(episode.id, selectedStream?.binding, file?.absolutePath)
            val session = EpisodePlayerSession(context.applicationContext, episode.id, file, selectedStream,
                saved?.takeIf { it.episodeId == episode.id }, episode.durationMs ?: 0, persist)
            fileLease = lease
            active = ActivePlayback(identity, session, episode, chapters, audio, selectedStream)
        } catch (error: Throwable) { lease.close(); throw error }
    }

    /** May be called from a database/IO collector. No host/session state is read before Main.
     * Once requested, do not let caller cancellation release files before the player finishes.
     */
    suspend fun closeIfEpisodeAndAwait(episodeId: String): Boolean = withContext(Dispatchers.Main.immediate + NonCancellable) {
        closeIfEpisode(episodeId)
    }

    fun closeIfEpisode(episodeId: String): Boolean {
        check(Looper.myLooper() == Looper.getMainLooper()) { "PlaybackHost.closeIfEpisode requires the main player looper" }
        if (active?.identity?.episodeId != episodeId) return false
        close(); return true
    }
    fun close() {
        check(Looper.myLooper() == Looper.getMainLooper()) { "PlaybackHost.close requires the main player looper" }
        // Keep BOTH ownership and lease on any unsuccessful release, for a safe retry.
        // Never use finally here: player.release may fail before native resources are free.
        active?.session?.let {
            releaseSession(it)
            check(it.isReleased) { "Session release did not complete; retaining its file lease" }
        }
        fileLease?.close()
        fileLease = null
        active = null
    }
}

@Composable
fun PlaybackHostEffects(host: PlaybackHost, repository: PodcastRepository) {
    val active = host.active
    DisposableEffect(host) { onDispose { host.close() } }
    LaunchedEffect(active) {
        val current = active ?: return@LaunchedEffect
        // Do not inherit Compose/test continuation interceptors for media access: a
        // flowOn(IO) emission can otherwise resume that collector on its producer thread.
        // Every child collector, restore and tick uses the actual Android main looper;
        // flowOn(IO)/withContext(IO) below still keep all file/receipt work off main.
        withContext(Dispatchers.Main.immediate) {
        val session = current.session
        launch { repository.observeEpisode(session.episodeId).collect { episode ->
            if (host.active !== current) return@collect
            if (episode != null) current.episode = episode else {
                try { host.closeIfEpisodeAndAwait(session.episodeId) }
                catch (cancelled: kotlinx.coroutines.CancellationException) { throw cancelled }
                catch (_: Exception) { /* Pending deletion keeps its lease; the next close/disposal can retry. */ }
            }
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
}
