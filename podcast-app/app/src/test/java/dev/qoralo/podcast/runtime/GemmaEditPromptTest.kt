package dev.qoralo.podcast.runtime

import dev.qoralo.podcast.data.ChapterDraft
import dev.qoralo.podcast.data.ScriptCodec
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.ComparisonFailure
import org.junit.Test
import java.security.MessageDigest

class GemmaEditPromptTest {
    @Test fun oldTitleFixtureStillFailsTheSameExactTargetPredicate() {
        val bytes = javaClass.classLoader!!.getResourceAsStream("gemma-ignored-rename-response.txt")!!.readBytes()
        assertEquals("c28ebe4a5f218a74c7356256273353602a7d303a971a3ca0cbee66ef0f7c0fe7",
            MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) })
        val raw = bytes.toString(Charsets.UTF_8)
        val result = JSONObject(raw.substring(raw.indexOf('{'), raw.lastIndexOf('}') + 1))
        assertThrows(ComparisonFailure::class.java) { assertEquals("Short plumbing 54f07f5a checked", result.getString("title")) }
        assertEquals("Short plumbing 54f07f5a", result.getString("title")) // no repair of the captured response
    }
    @Test fun exactNewRootTitleAndEscapingRemainDistinctFromChapterTitles() {
        val requested = "Episode \"quoted\" \\ checked"
        val encoded = ScriptCodec.encode(requested, listOf(ChapterDraft("chapter-1", "Unchanged chapter title", "Complete short narration.")))
        val result = JSONObject(encoded)
        assertEquals(requested, result.getString("title"))
        assertEquals("Unchanged chapter title", result.getJSONArray("chapters").getJSONObject(0).getString("title"))
    }
    @Test fun editInstructionDistinguishesStoredBaseFromEditableNewFields() {
        assertTrue(SCRIPT_EDIT_INSTRUCTION.contains("instruction is authoritative"))
        assertTrue(SCRIPT_EDIT_INSTRUCTION.contains("CURRENT EPISODE title"))
        assertTrue(SCRIPT_EDIT_INSTRUCTION.contains("NEW EPISODE title"))
        assertTrue(SCRIPT_EDIT_INSTRUCTION.contains("including its suffix and punctuation"))
        assertTrue(SCRIPT_EDIT_INSTRUCTION.contains("Chapter titles are separate"))
        assertTrue(SCRIPT_EDIT_INSTRUCTION.contains("OLD stored revision must remain unchanged"))
        assertTrue(SCRIPT_EDIT_INSTRUCTION.contains("do not claim a rename when the title stayed the same"))
    }
}
