package dev.qoralo.podcast.ui

import androidx.compose.ui.geometry.Rect
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONObject
import org.json.JSONArray
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class TextReadabilityPolicyTest {
    private fun measured(): List<ReadableLayout> {
        val json = JSONArray(InstrumentationRegistry.getInstrumentation().context.assets
            .open("text-layout/measured-labels.json").bufferedReader().use { it.readText() })
        return List(json.length()) { index ->
            val row = json.getJSONObject(index).getJSONArray("returnedLayouts").getJSONObject(0)
            ReadableLayout(row.getString("text"), row.number("sizeWidth"), row.number("sizeHeight"),
                row.number("paragraphWidth"), row.number("paragraphHeight"), row.getBoolean("didOverflowHeight"),
                row.getBoolean("didExceedMaxLines"), row.getInt("maxLines"),
                row.getJSONArray("lines").let { lines -> List(lines.length()) { i -> lines.getJSONObject(i).let { line ->
                    ReadableLine(line.getInt("start"), line.getInt("end"), line.getInt("visibleEnd"),
                        Rect(line.number("left"), line.number("top"), line.number("right"), line.number("bottom")), line.getBoolean("ellipsized"))
                } } },
                row.getJSONArray("characterBoxes").let { chars -> List(chars.length()) { i -> chars.getJSONObject(i).let { character ->
                    val values = character.getString("bounds").substringAfter('(').substringBefore(')').split(',').map { it.trim().toFloat() }
                    ReadableCharacter(character.getInt("utf16Offset"), Rect(values[0], values[1], values[2], values[3]))
                } } },
            )
        }
    }
    private fun JSONObject.number(key: String) = getDouble(key).toFloat()
    private fun minus() = measured().first { it.text == "−15" }
    private fun bounds(layout: ReadableLayout) = listOf(Rect(0f, 0f, layout.width + 40f, layout.height + 40f))
    private fun errors(layout: ReadableLayout) = TextReadabilityAssertions.problems(layout.text, listOf(layout), bounds(layout))
    private fun rejected(layout: ReadableLayout, reason: String) {
        val errors = errors(layout)
        assertTrue("Expected $reason rejection; got $errors", errors.any { it.contains(reason, ignoreCase = true) })
    }

    @Test fun measuredReconstructedWidthsDoNotRejectCompleteFittingLabels() {
        val labels = measured()
        assertTrue(labels.size == 4)
        labels.forEach { layout ->
            assertTrue(layout.paragraphWidth > layout.width)
            assertTrue("Measured label rejected: ${errors(layout)}", errors(layout).isEmpty())
        }
    }

    @Test fun narrowingMinusToTruncateItsLastDigitIsRejected() {
        val layout = minus()
        // Reproduce the earlier −1/+1 failure mode: last digit lies beyond the allocated width.
        val clipped = layout.copy(width = layout.characters.last().bounds.left + 1f)
        rejected(clipped, "Line"); rejected(clipped, "Character")
    }

    @Test fun heightAndMaxLineOverflowStillReject() {
        val layout = minus()
        rejected(layout.copy(heightOverflow = true), "Height")
        rejected(layout.copy(height = layout.height - 5f), "Height")
        rejected(layout.copy(exceededMaxLines = true), "Maximum lines")
        rejected(layout.copy(maxLines = 0), "Maximum lines")
    }

    @Test fun ellipsisAndIncompleteTextStillReject() {
        val layout = minus(); val line = layout.lines.single()
        rejected(layout.copy(lines = listOf(line.copy(ellipsized = true))), "ellipsized")
        rejected(layout.copy(lines = listOf(line.copy(end = 2, visibleEnd = 2))), "complete text")
        rejected(layout.copy(lines = listOf(line.copy(visibleEnd = 2))), "hides")
        rejected(layout.copy(characters = layout.characters.dropLast(1)), "Missing")
    }

    @Test fun wrongMissingOrAdditionalReturnedLayoutsCannotBeFilteredAway() {
        val layout = minus()
        assertTrue(TextReadabilityAssertions.problems("+15", listOf(layout), bounds(layout)).any { it.contains("differs") })
        assertTrue(TextReadabilityAssertions.problems(layout.text, emptyList(), bounds(layout)).isNotEmpty())
        assertTrue(TextReadabilityAssertions.problems(layout.text, listOf(layout, layout), bounds(layout)).isNotEmpty())
    }

    @Test fun outOfBoundsAndNonfiniteGeometryRejects() {
        val layout = minus(); val line = layout.lines.single()
        rejected(layout.copy(lines = listOf(line.copy(bounds = Rect(-5f, 0f, line.bounds.right, line.bounds.bottom)))), "Line")
        rejected(layout.copy(characters = layout.characters.map { it.copy(bounds = it.bounds.translate(0f, 10f)) }), "Character")
        rejected(layout.copy(width = Float.NaN), "Invalid")
        rejected(layout.copy(paragraphWidth = Float.POSITIVE_INFINITY), "Invalid")
    }

    @Test fun nodeAndAncestorClippingCannotBeHiddenByLargeParagraphOrParent() {
        val layout = minus(); val normal = bounds(layout).single()
        val short = Rect(0f, 0f, normal.right, layout.height - 5f)
        val narrowAncestor = Rect(0f, 0f, layout.width - 5f, normal.bottom)
        assertTrue(TextReadabilityAssertions.problems(layout.text, listOf(layout), listOf(short, normal)).any { it.contains("ancestor clips intrinsic height") })
        assertTrue(TextReadabilityAssertions.problems(layout.text, listOf(layout), listOf(normal, narrowAncestor)).any { it.contains("ancestor clips intrinsic width") })
        assertTrue(TextReadabilityAssertions.problems(layout.text, listOf(layout), emptyList()).isNotEmpty())
    }
}
