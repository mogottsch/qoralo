package dev.qoralo.podcast.wiring

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.io.File
import java.nio.file.FileAlreadyExistsException

@RunWith(RobolectricTestRunner::class)
class WiringEvidenceTest {
    @get:Rule val folder = TemporaryFolder()

    @Test fun terminalFailureCannotBeReplacedWithSuccess() {
        val evidence = WiringEvidence(folder.root)
        evidence.finish("failed", "gemma-outline", IllegalStateException("injected recording test"))
        evidence.finish("observations_complete", "finished")
        val result = JSONObject(File(folder.root, "service-result.json").readText())
        assertEquals("failed", result.getString("status"))
        assertEquals("gemma-outline", result.getString("stage"))
    }

    @Test fun repeatedRequestEvidenceCannotOverwriteRawOutput() {
        val evidence = WiringEvidence(folder.root)
        evidence.write("request.txt", "first")
        assertThrows(FileAlreadyExistsException::class.java) { evidence.write("request.txt", "second") }
        assertEquals("first", File(folder.root, "request.txt").readText())
    }
}
