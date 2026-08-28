package dev.vibevoice.podcast.runtime

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

    fun normalize(text: String): String {
        var value = text
        replacements.forEach { (old, new) -> value = value.replace(old, new) }
        value = buildString {
            value.codePoints().forEach { codepoint ->
                if (codepoint !in 0x1F000..0x1FFFF && codepoint != 0 &&
                    (!Character.isISOControl(codepoint) || Character.isWhitespace(codepoint))
                ) appendCodePoint(codepoint)
            }
        }
        value = value.replace(Regex(" ([,.!?;:'])"), "$1")
            .replace("`", "")
            .replace(Regex("\"\""), "\"")
            .replace(Regex("''"), "'")
            .replace(Regex("\\s+"), " ")
            .trim()
        if (value.isNotEmpty() && value.last() !in terminalPunctuation) value += "."
        value = Normalizer.normalize(value, Normalizer.Form.NFKD)
        value = buildString {
            value.codePoints().forEach { codepoint -> if (codepoint <= 0xFFFF && codepoint !in 0xD800..0xDFFF) appendCodePoint(codepoint) }
        }
        require(value.isNotBlank()) { "Complete chapter is empty after Supertonic normalization" }
        return value
    }
}
