package dev.vibevoice.podcast.ui

import android.accessibilityservice.AccessibilityServiceInfo
import android.graphics.Bitmap
import android.graphics.Rect
import android.os.Build
import android.os.SystemClock
import android.view.accessibility.AccessibilityNodeInfo
import android.view.accessibility.AccessibilityWindowInfo
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.espresso.Espresso
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.vibevoice.podcast.ui.theme.VibeVoiceTheme
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/** Run at default and actual 320dp/OS font2. No models or repositories; actual keyboard/window geometry. */
@RunWith(AndroidJUnit4::class)
class PasteImeRegressionTest {
    @get:Rule val rule = createComposeRule()

    @Test fun focusedBodyKeepsEntireAddActionAboveActualIme() {
        require(Build.HARDWARE in setOf("ranchu", "goldfish"))
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val automation = instrumentation.uiAutomation
        val previousFlags = automation.serviceInfo.flags
        automation.serviceInfo = automation.serviceInfo.apply { flags = flags or AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS }
        val output = File(context.filesDir, "ui-regressions/paste-ime-${System.currentTimeMillis()}")
        check(!output.exists() && output.mkdirs())
        var submitted: String? = null
        var current: Geometry? = null
        var passed = false
        var captured = false
        fun retain() {
            val bitmap = automation.takeScreenshot()
            if (bitmap != null) {
                try { File(output, "focused-body.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) } }
                finally { bitmap.recycle() }
            }
            File(output, "geometry.json").writeText(JSONObject().put("stage", "focused-body-before-submit-or-failure")
                .put("package", context.packageName).put("fontScale", context.resources.configuration.fontScale)
                .put("scope", "synthetic UI; no models; actual merged accessibility bounds")
                .put("geometry", current?.json() ?: JSONObject.NULL).toString(2))
        }
        try {
            rule.setContent { VibeVoiceTheme { PasteSourceDialog({}, { _, body -> submitted = body }) } }
            rule.onAllNodes(hasSetTextAction())[1].performScrollTo().performClick().performTextInput("Rivers can flood after heavy rain.")
            var previous: Geometry? = null
            var stableSince = SystemClock.elapsedRealtime()
            rule.waitUntil(timeoutMillis = 10_000) {
                val windows = automation.windows
                val ime = windows.firstOrNull { it.type == AccessibilityWindowInfo.TYPE_INPUT_METHOD }
                    ?.let { Rect().also(it::getBoundsInScreen) }?.takeUnless { it.isEmpty }
                current = if (ime == null) null else windows.filter { it.type == AccessibilityWindowInfo.TYPE_APPLICATION }
                    .sortedByDescending { it.layer }.firstNotNullOfOrNull { window ->
                        val root = window.root
                        if (root?.packageName?.toString() != context.packageName) null else findLabel(root)?.let { label ->
                            var button = label
                            while (!button.isClickable) {
                                val parent = button.parent ?: break
                                button = parent
                            }
                            Geometry(window.id, Rect().also(label::getBoundsInScreen), Rect().also(button::getBoundsInScreen), ime,
                                button.isClickable && button.isEnabled && button.isVisibleToUser && label.isVisibleToUser)
                        }
                    }
                if (current != previous) stableSince = SystemClock.elapsedRealtime()
                previous = current
                current?.fits() == true && SystemClock.elapsedRealtime() - stableSince >= 400
            }
            rule.onNodeWithContentDescription("Cancel paste").assertIsDisplayed().assertHasClickAction()
            rule.onNodeWithText("Add source").assertIsDisplayed().assertIsEnabled().assertHasClickAction()
            retain(); captured = true
            rule.onNodeWithText("Add source").performClick()
            rule.runOnIdle { assertEquals("Rivers can flood after heavy rain.", submitted) }
            passed = true
        } finally {
            try {
                // Keep the pre-click screenshot on success, or retain the actual failing geometry.
                if (!captured) retain()
                File(output, "result.json").writeText(JSONObject().put("passed", passed).put("submitted", submitted != null).toString(2))
            } finally {
                try { Espresso.closeSoftKeyboard() } finally {
                    automation.serviceInfo = automation.serviceInfo.apply { flags = previousFlags }
                }
            }
        }
    }

    private fun findLabel(node: AccessibilityNodeInfo, depth: Int = 0): AccessibilityNodeInfo? {
        if (node.text?.toString() == "Add source" && node.isVisibleToUser) return node
        if (depth >= 30) return null
        for (index in 0 until node.childCount) node.getChild(index)?.let { findLabel(it, depth + 1)?.let { result -> return result } }
        return null
    }

    private data class Geometry(val windowId: Int, val label: Rect, val button: Rect, val ime: Rect, val actionable: Boolean) {
        fun fits() = actionable && !button.isEmpty && !label.isEmpty && button.top >= 0 && label.top >= 0 &&
            button.bottom <= ime.top && label.bottom <= ime.top
        fun json() = JSONObject().put("windowId", windowId).put("label", label.toShortString()).put("button", button.toShortString())
            .put("ime", ime.toShortString()).put("actionable", actionable).put("entireActionAboveIme", fits())
    }
}
