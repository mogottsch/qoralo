package dev.vibevoice.podcast.wiring

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DurationLoadPolicyTest {
    @Test fun loadOnlyBaselineContractPinsZeroInferenceAndOriginalEnvironment() {
        val bytes = requireNotNull(javaClass.getResourceAsStream("/duration-load/contract.json")).use { it.readBytes() }
        assertEquals(DurationLoadService.CONTRACT_SHA, WiringContract.hash(bytes))
        val contract = JSONObject(bytes.toString(Charsets.UTF_8))
        assertEquals(1, contract.getInt("sessionConstructorCalls"))
        assertEquals(0, contract.getInt("sessionRunCalls"))
        assertEquals(0, contract.getInt("retryCount"))
        assertEquals("43", contract.getString("socModel"))
        assertEquals("unchanged-baseline-apk-native-library-directory-only", contract.getString("adspLibraryPathPolicy"))
        assertEquals("inherit-unchanged", contract.getString("ldLibraryPathPolicy"))
        assertEquals(45, contract.getInt("loadDeadlineSeconds"))
        assertEquals(120, contract.getInt("serviceDeadlineSeconds"))
        assertEquals(150, contract.getInt("hostInstrumentationDeadlineSeconds"))
    }

    @Test fun durationIdentifiersCannotTriggerOldWiringSuiteOrEscapeStore() {
        assertTrue(DurationLoadService.validRunId("duration-baseline-01"))
        listOf("wiring-baseline", "duration-../x", "duration-", "../duration-a").forEach {
            assertFalse(DurationLoadService.validRunId(it))
        }
    }
}
