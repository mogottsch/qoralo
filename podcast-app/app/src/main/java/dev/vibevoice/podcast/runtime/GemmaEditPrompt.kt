package dev.vibevoice.podcast.runtime

/** The saved base stays immutable; requested fields in the NEW response must change. */
internal const val SCRIPT_EDIT_INSTRUCTION =
    "Apply the instruction to create a NEW complete script revision. The instruction is authoritative. " +
    "The input top-level title is the CURRENT EPISODE title; the returned top-level title is the NEW EPISODE title. " +
    "If the instruction requests an episode rename, copy that requested new title EXACTLY, including its suffix and punctuation; do not copy the old title instead. " +
    "Chapter titles are separate from the top-level episode title. " +
    "An immutable base means the OLD stored revision must remain unchanged, not that requested fields in the NEW output must keep their old values. " +
    "Keep fields the instruction does not ask to change. Return the full new revision, not a patch. " +
    "The summary must describe actual differences in your returned fields; do not claim a rename when the title stayed the same. " +
    "Return only JSON: {\"schemaVersion\":1,\"title\":\"new episode title\",\"chapters\":[{\"id\":\"...\",\"title\":\"chapter title\",\"text\":\"...\"}],\"summary\":\"actual changes\"}."
