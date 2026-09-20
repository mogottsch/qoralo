package dev.qoralo.podcast.generation

import dev.qoralo.podcast.data.ChapterDraft
import org.json.JSONObject

internal data class ParsedAgentRevision(val title: String, val chapters: List<ChapterDraft>, val summary: String)

/** Existing strict v1 response parser, shared with diagnostics. No repair or acceptance of extra fields. */
internal fun parseAgentRevision(raw: String): ParsedAgentRevision {
    val json = JSONObject(raw)
    val keys = json.keys().asSequence().toSet()
    require(keys == setOf("schemaVersion", "title", "chapters", "summary")) { "Agent response schema is invalid" }
    require(json.getInt("schemaVersion") == 1) { "Agent response version is unsupported" }
    val array = json.getJSONArray("chapters")
    val chapters = List(array.length()) { index ->
        val chapter = array.getJSONObject(index)
        require(chapter.keys().asSequence().toSet() == setOf("id", "title", "text")) { "Agent chapter schema is invalid" }
        ChapterDraft(chapter.getString("id"), chapter.getString("title"), chapter.getString("text"))
    }
    return ParsedAgentRevision(json.getString("title"), chapters, json.getString("summary"))
}
