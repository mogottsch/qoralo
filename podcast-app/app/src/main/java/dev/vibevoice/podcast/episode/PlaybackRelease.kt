package dev.vibevoice.podcast.episode

/** A persistence error must not prevent release; a release error must never prove completion.
 * The owner calls this on the player thread and retains its file lease until released is true.
 */
class PlaybackRelease {
    var released: Boolean = false
        private set

    fun close(checkpoint: () -> Unit, release: () -> Unit) {
        if (released) return
        runCatching(checkpoint) // Best-effort position only; no private error is recorded.
        release() // Propagate failure. A subsequent close must retry this operation.
        released = true
    }
}
