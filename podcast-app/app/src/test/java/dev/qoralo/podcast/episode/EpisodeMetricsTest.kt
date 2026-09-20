package dev.qoralo.podcast.episode

import dev.qoralo.podcast.data.ArtifactStore
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class EpisodeMetricsTest {
    @get:Rule val temp = TemporaryFolder()
    private fun artifacts() = ArtifactStore(temp.newFolder("episodes"), temp.newFolder("models"))
    @Test fun missingAndInvalidCountersAreNullNotWordsOrKvCounts() {
        val absent = runtimeRequestMetrics("edit", "failed", 200.0, 10.0, 190.0).json()
        for (key in listOf("prefillTokens", "decodeTokens", "prefillTokensPerSecond", "decodeTokensPerSecond", "runtimeTtftMs")) assertTrue(absent.isNull(key))
        val invalid = runtimeRequestMetrics("chapter", "complete", 200.0, 10.0, 190.0, -1, 0, Double.NaN, Double.POSITIVE_INFINITY, -1.0, Double.NaN).json()
        assertTrue(invalid.isNull("prefillTokens")); assertTrue(invalid.isNull("prefillTokensPerSecond")); assertTrue(invalid.isNull("decodeTokensPerSecond"))
        assertTrue(invalid.isNull("runtimeInitMs")); assertTrue(invalid.isNull("runtimeTtftMs"))
        assertThrows(IllegalArgumentException::class.java) { runtimeRequestMetrics("private prompt", "complete", 1.0, null, null) }
    }
    @Test fun actualRuntimeFieldsRetainedWithoutReconstructingCounts() {
        val record = runtimeRequestMetrics("outline", "complete", 1000.0, 100.0, 900.0, 123, 45, 600.0, 50.0, .1, .3).json()
        assertEquals(123, record.getInt("prefillTokens")); assertEquals(45, record.getInt("decodeTokens"))
        assertEquals(600.0, record.getDouble("prefillTokensPerSecond"), 0.0)
        assertEquals(50.0, record.getDouble("decodeTokensPerSecond"), 0.0)
        assertEquals(300.0, record.getDouble("runtimeTtftMs"), 0.0)
    }
    @Test fun rtfUsesActualAudioIncludingGapsAndRecoveryHasNoSynthesisRate() = runTest {
        val artifacts = artifacts(); var ns = 0L
        val metrics = EpisodeMetrics(artifacts, "owned", "job", "AUDIO") { ns }
        metrics.measure("setup") { ns += 1_000_000_000L }
        metrics.measure("render") { ns += 2_000_000_000L }
        metrics.audioAvailable(132_300) // Three seconds of validated PCM, gaps already included.
        metrics.measure("finalization") { ns += 500_000_000L }
        metrics.measure("teardown") { ns += 500_000_000L }
        metrics.finish(null)
        val saved = requireNotNull(EpisodeMetrics.read(artifacts, "owned", "job"))
        assertEquals(4000.0, saved.getDouble("wallMs"), 0.0)
        assertEquals(3000.0, saved.getDouble("audioDurationMs"), 0.0)
        assertEquals(4.0 / 3, saved.getDouble("wallRtf"), 1e-9)
        assertEquals(2.0 / 3, saved.getDouble("renderRtf"), 1e-9)
        metrics.recovered(); assertTrue(metrics.snapshot().isNull("renderRtf")); assertTrue(metrics.snapshot().isNull("wallRtf"))
    }
    @Test fun jobRatesRequireEveryActualRequestAndUseRuntimePhaseWeights() {
        val metrics = EpisodeMetrics(artifacts(), "owned", "job", "SCRIPT")
        metrics.request(runtimeRequestMetrics("outline", "complete", 1100.0, null, null, 100, 10, 100.0, 10.0))
        metrics.request(runtimeRequestMetrics("chapter", "complete", 3100.0, null, null, 200, 20, 100.0, 20.0))
        assertEquals(100.0, metrics.snapshot().getDouble("llmPrefillTokensPerSecond"), 1e-9)
        assertEquals(15.0, metrics.snapshot().getDouble("llmDecodeTokensPerSecond"), 1e-9)
        metrics.request(runtimeRequestMetrics("chapter", "failed", 1100.0, null, null))
        assertTrue(metrics.snapshot().isNull("llmPrefillTokensPerSecond"))
        assertTrue(metrics.snapshot().isNull("llmDecodeTokensPerSecond"))
    }
    @Test fun abruptDeathHasNoInventedFinishAndDeletionCannotRecreateDiagnostics() {
        val artifacts = artifacts(); val metrics = EpisodeMetrics(artifacts, "owned", "job", "SCRIPT")
        assertEquals("running", requireNotNull(EpisodeMetrics.read(artifacts, "owned", "job")).getString("outcome"))
        assertTrue(metrics.snapshot().isNull("wallMs"))
        artifacts.episodeLeases.tombstone("owned")
        requireNotNull(artifacts.episodeLeases.tryCleanupLease("owned")).use { artifacts.episodeLeases.removeOwnedFiles("owned") }
        metrics.finish(IllegalStateException("PRIVATE_SECRET"))
        assertNull(EpisodeMetrics.read(artifacts, "owned", "job"))
        assertFalse(metrics.snapshot().toString().contains("PRIVATE_SECRET"))
    }
}
