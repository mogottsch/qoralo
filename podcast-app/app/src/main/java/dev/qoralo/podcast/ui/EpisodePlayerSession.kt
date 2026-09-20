package dev.qoralo.podcast.ui

import android.content.Context
import androidx.compose.runtime.*
import androidx.core.net.toUri
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import dev.qoralo.podcast.data.PlaybackStateEntity
import dev.qoralo.podcast.runtime.*
import java.io.File

/** One stable player for one episode/attempt. Final master appearance never replaces a live playlist. */
class EpisodePlayerSession(
    context: Context,
    val episodeId: String,
    file: File?,
    initialStream: AudioAvailability?,
    saved: PlaybackStateEntity?,
    initialDurationMs: Long,
    private val persist: (Long,Float,Boolean) -> Unit,
) {
    val player: ExoPlayer = ExoPlayer.Builder(context).build()
    val liveBinding = initialStream?.binding
    private val intent = ProgressivePlaybackIntent()
    private var stream = initialStream
    private var timeline = ProgressiveTimeline(initialStream?.chunks ?: emptyList())
    private var internalPauseEvents = 0
    private var closed = false
    private val releaseState = dev.qoralo.podcast.episode.PlaybackRelease()
    val isReleased: Boolean get() = releaseState.released
    private var interacted = false
    private var restored = saved != null
    var availableChunks by mutableStateOf(initialStream?.chunks ?: emptyList())
        private set
    var sleepMinutes by mutableStateOf<Int?>(null)
        private set
    var sleepDeadlineElapsedMs by mutableStateOf<Long?>(null)
        private set
    var positionMs by mutableLongStateOf(saved?.positionMs ?: 0L)
        private set
    var durationMs by mutableLongStateOf(initialStream?.availableMs ?: initialDurationMs)
        private set
    var isPlaying by mutableStateOf(false)
        private set
    var wantsPlayback by mutableStateOf(false)
        private set
    var waiting by mutableStateOf(false)
        private set
    var streamState by mutableStateOf(initialStream?.state)
        private set
    var speed by mutableFloatStateOf(saved?.speed ?: 1f)
        private set
    var transcript by mutableStateOf(saved?.transcriptVisible ?: false)
        private set
    var error by mutableStateOf<String?>(null)
        private set
    private fun syncIntent() { wantsPlayback=intent.wantsPlayback;waiting=streamState?.let(intent::isWaiting) ?: false }
    private fun absolute(): Long = if(liveBinding==null) player.currentPosition.coerceAtLeast(0)
        else if(player.playbackState==Player.STATE_ENDED && player.currentMediaItemIndex==timeline.chunks.lastIndex) timeline.availableMs
        else timeline.absoluteMs(player.currentMediaItemIndex,player.currentPosition)
    private fun persistNow() { persist(absolute(),speed,transcript) }
    private val listener = object : Player.Listener {
        override fun onIsPlayingChanged(playing: Boolean) {
            isPlaying=playing;positionMs=absolute()
            if(!playing && restored) persistNow()
        }
        override fun onPlaybackStateChanged(state: Int) {
            if(state==Player.STATE_ENDED) {
                if(liveBinding!=null) {
                    positionMs=timeline.availableMs
                    intent.ended(timeline.availableFrames,streamState ?: AudioAvailabilityState.STALE)
                } else {
                    positionMs=player.currentPosition.coerceAtLeast(0)
                    intent.ended(0,AudioAvailabilityState.COMPLETE)
                }
                syncIntent()
            }
        }
        override fun onPlayWhenReadyChanged(playWhenReady: Boolean,reason: Int) {
            if(!playWhenReady) {
                if(reason==Player.PLAY_WHEN_READY_CHANGE_REASON_USER_REQUEST && internalPauseEvents>0) {
                    internalPauseEvents--;return
                }
                val stop = when(reason) {
                    Player.PLAY_WHEN_READY_CHANGE_REASON_AUDIO_FOCUS_LOSS -> PlaybackStopReason.AUDIO_FOCUS
                    Player.PLAY_WHEN_READY_CHANGE_REASON_AUDIO_BECOMING_NOISY -> PlaybackStopReason.NOISY_ROUTE
                    else -> PlaybackStopReason.USER_PAUSE
                }
                if(intent.wantsPlayback || stop!=PlaybackStopReason.USER_PAUSE || intent.lastStopReason==null) intent.stop(stop)
                syncIntent()
            } else if(reason==Player.PLAY_WHEN_READY_CHANGE_REASON_USER_REQUEST && streamState!=AudioAvailabilityState.STALE) {
                intent.play();syncIntent()
            }
        }
        override fun onPlaybackSuppressionReasonChanged(reason: Int) {
            if(reason!=Player.PLAYBACK_SUPPRESSION_REASON_NONE) pause(PlaybackStopReason.AUDIO_FOCUS)
        }
        override fun onPlayerError(problem: PlaybackException) {
            error="Playback stopped. The available audio could not be read."
            pause(PlaybackStopReason.PLAYER_ERROR)
        }
    }
    init {
        RuntimeDiagnostics.configurePlayer(context,episodeId,liveBinding?.jobId,player)
        player.setAudioAttributes(AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_SPEECH).build(),true)
        player.setHandleAudioBecomingNoisy(true)
        player.addListener(listener)
        if(initialStream!=null) {
            require(initialStream.binding.episodeId==episodeId && initialStream.chunks.isNotEmpty())
            if(initialStream.state==AudioAvailabilityState.STALE) error=initialStream.problem ?: "Audio attempt is no longer current"
            player.setMediaItems(initialStream.chunks.map { MediaItem.Builder().setMediaId("${initialStream.binding.jobId}:${it.index}:${it.sha256}").setUri(it.file.toUri()).build() })
        } else player.setMediaItem(MediaItem.fromUri(requireNotNull(file).toUri()))
        player.prepare();player.setPlaybackSpeed(speed)
        seekInternal((saved?.positionMs ?: 0).coerceIn(0,durationMs.coerceAtLeast(0)))
        // No play() here: opening/restoring a player never grants autoplay permission.
    }
    private fun seekInternal(target: Long) {
        if(liveBinding!=null) timeline.location(target)?.let { player.seekTo(it.index,it.localMs) }
        else player.seekTo(target)
        positionMs=target
    }
    fun restore(saved: PlaybackStateEntity?) {
        if(closed) return
        if(!restored && !interacted && saved!=null && saved.episodeId==episodeId) {
            speed=saved.speed;transcript=saved.transcriptVisible;player.setPlaybackSpeed(speed)
            seekInternal(saved.positionMs.coerceIn(0,durationMs.coerceAtLeast(0)));restored=true
        }
    }
    fun update(next: AudioAvailability) {
        if (closed) return
        require(liveBinding!=null)
        if(next.binding!=liveBinding || next.state==AudioAvailabilityState.STALE || next.chunks.size<timeline.chunks.size ||
            next.chunks.take(timeline.chunks.size)!=timeline.chunks) {
            error="This audio attempt changed. Reopen the episode to select its current audio."
            streamState=AudioAvailabilityState.STALE;pause(PlaybackStopReason.STALE_ATTEMPT);return
        }
        val oldCount=timeline.chunks.size
        if(player.playbackState==Player.STATE_ENDED && intent.wantsPlayback && streamState==AudioAvailabilityState.GENERATING)
            intent.ended(timeline.availableFrames,AudioAvailabilityState.GENERATING)
        val resumeAt=intent.appended(next.availableFrames)
        // Prevent ExoPlayer from auto-starting an appended item before the explicit frontier seek.
        // This pause is transport-only, not a change to the user's still-active playback intent.
        if(resumeAt!=null && player.playWhenReady) { internalPauseEvents++;player.pause() }
        timeline=ProgressiveTimeline(next.chunks);availableChunks=next.chunks;stream=next;streamState=next.state;durationMs=next.availableMs
        if(next.chunks.size>oldCount) {
            player.addMediaItems(next.chunks.drop(oldCount).map { MediaItem.Builder().setMediaId("${next.binding.jobId}:${it.index}:${it.sha256}").setUri(it.file.toUri()).build() })
            if(resumeAt!=null && intent.wantsPlayback) { seekInternal(resumeAt);player.play() }
        }
        if(next.state!=AudioAvailabilityState.GENERATING && intent.waitingAtFrame!=null) intent.finalized()
        syncIntent()
    }
    fun tick() {
        if (closed) return
        sleepDeadlineElapsedMs?.let { deadline ->
            if (android.os.SystemClock.elapsedRealtime() >= deadline) {
                sleepMinutes=null;sleepDeadlineElapsedMs=null;pause(PlaybackStopReason.SLEEP)
            }
        }
        positionMs=absolute()
        if(liveBinding==null && player.duration>0) durationMs=player.duration
        syncIntent()
        RuntimeDiagnostics.observePlayer(player, episodeId, liveBinding?.jobId, positionMs, durationMs, wantsPlayback)
    }
    fun markInteraction() { interacted=true;restored=true }
    fun togglePlay() {
        if(closed) return
        markInteraction()
        if(intent.wantsPlayback || player.isPlaying) { pause(PlaybackStopReason.USER_PAUSE);return }
        if(streamState==AudioAvailabilityState.STALE) return
        error=null;intent.play()
        if(player.playbackState==Player.STATE_ENDED) {
            // A paused old tail may now be inside a longer playlist. Play that newly available
            // interval from the saved absolute cursor; do not move the wait frontier past it.
            if(liveBinding!=null && positionMs<timeline.availableMs) seekInternal(positionMs)
            else if(liveBinding!=null && streamState==AudioAvailabilityState.GENERATING) intent.ended(timeline.availableFrames,AudioAvailabilityState.GENERATING)
            else seekInternal(0) // Replay is an explicit action only for a terminal/completed player.
        } else if(liveBinding!=null) seekInternal(positionMs.coerceIn(0,timeline.availableMs))
        player.play();syncIntent()
    }
    fun pause(reason: PlaybackStopReason = PlaybackStopReason.USER_PAUSE) {
        if (closed) return
        intent.stop(reason);syncIntent();player.pause();positionMs=absolute();persistNow()
    }
    fun seek(target: Long) {
        if (closed) return
        markInteraction();intent.seek();seekInternal(target.coerceIn(0,durationMs.coerceAtLeast(0)));syncIntent();persistNow()
    }
    fun adjacentChapter(position: Long,delta: Int): Long? = if(liveBinding==null) null else timeline.adjacentChapter(position,delta)
    fun currentChapterPosition(position: Long): Int? = if(liveBinding==null) null else timeline.chapterStarts().lastOrNull { position>=it.second }?.first ?: timeline.chunks.firstOrNull()?.chapterPosition
    fun cycleSleepTimer() {
        if (closed) return
        sleepMinutes = when { sleepMinutes == null -> 15; requireNotNull(sleepMinutes) <= 15 -> 30; else -> null }
        sleepDeadlineElapsedMs = sleepMinutes?.let { android.os.SystemClock.elapsedRealtime() + it * 60_000L }
    }
    fun restoreSleepDeadline(deadlineElapsedMs: Long?) {
        if (closed) return
        sleepDeadlineElapsedMs=deadlineElapsedMs
        sleepMinutes=deadlineElapsedMs?.let { ((it-android.os.SystemClock.elapsedRealtime()).coerceAtLeast(0)+59_999L).div(60_000L).toInt() }
        tick()
    }
    fun changeSpeed(value: Float) { if(closed) return;markInteraction();speed=value;player.setPlaybackSpeed(value);persistNow() }
    fun showTranscript(value: Boolean) { if(closed) return;markInteraction();transcript=value;persistNow() }
    fun checkpoint() { if(!closed && restored) persistNow() }
    fun close() {
        check(android.os.Looper.myLooper() == player.applicationLooper) { "Player release requires its application looper" }
        if (releaseState.released) return
        closed=true // Reject new controls, but a failed release must remain retryable.
        intent.stop(PlaybackStopReason.CLOSED);syncIntent();isPlaying=false
        releaseState.close(checkpoint = ::persistNow, release = { player.removeListener(listener);player.pause();player.release() })
    }
}
