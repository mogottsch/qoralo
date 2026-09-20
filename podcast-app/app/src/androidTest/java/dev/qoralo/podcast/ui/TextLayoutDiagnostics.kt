package dev.qoralo.podcast.ui

import android.graphics.Bitmap
import android.os.Build
import android.os.SystemClock
import androidx.compose.ui.semantics.SemanticsNode
import androidx.compose.ui.test.SemanticsNodeInteraction
import androidx.compose.ui.test.printToString
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.sp
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.util.UUID

/** Opt-in evidence only. Does not filter results, replace semantics, or decide test acceptance. */
internal object TextLayoutDiagnostics {
    fun retain(target: String, node: SemanticsNodeInteraction, layouts: List<TextLayoutResult>, platform: Density, wrapper: Density) {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val runId = InstrumentationRegistry.getArguments().getString("textLayoutDiagnosticsRunId") ?: return
        require(runId.matches(Regex("text-[a-z0-9-]{1,64}")))
        require(Build.HARDWARE.contains("ranchu") || Build.HARDWARE.contains("goldfish")) { "Synthetic emulator only" }
        val context = instrumentation.targetContext
        // Each observation is new, including repeated/failed tests in a run; never overwrite evidence.
        val dir = File(context.filesDir, "ui-text-layout/$runId/${UUID.randomUUID()}")
        check(dir.mkdirs())
        val observed = node.fetchSemanticsNode()
        val report = JSONObject()
            .put("status", "observation-not-acceptance")
            .put("target", target).put("elapsedRealtimeMs", SystemClock.elapsedRealtime())
            .put("sourceApkSha256", sha256(File(context.applicationInfo.sourceDir)))
            .put("testApkSha256", sha256(File(instrumentation.context.applicationInfo.sourceDir)))
            .put("sdk", Build.VERSION.SDK_INT)
            .put("configurationFontScale", context.resources.configuration.fontScale)
            .put("configurationScreenWidthDp", context.resources.configuration.screenWidthDp)
            .put("platformDensity", density(platform)).put("wrapperDensity", density(wrapper))
            .put("targetNode", bounds(observed))
            .put("mergedTargetTree", node.printToString(maxDepth = 16))
            .put("ancestors", JSONArray().apply {
                var parent = observed.parent
                repeat(24) { parent?.let { put(bounds(it)); parent = it.parent } }
            })
            .put("returnedLayouts", JSONArray().apply { layouts.forEach { put(layout(it)) } })
        val json = File(dir, "observation.json")
        json.writeText(report.toString(2)) // Retain numeric evidence even if screenshot capture fails.
        val png = File(dir, "test-scene.png")
        try {
            val bitmap = checkNotNull(instrumentation.uiAutomation.takeScreenshot()) { "No screenshot returned" }
            try { png.outputStream().use { check(bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)) } }
            finally { bitmap.recycle() }
            report.put("screenshot", JSONObject().put("file", png.name).put("sha256", sha256(png))
                .put("elapsedRealtimeMs", SystemClock.elapsedRealtime()))
        } catch (error: Exception) {
            report.put("screenshotError", error.toString())
        }
        json.writeText(report.toString(2))
        println("TEXT_LAYOUT_OBSERVATION ${json.absolutePath}\n${report.toString(2)}")
    }

    private fun density(value: Density) = JSONObject()
        .put("class", value.javaClass.name).put("density", value.density).put("fontScale", value.fontScale)
        .put("spToPx", JSONObject().apply { listOf(11, 14, 16, 22, 28).forEach { sp -> put(sp.toString(), with(value) { sp.sp.toPx() }) } })

    private fun bounds(node: SemanticsNode) = JSONObject()
        .put("id", node.id).put("boundsInRoot", node.boundsInRoot.toString())
        .put("boundsInWindow", node.boundsInWindow.toString()).put("size", node.size.toString())
        .put("configuration", node.config.toString())

    private fun layout(result: TextLayoutResult): JSONObject {
        val input = result.layoutInput
        return JSONObject()
            .put("text", input.text.text).put("constraints", input.constraints.toString())
            .put("sizeWidth", result.size.width).put("sizeHeight", result.size.height)
            .put("paragraphWidth", result.multiParagraph.width).put("paragraphHeight", result.multiParagraph.height)
            .put("paragraphMinIntrinsicWidth", result.multiParagraph.intrinsics.minIntrinsicWidth)
            .put("paragraphMaxIntrinsicWidth", result.multiParagraph.intrinsics.maxIntrinsicWidth)
            .put("didOverflowWidth", result.didOverflowWidth).put("didOverflowHeight", result.didOverflowHeight)
            .put("hasVisualOverflow", result.hasVisualOverflow).put("didExceedMaxLines", result.multiParagraph.didExceedMaxLines)
            .put("lineCount", result.lineCount).put("maxLines", input.maxLines).put("softWrap", input.softWrap).put("overflow", input.overflow.toString())
            .put("style", input.style.toString()).put("density", density(input.density))
            // Public logical character boxes, not a claim about rasterized glyph-ink bounds.
            .put("characterBoxesTruncated", input.text.length > 512)
            .put("characterBoxes", JSONArray().apply {
                repeat(input.text.length.coerceAtMost(512)) { offset -> put(JSONObject()
                    .put("utf16Offset", offset).put("character", input.text[offset].toString())
                    .put("bounds", result.getBoundingBox(offset).toString())) }
            })
            .put("lines", JSONArray().apply {
                repeat(result.lineCount) { line -> put(JSONObject()
                    .put("start", result.getLineStart(line)).put("end", result.getLineEnd(line))
                    .put("visibleEnd", result.getLineEnd(line, visibleEnd = true))
                    .put("left", result.getLineLeft(line)).put("right", result.getLineRight(line))
                    .put("top", result.getLineTop(line)).put("bottom", result.getLineBottom(line))
                    .put("ellipsized", result.isLineEllipsized(line))) }
            })
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { stream ->
            val buffer = ByteArray(1024 * 1024)
            while (true) { val count = stream.read(buffer); if (count < 0) break; digest.update(buffer, 0, count) }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}
