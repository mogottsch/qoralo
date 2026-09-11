package dev.vibevoice.podcast.runtime

/** State the existing decoded-string contract; the margin is guidance, never an added hard bound/minimum. */
internal fun sourceNotesInstruction(): String =
    "Summarize the supplied source chunk faithfully for later podcast writing. " +
    "The decoded notes string must be nonempty and no longer than ${SourcePreparer.MAX_NOTE_CHARS} characters. " +
    "Aim for at most 1600 characters to leave room below that hard maximum; shorter is fine. " +
    "Keep the key facts, do not pad or invent details, and use less space for a short source. " +
    "Return only valid JSON with properly escaped quotes and newlines: {\"notes\":\"...\"}."

internal fun validatedSourceNotes(value: String): String = value.trim().also { notes ->
    require(notes.isNotBlank() && notes.length <= SourcePreparer.MAX_NOTE_CHARS) { "Gemma returned invalid source notes" }
}
