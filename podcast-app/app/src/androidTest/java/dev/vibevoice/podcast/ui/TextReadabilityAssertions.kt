package dev.vibevoice.podcast.ui

import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.text.TextLayoutResult

internal data class ReadableLine(val start: Int, val end: Int, val visibleEnd: Int, val bounds: Rect, val ellipsized: Boolean)
internal data class ReadableCharacter(val offset: Int, val bounds: Rect)
internal data class ReadableLayout(
    val text: String, val width: Float, val height: Float,
    val paragraphWidth: Float, val paragraphHeight: Float,
    val heightOverflow: Boolean, val exceededMaxLines: Boolean, val maxLines: Int,
    val lines: List<ReadableLine>, val characters: List<ReadableCharacter>,
)

/** Test-only checks on public, genuine text geometry. Logical boxes are not rasterized ink. */
internal object TextReadabilityAssertions {
    // Only float/physical-pixel rounding tolerance, not an allowance to remove a character.
    private const val EPSILON_PX = 1f

    fun snapshot(result: TextLayoutResult) = ReadableLayout(
        result.layoutInput.text.text, result.size.width.toFloat(), result.size.height.toFloat(),
        result.multiParagraph.width, result.multiParagraph.height,
        result.didOverflowHeight, result.multiParagraph.didExceedMaxLines, result.layoutInput.maxLines,
        List(result.lineCount) { line -> ReadableLine(result.getLineStart(line), result.getLineEnd(line),
            result.getLineEnd(line, visibleEnd = true), Rect(result.getLineLeft(line), result.getLineTop(line),
                result.getLineRight(line), result.getLineBottom(line)), result.isLineEllipsized(line)) },
        List(result.layoutInput.text.length) { offset -> ReadableCharacter(offset, result.getBoundingBox(offset)) },
    )

    fun problems(requested: String, layouts: List<ReadableLayout>, nodeAndAncestorBounds: List<Rect>): List<String> {
        val errors = mutableListOf<String>()
        if (layouts.size != 1) return listOf("Expected one exact text layout for $requested; received ${layouts.size}")
        val layout = layouts.single()
        if (layout.text != requested) errors += "Returned text differs from requested text: ${layout.text}"
        if (layout.text.isEmpty()) errors += "Empty text layout"
        if (!layout.width.isFinite() || !layout.height.isFinite() || layout.width <= 0 || layout.height <= 0) {
            return errors + "Invalid intrinsic dimensions"
        }
        if (!layout.paragraphWidth.isFinite() || !layout.paragraphHeight.isFinite() || layout.paragraphWidth <= 0 || layout.paragraphHeight <= 0) {
            errors += "Invalid paragraph dimensions"
        }
        // Compose1.7.6 simple-string semantics reconstructs MultiParagraph at incoming maxWidth,
        // while size remains intrinsic. Runtime evidence proves width alone is not a clipping test.
        // Do NOT discard height, missing text, ellipsis, or actual content extents instead.
        if (layout.heightOverflow || layout.paragraphHeight > layout.height + EPSILON_PX) errors += "Height overflow"
        if (layout.exceededMaxLines || layout.lines.size > layout.maxLines) errors += "Maximum lines exceeded"
        if (layout.lines.isEmpty()) errors += "No rendered lines"
        val intrinsic = Rect(0f, 0f, layout.width, layout.height)
        var previousEnd = 0
        layout.lines.forEachIndexed { index, line ->
            if (line.ellipsized) errors += "Line $index is ellipsized"
            if (line.start != previousEnd || line.end < line.start || line.end > layout.text.length ||
                line.visibleEnd !in line.start..line.end) {
                errors += "Line $index has incomplete or invalid text coverage"
            } else if (layout.text.substring(line.visibleEnd, line.end).any { !it.isWhitespace() }) {
                errors += "Line $index hides non-whitespace text"
            }
            if (!fits(line.bounds, intrinsic)) errors += "Line $index clips intrinsic bounds"
            previousEnd = line.end
        }
        if (previousEnd != layout.text.length) errors += "Rendered lines do not cover the complete text"
        if (layout.characters.map { it.offset } != layout.text.indices.toList()) errors += "Missing or duplicated character geometry"
        layout.characters.forEach { character ->
            if (character.offset !in layout.text.indices) errors += "Invalid character offset"
            else if (!layout.text[character.offset].isWhitespace() && !fits(character.bounds, intrinsic)) {
                errors += "Character ${character.offset} clips intrinsic bounds"
            }
        }
        if (nodeAndAncestorBounds.isEmpty()) errors += "No merged-node clipping bounds"
        else if (nodeAndAncestorBounds.any { !valid(it) || it.width <= 0 || it.height <= 0 }) errors += "Empty or invalid merged-node/ancestor bounds"
        else {
            // boundsInRoot is already clipped. Intersect with the actual semantic ancestors too;
            // do not compare unrelated paragraph maxWidth with a merged clickable card's width.
            val available = nodeAndAncestorBounds.reduce { a, b -> a.intersect(b) }
            if (available.width + EPSILON_PX < layout.width) errors += "Node/ancestor clips intrinsic width"
            if (available.height + EPSILON_PX < layout.height) errors += "Node/ancestor clips intrinsic height"
        }
        return errors
    }

    private fun valid(rect: Rect) = listOf(rect.left, rect.top, rect.right, rect.bottom).all { it.isFinite() } &&
        rect.right >= rect.left && rect.bottom >= rect.top

    private fun fits(rect: Rect, parent: Rect) = valid(rect) &&
        rect.left >= parent.left - EPSILON_PX && rect.top >= parent.top - EPSILON_PX &&
        rect.right <= parent.right + EPSILON_PX && rect.bottom <= parent.bottom + EPSILON_PX
}
