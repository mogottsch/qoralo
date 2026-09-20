package dev.qoralo.podcast.e2e

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.nio.file.Files

class ShortProductPolicyTest {
    private val shortText = (List(19) { "word" } + "end.").joinToString(" ")
    private fun chapterRequest(ids: List<String> = ShortProductPolicy.chapterIds, requested: String = "chapter-1") = JSONObject()
        .put("outline", JSONObject().put("chapters", JSONArray(ids.map { JSONObject().put("id", it) })))
        .put("requestedChapterId", requested).toString()

    @Test fun exactAssetContractAndDistinctShortScenario() {
        val bytes = javaClass.classLoader!!.getResourceAsStream("short-product-e2e/contract.json")!!.readBytes()
        assertEquals(ShortProductPolicy.CONTRACT_SHA, ShortProductPolicy.hash(bytes))
        val contract = JSONObject(bytes.toString(Charsets.UTF_8))
        assertEquals("supertonic-3", contract.getString("packId"))
        assertEquals(190, contract.getInt("maxNormalizedCodepoints"))
        assertFalse(contract.getBoolean("collectProfiles"))
        contract.getJSONObject("files").let { files -> files.keys().forEach { name ->
            val input = javaClass.classLoader!!.getResourceAsStream("short-product-e2e/$name")!!.readBytes()
            assertEquals(files.getString(name), ShortProductPolicy.hash(input))
        } }
    }
    @Test fun finalShortScopeAcceptsTwoWholeInputs() {
        ShortProductPolicy.validateFinal(ShortProductPolicy.chapterIds.map { it to shortText })
    }
    @Test fun finalScopeRejectsWrongCountIdsWordsOrCapacityWithoutTrimming() {
        val good = ShortProductPolicy.chapterIds.map { it to shortText }
        for (bad in listOf(good.reversed(), good.take(1), listOf("other" to shortText, good[1]),
            listOf(good[0].first to "Too brief.", good[1]), listOf(good[0].first to ("x".repeat(200) + " " + List(19) { "a" }.joinToString(" ")), good[1]))) {
            assertThrows(IllegalArgumentException::class.java) { ShortProductPolicy.validateFinal(bad) }
        }
    }
    @Test fun normalFourPlusOneLimitsAndOrderAreExact() {
        ShortProductPolicy.validateRequest("SCRIPT", 0, "source_notes", "{}", 1200)
        ShortProductPolicy.validateRequest("SCRIPT", 1, "outline", "{}", 1200)
        ShortProductPolicy.validateRequest("SCRIPT", 2, "chapter", chapterRequest(), 4096)
        ShortProductPolicy.validateRequest("SCRIPT", 3, "chapter", chapterRequest(requested = "chapter-2"), 4096)
        ShortProductPolicy.validateRequest("AGENT_EDIT", 0, "edit", "{}", 4096)
        assertThrows(IllegalArgumentException::class.java) { ShortProductPolicy.validateRequest("SCRIPT", 1, "source_notes", "{}", 1200) }
        assertThrows(IllegalArgumentException::class.java) { ShortProductPolicy.validateRequest("SCRIPT", 4, "chapter", chapterRequest(), 4096) }
        assertThrows(IllegalArgumentException::class.java) { ShortProductPolicy.validateRequest("AGENT_EDIT", 0, "edit", "{}", 768) }
        assertThrows(IllegalArgumentException::class.java) { ShortProductPolicy.validateRequest("SCRIPT", 2, "chapter", chapterRequest(listOf("wrong")), 4096) }
    }
    @Test fun boundsAndRunIdsAreFiniteAndScoped() {
        assertTrue(ShortProductPolicy.validRun("short-product-test-01"))
        assertFalse(ShortProductPolicy.validRun("../other"))
        assertTrue(ShortProductPolicy.jobMs("SCRIPT") < ShortProductPolicy.DRIVER_MS)
        assertEquals(emptyList<String>(), ShortProductPolicy.modes("AUDIO"))
    }
    @Test fun rawEvidenceCannotOverwriteARecordedReturn() {
        val dir = Files.createTempDirectory("short-product-policy").toFile()
        try {
            val path = dir.resolve("raw.txt")
            ShortProductDiagnostics.write(path, "original".toByteArray())
            assertThrows(IllegalStateException::class.java) { ShortProductDiagnostics.write(path, "replacement".toByteArray()) }
            assertEquals("original", path.readText())
        } finally { dir.deleteRecursively() }
    }
}
