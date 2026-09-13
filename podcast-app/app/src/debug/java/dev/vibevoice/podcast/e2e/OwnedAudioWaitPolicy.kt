package dev.vibevoice.podcast.e2e

import dev.vibevoice.podcast.data.GenerationJobEntity
import dev.vibevoice.podcast.data.JobKind
import dev.vibevoice.podcast.data.JobStatus

internal enum class OwnedListenDecision { WAIT, LISTEN, TERMINAL, IDENTITY_CHANGED }

/** Driver-only observation policy. A failed/finished attempt is not a missing-button timeout. */
internal object OwnedAudioWaitPolicy {
    fun listen(episodeId:String,jobId:String,job:GenerationJobEntity?,visible:Boolean):OwnedListenDecision = when {
        job==null || job.id!=jobId || job.episodeId!=episodeId || job.kind!=JobKind.AUDIO -> OwnedListenDecision.IDENTITY_CHANGED
        job.status==JobStatus.FAILED || job.status==JobStatus.COMPLETE -> OwnedListenDecision.TERMINAL
        job.status==JobStatus.RUNNING -> if(visible) OwnedListenDecision.LISTEN else OwnedListenDecision.WAIT
        job.status==JobStatus.QUEUED -> OwnedListenDecision.WAIT
        else -> OwnedListenDecision.IDENTITY_CHANGED
    }
    fun retainRunning(episodeId:String,jobId:String,job:GenerationJobEntity?) =
        job?.episodeId==episodeId && job.id==jobId && job.kind==JobKind.AUDIO && job.status==JobStatus.RUNNING
}
