package dev.qoralo.podcast.gallery

internal data class GalleryWindowObservation(
    val id: Int,
    val application: Boolean,
    val ime: Boolean,
    val title: String?,
    val rootPackage: String?,
    val active: Boolean,
    val focused: Boolean,
    val layer: Int,
    val bounds: String,
    val nonemptyBounds: Boolean,
    val rootAvailable: Boolean,
    val rootHasContent: Boolean,
    val rootVisible: Boolean,
    val verifiedOwnerToken: String?,
    val rootWindowId: Int?,
)

internal data class GalleryWindowReadiness(
    val selected: GalleryWindowObservation?, val windows: List<GalleryWindowObservation>, val polls: Int,
)

internal data class GalleryAcknowledgement(
    val frame: String?, val token: String?, val process: String?, val pid: Int, val synthetic: Boolean,
    val windowIds: Set<Int>, val sampledAtElapsedMs: Long,
)

internal object GalleryCapturePolicy {
    fun selectFrames(requested: String, allowed: List<String>): List<String> {
        val frames = if (requested == "all") allowed else requested.split(',').map { it.trim() }
        require(frames.isNotEmpty() && frames.size <= 15 && frames.all { it in allowed && it != "all" } && frames.distinct().size == frames.size) {
            "Frames must be a nonempty, unique, known selection"
        }
        return frames
    }

    fun captureValidatedPair(contentMatches: Boolean, verifyOwner: (String) -> Unit, captureImage: () -> Unit, publish: () -> Unit): Boolean {
        if (!contentMatches) return false
        verifyOwner("before")
        captureImage()
        verifyOwner("after")
        publish()
        return true
    }

    fun acknowledges(frame: String, token: String, packageName: String, value: GalleryAcknowledgement) =
        value.frame == frame && value.token == token && value.process == "$packageName:ui_gallery" && value.pid > 0 && value.synthetic

    /** IDs come from public View.createAccessibilityNodeInfo() in the acknowledged gallery process. */
    fun ownsWindow(frame: String, token: String, packageName: String, expectedPid: Int, value: GalleryAcknowledgement, windowId: Int, now: Long) =
        acknowledges(frame, token, packageName, value) && value.pid == expectedPid && windowId >= 0 && windowId in value.windowIds &&
            now - value.sampledAtElapsedMs in 0..1500L

    const val WINDOW_TIMEOUT_MS = 10_000L
    const val STABLE_MS = 400L
    const val POLL_MS = 200L

    fun awaitWindow(
        packageName: String,
        token: String,
        requireIme: Boolean,
        now: () -> Long,
        sleep: (Long) -> Unit,
        sample: () -> List<GalleryWindowObservation>,
        observe: (List<GalleryWindowObservation>) -> Unit = {},
        previousWindowIds: Set<Int> = emptySet(),
    ): GalleryWindowReadiness {
        val deadline = now() + WINDOW_TIMEOUT_MS
        var stableSince = now()
        var previous: GalleryWindowObservation? = null
        var windows = emptyList<GalleryWindowObservation>()
        var polls = 0
        while (now() < deadline) {
            windows = sample(); polls++; observe(windows)
            val imeVisible = windows.any { it.ime && it.nonemptyBounds }
            val candidate = windows.filter {
                it.application && it.id !in previousWindowIds && it.verifiedOwnerToken == token && it.rootPackage == packageName &&
                    (it.focused || it.active || requireIme && imeVisible) && it.nonemptyBounds &&
                    it.rootAvailable && it.rootWindowId == it.id && it.rootHasContent && it.rootVisible
            }.maxWithOrNull(compareBy<GalleryWindowObservation> { it.focused }.thenBy { it.layer })
            val imeReady = !requireIme || imeVisible
            if (candidate != previous || !imeReady) stableSince = now()
            if (candidate != null && imeReady && now() < deadline && now() - stableSince >= STABLE_MS) {
                return GalleryWindowReadiness(candidate, windows, polls)
            }
            previous = candidate
            sleep(minOf(POLL_MS, (deadline - now()).coerceAtLeast(0)))
        }
        return GalleryWindowReadiness(null, windows, polls)
    }

    /** Screenshot and partial metadata survive missing roots or a later tree serialization failure. */
    fun retainEvidence(
        rootAvailable: Boolean,
        initialProblems: List<String> = emptyList(),
        screenshot: () -> Unit,
        tree: () -> Unit,
        metadata: (List<String>) -> Unit,
    ): List<String> {
        val problems = initialProblems.toMutableList()
        fun attempt(label: String, action: () -> Unit) {
            try { action() } catch (error: Exception) { problems += "$label: ${error.javaClass.simpleName}: ${error.message}" }
        }
        attempt("partial-metadata") { metadata(problems.toList()) }
        attempt("screenshot", screenshot)
        if (rootAvailable) attempt("accessibility-tree", tree) else problems += "accessibility-tree: unavailable (correct app window/root not ready)"
        attempt("final-metadata") { metadata(problems.toList()) }
        return problems
    }
}
