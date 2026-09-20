package dev.qoralo.podcast.episode

import kotlinx.coroutines.CancellationException
import kotlin.coroutines.AbstractCoroutineContextElement
import kotlin.coroutines.CoroutineContext

/**
 * Lets a bounded chapter retry surface as ordinary progress instead of a failure.
 *
 * The notice is presentation only: it never changes inference, never decides whether another attempt
 * happens, and a failing status write cannot abort generation. Cancellation still propagates.
 */
class ChapterRetryNotice(private val onRetry: suspend (attempt: Int, attempts: Int) -> Unit) :
    AbstractCoroutineContextElement(Key) {
    companion object Key : CoroutineContext.Key<ChapterRetryNotice>

    suspend fun retrying(attempt: Int, attempts: Int) {
        require(attempt in 2..attempts) { "A retry notice describes a later attempt" }
        try {
            onRetry(attempt, attempts)
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (_: Throwable) {
            // Optional status only; the attempt itself remains authoritative.
        }
    }
}
