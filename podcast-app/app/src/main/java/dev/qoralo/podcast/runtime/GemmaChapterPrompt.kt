package dev.qoralo.podcast.runtime

import org.json.JSONObject

/**
 * The spoken-chapter brief.
 *
 * Every chapter is generated in its own fresh conversation, so without an explicit recap the model
 * cannot know the episode already started and re-introduces it. The caller supplies what came before;
 * these rules turn that into continuation rather than repetition.
 */
internal fun singleChapterInstruction(chapter: OutlineChapter, wordCeiling: Int? = null,
    preceding: List<ChapterRecap> = emptyList()): String {
    val schema = JSONObject().put("id", chapter.id).put("title", chapter.title).put("text", "...")
    val budget = wordCeiling ?: CHAPTER_WORD_TARGET
    val length = if (wordCeiling == null) {
        "Aim for about $budget spoken words, and treat ${budget + CHAPTER_WORD_TOLERANCE} as the upper limit. "
    } else {
        "The previous attempt did not finish inside the output budget. Keep this chapter's narration under " +
            "$budget spoken words and bring it to a complete, natural close. This ceiling replaces any longer " +
            "per-chapter word length requested elsewhere; never stop mid-sentence to satisfy it. "
    }
    val continuity = if (preceding.isEmpty()) {
        "This is the opening chapter, so it is the only one that introduces the episode. "
    } else {
        val openings = preceding.map { it.opening }.filter { it.isNotBlank() }
        val leadIns = openings.mapNotNull { Regex("[\\w']+").find(it)?.value?.lowercase() }.distinct()
        "The episode is already under way: chapters " + preceding.joinToString(", ") { JSONObject.quote(it.title) } +
            " have been spoken already. Do NOT welcome or greet the listener, do NOT introduce the episode or its " +
            "topic again, and do NOT summarize what those chapters covered. Continue from where they left off, and " +
            "do not repeat facts, examples or phrasings they already used. " +
            if (openings.isEmpty()) "" else
                "Those chapters opened with " + openings.joinToString(", ", transform = JSONObject::quote) + ". " +
                "Open this chapter differently: reuse none of those words, and do not copy their sentence pattern " +
                "or run-up. Your first word must not be " + leadIns.joinToString(", ", transform = JSONObject::quote) +
                ". Begin on a concrete subject from your own material - a place, person, number, date or event - " +
                "not a conversational lead-in. "
    }
    return "Generate ONLY this one chapter: ${JSONObject.quote(chapter.id)}, titled ${JSONObject.quote(chapter.title)}. " +
        "This is a single-chapter request, not an episode-generation request. " +
        "The episode instructions about the episode title and total chapter count apply to outline planning, not to this response. " +
        "Other outline chapters are context only: do not write them. " +
        continuity +
        "The selected chapter plan is ${JSONObject.quote(chapter.brief)}. " +
        "Cover the material this chapter owns, and leave material assigned to other chapters to them. " +
        "Develop this chapter's brief into complete source-grounded spoken narration; honor the requested audience. " +
        "Write for someone listening while doing something else: conversational, concrete and specific, never a lecture. " +
        "Every fact, name, place, organisation and date must come from the supplied notes. Invent nothing. " +
        "If this chapter asks the listener questions, every question, its answer and any alternative options offered " +
        "must also come from the notes; never invent plausible-sounding options. " +
        length +
        "If the brief has little material, write a shorter chapter instead of padding it: never restate a point you " +
        "have already made in different words, and never stretch one fact across several paragraphs. " +
        "Copy the exact requested chapter ID and matching chapter title shown below. Never use the episode title as the ID. " +
        "The text field must contain only this chapter's narration, with no chapter headings, speaker labels, placeholders or analysis. " +
        "Return only JSON: $schema"
}

/** The tail the next chapter continues from; bounded so continuity never eats the context budget. */
internal fun chapterEnding(text: String, sentences: Int = 2, maxChars: Int = 400): String {
    val trimmed = text.trim()
    if (trimmed.isEmpty()) return ""
    val boundaries = Regex("[.!?]['\"\u201d\u2019]?\\s+").findAll(trimmed).map { it.range.last + 1 }.toList()
    val start = boundaries.getOrNull(boundaries.size - sentences) ?: 0
    return trimmed.substring(start).trim().takeLast(maxChars)
}

/** The run-up a later chapter must not imitate. Bounded: enough to recognise, too little to copy from. */
internal fun chapterOpening(text: String, maxChars: Int = 120): String {
    val trimmed = text.trim()
    if (trimmed.isEmpty()) return ""
    val end = Regex("[.!?]['\"\u201d\u2019]?(\\s|$)").find(trimmed)?.range?.last?.plus(1) ?: trimmed.length
    return trimmed.substring(0, end).trim().take(maxChars)
}
