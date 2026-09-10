package dev.vibevoice.podcast.gallery

internal data class GallerySemanticValue(val text: String?, val description: String?, val enabled: Boolean)

/** Match existing production UI, never a synthetic marker node. Ownership alone cannot prove freshness. */
internal object GalleryFrameContent {
    private val landmarks = mapOf(
        "library" to listOf("CONTINUE LISTENING", "Why cities remember rivers"),
        "library-empty" to listOf("Your first episode", "Create an episode"),
        "sources" to listOf("Add sources", "Continue"),
        "sources-empty" to listOf("Add sources", "Continue"),
        "paste" to listOf("Paste text", "Source name", "Add source"),
        "instructions" to listOf("Initial instructions", "Create"),
        "review" to listOf("Review script", "Edit with agent"),
        "agent" to listOf("Edit the script", "Ask for a change…"),
        "agent-error" to listOf("Edit the script", "Change wasn’t applied"),
        "lock" to listOf("Ready to create audio?", "Lock & create"),
        "generating" to listOf("Creating episode", "Creating What flooding remembers"),
        "script-loading" to listOf("Creating episode", "Writing the complete chapter"),
        "failure" to listOf("Episode stopped", "Generation couldn’t finish"),
        "player" to listOf("Now playing", "Playback position"),
        "transcript" to listOf("Frozen chapter transcript", "Close transcript"),
    )

    fun problems(frame: String, values: List<GallerySemanticValue>): List<String> = buildList {
        val expected = requireNotNull(landmarks[frame]) { "Unknown gallery frame" }
        val strings = values.flatMap { listOfNotNull(it.text, it.description) }
        for (text in expected) if (strings.none { it == text }) add("Missing production landmark: $text")
        if (frame == "sources" || frame == "sources-empty") {
            val enabled = frame == "sources"
            if (values.none { it.text == "Continue" && it.enabled == enabled }) add("Continue enabled state must be $enabled")
        }
        if (frame == "agent" && strings.any { it == "Change wasn’t applied" }) add("Unexpected failed-edit content in agent frame")
    }
}
