package dev.vibevoice.podcast.runtime

import com.google.ai.edge.litertlm.LiteRtLmJniException
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException
import java.util.concurrent.CancellationException

class GemmaRequestExecutionTest {
    private val secret = "PRIVATE_SOURCE_SENTINEL_773"
    private class Conversation(val closeError: Throwable? = null) : AutoCloseable {
        var closed = 0
        override fun close() { closed++; closeError?.let { throw it } }
    }
    private fun failure(block: () -> Unit): GemmaRequestException {
        try { block(); error("expected failure") } catch (error: GemmaRequestException) { return error }
    }

    @Test fun sameSingleSendCloseAndExtractionPreserveReturnedBytes() {
        val conversation = Conversation(); var sends = 0; var observed: String? = null
        val raw = "```json\n{\"id\":\"chapter-5\",\"text\":\"$secret\"}\n```"
        val json = executeGemmaRequest("chapter", { conversation }, { sends++; raw }, { observed = it })
        assertEquals(raw, observed); assertEquals(raw.substringAfter('\n').substringBeforeLast('\n'), json)
        assertEquals(1, sends); assertEquals(1, conversation.closed)
    }
    @Test fun creationFailureDoesNotSendAndReportsActualCauseWithoutMessage() {
        val original = LiteRtLmJniException("RESOURCE_EXHAUSTED: $secret")
        val result = failure { executeGemmaRequest<Conversation>("chapter", { throw original }, { error("no send") }) }
        assertSame(original, result.cause); assertEquals(GemmaFailurePhase.CONVERSATION_CREATE, result.failurePhase)
        assertEquals("RESOURCE_EXHAUSTED", result.typeGraph.nodes.single().sdkStatus)
        assertFalse(generationFailureMessage(result).contains(secret))
    }
    @Test fun sendFailureKeepsPrimaryAndSuppressedCloseErrors() {
        val original = LiteRtLmJniException("Status Code: 13. Message: $secret")
        val close = IOException("private close $secret"); val conversation = Conversation(close)
        val result = failure { executeGemmaRequest("chapter", { conversation }, { throw original }) }
        assertSame(original, result.cause); assertSame(close, original.suppressed.single())
        assertEquals(GemmaFailurePhase.SEND, result.failurePhase); assertEquals(1, conversation.closed)
        assertEquals("code_13", result.typeGraph.nodes[0].sdkStatus)
        assertEquals(listOf(1), result.typeGraph.nodes[0].suppressed)
        assertFalse(generationFailureMessage(result).contains(secret))
    }
    @Test fun closeOnlyFailureStillObservesReturnedOutput() {
        val original = IOException(secret); val conversation = Conversation(original); var observed: String? = null
        val result = failure { executeGemmaRequest("chapter", { conversation }, { "{\"text\":\"$secret\"}" }, { observed = it }) }
        assertEquals(GemmaFailurePhase.CONVERSATION_CLOSE, result.failurePhase)
        assertSame(original, result.cause); assertTrue(observed!!.contains(secret)); assertEquals(1, conversation.closed)
    }
    @Test fun cancellationRetainsOriginalCauseAndSuppressedCloseWithoutRetry() {
        val cancelled = CancellationException(secret); val close = IOException("close $secret")
        val conversation = Conversation(close); var sends = 0
        val result = assertThrows(CancellationException::class.java) {
            executeGemmaRequest("chapter", { conversation }, { sends++; throw cancelled })
        }
        assertSame(cancelled, result); assertSame(close, cancelled.suppressed.single())
        assertEquals(1, sends); assertEquals(1, conversation.closed)
        assertFalse(generationFailureMessage(result).contains(secret))
    }
    @Test fun missingObjectAndTruncatedObjectRemainExtractionFailuresWithoutRepair() {
        for (raw in listOf("", "[$secret]", "{\"text\":\"$secret")) {
            val result = failure { executeGemmaRequest("chapter", { Conversation() }, { raw }) }
            assertEquals(GemmaFailurePhase.JSON_EXTRACTION, result.failurePhase)
            assertFalse(generationFailureMessage(result).contains(secret))
        }
    }
    @Test fun malformedReturnedObjectIsParsingFailureNotGpuFailure() {
        val result = failure { executeGemmaRequest("chapter", { Conversation() }, { "{\"text\":\"$secret}" }) }
        assertEquals(GemmaFailurePhase.JSON_PARSE, result.failurePhase)
        assertEquals("org.json.JSONException", result.typeGraph.nodes.single().type)
        assertFalse(generationFailureMessage(result).contains(secret))
    }
    @Test fun observationFailuresCannotChangeValidResultOrOriginalFailure() {
        assertEquals("{}", executeGemmaRequest("chapter", { Conversation() }, { "{}" }, { throw IOException(secret) }))
        val original = IOException(secret)
        val result = failure { executeGemmaRequest("chapter", { Conversation() }, { throw original }, failed = { throw IOException("receipt $secret") }) }
        assertSame(original, result.cause)
    }
    @Test fun cyclicCauseAndSuppressedGraphIsFiniteContentFreeAndLinked() {
        val a = IOException(secret); val b = IllegalArgumentException(secret); val c = IllegalStateException(secret)
        a.initCause(b); b.initCause(a); a.addSuppressed(c); c.initCause(a)
        val graph = FailureTypeGraph.capture(a)
        assertEquals(3, graph.nodes.size); assertEquals(1, graph.nodes[0].cause)
        assertEquals(0, graph.nodes[1].cause); assertEquals(listOf(2), graph.nodes[0].suppressed)
        assertEquals(0, graph.nodes[2].cause); assertFalse(graph.truncated); assertFalse(graph.safeText().contains(secret))
    }
    @Test fun oversizedGraphIsExplicitlyBoundedAndOuterWrapperPreservesSafeDetails() {
        var error: Throwable = IOException(secret)
        repeat(20) { error = IllegalStateException(secret, error) }
        repeat(6) { error.addSuppressed(IOException(secret)) }
        val result = failure { executeGemmaRequest("chapter", { Conversation() }, { throw error }) }
        assertTrue(result.typeGraph.truncated); assertEquals(8, result.typeGraph.nodes.size)
        val text = generationFailureMessage(RuntimeException(secret, result))
        assertTrue(text.length <= 1000); assertFalse(text.contains(secret)); assertTrue(text.contains("SEND"))
    }
    @Test fun unwrappedSchemaErrorAndDeepOuterWrapperNeverLeakTheirMessages() {
        val schema = org.json.JSONException("Invalid array from $secret")
        val direct = generationFailureMessage(schema)
        assertFalse(direct.contains(secret)); assertTrue(direct.length <= 1000)
        var wrapped: Throwable = failure { executeGemmaRequest("chapter", { Conversation() }, { throw IOException(secret) }) }
        repeat(20) { wrapped = RuntimeException(secret, wrapped) }
        val text = generationFailureMessage(wrapped)
        assertFalse(text.contains(secret)); assertTrue(text.length <= 1000); assertTrue(text.contains("graph_truncated"))
    }
    @Test fun sdkStatusOnlyComesFromKnownTypeAndWhitelistedPrefix() {
        assertNull(FailureTypeGraph.capture(IOException("INTERNAL: $secret")).nodes[0].sdkStatus)
        assertNull(FailureTypeGraph.capture(LiteRtLmJniException("Status Code: 99. $secret")).nodes[0].sdkStatus)
        assertNull(FailureTypeGraph.capture(LiteRtLmJniException(secret)).nodes[0].sdkStatus)
    }
}
