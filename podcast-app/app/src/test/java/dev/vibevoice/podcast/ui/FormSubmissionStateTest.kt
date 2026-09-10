package dev.vibevoice.podcast.ui

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test

@OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
class FormSubmissionStateTest {
    @Test fun pendingAcknowledgementNeitherCompletesNorAllowsDuplicateSubmit() = runTest {
        val state = FormSubmissionState("form-a")
        val ticket = state.begin()!!
        val acknowledgement = CompletableDeferred<Unit>()
        var calls = 0
        val result = async { state.await(ticket) { calls++; acknowledgement.await() } }
        runCurrent()
        assertTrue(state.submitting); assertNull(state.begin()); assertFalse(result.isCompleted); assertEquals(1, calls)
        acknowledgement.complete(Unit)
        assertEquals(SubmissionCompletion.ACCEPTED_CURRENT, result.await())
        assertFalse(state.submitting); assertNull(state.feedback)
    }

    @Test fun rejectionKeepsDraftAndDoesNotRetryAutomatically() = runTest {
        val state = FormSubmissionState("form-a")
        var calls = 0
        var draft = "Keep these exact words"
        val result = state.await(state.begin()!!) { calls++; error("Storage unavailable") }
        if (result == SubmissionCompletion.ACCEPTED_CURRENT) draft = ""
        runCurrent()
        assertEquals(SubmissionCompletion.REJECTED, result)
        assertEquals("Keep these exact words", draft); assertEquals(1, calls)
        assertEquals("Storage unavailable", state.feedback!!.detail); assertFalse(state.submitting)
    }

    @Test fun editsWhilePendingPreventAnOlderSuccessFromClearingOrDismissing() {
        val state = FormSubmissionState("form-a")
        val old = state.begin()!!
        state.edited()
        assertEquals(SubmissionCompletion.ACCEPTED_OLDER, state.acknowledge(old, null))
        assertTrue(state.feedback!!.accepted); assertTrue(state.feedback!!.newerInput)
    }

    @Test fun evenEditThenUndoCountsAsANewerDraft() {
        val state = FormSubmissionState("form-a")
        val ticket = state.begin()!!
        state.edited(); state.edited()
        assertEquals(SubmissionCompletion.ACCEPTED_OLDER, state.acknowledge(ticket, null))
    }

    @Test fun lateRejectionDescribesThePreviousSubmissionWithoutClearingNewerInput() {
        val state = FormSubmissionState("form-a")
        val ticket = state.begin()!!
        state.edited()
        assertEquals(SubmissionCompletion.REJECTED, state.acknowledge(ticket, "Another job is active"))
        assertFalse(state.feedback!!.accepted); assertTrue(state.feedback!!.newerInput)
    }

    @Test fun dismissedOrReplacedFormCannotAcceptAnOldAcknowledgement() {
        val a = FormSubmissionState("episode-a-form-1")
        val old = a.begin()!!
        a.dispose()
        val b = FormSubmissionState("episode-b-form-1")
        val newer = b.begin()!!
        assertEquals(SubmissionCompletion.IGNORED, a.acknowledge(old, null))
        assertEquals(SubmissionCompletion.IGNORED, b.acknowledge(old, "Old failure"))
        assertTrue(b.submitting); assertNull(b.feedback)
        assertEquals(SubmissionCompletion.ACCEPTED_CURRENT, b.acknowledge(newer, null))
    }

    @Test fun repeatedOrOutOfOrderAcknowledgementCannotCompleteNextSubmission() {
        val state = FormSubmissionState("form-a")
        val first = state.begin()!!
        state.acknowledge(first, null)
        val second = state.begin()!!
        assertEquals(SubmissionCompletion.IGNORED, state.acknowledge(first, "late error"))
        assertTrue(state.submitting); assertNull(state.feedback)
        assertEquals(SubmissionCompletion.ACCEPTED_CURRENT, state.acknowledge(second, null))
    }

    @Test fun cancellationIsNotDisplayedAsARejectedSubmission() = runTest {
        val state = FormSubmissionState("form-a")
        val ticket = state.begin()!!
        val wait = CompletableDeferred<Unit>()
        val task = async { state.await(ticket) { wait.await() } }
        runCurrent(); task.cancelAndJoin()
        assertFalse(state.submitting); assertNull(state.feedback)
    }

    @Test fun disposedBeforeDispatchNeverInvokesTheCallback() = runTest {
        val state = FormSubmissionState("form-a")
        val ticket = state.begin()!!
        state.dispose()
        assertEquals(SubmissionCompletion.IGNORED, state.await(ticket) { error("Must not run") })
        assertNull(state.begin())
    }
}
