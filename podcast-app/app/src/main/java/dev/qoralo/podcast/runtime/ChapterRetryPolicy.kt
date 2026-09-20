package dev.qoralo.podcast.runtime

/**
 * Bounded retry policy for one chapter request.
 *
 * Chapter generation is decoded under a JSON grammar, so a malformed envelope cannot be produced. The
 * remaining way a response fails to parse is an unfinished one: generation stopped at the output ceiling.
 * A different sampler cannot fix that, so each further attempt asks for a shorter chapter instead.
 */
internal const val CHAPTER_ATTEMPTS = 3

internal val RETRIABLE_CHAPTER_PHASES = setOf(GemmaFailurePhase.JSON_EXTRACTION, GemmaFailurePhase.JSON_PARSE)

/**
 * Escalating completion budget. Attempt 1 uses the ordinary per-chapter target; later attempts apply
 * only after a previous attempt did not finish inside the output ceiling, and must be shorter than it.
 */
internal const val CHAPTER_WORD_TARGET = 300
internal const val CHAPTER_WORD_TOLERANCE = 60

internal fun chapterWordCeiling(attempt: Int): Int? = when {
    attempt <= 1 -> null
    attempt == 2 -> 240
    else -> 180
}

/** Only an unparsed (unfinished) response is retried, and never beyond the fixed attempt budget. */
internal fun shouldRetryChapter(error: GemmaRequestException, attempt: Int, attempts: Int = CHAPTER_ATTEMPTS): Boolean =
    attempt < attempts && error.failurePhase in RETRIABLE_CHAPTER_PHASES
