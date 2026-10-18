package dev.qoralo.podcast.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.requiredWidth
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.layout.boundsInRoot
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.assertHasClickAction
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertTextEquals
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performSemanticsAction
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import dev.qoralo.podcast.ui.theme.QoraloTheme
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import kotlin.math.abs

/** Real native Compose layout and callbacks; no player, model, job or user data needed. */
@RunWith(AndroidJUnit4::class)
class PlayerOptionsTest {
    @get:Rule val rule = createComposeRule()
    private lateinit var density: Density
    private var container = Rect.Zero

    @Test fun regularPhoneUsesEqualCenteredSlots() {
        render(360, 1f)
        assertEqualCenteredRow()
    }

    @Test fun narrowPhoneKeepsAllThreeActionsOnOneRow() {
        render(320, 1f)
        assertEqualCenteredRow()
    }

    @Test fun largerFontReflowsInsteadOfCrowdingTranscript() {
        render(320, 1.4f)
        assertCenteredStack()
    }

    @Test fun doubledFontKeepsLabelsReadableAndTargetsSeparate() {
        render(320, 2f)
        assertCenteredStack()
    }

    @Test fun activeSpeedAndTimerRetainCenteredSlots() {
        render(360, 1f, speed = 1.25f, sleep = 30)
        assertEqualCenteredRow(listOf("1.25×", "Transcript", "30 min"))
    }

    @Test fun everyActionStillDispatchesAndChangingStateRemainsReadable() {
        var speed by mutableStateOf(1f)
        var sleep by mutableStateOf<Int?>(null)
        var transcriptClicks = 0
        rule.setContent {
            QoraloTheme {
                Box(Modifier.fillMaxWidth().safeDrawingPadding(), contentAlignment = Alignment.TopCenter) {
                    Box(Modifier.requiredWidth(320.dp)) {
                        PlayerOptions(speed, sleep,
                            onSpeedClick = { speed = 1.25f },
                            onTranscriptClick = { transcriptClicks++ },
                            onSleepClick = { sleep = when (sleep) { null -> 15; 15 -> 30; else -> null } })
                    }
                }
            }
        }
        rule.onNodeWithText("1.0×").performClick()
        rule.onNodeWithText("1.25×").assertTextEquals("1.25×")
        rule.onNodeWithText("Transcript").performClick()
        rule.onNodeWithText("Sleep").performClick()
        rule.onNodeWithText("15 min").assertIsDisplayed().performClick()
        rule.onNodeWithText("30 min").assertIsDisplayed().performClick()
        rule.onNodeWithText("Sleep").assertIsDisplayed()
        rule.runOnIdle { assertEquals(1, transcriptClicks); assertEquals(1.25f, speed); assertEquals(null, sleep) }
    }

    private fun render(width: Int, fontScale: Float, speed: Float = 1f, sleep: Int? = null) {
        rule.setContent {
            val platform = LocalDensity.current
            density = Density(platform.density, fontScale)
            CompositionLocalProvider(LocalDensity provides density) {
                QoraloTheme {
                    Box(Modifier.fillMaxWidth().safeDrawingPadding(), contentAlignment = Alignment.TopCenter) {
                        Box(Modifier.requiredWidth(width.dp).onGloballyPositioned { container = it.boundsInRoot() }) {
                            PlayerOptions(speed, sleep, {}, {}, {})
                        }
                    }
                }
            }
        }
    }

    private fun assertEqualCenteredRow(labels: List<String> = listOf("1.0×", "Transcript", "Sleep")) {
        val bounds = labels.map(::assertReadableTarget)
        val tolerance = 1.5f
        bounds.forEach { assertTrue("Unequal slot widths: $bounds", abs(it.width - bounds.first().width) < tolerance) }
        assertTrue("Actions not centered as a group", abs((bounds.first().left + bounds.last().right) / 2 - container.center.x) < tolerance)
        bounds.zipWithNext().forEach { (a, b) ->
            assertTrue("Different row centers: $bounds", abs(a.center.y - b.center.y) < tolerance)
            assertTrue("Touch targets overlap or have no gap", b.left - a.right >= with(density) { 8.dp.toPx() } - tolerance)
        }
        labels.zip(bounds).forEach { (label, button) ->
            val text = rule.onNodeWithText(label, useUnmergedTree = true).fetchSemanticsNode().boundsInRoot
            assertTrue("$label is not centered in its slot", abs(text.center.x - button.center.x) < tolerance)
        }
    }

    private fun assertCenteredStack() {
        val bounds = listOf("1.0×", "Transcript", "Sleep").map(::assertReadableTarget)
        bounds.forEach { assertTrue("Action is not centered", abs(it.center.x - container.center.x) < 1.5f) }
        bounds.zipWithNext().forEach { (a, b) ->
            assertTrue("Stacked touch targets overlap", b.top - a.bottom >= with(density) { 8.dp.toPx() } - 1.5f)
        }
    }

    private fun assertReadableTarget(label: String): Rect {
        val button = rule.onNodeWithText(label).assertIsDisplayed().assertHasClickAction().fetchSemanticsNode().boundsInRoot
        val minimum = with(density) { 48.dp.toPx() } - 1f
        assertTrue("Small touch target for $label: $button", button.width >= minimum && button.height >= minimum)
        val text = rule.onNodeWithText(label, useUnmergedTree = true).assertIsDisplayed()
        val layouts = mutableListOf<TextLayoutResult>()
        text.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
        assertTrue("Missing real text layout for $label", layouts.isNotEmpty())
        val ancestors = generateSequence(text.fetchSemanticsNode()) { it.parent }.take(64).map { it.boundsInRoot }.toList()
        val errors = TextReadabilityAssertions.problems(label, layouts.map(TextReadabilityAssertions::snapshot), ancestors)
        assertTrue("Unreadable $label: $errors", errors.isEmpty())
        return button
    }
}
