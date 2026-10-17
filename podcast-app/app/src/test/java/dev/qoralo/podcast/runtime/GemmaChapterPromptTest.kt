package dev.qoralo.podcast.runtime

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.security.MessageDigest

class GemmaChapterPromptTest {
    private val chapter = OutlineChapter("chapter-2", "Returning Your Book", "Use the return slot.")

    @Test fun requestedChapterIdentityIsConcreteNotEpisodeOrPlaceholder() {
        val text = singleChapterInstruction(OutlineChapter("chapter-2", "Returning Your Book", "Use the return slot."))
        val schema = JSONObject(text.substringAfter("Return only JSON: "))
        assertEquals(setOf("id", "title", "text"), schema.keys().asSequence().toSet())
        assertEquals("chapter-2", schema.getString("id"))
        assertEquals("Returning Your Book", schema.getString("title"))
        assertFalse(text.contains("requested id"))
    }

    @Test fun identityTitleAndBriefEscapingCannotBreakTheExample() {
        val awkward = OutlineChapter("chapter-\"quoted\"", "Line\nTwo \\ title", "Quoted \"plan\"\nnext")
        val text = singleChapterInstruction(awkward)
        val schema = JSONObject(text.substringAfter("Return only JSON: "))
        assertEquals(awkward.id, schema.getString("id")); assertEquals(awkward.title, schema.getString("title"))
        assertTrue(text.contains(JSONObject.quote(awkward.brief)))
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

    @Test fun onlyTheOpeningChapterIntroducesTheEpisode() {
        val first = singleChapterInstruction(chapter)
        assertTrue(first.contains("This is the opening chapter"))
        assertFalse(first.contains("Do NOT welcome"))

        val later = singleChapterInstruction(chapter, preceding = listOf(ChapterRecap("One", "It ended here.")))
        assertTrue(later.contains("Do NOT welcome or greet the listener"))
        assertTrue(later.contains("do NOT introduce the episode"))
        assertTrue(later.contains("do not repeat facts, examples or phrasings"))
        assertFalse(later.contains("This is the opening chapter"))
    }

    @Test fun everySpokenChapterTitleIsNamedSoTheModelKnowsWhatCameBefore() {
        val prompt = singleChapterInstruction(chapter,
            preceding = listOf(ChapterRecap("Arrivals"), ChapterRecap("Departures", "We left at dawn.")))
        assertTrue(prompt.contains("\"Arrivals\""))
        assertTrue(prompt.contains("\"Departures\""))
    }

    @Test fun earlierOpeningsAreQuotedBackSoTheNextChapterStartsDifferently() {
        val prompt = singleChapterInstruction(chapter, preceding = listOf(
            ChapterRecap("One", opening = "So, let's talk about Sandyford."),
            ChapterRecap("Two", "It ended here.", "Moving on to the community side.")))
        assertTrue(prompt.contains("\"So, let's talk about Sandyford.\""))
        assertTrue(prompt.contains("\"Moving on to the community side.\""))
        assertTrue(prompt.contains("Open this chapter differently"))
        assertTrue(prompt.contains("do not copy their sentence pattern"))
        // The actual lead-in words used so far are excluded by name, derived from the run, not a fixed list.
        assertTrue(prompt.contains("Your first word must not be \"so\", \"moving\""))
        assertTrue(prompt.contains("Begin on a concrete subject"))
        // Nothing is banned globally; only what previous chapters actually used is excluded.
        val fresh = singleChapterInstruction(chapter, preceding = listOf(ChapterRecap("One")))
        assertFalse(fresh.contains("Open this chapter differently"))
    }

    @Test fun theQuotedOpeningIsOneBoundedSentence() {
        val text = "So, let's talk about Sandyford. It is a suburb of Dublin. More follows here."
        assertEquals("So, let's talk about Sandyford.", chapterOpening(text))
        assertEquals("", chapterOpening("   "))
        assertTrue(chapterOpening("word ".repeat(200)).length <= 120)
        assertEquals("Only one sentence", chapterOpening("Only one sentence"))
    }

    @Test fun theFirstAttemptCarriesATargetAndARetryCarriesAStrictlyLowerCeiling() {
        val first = singleChapterInstruction(chapter, chapterWordCeiling(1))
        assertTrue(first.contains("about $CHAPTER_WORD_TARGET spoken words"))
        assertTrue(first.contains("${CHAPTER_WORD_TARGET + CHAPTER_WORD_TOLERANCE} as the upper limit"))

        val second = singleChapterInstruction(chapter, chapterWordCeiling(2))
        assertTrue(second.contains("under 240 spoken words"))
        assertFalse(second.contains("about $CHAPTER_WORD_TARGET spoken words"))
        // Each retry must ask for less than the attempt that overran, never more.
        assertTrue(requireNotNull(chapterWordCeiling(2)) < CHAPTER_WORD_TARGET)
        assertTrue(requireNotNull(chapterWordCeiling(3)) < requireNotNull(chapterWordCeiling(2)))
    }

    @Test fun thinMaterialMustShortenTheChapterAndFactsMustComeFromTheNotes() {
        val prompt = singleChapterInstruction(chapter)
        assertTrue(prompt.contains("write a shorter chapter instead of padding it"))
        assertTrue(prompt.contains("never restate a point you have already made"))
        assertTrue(prompt.contains("Every fact, name, place, organisation and date must come from the supplied notes"))
        // The trivia chapter invented plausible decoys; options are held to the same source rule.
        assertTrue(prompt.contains("never invent plausible-sounding options"))
        assertTrue(prompt.contains("listening while doing something else"))
    }

    @Test fun theRecapKeepsOnlyABoundedTailOfThePreviousChapter() {
        val text = "First sentence here. Second sentence follows! Third sentence ends the chapter?"
        assertEquals("Second sentence follows! Third sentence ends the chapter?", chapterEnding(text))
        assertEquals("Third sentence ends the chapter?", chapterEnding(text, sentences = 1))
        assertEquals("", chapterEnding("   "))
        // A single unpunctuated block still yields a bounded tail rather than the whole chapter.
        val long = "word ".repeat(400)
        assertTrue(chapterEnding(long).length <= 400)
        assertTrue(chapterEnding(text, maxChars = 12).length <= 12)
    }
}
