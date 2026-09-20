package dev.qoralo.podcast.runtime

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SupertonicTextNormalizerTest {
    @Test fun matchesGoldenOutputsDerivedFromAcceptedPythonFrontend() {
        val resource = requireNotNull(javaClass.getResourceAsStream("/supertonic-normalization-reference.json"))
        val fixtures = resource.bufferedReader(Charsets.UTF_8).use { JSONObject(it.readText()).getJSONArray("cases") }
        for (index in 0 until fixtures.length()) {
            val fixture = fixtures.getJSONObject(index)
            assertEquals(fixture.getString("name"), fixture.getString("expected"),
                SupertonicTextNormalizer.normalize(fixture.getString("input")))
        }
    }

    @Test fun preservesWordBoundariesForEveryAcceptedUnicodeWhitespaceCodepoint() {
        // Exact Python str.isspace()/Unicode regex whitespace set, including NEL.
        val whitespace = (0x09..0x0D) + (0x1C..0x20) + listOf(0x85, 0xA0, 0x1680) +
            (0x2000..0x200A) + listOf(0x2028, 0x2029, 0x202F, 0x205F, 0x3000)
        whitespace.forEach { codepoint ->
            val separator = String(Character.toChars(codepoint))
            assertEquals("U+${codepoint.toString(16)}", "Hello world.",
                SupertonicTextNormalizer.normalize("Hello${separator}world"))
            assertEquals("repeated U+${codepoint.toString(16)}", "Hello world.",
                SupertonicTextNormalizer.normalize("${separator}Hello$separator $separator\tworld$separator"))
        }
    }

    @Test fun preservesOriginalCombiningMarkOrderDuringPerCodepointNfkd() {
        assertEquals("e\u0301\u0323.", SupertonicTextNormalizer.normalize("e\u0301\u0323"))
        assertEquals("e\u0301\u0323.", SupertonicTextNormalizer.normalize("\u00e9\u0323"))
        assertEquals("fi\u0301\u0323.", SupertonicTextNormalizer.normalize("\ufb01\u0301\u0323"))
    }

    @Test fun retainsAcceptedPunctuationCleanupBeforeWhitespaceCollapse() {
        assertEquals("Hello , world.", SupertonicTextNormalizer.normalize("Hello\u0085,\u2028world"))
        assertEquals("hello !", SupertonicTextNormalizer.normalize("hello   !"))
    }

    @Test fun canonicalizesParagraphsCurlyPunctuationDashAccentAndEmoji() {
        val normalized = SupertonicTextNormalizer.normalize("  “Café”—today\n\nwe’re #1 😀  ")
        assertEquals("\"Cafe\u0301\"-today we're 1.", normalized)
        assertFalse(normalized.contains('\n'))
        assertTrue(normalized.codePoints().allMatch { it <= 0xFFFF })
    }

    @Test fun mirrorsSymbolAndAbbreviationReplacements() {
        assertEquals("Use for example, A at B that is, not C D.",
            SupertonicTextNormalizer.normalize("Use e.g., [A] @ B i.e., not C/D"))
    }

    @Test fun preservesExistingTerminalPunctuationWithoutDoubling() {
        assertEquals("Is this ready?", SupertonicTextNormalizer.normalize("Is this ready?"))
        assertEquals("Quoted.\"", SupertonicTextNormalizer.normalize("Quoted.\""))
    }

    @Test fun removesSupplementaryCharactersBeforeJniModifiedUtf8Boundary() {
        val normalized = SupertonicTextNormalizer.normalize("Words 🧠 🚀 remain")
        assertEquals("Words remain.", normalized)
        assertTrue(normalized.none(Char::isSurrogate))
    }
}
