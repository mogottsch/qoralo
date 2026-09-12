package dev.vibevoice.podcast.ui

import dev.vibevoice.podcast.runtime.AudioAvailabilityState
import dev.vibevoice.podcast.runtime.AvailableAudioChunk

/** No player side effects here. Absolute time is derived from cumulative PCM frames, never summed rounded item durations. */
class ProgressiveTimeline(val chunks: List<AvailableAudioChunk>) {
    val availableFrames: Long get() = chunks.lastOrNull()?.endFrame ?: 0
    val availableMs: Long get() = availableFrames * 1000 / 44100
    fun absoluteMs(item: Int, localMs: Long): Long {
        val chunk=chunks.getOrNull(item) ?: return 0
        return (chunk.startFrame * 1000 / 44100 + localMs.coerceAtLeast(0)).coerceAtMost(chunk.endFrame * 1000 / 44100)
    }
    data class Location(val index: Int, val localMs: Long)
    fun location(positionMs: Long): Location? {
        if(chunks.isEmpty()) return null
        val target=positionMs.coerceIn(0,availableMs)
        val index=chunks.indexOfLast { it.startFrame * 1000 / 44100 <= target }.coerceAtLeast(0)
        return Location(index,(target-chunks[index].startFrame*1000/44100).coerceAtLeast(0))
    }
    fun chapterStarts(): List<Pair<Int,Long>> = chunks.distinctBy { it.chapterPosition }.map { it.chapterPosition to it.speechStartFrame*1000/44100 }
    fun adjacentChapter(position: Long, delta: Int): Long? {
        val starts=chapterStarts();if(starts.isEmpty()) return null
        val current=starts.indexOfLast { it.second <= position }.coerceAtLeast(0)
        val target=current+delta
        return starts.getOrNull(target)?.second?.takeIf { it <= availableMs }
    }
}

enum class PlaybackStopReason { USER_PAUSE, SLEEP, AUDIO_FOCUS, NOISY_ROUTE, CLOSED, STALE_ATTEMPT, PLAYER_ERROR }

/** Waiting at a live frontier is NOT permission to restart at0 and is NOT an explicit pause. */
class ProgressivePlaybackIntent {
    var wantsPlayback: Boolean = false
        private set
    var waitingAtFrame: Long? = null
        private set
    var lastStopReason: PlaybackStopReason? = null
        private set
    fun play() { wantsPlayback=true;lastStopReason=null }
    fun stop(reason: PlaybackStopReason) { wantsPlayback=false;waitingAtFrame=null;lastStopReason=reason }
    fun ended(availableFrames: Long,state: AudioAvailabilityState) {
        waitingAtFrame = if(wantsPlayback && state==AudioAvailabilityState.GENERATING) availableFrames else null
        if(state!=AudioAvailabilityState.GENERATING) wantsPlayback=false
    }
    fun appended(availableFrames: Long): Long? {
        val boundary=waitingAtFrame ?: return null
        if(!wantsPlayback || availableFrames<=boundary) return null
        waitingAtFrame=null
        return boundary*1000/44100 // Explicit adapter seek to the next item at the old absolute frontier.
    }
    fun seek() { waitingAtFrame=null }
    fun isWaiting(state: AudioAvailabilityState): Boolean = wantsPlayback && waitingAtFrame!=null && state==AudioAvailabilityState.GENERATING
    fun finalized() { if(waitingAtFrame!=null) wantsPlayback=false;waitingAtFrame=null } // No seek or player recreation.
}
