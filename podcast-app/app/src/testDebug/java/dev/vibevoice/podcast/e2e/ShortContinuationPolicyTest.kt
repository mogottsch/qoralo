package dev.vibevoice.podcast.e2e

import dev.vibevoice.podcast.data.ChapterEntity
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class ShortContinuationPolicyTest {
    private fun contract(): JSONObject {
        val bytes=javaClass.classLoader!!.getResourceAsStream("short-product-continuation/contract.json")!!.readBytes()
        assertEquals(ShortContinuationPolicy.CONTRACT_SHA,ShortProductPolicy.hash(bytes))
        return JSONObject(bytes.toString(Charsets.UTF_8))
    }
    private fun chapters(): List<ChapterEntity> {
        val bytes=javaClass.classLoader!!.getResourceAsStream("short-continuation-real-final.json")!!.readBytes()
        assertEquals(ShortContinuationPolicy.CONTENT_HASH,ShortProductPolicy.hash(bytes))
        val array=JSONObject(bytes.toString(Charsets.UTF_8)).getJSONArray("chapters")
        return List(array.length()) { i -> val row=array.getJSONObject(i)
            ChapterEntity("fixture-$i",ShortContinuationPolicy.REVISION_ID,row.getString("id"),i,row.getString("title"),row.getString("text"),10)
        }
    }
    @Test fun contractIsZeroLlmOneAudioOnRealPriorRevision() {
        val value=contract()
        assertEquals(0,value.getInt("newLogicalGemmaRequests"));assertEquals(1,value.getInt("newAudioJobs"));assertEquals(2,value.getInt("logicalTtsRequests"))
        assertEquals(ShortContinuationPolicy.EPISODE_ID,value.getString("episodeId"))
        assertEquals(ShortContinuationPolicy.CONTENT_HASH,value.getString("contentHash"))
        assertEquals(190,value.getInt("maxNormalizedCodepoints"));assertFalse(value.getBoolean("wordTargetIsValidityGate"))
        assertEquals(360,value.getInt("driverSeconds"));assertEquals(390,value.getInt("hostInstrumentationSeconds"))
    }
    @Test fun exactRealTwentySixAndTwentyNineWordTextsAreCapacitySafeButMissTarget() {
        val chapters=chapters();ShortContinuationPolicy.validateText(chapters,contract())
        val report=ShortContinuationPolicy.wordReport(chapters)
        assertEquals(26,report.getJSONObject(0).getInt("words"));assertEquals(29,report.getJSONObject(1).getInt("words"))
        assertFalse(report.getJSONObject(0).getBoolean("targetMet"));assertFalse(report.getJSONObject(1).getBoolean("targetMet"))
    }
    @Test fun alteredIdentityTextOrEmptyInputIsRejectedWithoutRepair() {
        val good=chapters();val value=contract()
        for (bad in listOf(good.reversed(),listOf(good[0].copy(revisionId="other"),good[1]),
            listOf(good[0].copy(text=good[0].text+" Extra."),good[1]),listOf(good[0].copy(text=""),good[1]))) {
            assertThrows(IllegalArgumentException::class.java) { ShortContinuationPolicy.validateText(bad,value) }
        }
    }
}
