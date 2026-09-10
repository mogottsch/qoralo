package dev.vibevoice.podcast.e2e

import android.content.Context
import dev.vibevoice.podcast.PodcastApplication
import dev.vibevoice.podcast.data.*
import org.json.JSONArray
import org.json.JSONObject

/** Validation only: never constructs/inserts a draft or supplies text to a model. */
internal object ShortContinuationPolicy {
    const val CONTRACT_SHA = "2f22bd6e500eca3f45e51c401aded0cd570bc576e8f805063f95d6dd02d23721"
    const val EPISODE_ID = "ba099f63-74da-43c5-96a1-27eb84251da4"
    const val REVISION_ID = "f48e7ea3-62cf-4afc-9b17-2cc6659c6e5a"
    const val CONTENT_HASH = "c1c9d30a1d1264e5c212b53d53d5b014b1900c56b87945174fbd24f4aeb2c2b5"
    const val DRIVER_MS = 360_000L
    fun load(context: Context): JSONObject {
        ShortProductPolicy.load(context)
        val raw = context.assets.open("short-product-continuation/contract.json").use { it.readBytes() }
        require(ShortProductPolicy.hash(raw) == CONTRACT_SHA)
        return JSONObject(raw.toString(Charsets.UTF_8))
    }
    fun validateText(chapters: List<ChapterEntity>, contract: JSONObject) {
        ShortProductPolicy.validateFinal(chapters.map { it.stableChapterId to it.text }, enforceWordTarget = false)
        val expected = contract.getJSONArray("chapters")
        chapters.forEachIndexed { index, chapter ->
            val pin = expected.getJSONObject(index)
            require(chapter.revisionId == REVISION_ID && chapter.position == index)
            require(chapter.stableChapterId == pin.getString("id") && chapter.title == pin.getString("title"))
            require(ShortProductPolicy.hash(chapter.text.toByteArray()) == pin.getString("textSha256")) { "Stored real chapter differs from reviewed prior output" }
        }
    }
    suspend fun validateStored(context: Context, locked: Boolean): Pair<ScriptRevisionEntity, List<ChapterEntity>> {
        val contract = load(context)
        val app = context.applicationContext as PodcastApplication
        val episode = app.repository.episode(EPISODE_ID)
        val (revision, chapters) = app.repository.activeRevision(EPISODE_ID)
        require(episode.reviewEnabled && episode.activeRevisionId == REVISION_ID && episode.title == contract.getString("title"))
        require(ShortProductPolicy.hash(episode.instructions.toByteArray()) == contract.getString("instructionsSha256"))
        require(revision.id == REVISION_ID && revision.contentHash == CONTENT_HASH && revision.episodeId == EPISODE_ID)
        require(revision.baseRevisionId == contract.getString("baseRevisionId") && revision.revisionNumber == 2)
        require(ShortProductPolicy.hash(app.repository.resolveArtifact(revision.relativePath).readBytes()) == CONTENT_HASH)
        val base = requireNotNull(app.database.podcastDao().revision(contract.getString("baseRevisionId")))
        require(base.episodeId == EPISODE_ID && base.contentHash == contract.getString("baseContentHash"))
        require(ShortProductPolicy.hash(app.repository.resolveArtifact(base.relativePath).readBytes()) == base.contentHash)
        val sources = app.database.podcastDao().sources(EPISODE_ID)
        val pins = contract.getJSONArray("sources"); require(sources.size == pins.length())
        sources.forEachIndexed { index, source ->
            val pin = pins.getJSONObject(index)
            require(source.id == pin.getString("id") && source.relativePath == pin.getString("relativePath") && source.sha256 == pin.getString("sha256"))
            val file = app.repository.resolveArtifact(source.relativePath)
            require(file.length() == pin.getLong("byteCount") && ShortProductPolicy.hash(file.readBytes()) == source.sha256)
        }
        if (locked) require(episode.lockedRevisionId == REVISION_ID && episode.lockedContentHash == CONTENT_HASH)
        else require(episode.phase == EpisodePhase.SCRIPT_DRAFT && episode.lockedRevisionId == null && episode.finalAudioPath == null)
        val prior = contract.getJSONObject("priorJobs")
        for (kind in listOf(JobKind.SCRIPT, JobKind.AGENT_EDIT)) {
            val job = requireNotNull(app.database.podcastDao().job(prior.getString(kind)))
            require(job.episodeId == EPISODE_ID && job.kind == kind && job.status == JobStatus.COMPLETE)
        }
        validateText(chapters, contract)
        return revision to chapters
    }
    fun wordReport(chapters: List<ChapterEntity>) = JSONArray(chapters.map {
        val count = it.text.trim().split(Regex("\\s+")).size
        JSONObject().put("id", it.stableChapterId).put("words", count).put("target", JSONArray(listOf(20,25)))
            .put("targetMet", count in 20..25).put("wordTargetIsValidityGate", false)
    })
}
