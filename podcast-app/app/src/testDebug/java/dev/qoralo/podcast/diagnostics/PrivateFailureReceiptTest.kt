package dev.qoralo.podcast.diagnostics

import dev.qoralo.podcast.runtime.*
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.io.IOException

class PrivateFailureReceiptTest {
    @get:Rule val temp = TemporaryFolder()
    private val secret = "PRIVATE_SOURCE_SENTINEL_991\nquoted \"text\""
    private val identity = JSONObject().put("episodeId", "owned").put("jobId", "owned-job").put("appApkSha256", "a".repeat(64))
    private fun fail(store: PrivateFailureReceipt, send: () -> String, close: () -> Unit = {}): GemmaRequestException {
        try {
            executeGemmaRequest("chapter", { AutoCloseable { close() } }, { send() }, store::responseReturned, store::failed)
            error("expected failure")
        } catch (failure: GemmaRequestException) { return failure }
    }
    private fun root() = File(temp.root, "new-private-run")

    @Test fun exactRequestInstructionConfigRawAndUnderlyingExceptionStayInPrivateReceipt() {
        val root = root(); val store = PrivateFailureReceipt(root, identity)
        val request = JSONObject().put("source", secret).toString(); val system = "instruction $secret"
        store.modelBinding(JSONObject().put("manifestSha256", "b".repeat(64)))
        store.beforeRequest("chapter", request, system, 4096)
        val malformed = "{\"text\":\"$secret}"
        val failure = fail(store, { malformed })
        assertEquals(request, File(root, "request-001/request.json").readText())
        assertEquals(system, File(root, "request-001/system.txt").readText())
        assertEquals(malformed, File(root, "request-001/response.txt").readText())
        val meta = JSONObject(File(root, "request-001/config.json").readText())
        assertEquals(4096, meta.getInt("maxOutputTokens")); assertEquals(8192, meta.getInt("contextTokens"))
        assertEquals(1, meta.getInt("topK")); assertFalse(meta.getBoolean("thinking"))
        assertEquals(PrivateFailureReceipt.sha256(request.toByteArray()), meta.getJSONObject("request").getString("sha256"))
        assertEquals(GemmaFailurePhase.JSON_PARSE, failure.failurePhase)
        assertEquals(failure.cause!!.stackTraceToString(), File(root, "request-001/private-exception.txt").readText())
        assertFalse(generationFailureMessage(failure).contains("PRIVATE_SOURCE_SENTINEL_991"))
        val saved = JSONObject(File(root, "request-001/failure.json").readText())
        assertTrue(saved.getBoolean("sdkReturnedOutput")); assertFalse(saved.isNull("rawResponse"))
        assertTrue(saved.isNull("rawResponseUnavailableReason"))
    }
    @Test fun declaredEditConstraintIsHashBoundWithoutChangingStoredRequestOrResponse() {
        val root = root(); val store = PrivateFailureReceipt(root, identity)
        store.beforeRequest("edit", secret, "unchanged instruction", 4096, EDIT_REVISION_JSON_SCHEMA)
        store.responseReturned("{\"raw\":\"unchanged\"}")
        val config = JSONObject(File(root, "request-001/config.json").readText())
        assertEquals("json_schema", config.getString("responseFormat")); assertTrue(config.getBoolean("constrainedDecoding"))
        assertEquals(EDIT_REVISION_JSON_SCHEMA, File(root, "request-001/response-schema.json").readText())
        assertEquals(PrivateFailureReceipt.sha256(EDIT_REVISION_JSON_SCHEMA.toByteArray()), config.getJSONObject("responseSchema").getString("sha256"))
        assertEquals(secret, File(root, "request-001/request.json").readText())
        assertEquals("{\"raw\":\"unchanged\"}", File(root, "request-001/response.txt").readText())
        store.beforeRequest("chapter", "{}", "sys", 4096)
        val plain = JSONObject(File(root, "request-002/config.json").readText())
        assertEquals("none", plain.getString("responseFormat")); assertFalse(plain.getBoolean("constrainedDecoding"))
        assertTrue(plain.isNull("responseSchema")); assertFalse(File(root, "request-002/response-schema.json").exists())
    }
    @Test fun sdkFailureHasExplicitNoReturnedOutputAndUsefulUnderlyingDetail() {
        val root = root(); val store = PrivateFailureReceipt(root, identity); store.beforeRequest("chapter", "{}", "sys", 4096)
        val original = IOException(secret); val result = fail(store, { throw original })
        assertSame(original, result.cause)
        val saved = JSONObject(File(root, "request-001/failure.json").readText())
        assertFalse(saved.getBoolean("sdkReturnedOutput")); assertTrue(saved.isNull("rawResponse"))
        assertTrue(saved.getString("rawResponseUnavailableReason").contains("has not returned"))
        assertTrue(File(root, "request-001/private-exception.txt").readText().contains("PRIVATE_SOURCE_SENTINEL_991"))
        assertFalse(result.message!!.contains("PRIVATE_SOURCE_SENTINEL_991"))
    }
    @Test fun rawResponseIsKeptWhenConversationCloseFails() {
        val root = root(); val store = PrivateFailureReceipt(root, identity); store.beforeRequest("chapter", "{}", "sys", 4096)
        val raw = JSONObject().put("text", secret).toString(); val close = IOException(secret)
        val result = fail(store, { raw }, { throw close })
        assertEquals(GemmaFailurePhase.CONVERSATION_CLOSE, result.failurePhase); assertSame(close, result.cause)
        assertEquals(raw, File(root, "request-001/response.txt").readText())
    }
    @Test fun receiptWriteFailureNeverOverwritesOrReplacesOriginalException() {
        val root = root(); val store = PrivateFailureReceipt(root, identity); store.beforeRequest("chapter", "{}", "sys", 4096)
        File(root, "request-001/private-exception.txt").writeText("KEEP_EXISTING")
        File(root, "request-001/failure.json").writeText("KEEP_EXISTING_FAILURE")
        val original = IOException(secret); val result = fail(store, { throw original })
        assertSame(original, result.cause)
        assertEquals("KEEP_EXISTING", File(root, "request-001/private-exception.txt").readText())
        assertEquals("KEEP_EXISTING_FAILURE", File(root, "request-001/failure.json").readText())
    }
    @Test fun duplicateCaptureRootRefusesReuseAndLargeOutputIsNotTruncated() {
        val root = root(); val store = PrivateFailureReceipt(root, identity)
        val identityBytes = File(root, "identity.json").readBytes()
        assertThrows(IllegalStateException::class.java) { PrivateFailureReceipt(root, identity) }
        assertArrayEquals(identityBytes, File(root, "identity.json").readBytes())
        store.beforeRequest("chapter", "{}", "sys", 4096)
        val raw = "x".repeat(1_048_577)
        val failure = fail(store, { raw })
        assertEquals(GemmaFailurePhase.JSON_EXTRACTION, failure.failurePhase)
        assertFalse(File(root, "request-001/response.txt").exists())
        val saved = JSONObject(File(root, "request-001/failure.json").readText())
        assertTrue(saved.getBoolean("sdkReturnedOutput")); assertTrue(saved.isNull("rawResponse"))
        assertTrue(saved.getString("rawResponseUnavailableReason").contains("original response unchanged"))
    }
    @Test fun postReturnSchemaFailureKeepsUsefulPrivateDetailsWithoutUiLeak() {
        val root = root(); val store = PrivateFailureReceipt(root, identity); store.beforeRequest("outline", "{}", "sys", 1200)
        val raw = JSONObject().put("chapters", secret).toString()
        val json = executeGemmaRequest("outline", { AutoCloseable {} }, { raw }, store::responseReturned, store::failed)
        val original = try { JSONObject(json).getJSONArray("chapters"); error("expected schema failure") } catch (error: org.json.JSONException) { error }
        store.jobFailed(original)
        val record = JSONObject(File(root, "job-failure.json").readText())
        assertTrue(record.getBoolean("sdkReturnedOutput")); assertFalse(record.isNull("rawResponse"))
        assertFalse(record.getString("safeSummary").contains("PRIVATE_SOURCE_SENTINEL_991"))
        assertTrue(File(root, "private-job-exception.txt").readText().contains("PRIVATE_SOURCE_SENTINEL_991"))
        assertEquals(raw, File(root, "request-001/response.txt").readText())
    }
    @Test fun absentPendingReceiptDoesNotChangeFailureOutcome() {
        val store = PrivateFailureReceipt(root(), identity); val original = IOException(secret)
        assertSame(original, fail(store, { throw original }).cause)
    }
    @Test fun scopeRequiresExactOwnedScriptInputAndRuntimeAndCannotCaptureAnotherEpisode() {
        val eid = "11111111-1111-1111-1111-111111111111"
        fun control() = JSONObject().put("schemaVersion", 1).put("runId", "owned-diagnostic-01").put("episodeId", eid)
            .put("instructionsSha256", PrivateFailureReceipt.sha256(secret.toByteArray())).put("sourceSha256s", JSONArray(listOf("s")))
            .put("gemmaManifestSha256", "g").put("appApkSha256", "a")
        val scope = UserFailureCaptureScope(control().toString().toByteArray())
        fun check(episode: String = eid, kind: String = "SCRIPT", review: Boolean = true, active: Boolean = false,
                  text: String = secret, sources: List<String> = listOf("s"), model: String = "g", apk: String = "a") =
            scope.requireOwnership(episode, eid, kind, "QUEUED", "GENERATING_SCRIPT", review, active, false, text, sources, model, apk)
        check()
        assertThrows(IllegalArgumentException::class.java) { check(episode = "other") }
        assertThrows(IllegalArgumentException::class.java) { check(kind = "AUDIO") }
        assertThrows(IllegalArgumentException::class.java) { check(review = false) }
        assertThrows(IllegalArgumentException::class.java) { check(active = true) }
        assertThrows(IllegalArgumentException::class.java) { check(text = "different") }
        assertThrows(IllegalArgumentException::class.java) { check(sources = listOf("different")) }
        assertThrows(IllegalArgumentException::class.java) { check(model = "different") }
        assertThrows(IllegalArgumentException::class.java) { check(apk = "different") }
        assertThrows(IllegalArgumentException::class.java) { UserFailureCaptureScope(control().put("runId", "../escape").toString().toByteArray()) }
        assertThrows(IllegalArgumentException::class.java) { UserFailureCaptureScope(control().put("extra", "capture all").toString().toByteArray()) }
    }
}
