package dev.qoralo.podcast.ui

object InstructionDraftPolicy {
    const val MAX_CHARACTERS = 2_000
    fun appendedHint(current: String, hint: String): String? {
        val candidate = listOf(current.trim(), hint).filter(String::isNotBlank).joinToString("\n")
        return candidate.takeIf { it.length <= MAX_CHARACTERS }
    }
}
