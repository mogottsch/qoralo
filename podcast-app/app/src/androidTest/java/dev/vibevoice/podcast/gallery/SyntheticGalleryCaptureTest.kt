package dev.vibevoice.podcast.gallery

import android.accessibilityservice.AccessibilityServiceInfo
import android.app.UiAutomation
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Rect
import android.os.Build
import android.os.SystemClock
import android.view.accessibility.AccessibilityNodeInfo
import android.view.accessibility.AccessibilityWindowInfo
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/** Emulator-only, real merged accessibility trees; missing trees are evidence failures, not rendering verdicts. */
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
        // Connect accessibility before launching a separate-process Compose window.
        val automation = instrumentation.uiAutomation
        val serviceInfo = requireNotNull(automation.serviceInfo)
        val originalFlags = serviceInfo.flags
        automation.serviceInfo = serviceInfo.apply { flags = flags or AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS }
        val results = JSONArray()
        var launched = false
        var failed = false
        try {
            for (frame in frames) {
                val token = "$run-$frame"
                val metadata = JSONObject().put("frame", frame).put("token", token).put("runId", run)
                    .put("expectedPackage", context.packageName).put("ownershipMethod", "gallery decor AccessibilityNodeInfo.windowId → UiAutomation window.id")
                    .put("imeRequested", ime).put("imeClickSucceeded", false).put("acknowledged", false)
                    .put("evidenceType", "synthetic-emulator-ui-no-model-inference")
                    .put("appApkPath", context.applicationInfo.sourceDir).put("deviceFingerprint", Build.FINGERPRINT)
                    .put("screenshotStatus", "not-attempted").put("treeStatus", "not-attempted")
                File(output, "$frame-metadata.json").writeText(metadata.toString(2))
                val problems = mutableListOf<String>()
                var selected: GalleryWindowObservation? = null
                var expectedPid = -1
                val ready = File(context.filesDir, "ui-gallery-ready.json")
                fun currentOwner(): GalleryAcknowledgement? {
                    val owner = runCatching { JSONObject(ready.readText()) }.getOrNull()
                    metadata.put("lastOwnershipSnapshot", owner ?: JSONObject.NULL)
                    return owner?.let { acknowledgement(it, context.packageName) }
                }
                fun ownedRoot(window: GalleryWindowObservation): AccessibilityNodeInfo {
                    val owner = requireNotNull(currentOwner()) { "Gallery ownership snapshot missing" }
                    check(GalleryCapturePolicy.ownsWindow(frame, token, context.packageName, expectedPid, owner, window.id, SystemClock.elapsedRealtime())) {
                        "Gallery window ownership changed or expired after readiness"
                    }
                    return liveRoot(automation, window)
                }
                val observations = ArrayDeque<JSONObject>()
                try {
                    context.startActivity(Intent(context, SyntheticGalleryActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        .putExtra("frame", frame).putExtra("token", token))
                    launched = true
                    val deadline = SystemClock.elapsedRealtime() + 10_000
                    var state: JSONObject? = null
                    var acknowledged = false
                    while (SystemClock.elapsedRealtime() < deadline) {
                        state = runCatching { JSONObject(ready.readText()) }.getOrNull()
                        acknowledged = state?.let {
                            GalleryCapturePolicy.acknowledges(frame, token, context.packageName, acknowledgement(it, context.packageName))
                        } == true
                        if (acknowledged) break
                        Thread.sleep(100)
                    }
                    metadata.put("acknowledged", acknowledged).put("acknowledgement", state ?: JSONObject.NULL)
                    check(acknowledged) { "Gallery acknowledgement identity/deadline failure" }
                    expectedPid = requireNotNull(state).getInt("pid")
                    fun waitForWindow(expectIme: Boolean): GalleryWindowObservation? {
                        val result = GalleryCapturePolicy.awaitWindow(context.packageName, token, expectIme,
                            SystemClock::elapsedRealtime, Thread::sleep, {
                                sampleWindows(automation, frame, token, context.packageName, expectedPid, currentOwner())
                            }, { windows ->
                                if (observations.size == 12) observations.removeFirst()
                                observations.addLast(JSONObject().put("elapsedRealtimeMs", SystemClock.elapsedRealtime())
                                    .put("windows", JSONArray(windows.map(::windowJson))))
                            })
                        metadata.put(if (expectIme) "imeWindowPolls" else "windowPolls", result.polls)
                            .put("imeWindowPresent", result.windows.any { it.ime && it.nonemptyBounds })
                        return result.selected
                    }
                    selected = waitForWindow(false)
                    check(selected != null) { "Correct live gallery window/root did not stabilize within 10 seconds" }
                    if (ime) {
                        val root = ownedRoot(selected)
                        val editors = editableNodes(root).filter { it.isVisibleToUser }
                        val editor = if (frame == "paste") editors.firstOrNull() else editors.lastOrNull()
                        val clicked = editor?.performAction(AccessibilityNodeInfo.ACTION_CLICK) ?: false
                        metadata.put("imeClickSucceeded", clicked)
                        if (!clicked) problems += "IME editor click unavailable"
                        val imeSelected = waitForWindow(true)
                        if (imeSelected == null) problems += "IME/window readiness timeout"
                        // No stale pre-IME root is accepted as ready after a failed IME wait.
                        selected = imeSelected
                    }
                } catch (error: Exception) {
                    problems += "readiness: ${error.javaClass.simpleName}: ${error.message}"
                    File(output, "$frame-error.txt").writeText(error.stackTraceToString())
                }
                metadata.put("windowObservations", JSONArray(observations.toList()))
                    .put("selectedWindow", selected?.let(::windowJson) ?: JSONObject.NULL)
                    .put("screenshotWindowVerifiedAtReadiness", selected != null)
                val issues = GalleryCapturePolicy.retainEvidence(selected != null, problems,
                    screenshot = {
                        metadata.put("screenshotElapsedRealtimeMs", SystemClock.elapsedRealtime())
                        val bitmap = requireNotNull(automation.takeScreenshot()) { "UiAutomation returned no screenshot" }
                        try {
                            File(output, "$frame.png").outputStream().use { check(bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)) }
                            metadata.put("screenshotWidth", bitmap.width).put("screenshotHeight", bitmap.height).put("screenshotStatus", "retained")
                        } finally { bitmap.recycle() }
                    },
                    tree = {
                        val root = ownedRoot(requireNotNull(selected))
                        val budget = TreeBudget(SystemClock.elapsedRealtime() + 5000)
                        val tree = nodeJson(root, budget)
                        File(output, "$frame-accessibility.json").writeText(tree.toString(2))
                        metadata.put("treeStatus", if (budget.truncated) "partial" else "retained").put("treeWindowId", root.windowId)
                        check(!budget.truncated) { "Tree changed or exceeded 512 nodes / 5-second extraction budget; partial tree retained" }
                    },
                    metadata = { errors ->
                        metadata.put("status", if (errors.isEmpty() && metadata.optString("treeStatus") == "retained") "complete" else "partial")
                            .put("problems", JSONArray(errors))
                        if (selected == null) metadata.put("treeStatus", "unavailable")
                        else if (errors.any { it.startsWith("accessibility-tree:") } && metadata.optString("treeStatus") != "partial") metadata.put("treeStatus", "unavailable")
                        if (errors.any { it.startsWith("screenshot:") }) metadata.put("screenshotStatus", "unavailable")
                        File(output, "$frame-metadata.json").writeText(metadata.toString(2))
                    })
                results.put(JSONObject().put("frame", frame).put("token", token).put("status", if (issues.isEmpty()) "complete" else "partial")
                    .put("problems", JSONArray(issues)))
                failed = failed || issues.isNotEmpty()
                File(output, "run-summary.json").writeText(JSONObject().put("runId", run).put("frames", results)
                    .put("complete", !failed && results.length() == frames.size).toString(2))
                if (hold > 0) Thread.sleep(hold)
            }
            check(!failed) { "One or more gallery captures were partial; screenshots/metadata and all requested frame results retained" }
        } catch (error: Throwable) {
            File(output, "capture-error.txt").writeText(error.stackTraceToString())
            throw error
        } finally {
            try {
                if (launched) context.startActivity(Intent(context, SyntheticGalleryActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK).putExtra("finish", true))
            } finally {
                automation.serviceInfo = requireNotNull(automation.serviceInfo).apply { flags = originalFlags }
            }
        }
    }

    private fun acknowledgement(value: JSONObject, packageName: String): GalleryAcknowledgement {
        val windows = value.optJSONArray("observedWindows") ?: JSONArray()
        val ids = (0 until windows.length()).mapNotNull { index ->
            val window = windows.optJSONObject(index)
            window?.optInt("windowId", -1)?.takeIf { it >= 0 && window.optString("rootPackage") == packageName }
        }.toSet()
        return GalleryAcknowledgement(value.optString("frame"), value.optString("token"), value.optString("process"),
            value.optInt("pid"), value.optBoolean("syntheticUiOnly"), ids, value.optLong("sampledAtElapsedMs", -1))
    }

    private fun sampleWindows(automation: UiAutomation, frame: String, token: String, packageName: String, expectedPid: Int, owner: GalleryAcknowledgement?): List<GalleryWindowObservation> = automation.windows.map { window ->
        val bounds = Rect().also(window::getBoundsInScreen)
        val root = window.root
        GalleryWindowObservation(window.id, window.type == AccessibilityWindowInfo.TYPE_APPLICATION, window.type == AccessibilityWindowInfo.TYPE_INPUT_METHOD,
            window.title?.toString(), root?.packageName?.toString(), window.isActive, window.isFocused, window.layer, bounds.toShortString(), !bounds.isEmpty,
            root != null, root != null && (root.childCount > 0 || !root.text.isNullOrBlank() || !root.contentDescription.isNullOrBlank()), root?.isVisibleToUser == true,
            token.takeIf { owner != null && GalleryCapturePolicy.ownsWindow(frame, token, packageName, expectedPid, owner, window.id, SystemClock.elapsedRealtime()) }, root?.windowId)
    }

    private fun liveRoot(automation: UiAutomation, expected: GalleryWindowObservation): AccessibilityNodeInfo {
        val window = automation.windows.single { it.id == expected.id && it.title?.toString() == expected.title }
        return requireNotNull(window.root).also {
            check(it.windowId == expected.id && it.packageName?.toString() == expected.rootPackage && it.isVisibleToUser) { "Window/root changed after readiness" }
        }
    }

    private fun windowJson(w: GalleryWindowObservation) = JSONObject().put("id", w.id).put("application", w.application).put("ime", w.ime)
        .put("title", w.title ?: JSONObject.NULL).put("rootPackage", w.rootPackage ?: JSONObject.NULL).put("active", w.active).put("focused", w.focused)
        .put("layer", w.layer).put("bounds", w.bounds).put("rootAvailable", w.rootAvailable).put("rootHasContent", w.rootHasContent).put("rootVisible", w.rootVisible)
        .put("verifiedOwnerToken", w.verifiedOwnerToken ?: JSONObject.NULL).put("rootWindowId", w.rootWindowId ?: JSONObject.NULL)

    private fun editableNodes(node: AccessibilityNodeInfo, remainingDepth: Int = 30): List<AccessibilityNodeInfo> = buildList {
        if (node.isEditable) add(node)
        if (remainingDepth > 0) for (index in 0 until node.childCount) node.getChild(index)?.let { addAll(editableNodes(it, remainingDepth - 1)) }
    }

    private class TreeBudget(val deadline: Long, var nodes: Int = 0, var truncated: Boolean = false)
    private fun nodeJson(node: AccessibilityNodeInfo, budget: TreeBudget, depth: Int = 0): JSONObject = JSONObject().apply {
        if (++budget.nodes > 512 || depth > 40 || SystemClock.elapsedRealtime() >= budget.deadline) {
            budget.truncated = true; put("unavailable", "extraction budget"); return@apply
        }
        val bounds = Rect().also(node::getBoundsInScreen)
        put("text", node.text?.toString() ?: JSONObject.NULL); put("contentDescription", node.contentDescription?.toString() ?: JSONObject.NULL)
        put("className", node.className?.toString()); put("resourceId", node.viewIdResourceName ?: JSONObject.NULL)
        put("packageName", node.packageName?.toString()); put("windowId", node.windowId)
        put("clickable", node.isClickable); put("editable", node.isEditable); put("visibleToUser", node.isVisibleToUser)
        put("enabled", node.isEnabled); put("focused", node.isFocused); put("checked", node.isChecked)
        put("bounds", bounds.toShortString()); put("actions", JSONArray(node.actionList.map { it.id }))
        val children = JSONArray()
        for (index in 0 until node.childCount) {
            val child = node.getChild(index)
            if (child == null) { budget.truncated = true; children.put(JSONObject().put("unavailable", "child changed")) }
            else children.put(nodeJson(child, budget, depth + 1))
            if (budget.truncated) break
        }
        put("children", children)
    }
}
