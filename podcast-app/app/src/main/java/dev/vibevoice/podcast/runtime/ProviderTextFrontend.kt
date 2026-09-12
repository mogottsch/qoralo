package dev.vibevoice.podcast.runtime

/** Port of supertonic-py1.3.1 (908a5648): raw grouping FIRST, then global NFKD/provider processing. */
object ProviderTextFrontend {
    const val VERSION = "supertonic-py-1.3.1-en-v1"
    const val TARGET_CODEPOINTS = 300
    private const val SPACE_CLASS = "[\\u0009-\\u000D\\u001C-\\u0020\\u0085\\u00A0\\u1680\\u2000-\\u200A\\u2028\\u2029\\u202F\\u205F\\u3000]"
    private val spaces = Regex("$SPACE_CLASS+")
    private val paragraphs = Regex("\\n$SPACE_CLASS*\\n+")
    private val abbreviations = listOf("Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "Sr.", "Jr.", "Ph.D.", "etc.", "e.g.", "i.e.", "vs.", "Inc.", "Ltd.", "Co.", "Corp.", "St.", "Ave.", "Blvd.")
    private val symbols = listOf(
        "–" to "-", "‑" to "-", "—" to "-", "¯" to " ", "_" to " ",
        "“" to "\"", "”" to "\"", "‘" to "'", "’" to "'", "´" to "'", "`" to "'",
        "[" to " ", "]" to " ", "|" to " ", "/" to " ", "#" to " ", "→" to " ", "←" to " ",
    )
    private val terminal = ".!?;:,'\")]}…。」』】〉》›»".codePoints().toArray().toSet()
    private val duplicateQuotes = Regex("([\"'`])\\1+")

    data class Segment(val raw: String, val processed: String, val ids: LongArray) {
        val textExtent: Int get() = ids.size
    }

    fun isPythonSpace(cp: Int): Boolean = cp in 9..13 || cp in 0x1c..0x20 || cp == 0x85 || cp == 0xa0 || cp == 0x1680 ||
        cp in 0x2000..0x200a || cp in setOf(0x2028, 0x2029, 0x202f, 0x205f, 0x3000)
    private fun strip(value: String) = value.trim { isPythonSpace(it.code) }
    private fun count(value: String) = value.codePointCount(0, value.length)
    private fun pythonWord(cp: Int): Boolean = ProviderUnicode14.isWord(cp)
    private fun sentenceBoundary(value: String, whitespaceStart: Int): Boolean {
        if (whitespaceStart == 0 || value[whitespaceStart - 1] !in ".!?") return false
        if (abbreviations.any { whitespaceStart >= it.length && value.regionMatches(whitespaceStart - it.length, it, 0, it.length) }) return false
        if (whitespaceStart >= 2 && value[whitespaceStart - 1] == '.' && value[whitespaceStart - 2] in 'A'..'Z') {
            val letter = whitespaceStart - 2
            if (letter == 0 || !pythonWord(value.codePointBefore(letter))) return false
        }
        return true
    }
    private fun sentences(paragraph: String): List<String> {
        val result = mutableListOf<String>(); var start = 0
        spaces.findAll(paragraph).forEach { match ->
            if (sentenceBoundary(paragraph, match.range.first)) {
                result += paragraph.substring(start, match.range.first)
                start = match.range.last + 1
            }
        }
        result += paragraph.substring(start)
        return result
    }

    /** Target is not a hard cap. An overlong sentence is kept intact; never split at words/commas. */
    fun segmentRaw(text: String, target: Int = TARGET_CODEPOINTS): List<String> {
        require(target >= 10) { "Provider segment target must be at least 10" }
        val output = mutableListOf<String>()
        paragraphs.split(strip(text)).forEach { rawParagraph ->
            val paragraph = strip(rawParagraph)
            if (paragraph.isNotEmpty()) {
                var current = ""
                sentences(paragraph).forEach { sentence ->
                    val value = strip(sentence)
                    if (value.isNotEmpty()) {
                        if (count(current) + count(value) + 1 <= target) current += (if (current.isEmpty()) "" else " ") + value
                        else {
                            if (current.isNotEmpty()) output += strip(current)
                            current = value
                        }
                    }
                }
                if (strip(current).isNotEmpty()) output += strip(current)
            }
        }
        val original = text.codePoints().toArray().filterNot(::isPythonSpace)
        val grouped = output.flatMap { it.codePoints().toArray().filterNot(::isPythonSpace) }
        check(original == grouped) { "Provider segmentation changed source content/order" }
        return output
    }

    data class SourceSpan(val raw: String, val startUtf16: Int, val endUtf16: Int)
    /** Source offsets in the immutable chapter, including its original internal whitespace. No normalization/timing guess. */
    fun segmentSpans(text: String): List<SourceSpan> {
        val positions = mutableListOf<Pair<Int, Int>>()
        var offset = 0
        text.codePoints().forEach { cp ->
            val end = offset + Character.charCount(cp)
            if (!isPythonSpace(cp)) positions += offset to end
            offset = end
        }
        var cursor = 0
        return segmentRaw(text).map { raw ->
            val count = raw.codePoints().toArray().count { !isPythonSpace(it) }
            require(count > 0 && cursor + count <= positions.size)
            val span = SourceSpan(raw, positions[cursor].first, positions[cursor + count - 1].second)
            cursor += count
            span
        }.also { check(cursor == positions.size) }
    }

    private fun emoji(cp: Int): Boolean = cp in 0x1f600..0x1f64f || cp in 0x1f300..0x1f5ff || cp in 0x1f680..0x1f6ff ||
        cp in 0x1f700..0x1f77f || cp in 0x1f780..0x1f7ff || cp in 0x1f800..0x1f8ff || cp in 0x1f900..0x1f9ff ||
        cp in 0x1fa00..0x1fa6f || cp in 0x1fa70..0x1faff || cp in 0x2600..0x26ff || cp in 0x2700..0x27bf || cp in 0x1f1e6..0x1f1ff

    /** Does not mutate the supplied raw text. Empty/emoji-only normalized strings receive the provider's period. */
    fun normalize(text: String, language: String? = "en"): String {
        require(language == null || language == "en") { "This app provider route is explicitly English" }
        var value = buildString {
            ProviderUnicode14.normalize(text).codePoints().forEach { cp -> if (!emoji(cp)) appendCodePoint(cp) }
        }
        symbols.forEach { (old, new) -> value = value.replace(old, new) }
        for (symbol in listOf("♥", "☆", "♡", "©", "\\")) value = value.replace(symbol, "")
        for ((old, new) in listOf("@" to " at ", "e.g.," to "for example, ", "i.e.," to "that is, ")) value = value.replace(old, new)
        for (mark in listOf(",", ".", "!", "?", ";", ":", "'")) value = value.replace(" $mark", mark)
        value = duplicateQuotes.replace(value, "$1")
        value = strip(spaces.replace(value, " "))
        if (value.isEmpty() || value.codePointBefore(value.length) !in terminal) value += "."
        return if (language == null) value else "<$language>$value</$language>"
    }

    /** Official validation preprocesses EACH original character before checking the supported table. */
    fun validateOriginal(text: String, indexer: IntArray) {
        require(indexer.isNotEmpty()) { "Provider indexer is missing" }
        text.codePoints().distinct().forEach { cp ->
            val single = String(Character.toChars(cp))
            require(normalize(single, null).codePoints().allMatch { it in indexer.indices && indexer[it] >= 0 }) {
                "Input contains an unsupported provider character (U+${cp.toString(16).uppercase()})"
            }
        }
    }

    fun prepare(text: String, indexer: IntArray): List<Segment> {
        require(strip(text).isNotEmpty()) { "A complete chapter must contain text" }
        validateOriginal(text, indexer)
        return segmentRaw(text).map { raw ->
            val normalized = normalize(raw)
            val ids = normalized.codePoints().toArray().map { cp ->
                require(cp in indexer.indices && indexer[cp] >= 0) { "Processed text contains an unsupported provider character" }
                indexer[cp].toLong()
            }.toLongArray()
            Segment(raw, normalized, ids)
        }
    }
}
