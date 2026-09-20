package dev.qoralo.podcast.runtime

class SourcePreparer {
    suspend fun prepare(
        sources: List<SourceMaterial>,
        engine: LlmEngine,
        onProgress: suspend (String) -> Unit = {},
    ): List<SourceMaterial> {
        require(sources.isNotEmpty()) { "At least one source is required" }
        var notes = mutableListOf<SourceMaterial>()
        sources.forEachIndexed { sourceIndex, source ->
            val chunks = chunk(source.text)
            chunks.forEachIndexed { chunkIndex, text ->
                onProgress("Reading source ${sourceIndex + 1} of ${sources.size}, part ${chunkIndex + 1} of ${chunks.size}")
                notes += engine.createSourceNotes(SourceMaterial(source.id, source.title, text), chunkIndex, chunks.size)
            }
        }
        var reduction = 0
        while (notes.sumOf { it.text.length } > MAX_PREPARED_CHARS) {
            require(reduction++ < MAX_REDUCTION_ROUNDS) { "Source notes could not fit the Gemma context budget" }
            val groups = pack(notes)
            notes = groups.mapIndexed { index, group ->
                onProgress("Condensing source notes ${index + 1} of ${groups.size}")
                engine.createSourceNotes(
                    SourceMaterial("reduction-$reduction-$index", "Condensed source notes", group.joinToString("\n\n") { "${it.title}: ${it.text}" }),
                    index,
                    groups.size,
                )
            }.toMutableList()
        }
        require(notes.sumOf { it.text.length } <= MAX_PREPARED_CHARS)
        return notes
    }

    fun chunk(text: String): List<String> {
        require(text.isNotBlank())
        val output = mutableListOf<String>()
        var remaining = text.trim()
        while (remaining.isNotEmpty()) {
            if (remaining.length <= MAX_REQUEST_CHARS) {
                output += remaining
                break
            }
            val window = remaining.substring(0, MAX_REQUEST_CHARS)
            val split = maxOf(window.lastIndexOf("\n\n"), window.lastIndexOf('\n'), window.lastIndexOf(' '))
                .takeIf { it >= MAX_REQUEST_CHARS / 2 } ?: MAX_REQUEST_CHARS
            output += remaining.substring(0, split).trim()
            remaining = remaining.substring(split).trimStart()
        }
        require(output.all { it.isNotBlank() && it.length <= MAX_REQUEST_CHARS })
        return output
    }

    private fun pack(notes: List<SourceMaterial>): List<List<SourceMaterial>> {
        val groups = mutableListOf<MutableList<SourceMaterial>>()
        var current = mutableListOf<SourceMaterial>()
        var length = 0
        notes.forEach { note ->
            require(note.text.length <= MAX_NOTE_CHARS)
            val addition = note.title.length + note.text.length + 4
            if (current.isNotEmpty() && length + addition > MAX_REQUEST_CHARS) {
                groups += current; current = mutableListOf(); length = 0
            }
            current += note; length += addition
        }
        if (current.isNotEmpty()) groups += current
        return groups
    }

    companion object {
        const val MAX_REQUEST_CHARS = 12_000
        const val MAX_NOTE_CHARS = 2_000
        const val MAX_PREPARED_CHARS = 8_000
        const val MAX_REDUCTION_ROUNDS = 8
    }
}
