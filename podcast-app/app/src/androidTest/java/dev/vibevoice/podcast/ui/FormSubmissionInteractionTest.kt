package dev.vibevoice.podcast.ui

import androidx.compose.runtime.*
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.test.ext.junit.runners.AndroidJUnit4
import dev.vibevoice.podcast.ui.theme.QoraloTheme
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.withContext
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Synthetic callbacks only. Uses production forms and real merged editable/button semantics. */
@RunWith(AndroidJUnit4::class)
class FormSubmissionInteractionTest {
    @get:Rule val rule = createComposeRule()

    @Test fun pasteSaveRejectionRetainsExactTitleBodyAndVisibleLocalError() {
        var accepted = 0
        var calls = 0
        rule.setContent { QoraloTheme { PasteSourceDialog({}, { _, _ -> calls++; error("Synthetic storage failure") }, { accepted++ }) } }
        rule.onAllNodes(hasSetTextAction())[0].performTextInput("Precise source title")
        pasteBody("Keep  all punctuation, and text.")
        rule.onNodeWithText("Add source").performClick()
        rule.onNodeWithText("Source wasn’t added").assertIsDisplayed()
        rule.onNodeWithText("Synthetic storage failure").performScrollTo().assertIsDisplayed()
        rule.onAllNodes(hasSetTextAction())[0].assertTextContains("Precise source title")
        rule.onAllNodes(hasSetTextAction())[1].assertTextContains("Keep  all punctuation, and text.")
        rule.runOnIdle { assertEquals(0, accepted); assertEquals(1, calls) }
    }

    @Test fun agentQueueRejectionRetainsExactRequestAndVisibleLocalError() {
        var calls = 0
        rule.setContent { QoraloTheme { AgentEditorSheet(emptyList(), null, {}, { calls++; error("Another on-device generation job is active") }) } }
        rule.onNode(hasSetTextAction()).performTextInput("Keep this exact change request.")
        rule.onNodeWithContentDescription("Send change request").performClick()
        rule.onNodeWithText("Request wasn’t sent").assertIsDisplayed()
        rule.onNodeWithText("Another on-device generation job is active").assertIsDisplayed()
        rule.onNode(hasSetTextAction()).assertTextContains("Keep this exact change request.")
        rule.onNodeWithText("Changes ready").assertDoesNotExist()
        rule.runOnIdle { assertEquals(1, calls) }
    }

    @Test fun pasteDismissesOnlyAfterSuccessfulAcknowledgement() {
        val acknowledgement = CompletableDeferred<Unit>()
        var accepted = 0
        var open by mutableStateOf(true)
        rule.setContent { if (open) QoraloTheme { PasteSourceDialog({}, { _, _ -> acknowledgement.await() }, { accepted++; open = false }) } }
        pasteBody("Await persistence")
        rule.onNodeWithText("Add source").performClick()
        rule.onNodeWithText("Adding source…").assertIsDisplayed().assertIsNotEnabled()
        rule.onAllNodes(hasSetTextAction())[1].assertTextContains("Await persistence")
        rule.runOnIdle { assertEquals(0, accepted); acknowledgement.complete(Unit) }
        rule.waitForIdle()
        rule.onNodeWithText("Paste text").assertDoesNotExist()
        rule.runOnIdle { assertEquals(1, accepted) }
    }

    @Test fun olderPasteSuccessDoesNotDismissOrClearNewerEdits() {
        val acknowledgement = CompletableDeferred<Unit>()
        var accepted = 0
        var submitted: String? = null
        rule.setContent { QoraloTheme { PasteSourceDialog({}, { _, body -> submitted = body; acknowledgement.await() }, { accepted++ }) } }
        pasteBody("Original submitted body")
        rule.onNodeWithText("Add source").performClick()
        rule.onAllNodes(hasSetTextAction())[1].performTextReplacement("Newer unsent body")
        rule.runOnIdle { acknowledgement.complete(Unit) }
        rule.waitForIdle()
        rule.onAllNodes(hasSetTextAction())[1].assertTextContains("Newer unsent body")
        rule.runOnIdle { assertEquals("Original submitted body", submitted); assertEquals(0, accepted) }
    }

    @Test fun dismissedFormAcknowledgementCannotDismissReplacementForm() {
        val acknowledgement = CompletableDeferred<Unit>()
        var generation by mutableIntStateOf(1)
        var accepted = 0
        rule.setContent {
            key(generation) {
                QoraloTheme { PasteSourceDialog({ generation++ }, { _, _ ->
                    // Emulate an already-owned backend operation completing after its UI is gone.
                    withContext(NonCancellable) { acknowledgement.await() }
                }, { accepted++ }) }
            }
        }
        pasteBody("Old form body")
        rule.onNodeWithText("Add source").performClick()
        rule.onNodeWithContentDescription("Close paste").performClick()
        pasteBody("Replacement form body")
        rule.runOnIdle { acknowledgement.complete(Unit) }
        rule.waitForIdle()
        rule.onAllNodes(hasSetTextAction())[1].assertTextContains("Replacement form body")
        rule.runOnIdle { assertEquals(0, accepted); assertEquals(2, generation) }
    }

    @Test fun unchangedAgentRequestClearsOnlyAfterQueueAcknowledgement() {
        val acknowledgement = CompletableDeferred<Unit>()
        var submitted: String? = null
        rule.setContent { QoraloTheme { AgentEditorSheet(emptyList(), null, {}, { request -> submitted = request; acknowledgement.await() }) } }
        rule.onNode(hasSetTextAction()).performTextInput("Please shorten chapter two")
        rule.onNodeWithContentDescription("Send change request").performClick()
        rule.onNode(hasSetTextAction()).assertTextContains("Please shorten chapter two")
        rule.onNodeWithContentDescription("Send change request").assertIsNotEnabled()
        rule.runOnIdle { acknowledgement.complete(Unit) }
        rule.waitForIdle()
        assertEquals("", rule.onNode(hasSetTextAction()).fetchSemanticsNode().config[SemanticsProperties.EditableText].text)
        rule.runOnIdle { assertEquals("Please shorten chapter two", submitted) }
    }

    @Test fun olderAgentAcknowledgementDoesNotClearNewerRequest() {
        val acknowledgement = CompletableDeferred<Unit>()
        var submitted: String? = null
        rule.setContent { QoraloTheme { AgentEditorSheet(emptyList(), null, {}, { request -> submitted = request; acknowledgement.await() }) } }
        rule.onNode(hasSetTextAction()).performTextInput("Original submitted request")
        rule.onNodeWithContentDescription("Send change request").performClick()
        rule.onNode(hasSetTextAction()).performTextReplacement("Newer unsent request")
        rule.runOnIdle { acknowledgement.complete(Unit) }
        rule.waitForIdle()
        rule.onNode(hasSetTextAction()).assertTextContains("Newer unsent request")
        rule.runOnIdle { assertEquals("Original submitted request", submitted) }
    }

    private fun pasteBody(text: String) {
        rule.onAllNodes(hasSetTextAction())[1].performScrollTo().performClick().performTextInput(text)
    }
}
