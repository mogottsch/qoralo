package dev.qoralo.podcast.runtime

import org.json.JSONObject

/** Scope the current call without rewriting output IDs or discarding any returned content. */
internal fun singleChapterInstruction(chapter: OutlineChapter, wordCeiling: Int? = null): String {
    val schema = JSONObject().put("id", chapter.id).put("title", chapter.title).put("text", "...")
    val brevity = if (wordCeiling == null) "" else
        "The previous attempt did not finish inside the output budget. Keep this chapter's narration under " +
            "$wordCeiling spoken words and bring it to a complete, natural close. This ceiling replaces any longer " +
            "per-chapter word length requested elsewhere; never stop mid-sentence to satisfy it. "
    return "Generate ONLY this one chapter: ${JSONObject.quote(chapter.id)}, titled ${JSONObject.quote(chapter.title)}. " +
        "This is a single-chapter request, not an episode-generation request. " +
        "The episode instructions about the episode title and total chapter count apply to outline planning, not to this response. " +
        "Other outline chapters are context only: do not write them. " +
        "The selected chapter plan is ${JSONObject.quote(chapter.brief)}. " +
        "Develop this chapter's brief into complete source-grounded spoken narration; honor the requested audience and per-chapter word length. " +
        "Copy the exact requested chapter ID and matching chapter title shown below. Never use the episode title as the ID. " +
        "The text field must contain only this chapter's narration, with no chapter headings, speaker labels, placeholders or analysis. " +
        brevity +
        "Return only JSON: $schema"
}
