package dev.qoralo.podcast.runtime

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class ChapterResponseFormatTest {
    private fun failure(phase: GemmaFailurePhase) =
        GemmaRequestException("chapter", phase, FailureTypeGraph.capture(RuntimeException("private")), RuntimeException("private"))

    @Test fun schemaPinsTheRequestedIdentityAndForbidsExtraFields() {
        val schema = JSONObject(chapterResponseSchema(OutlineChapter("chapter-2", "Mapping It Out", "A plan.")))
        val properties = schema.getJSONObject("properties")
        assertEquals("chapter-2", properties.getJSONObject("id").getString("const"))
        assertEquals("Mapping It Out", properties.getJSONObject("title").getString("const"))
        assertFalse(schema.getBoolean("additionalProperties"))
        assertEquals(setOf("id", "title", "text"), properties.keys().asSequence().toSet())
        assertEquals(1, properties.getJSONObject("text").getInt("minLength"))
        // A grammar cannot guarantee completion, so length is deliberately not constrained.
        assertFalse(properties.getJSONObject("text").has("maxLength"))
    }

    @Test fun schemaEscapesIdentitiesThatWouldOtherwiseBreakTheGrammar() {
        val chapter = OutlineChapter("chapter-\"quoted\"", "Line\nTwo \\ title", "Quoted \"plan\"")
        val properties = JSONObject(chapterResponseSchema(chapter)).getJSONObject("properties")
        assertEquals(chapter.id, properties.getJSONObject("id").getString("const"))
        assertEquals(chapter.title, properties.getJSONObject("title").getString("const"))
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
