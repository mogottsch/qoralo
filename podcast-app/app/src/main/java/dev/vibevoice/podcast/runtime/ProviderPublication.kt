package dev.vibevoice.podcast.runtime

import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest
import java.util.UUID

/** Preserve the completed source; stage beside destination to respect the existing durable atomic-commit contract. */
internal object ProviderPublication {
    fun publish(source: File, destination: File, expectedSha256: String) {
        require(source.isFile && hash(source) == expectedSha256) { "Completed provider artifact changed" }
        val parent = requireNotNull(destination.parentFile)
        require(parent.isDirectory || parent.mkdirs())
        val staged = File(parent, ".provider-publish-${UUID.randomUUID()}.tmp")
        require(staged.createNewFile())
        try {
            FileOutputStream(staged).use { output -> source.inputStream().use { it.copyTo(output) };output.fd.sync() }
            require(hash(staged) == expectedSha256) { "Provider publication copy integrity mismatch" }
            AtomicArtifactCommit.commit(staged, destination)
        } finally { staged.delete() }
    }
    fun hash(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input -> val buffer=ByteArray(65536);while(true) {val n=input.read(buffer);if(n<0) break;digest.update(buffer,0,n)} }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}
