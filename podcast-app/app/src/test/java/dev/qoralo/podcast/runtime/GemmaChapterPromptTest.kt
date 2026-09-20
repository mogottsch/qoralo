package dev.qoralo.podcast.runtime

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.security.MessageDigest

class GemmaChapterPromptTest {
    @Test fun requestedChapterIdentityIsConcreteNotEpisodeOrPlaceholder() {
        val text = singleChapterInstruction(OutlineChapter("chapter-2", "Returning Your Book", "Use the return slot."))
        val schema = JSONObject(text.substringAfter("Return only JSON: "))
        assertEquals(setOf("id", "title", "text"), schema.keys().asSequence().toSet())
        assertEquals("chapter-2", schema.getString("id"))
        assertEquals("Returning Your Book", schema.getString("title"))
        assertFalse(text.contains("requested id"))
    }
    @Test fun identityTitleAndBriefEscapingCannotBreakTheExample() {
        val chapter = OutlineChapter("chapter-\"quoted\"", "Line\nTwo \\ title", "Quoted \"plan\"\nnext")
        val text = singleChapterInstruction(chapter)
        val schema = JSONObject(text.substringAfter("Return only JSON: "))
        assertEquals(chapter.id, schema.getString("id")); assertEquals(chapter.title, schema.getString("title"))
        assertTrue(text.contains(JSONObject.quote(chapter.brief)))
    }
    @Test fun singleChapterTaskOverridesGlobalPlanningWithoutEditingSavedFailure() {
        val prompt = singleChapterInstruction(OutlineChapter("chapter-1", "Checking Before Borrowing", "Check the label."))
        assertTrue(prompt.contains("Generate ONLY this one chapter"))
        assertTrue(prompt.contains("episode title and total chapter count apply to outline planning, not to this response"))
        assertTrue(prompt.contains("Other outline chapters are context only: do not write them"))
        assertTrue(prompt.contains("no chapter headings"))
        val raw = javaClass.classLoader!!.getResourceAsStream("gemma-wrong-whole-episode-response.txt")!!.readBytes()
        assertEquals("4491ff363c66fed4765e060654112ccbfe9a33f7ebf4cbc957062dda0a3b7206",
            MessageDigest.getInstance("SHA-256").digest(raw).joinToString("") { "%02x".format(it) })
    }
}
