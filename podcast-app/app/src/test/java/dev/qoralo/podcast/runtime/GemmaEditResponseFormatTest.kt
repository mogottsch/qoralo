package dev.qoralo.podcast.runtime

import com.google.ai.edge.litertlm.ResponseFormat
import dev.qoralo.podcast.data.validateCompleteScript
import dev.qoralo.podcast.generation.parseAgentRevision
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class GemmaEditResponseFormatTest {
    private fun JSONArray.strings() = (0 until length()).map(::getString).toSet()
    private fun revision() = JSONObject().put("schemaVersion", 1).put("title", "Title")
        .put("chapters", JSONArray().put(JSONObject().put("id", "c1").put("title", "One").put("text", "A complete chapter.")))
        .put("summary", "Changed the tone")

    @Test fun onlyEditEnablesTheNewResponseConstraint() {
        assertEquals(EDIT_REVISION_JSON_SCHEMA, responseSchemaForMode("edit"))
        for (mode in listOf("source_notes", "outline", "chapter", "unknown")) assertNull(responseSchemaForMode(mode))
        val format = ResponseFormat.json(EDIT_REVISION_JSON_SCHEMA)
        assertEquals(ResponseFormat.Type.JSON_OBJECT, format.type)
        assertEquals(EDIT_REVISION_JSON_SCHEMA, format.schemaOrPattern)
    }

    @Test fun grammarRequiresTheExistingCompleteRevisionShapeIncludingSummary() {
        val schema = JSONObject(EDIT_REVISION_JSON_SCHEMA)
        assertEquals("object", schema.getString("type")); assertFalse(schema.getBoolean("additionalProperties"))
        assertEquals(setOf("schemaVersion", "title", "chapters", "summary"), schema.getJSONArray("required").strings())
        val properties = schema.getJSONObject("properties")
        assertEquals(1, properties.getJSONObject("schemaVersion").getJSONArray("enum").getInt(0))
        val array = properties.getJSONObject("chapters")
        assertEquals(1, array.getInt("minItems")); assertEquals(20, array.getInt("maxItems"))
        val chapter = array.getJSONObject("items")
        assertFalse(chapter.getBoolean("additionalProperties"))
        assertEquals(setOf("id", "title", "text"), chapter.getJSONArray("required").strings())
        assertEquals("string", properties.getJSONObject("summary").getString("type"))
    }

    @Test fun parserDoesNotRepairExtraObjectClosuresOrMissingSummary() {
        val malformed = """{"schemaVersion":1,"title":"Title","chapters":[{"id":"c1","title":"One","text":"Full text"},},{"id":"c2","title":"Two","text":"More text"}],"summary":"Changed"}"""
        assertThrows(JSONException::class.java) { parseAgentRevision(malformed) }
        val missing = revision().apply { remove("summary") }
        assertThrows(IllegalArgumentException::class.java) { parseAgentRevision(missing.toString()) }
        assertThrows(IllegalArgumentException::class.java) { parseAgentRevision(revision().put("patch", true).toString()) }
    }

    @Test fun validEscapedCompleteTextIsPreservedAndSemanticValidationStillApplies() {
        val input = revision(); val text = "He said \"hello\".\nKeep the full line and \\ character."
        input.getJSONArray("chapters").getJSONObject(0).put("text", text)
        val parsed = parseAgentRevision(input.toString()); validateCompleteScript(parsed.title, parsed.chapters)
        assertEquals(text, parsed.chapters.single().text)
        assertThrows(IllegalArgumentException::class.java) { validateCompleteScript(parsed.title, parsed.chapters + parsed.chapters) }
        assertThrows(IllegalArgumentException::class.java) { validateCompleteScript(parsed.title, listOf(parsed.chapters.single().copy(text = "   "))) }
        assertThrows(IllegalArgumentException::class.java) { validateCompleteScript("x".repeat(201), parsed.chapters) }
    }
}
