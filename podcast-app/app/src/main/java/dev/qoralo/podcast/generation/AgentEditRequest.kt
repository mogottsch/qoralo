package dev.qoralo.podcast.generation

import dev.qoralo.podcast.data.AgentMessageEntity
import dev.qoralo.podcast.data.ChapterEntity
import dev.qoralo.podcast.data.ScriptRevisionEntity
import org.json.JSONArray
import org.json.JSONObject

/** The existing v1 request, shared by normal editing and exact saved-input diagnostics. No text changes. */
internal fun agentEditRequest(revision: ScriptRevisionEntity, chapters: List<ChapterEntity>, message: AgentMessageEntity): String =
    JSONObject()
        .put("schemaVersion", 1)
        .put("baseRevisionId", revision.id)
        .put("instruction", message.text)
        .put("allowedOperations", JSONArray(listOf("rewrite", "shorten", "remove", "split", "combine", "rename")))
        .put("title", revision.title)
        .put("chapters", JSONArray(chapters.map {
            JSONObject().put("id", it.stableChapterId).put("title", it.title).put("text", it.text)
        })).toString()
