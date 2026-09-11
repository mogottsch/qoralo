package dev.vibevoice.podcast.data

/** UI eligibility only; the repository additionally verifies current ownership, files and idle jobs. */
fun canReturnToSavedDraft(episode: EpisodeEntity?, job: GenerationJobEntity?): Boolean =
    episode != null && job != null && episode.phase == EpisodePhase.FAILED &&
        episode.activeRevisionId != null && episode.lockedRevisionId == null &&
        episode.lockedContentHash == null && episode.lockedAtEpochMs == null &&
        episode.finalAudioPath == null && episode.finalAudioSha256 == null && episode.finalAudioByteCount == null &&
        episode.timelinePath == null && episode.timelineSha256 == null && episode.timelineByteCount == null && episode.durationMs == null &&
        job.episodeId == episode.id && job.kind == JobKind.AGENT_EDIT && job.status == JobStatus.FAILED &&
        job.requestedRevisionId == episode.activeRevisionId && job.requestMessageId != null
