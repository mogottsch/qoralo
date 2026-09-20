package dev.qoralo.podcast.data

/**
 * Whether a stopped episode can simply be attempted again.
 *
 * A retry re-runs the same work from the last durable state: a failed script starts over from the
 * instructions, and a failed audio run starts over from the locked script. Anything that already
 * produced durable content, or that has its own recovery path, is deliberately excluded so the
 * button can never overwrite work the user still has.
 */
fun canRetryFailedGeneration(episode: EpisodeEntity?, job: GenerationJobEntity?): Boolean {
    if (episode == null || job == null) return false
    if (episode.phase != EpisodePhase.FAILED || job.status != JobStatus.FAILED || job.episodeId != episode.id) return false
    return when (job.kind) {
        // The script never reached a saved revision, so re-running cannot discard one.
        JobKind.SCRIPT -> episode.instructions.isNotBlank() &&
            episode.activeRevisionId == null && episode.lockedRevisionId == null && episode.finalAudioPath == null
        // The locked script is still the input; the finished episode must not be rebuilt.
        JobKind.AUDIO -> episode.lockedRevisionId != null && episode.lockedContentHash != null &&
            episode.finalAudioPath == null
        // A failed chat edit has its own recovery; it returns to the saved draft instead.
        else -> false
    }
}
