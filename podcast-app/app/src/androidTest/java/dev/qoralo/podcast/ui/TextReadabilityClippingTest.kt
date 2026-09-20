package dev.qoralo.podcast.ui

import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Text
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performSemanticsAction
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.test.ext.junit.runners.AndroidJUnit4
import dev.qoralo.podcast.ui.theme.QoraloTheme
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Real Compose clipping negatives, not invented accessibility nodes or acceptance markers. */
@RunWith(AndroidJUnit4::class)
class TextReadabilityClippingTest {
    @get:Rule val rule = createComposeRule()

    @Test fun genuinelyWidthConstrainedMinusCannotPassReadability() {
        rule.setContent { QoraloTheme { Text("−15", modifier = Modifier.width(16.dp), fontSize = 28.sp, maxLines = 1, softWrap = false) } }
        val errors = errors("−15")
        assertTrue("Actually truncated −15 was accepted: $errors", errors.any { it.contains("clips intrinsic") || it.contains("complete text") || it.contains("Maximum lines") })
    }

    @Test fun genuinelyHeightConstrainedHeaderCannotPassReadability() {
        rule.setContent { QoraloTheme { Text("Episode stopped", modifier = Modifier.height(4.dp), fontSize = 22.sp) } }
        val errors = errors("Episode stopped")
        assertTrue("Actually clipped title was accepted: $errors", errors.any { it.contains("Height") || it.contains("clips intrinsic") })
    }

    private fun errors(text: String): List<String> {
        val node = rule.onNodeWithText(text).assertIsDisplayed()
        val layouts = mutableListOf<TextLayoutResult>()
        node.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(layouts) }
        assertTrue("No actual layout for negative control", layouts.isNotEmpty())
        val ancestors = generateSequence(node.fetchSemanticsNode()) { it.parent }.take(64).map { it.boundsInRoot }.toList()
        return TextReadabilityAssertions.problems(text, layouts.map(TextReadabilityAssertions::snapshot), ancestors)
    }
}
