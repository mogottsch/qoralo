package dev.qoralo.podcast.runtime

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class ChapterResponseFormatTest {
    private fun failure(phase: GemmaFailurePhase) =
        GemmaRequestException("chapter", phase, FailureTypeGraph.capture(RuntimeException("private")), RuntimeException("private"))

    @Test fun schemaUsesOnlyConstructsTheShippedEditSchemaAlreadyProves() {
        val schema = JSONObject(chapterResponseSchema(OutlineChapter("chapter-2", "Mapping It Out", "A plan.")))
        val properties = schema.getJSONObject("properties")
        assertFalse(schema.getBoolean("additionalProperties"))
        assertEquals(setOf("id", "title", "text"), properties.keys().asSequence().toSet())
        val edit = JSONObject(EDIT_REVISION_JSON_SCHEMA)
        fun keywords(node: Any?, into: MutableSet<String>): Set<String> {
            if (node is JSONObject) node.keys().forEach { key -> into += key; keywords(node.get(key), into) }
            return into
        }
        // A construct the runtime refuses fails the request at SEND, so stay inside the proven vocabulary.
        assertTrue(keywords(schema, mutableSetOf()).minus(keywords(edit, mutableSetOf())).isEmpty())
        for (field in listOf("id", "title", "text")) {
            assertEquals(1, properties.getJSONObject(field).getInt("minLength"))
            assertFalse(properties.getJSONObject(field).has("const"))
        }
        // A grammar cannot guarantee completion, so length is deliberately not constrained.
        assertFalse(properties.getJSONObject("text").has("maxLength"))
    }

    @Test fun schemaEscapesIdentitiesThatWouldOtherwiseBreakTheGrammar() {
        val chapter = OutlineChapter("chapter-\"quoted\"", "Line\nTwo \\ title", "Quoted \"plan\"")
        // Identity is carried by the prompt and re-checked by the caller, never embedded in the grammar.
        val schema = JSONObject(chapterResponseSchema(chapter))
        assertFalse(schema.toString().contains("quoted"))
        assertEquals("string", schema.getJSONObject("properties").getJSONObject("id").getString("type"))
    }

    @Test fun onlyChapterModeGetsTheChapterSchemaThroughTheModeSeam() {
        assertNull(responseSchemaForMode("chapter"))
        assertNull(responseSchemaForMode("outline"))
        assertNull(responseSchemaForMode("source_notes"))
        assertEquals(EDIT_REVISION_JSON_SCHEMA, responseSchemaForMode("edit"))
    }

    @Test fun laterAttemptsAskForShorterChaptersInsteadOfResamplingTheSameRequest() {
        assertNull(chapterWordCeiling(1))
        assertEquals(500, chapterWordCeiling(2))
        assertEquals(300, chapterWordCeiling(3))
        assertEquals(300, chapterWordCeiling(CHAPTER_ATTEMPTS))
    }

    @Test fun brevityAppearsOnlyOnRetryAndNeverDisturbsTheReturnedExample() {
        val chapter = OutlineChapter("chapter-2", "Mapping It Out", "A plan.")
        val first = singleChapterInstruction(chapter)
        val second = singleChapterInstruction(chapter, chapterWordCeiling(2))
        assertFalse(first.contains("500 spoken words"))
        assertTrue(second.contains("under 500 spoken words"))
        assertTrue(second.contains("never stop mid-sentence"))
        // The trailing JSON example stays parseable and identical for every attempt.
        assertEquals(first.substringAfter("Return only JSON: "), second.substringAfter("Return only JSON: "))
        assertEquals("chapter-2", JSONObject(second.substringAfter("Return only JSON: ")).getString("id"))
    }

    @Test fun onlyUnfinishedResponsesRetryAndTheAttemptBudgetIsFixed() {
        assertTrue(shouldRetryChapter(failure(GemmaFailurePhase.JSON_PARSE), 1))
        assertTrue(shouldRetryChapter(failure(GemmaFailurePhase.JSON_EXTRACTION), 2))
        assertFalse(shouldRetryChapter(failure(GemmaFailurePhase.JSON_PARSE), CHAPTER_ATTEMPTS))
        for (phase in listOf(GemmaFailurePhase.CONVERSATION_CREATE, GemmaFailurePhase.SEND, GemmaFailurePhase.CONVERSATION_CLOSE)) {
            assertFalse(shouldRetryChapter(failure(phase), 1))
        }
    }

    @Test fun exhaustedRetriesStillReportTheOriginalStructuredFailure() {
        val error = failure(GemmaFailurePhase.JSON_PARSE)
        assertFalse(shouldRetryChapter(error, CHAPTER_ATTEMPTS))
        assertTrue(generationFailureMessage(error).contains("failed at JSON_PARSE"))
        assertFalse(generationFailureMessage(error).contains("private"))
    }
}
