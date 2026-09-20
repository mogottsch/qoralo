package dev.qoralo.podcast.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CancellationException
import java.util.UUID

internal data class SubmissionTicket(val formId: String, val sequence: Long, val inputRevision: Long)
internal enum class SubmissionCompletion { ACCEPTED_CURRENT, ACCEPTED_OLDER, REJECTED, IGNORED }
internal data class SubmissionFeedback(val accepted: Boolean, val newerInput: Boolean, val detail: String?)

/** One UI form lifetime. A backend acknowledgement cannot clear a newer draft or a replacement form. */
internal class FormSubmissionState(private val formId: String = UUID.randomUUID().toString()) {
    private var sequence = 0L
    private var inputRevision = 0L
    private var attached = true
    private var pending by mutableStateOf<SubmissionTicket?>(null)
    var feedback by mutableStateOf<SubmissionFeedback?>(null)
        private set
    val submitting: Boolean get() = pending != null

    fun edited() { inputRevision++; feedback = null }
    fun begin(): SubmissionTicket? {
        if (!attached || pending != null) return null
        return SubmissionTicket(formId, ++sequence, inputRevision).also { pending = it; feedback = null }
    }
    fun dispose() { attached = false; pending = null }

    suspend fun await(ticket: SubmissionTicket, submit: suspend () -> Unit): SubmissionCompletion {
        if (!attached || pending != ticket) return SubmissionCompletion.IGNORED
        val failure = try { submit(); null }
        catch (cancelled: CancellationException) {
            if (pending == ticket) pending = null
            throw cancelled
        }
        catch (error: Exception) { error.message ?: "The submission could not be saved." }
        return acknowledge(ticket, failure)
    }

    internal fun acknowledge(ticket: SubmissionTicket, failure: String?): SubmissionCompletion {
        if (!attached || pending != ticket) return SubmissionCompletion.IGNORED
        pending = null
        val newer = inputRevision != ticket.inputRevision
        if (failure != null) {
            feedback = SubmissionFeedback(false, newer, failure)
            return SubmissionCompletion.REJECTED
        }
        if (newer) {
            feedback = SubmissionFeedback(true, true, null)
            return SubmissionCompletion.ACCEPTED_OLDER
        }
        feedback = null
        return SubmissionCompletion.ACCEPTED_CURRENT
    }
}

@Composable
internal fun rememberFormSubmission(): FormSubmissionState {
    val state = remember { FormSubmissionState() }
    DisposableEffect(state) { onDispose { state.dispose() } }
    return state
}
