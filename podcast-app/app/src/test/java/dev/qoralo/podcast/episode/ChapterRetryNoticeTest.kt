package dev.qoralo.podcast.episode

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import kotlin.coroutines.coroutineContext
import org.junit.Assert.*
import org.junit.Test

class ChapterRetryNoticeTest {
    @Test fun noticeReachesTheInstalledObserverThroughTheCoroutineContext() = runTest {
        val seen = mutableListOf<Pair<Int, Int>>()
        withContext(ChapterRetryNotice { attempt, attempts -> seen += attempt to attempts }) {
            coroutineContext[ChapterRetryNotice]?.retrying(2, 3)
            coroutineContext[ChapterRetryNotice]?.retrying(3, 3)
        }
        assertEquals(listOf(2 to 3, 3 to 3), seen)
    }

    @Test fun aFailingStatusWriteCannotAbortGeneration() = runTest {
        val notice = ChapterRetryNotice { _, _ -> throw java.io.IOException("status write failed") }
        notice.retrying(2, 3)
    }

    @Test fun cancellationStillPropagates() = runTest {
        val notice = ChapterRetryNotice { _, _ -> throw CancellationException("cancelled") }
        try {
            notice.retrying(2, 3); fail("cancellation was swallowed")
        } catch (_: CancellationException) {
        }
    }

    @Test fun aNoticeAlwaysDescribesALaterAttempt() = runTest {
        val notice = ChapterRetryNotice { _, _ -> fail("first attempt is not a retry") }
        assertThrows(IllegalArgumentException::class.java) { runBlockingRetry(notice, 1, 3) }
        assertThrows(IllegalArgumentException::class.java) { runBlockingRetry(notice, 4, 3) }
    }

    private fun runBlockingRetry(notice: ChapterRetryNotice, attempt: Int, attempts: Int) =
        kotlinx.coroutines.runBlocking { notice.retrying(attempt, attempts) }
}
