package dev.vibevoice.podcast.runtime

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SupertonicTextNormalizerTest {
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
