package dev.vibevoice.podcast.data

private val CHAPTER_ID = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,127}")

/** Existing repository admission checks, also usable without persistence by the one-response diagnostic. */
internal fun validateCompleteScript(title: String, chapters: List<ChapterDraft>) {
    require(title.isNotBlank() && title.length <= 200) { "Invalid episode title" }
    require(chapters.size in 1..20) { "A script must contain 1–20 complete chapters" }
    require(chapters.map { it.stableId }.toSet().size == chapters.size) { "Chapter IDs must be unique" }
    chapters.forEach {
        require(CHAPTER_ID.matches(it.stableId)) { "Invalid chapter ID" }
        require(it.title.isNotBlank() && it.title.length <= 200) { "Invalid chapter title" }
        require(it.text.isNotBlank() && it.text.length <= 100_000) { "Invalid complete chapter transcript" }
    }
}
