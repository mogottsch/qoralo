package dev.qoralo.podcast.generation

import dev.qoralo.podcast.data.*
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class AgentEditRequestTest {
    private val revision = ScriptRevisionEntity("base-uuid", "episode", null, 1, "A \"quoted\" title", "hash", "revision.json", 1)
    private val chapters = listOf(
        ChapterEntity("row-1", revision.id, "c1", 0, "One", "Full text with \"quotes\", \\ and\nnewlines. Café.", 30),
        ChapterEntity("row-2", revision.id, "c2", 1, "Two", "Keep this complete narration unchanged.", 30),
    )
    private val message = AgentMessageEntity("message", "episode", AgentRole.USER, "Change the tone, not the facts.", revision.id, null, 2)

    @Test fun sharedRequestIsByteIdenticalToPreviousInlineConstruction() {
        val old = JSONObject().put("schemaVersion", 1).put("baseRevisionId", revision.id)
            .put("instruction", message.text).put("allowedOperations", JSONArray(listOf("rewrite", "shorten", "remove", "split", "combine", "rename")))
            .put("title", revision.title).put("chapters", JSONArray(chapters.map {
                JSONObject().put("id", it.stableChapterId).put("title", it.title).put("text", it.text)
            })).toString()
        assertEquals(old, agentEditRequest(revision, chapters, message))
    }

    @Test fun requestPreservesCompleteTextOriginalBaseIdentityAndChapterOrder() {
        val value = JSONObject(agentEditRequest(revision, chapters, message))
        assertEquals(revision.id, value.getString("baseRevisionId")); assertEquals(message.text, value.getString("instruction"))
        assertEquals(revision.title, value.getString("title"))
        val array = value.getJSONArray("chapters"); assertEquals(chapters.size, array.length())
        chapters.forEachIndexed { i, c ->
            assertEquals(c.stableChapterId, array.getJSONObject(i).getString("id"))
            assertEquals(c.title, array.getJSONObject(i).getString("title"))
            assertEquals(c.text, array.getJSONObject(i).getString("text"))
        }
    }
}
