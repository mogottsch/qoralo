package dev.vibevoice.podcast.runtime

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.io.File

class SupertonicTextCapacityTest {
    @Test fun exactPinnedManifestBoundsIncludeNineNativeLanguageCodepoints() {
        assertEquals(239, SupertonicTextCapacity.textLengthForManifest(SupertonicTextCapacity.SHORT_MANIFEST))
        assertEquals(2048, SupertonicTextCapacity.textLengthForManifest(SupertonicTextCapacity.LONG_MANIFEST))
        assertEquals(9, "<en></en>".codePointCount(0, "<en></en>".length))
        assertEquals(230, SupertonicTextCapacity.assess(listOf("hello"), 239).maxNormalizedCodePoints)
        assertEquals(2039, SupertonicTextCapacity.assess(listOf("hello"), 2048).maxNormalizedCodePoints)
        assertNull(SupertonicTextCapacity.textLengthForManifest("unreviewed"))
        assertFalse(SupertonicTextCapacity.assess(listOf("hello"), null).fits)
    }
    @Test fun capacityBindingsMatchExactPreviouslyVerifiedManifestBytes() {
        for ((name, pin) in listOf("short" to SupertonicTextCapacity.SHORT_MANIFEST, "long" to SupertonicTextCapacity.LONG_MANIFEST)) {
            val bytes = javaClass.classLoader!!.getResourceAsStream("supertonic-capacity/$name-manifest.json")!!.readBytes()
            val hash = java.security.MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
            assertEquals(pin, hash)
            assertEquals(JSONObject(bytes.toString(Charsets.UTF_8)).getJSONObject("contract").getInt("textLength"), SupertonicTextCapacity.textLengthForManifest(pin))
        }
    }
    @Test fun inclusive230Passes231RejectsWithoutChangingInput() {
        val at = "a".repeat(229) + "."; val over = "a".repeat(230) + "."
        val good = SupertonicTextCapacity.assess(listOf(at), 239)
        val bad = SupertonicTextCapacity.assess(listOf(over), 239)
        assertTrue(good.fits); assertEquals(239, good.chapters.single().activeCodePoints)
        assertFalse(bad.fits); assertEquals(240, bad.chapters.single().activeCodePoints)
        assertEquals(231, over.length); assertEquals(230, at.length)
    }
    @Test fun punctuationNfkdWhitespaceAndEmojiUseActualSharedFrontendNotRawLength() {
        assertTrue(SupertonicTextCapacity.assess(listOf("a".repeat(229)), 239).fits)
        assertFalse(SupertonicTextCapacity.assess(listOf("a".repeat(230)), 239).fits) // Added full stop.
        assertFalse(SupertonicTextCapacity.assess(listOf("é".repeat(115)), 239).fits) // NFKD expansion + stop.
        assertTrue(SupertonicTextCapacity.assess(listOf("😀".repeat(300) + "hello"), 239).fits)
        val value = " a\u00a0\u0085\t b "
        val normalized = SupertonicTextNormalizer.normalize(value)
        assertEquals(normalized.codePointCount(0, normalized.length), SupertonicTextCapacity.assess(listOf(value),239).chapters.single().normalizedCodePoints)
    }
    @Test fun emptyAfterNormalizationAndEmptyScriptAreNotAudioAdmissible() {
        assertFalse(SupertonicTextCapacity.assess(emptyList(),239).fits)
        val result = SupertonicTextCapacity.assess(listOf("😀♥☆"),239)
        assertFalse(result.fits); assertNull(result.chapters.single().normalizedCodePoints)
    }
    @Test fun notesGuidanceLeavesMarginButDoesNotChangeHardBoundOrIntroduceMinimum() {
        val instruction = sourceNotesInstruction()
        assertTrue(instruction.contains("${SourcePreparer.MAX_NOTE_CHARS} characters"))
        assertTrue(instruction.contains("at most 1600")); assertTrue(instruction.contains("shorter is fine"))
        assertEquals("short", validatedSourceNotes(" short "))
        assertEquals(1800, validatedSourceNotes("a".repeat(1800)).length)
        assertEquals(2000, validatedSourceNotes("a".repeat(2000)).length)
        assertThrows(IllegalArgumentException::class.java) { validatedSourceNotes("a".repeat(2001)) }
        assertThrows(IllegalArgumentException::class.java) { validatedSourceNotes(" \n ") }
    }
    @Test fun optionalPrivateRealDraftCountsUseActualKotlinNormalizerWithoutPublishingText() {
        val path = System.getenv("PODCAST_PRIVATE_CAPACITY_INPUT") ?: return
        val source = JSONObject(File(path).readText()).getJSONArray("cases")
        val result = JSONArray()
        for (index in 0 until source.length()) {
            val value = source.getJSONObject(index); val array = value.getJSONArray("chapters")
            val assessed = SupertonicTextCapacity.assess(List(array.length()) { array.getString(it) },239)
            result.put(JSONObject().put("case", value.getString("id")).put("maxNormalizedCodePoints", assessed.maxNormalizedCodePoints)
                .put("allFit", assessed.fits).put("chapters", JSONArray(assessed.chapters.map { c -> JSONObject()
                    .put("position", c.position).put("normalizedCodePoints", c.normalizedCodePoints)
                    .put("activeCodePointsWithLanguageTags", c.activeCodePoints).put("fits", c.fits) })))
        }
        File(requireNotNull(System.getenv("PODCAST_PRIVATE_CAPACITY_OUTPUT"))).writeText(result.toString(2)+"\n")
        assertEquals(2, source.length())
    }
}
