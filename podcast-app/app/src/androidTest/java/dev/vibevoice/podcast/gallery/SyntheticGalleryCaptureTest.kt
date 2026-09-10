package dev.vibevoice.podcast.gallery

import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Rect
import android.os.Build
import android.os.SystemClock
import android.view.accessibility.AccessibilityNodeInfo
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/** Emulator-only synthetic screenshots/accessibility trees using real production composables. */
@RunWith(AndroidJUnit4::class)
class SyntheticGalleryCaptureTest {
    @Test fun captureStableProductionComposableFixtures() {
        val args = InstrumentationRegistry.getArguments()
        assumeTrue("Explicit synthetic gallery opt-in required", args.getString("galleryApproved") == "synthetic-only")
        require(Build.HARDWARE in setOf("ranchu", "goldfish")) { "Gallery capture is emulator-only; no physical phone" }
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val run = requireNotNull(args.getString("galleryRunId"))
        require(run.matches(Regex("ui-[a-z0-9-]{1,64}")))
        val requested = args.getString("galleryFrame") ?: "all"
        val frames = if (requested == "all") SyntheticGalleryActivity.FRAMES else listOf(requested)
        require(frames.all { it in SyntheticGalleryActivity.FRAMES })
        val ime = args.getString("galleryIme") == "true"
        require(!ime || frames.size == 1 && frames.single() in setOf("paste", "instructions", "agent", "agent-error"))
        val hold = args.getString("galleryHoldMs")?.toLong() ?: 0L
        require(hold in 0..30_000 && (hold == 0L || frames.size == 1))
        val output = File(context.filesDir, "ui-gallery/$run")
        require(!output.exists() && output.mkdirs())
        var launched = false
        try {
            for (frame in frames) {
                val token = "$run-$frame"
                context.startActivity(Intent(context, SyntheticGalleryActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    .putExtra("frame", frame).putExtra("token", token))
                launched = true
                val ready = File(context.filesDir, "ui-gallery-ready.json")
                val deadline = SystemClock.elapsedRealtime() + 10_000
                var state: JSONObject? = null
                while (SystemClock.elapsedRealtime() < deadline) {
                    state = runCatching { JSONObject(ready.readText()) }.getOrNull()
                    if (state?.optString("token") == token && state.optString("frame") == frame) break
                    Thread.sleep(100)
                }
                require(state?.optString("token") == token && state.optString("frame") == frame) { "Gallery did not reach requested frame" }
                require(state.getString("process") == "${context.packageName}:ui_gallery")
                Thread.sleep(750)
                var imeClick = false
                if (ime) {
                    val root = requireNotNull(instrumentation.uiAutomation.rootInActiveWindow)
                    val editors = editableNodes(root).filter { it.isVisibleToUser }
                    val editor = if (frame == "paste") editors.firstOrNull() else editors.lastOrNull()
                    imeClick = editor?.performAction(AccessibilityNodeInfo.ACTION_CLICK) ?: false
                    Thread.sleep(1000)
                }
                val root = requireNotNull(instrumentation.uiAutomation.rootInActiveWindow)
                val screenshot = requireNotNull(instrumentation.uiAutomation.takeScreenshot())
                File(output, "$frame.png").outputStream().use { screenshot.compress(Bitmap.CompressFormat.PNG, 100, it) }
                File(output, "$frame-accessibility.json").writeText(nodeJson(root).toString(2))
                File(output, "$frame-metadata.json").writeText(state.put("screenshotWidth", screenshot.width).put("screenshotHeight", screenshot.height)
                    .put("imeRequested", ime).put("imeClickSucceeded", imeClick).put("evidenceType", "synthetic-emulator-ui-no-model-inference")
                    .put("appApkPath", context.applicationInfo.sourceDir).put("deviceFingerprint", Build.FINGERPRINT).toString(2))
                screenshot.recycle()
                if (hold > 0) Thread.sleep(hold)
            }
        } catch (error: Throwable) {
            File(output, "capture-error.txt").writeText(error.stackTraceToString())
            throw error
        } finally {
            if (launched) context.startActivity(Intent(context, SyntheticGalleryActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK).putExtra("finish", true))
        }
    }

    private fun editableNodes(node: AccessibilityNodeInfo): List<AccessibilityNodeInfo> = buildList {
        if (node.isEditable) add(node)
        for (index in 0 until node.childCount) node.getChild(index)?.let { addAll(editableNodes(it)) }
    }

    private fun nodeJson(node: AccessibilityNodeInfo): JSONObject = JSONObject().apply {
        val bounds = Rect().also(node::getBoundsInScreen)
        put("text", node.text?.toString() ?: JSONObject.NULL)
        put("contentDescription", node.contentDescription?.toString() ?: JSONObject.NULL)
        put("className", node.className?.toString()); put("resourceId", node.viewIdResourceName ?: JSONObject.NULL)
        put("clickable", node.isClickable); put("editable", node.isEditable); put("visibleToUser", node.isVisibleToUser)
        put("bounds", bounds.toShortString()); put("actions", JSONArray(node.actionList.map { it.id }))
        put("children", JSONArray((0 until node.childCount).mapNotNull { node.getChild(it)?.let(::nodeJson) }))
    }
}
