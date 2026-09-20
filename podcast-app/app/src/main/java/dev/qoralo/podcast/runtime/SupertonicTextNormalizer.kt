package dev.qoralo.podcast.runtime

import java.text.Normalizer

/** Mirrors the accepted sherpa-onnx/Supertonic frontend before language tags and indexing. */
object SupertonicTextNormalizer {
    private val replacements = listOf(
        "–" to "-", "‑" to "-", "—" to "-", "_" to " ",
        "“" to "\"", "”" to "\"", "‘" to "'", "’" to "'", "´" to "'", "`" to "'",
        "[" to " ", "]" to " ", "|" to " ", "/" to " ", "#" to " ",
        "→" to " ", "←" to " ", "♥" to "", "☆" to "", "♡" to "", "©" to "", "\\" to "",
        "@" to " at ", "e.g.," to "for example, ", "i.e.," to "that is, ",
    )
    private val terminalPunctuation = setOf('.', '!', '?', ';', ':', ',', '\'', '"', ')', ']', '}', '>', '…', '。', '」', '』', '】', '〉', '》', '›', '»', '“', '”', '‘', '’')

    // Python's Unicode \s / str.isspace() set used by the accepted frontend.
    // JVM Regex("\\s+") is ASCII-only; Character.isWhitespace also omits NEL/NBSP.
    private val unicodeWhitespace = Regex("[\\u0009-\\u000D\\u001C-\\u0020\\u0085\\u00A0\\u1680\\u2000-\\u200A\\u2028\\u2029\\u202F\\u205F\\u3000]+")

    private fun isUnicodeWhitespace(codepoint: Int): Boolean =
        Character.isWhitespace(codepoint) || Character.isSpaceChar(codepoint) || codepoint == 0x85

    fun normalize(text: String): String {
        var value = text
        replacements.forEach { (old, new) -> value = value.replace(old, new) }
        value = buildString {
            value.codePoints().forEach { codepoint ->
                if (codepoint !in 0x1F000..0x1FFFF && codepoint != 0 &&
                    (!Character.isISOControl(codepoint) || isUnicodeWhitespace(codepoint))
                ) appendCodePoint(codepoint)
            }
        }
        value = value.replace(Regex(" ([,.!?;:'])"), "$1")
            .replace("`", "")
            .replace(Regex("\"\""), "\"")
            .replace(Regex("''"), "'")
            .replace(unicodeWhitespace, " ")
            .trim()
        if (value.isNotEmpty() && value.last() !in terminalPunctuation) value += "."
        value = buildString {
            // Decompose each original code point, as text_tensors() does. Whole-string
            // NFKD would reorder combining marks across original code-point boundaries.
            value.codePoints().forEach { original ->
                val decomposed = Normalizer.normalize(String(Character.toChars(original)), Normalizer.Form.NFKD)
                decomposed.codePoints().forEach { codepoint ->
                    if (codepoint <= 0xFFFF && codepoint !in 0xD800..0xDFFF) appendCodePoint(codepoint)
                }
            }
        }
        require(value.isNotBlank()) { "Complete chapter is empty after Supertonic normalization" }
        return value
    }
}
