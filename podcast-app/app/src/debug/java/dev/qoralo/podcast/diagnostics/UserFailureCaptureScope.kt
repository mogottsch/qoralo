package dev.qoralo.podcast.diagnostics

import org.json.JSONObject

/** Pure policy shared by the debug adapter and host fixtures. No implicit opt-in or wildcard episode. */
internal class UserFailureCaptureScope(bytes: ByteArray) {
    val control: JSONObject
    val runId: String
    init {
        require(bytes.size <= 8192)
        control = JSONObject(bytes.toString(Charsets.UTF_8))
        require(control.keys().asSequence().toSet() == setOf("schemaVersion", "runId", "episodeId", "instructionsSha256",
            "sourceSha256s", "gemmaManifestSha256", "appApkSha256"))
        require(control.getInt("schemaVersion") == 1)
        runId = control.getString("runId")
        require(Regex("[a-z0-9-]{1,64}").matches(runId))
        require(Regex("[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}").matches(control.getString("episodeId")))
    }
    fun requireOwnership(
        episodeId: String, jobEpisodeId: String, jobKind: String, jobStatus: String, phase: String,
        reviewEnabled: Boolean, hasActiveRevision: Boolean, hasLockedRevision: Boolean,
        instructions: String, sourceSha256s: List<String>, gemmaManifestSha256: String, appApkSha256: String,
    ) {
        require(control.getString("episodeId") == episodeId && jobEpisodeId == episodeId)
        require(jobKind == "SCRIPT" && jobStatus == "QUEUED" && phase == "GENERATING_SCRIPT")
        require(reviewEnabled && !hasActiveRevision && !hasLockedRevision)
        require(control.getString("instructionsSha256") == PrivateFailureReceipt.sha256(instructions.toByteArray(Charsets.UTF_8)))
        val expected = control.getJSONArray("sourceSha256s").let { a -> List(a.length()) { a.getString(it) }.sorted() }
        require(expected.isNotEmpty() && expected == sourceSha256s.sorted())
        require(control.getString("gemmaManifestSha256") == gemmaManifestSha256)
        require(control.getString("appApkSha256") == appApkSha256)
    }
}
