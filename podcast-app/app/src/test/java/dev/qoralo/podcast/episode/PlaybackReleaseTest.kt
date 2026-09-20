package dev.qoralo.podcast.episode

import org.junit.Assert.*
import org.junit.Test
import org.junit.Rule
import org.junit.rules.TemporaryFolder

class PlaybackReleaseTest {
    @get:Rule val temporary = TemporaryFolder()
    @Test fun failedCheckpointCannotStrandAPlayerAndSuccessfulReleaseIsIdempotent() {
        val state = PlaybackRelease(); var releases = 0
        state.close({ error("private checkpoint failure") }, { releases++ })
        assertTrue(state.released); assertEquals(1, releases)
        state.close({ error("must not run twice") }, { releases++ })
        assertEquals(1, releases)
    }
    @Test fun failedReleaseRetainsLeaseAndRetriesBeforeAcknowledgingCompletion() {
        val state = PlaybackRelease(); var releases = 0
        val leases = EpisodeFileLeases(temporary.newFolder("episodes"))
        val lease = leases.acquire("owned")
        leases.tombstone("owned")
        fun ownerClose() {
            state.close({}, { if (++releases == 1) error("injected release failure") })
            check(state.released)
            lease.close()
        }
        try {
            assertThrows(IllegalStateException::class.java) { ownerClose() }
            assertFalse(state.released); assertNull(leases.tryCleanupLease("owned"))
            ownerClose()
            assertTrue(state.released); assertEquals(2, releases)
            requireNotNull(leases.tryCleanupLease("owned")).use { leases.removeOwnedFiles("owned") }
        } finally { lease.close() }
    }
}
