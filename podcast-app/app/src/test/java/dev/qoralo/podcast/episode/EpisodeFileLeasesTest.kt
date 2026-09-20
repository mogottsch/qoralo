package dev.qoralo.podcast.episode

import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.nio.file.Files

class EpisodeFileLeasesTest {
    @get:Rule val temp = TemporaryFolder()
    @Test fun tombstoneRevokesNewLeasesButDoesNotRemoveBlockedWorkersFiles() {
        val root = temp.newFolder("episodes"); val a = EpisodeFileLeases(root); val b = EpisodeFileLeases(root)
        val file = File(root, "owned/audio.wav").apply { parentFile.mkdirs(); writeText("owned") }
        val first = a.acquire("owned"); val second = b.acquire("owned")
        a.tombstone("owned")
        assertTrue(b.isDeleted("owned"))
        assertThrows(EpisodeDeletedException::class.java) { b.acquire("owned") }
        assertNull(b.tryCleanupLease("owned")); assertTrue(file.isFile)
        first.close(); first.close(); assertNull(b.tryCleanupLease("owned"))
        second.close()
        requireNotNull(b.tryCleanupLease("owned")).use { b.removeOwnedFiles("owned") }
        assertFalse(file.exists())
        assertTrue(EpisodeFileLeases(root).isDeleted("owned"))
        assertThrows(EpisodeDeletedException::class.java) { a.acquire("owned") }
    }
    @Test fun onlyOwnedTreeRemovedAndSymlinksNeverFollowed() {
        val root = temp.newFolder("episodes"); val leases = EpisodeFileLeases(root)
        val other = File(root, "other/source.txt").apply { parentFile.mkdirs(); writeText("retain") }
        val model = temp.newFile("model.pack").apply { writeText("model") }
        val owned = File(root, "owned").apply { mkdirs() }
        Files.createSymbolicLink(File(owned, "other-link").toPath(), other.parentFile.toPath())
        Files.createSymbolicLink(File(owned, "model-link").toPath(), model.toPath())
        leases.tombstone("owned")
        requireNotNull(leases.tryCleanupLease("owned")).use { leases.removeOwnedFiles("owned") }
        assertEquals("retain", other.readText()); assertEquals("model", model.readText()); assertFalse(owned.exists())
        for (id in listOf("../other", ".", "", "/other", "a/b")) {
            assertThrows(IllegalArgumentException::class.java) { leases.tombstone(id) }
        }
    }
    @Test fun referencedSourceBytesSurviveOwnedCleanup() {
        val root = temp.newFolder("episodes"); val leases = EpisodeFileLeases(root)
        val shared = File(root, "owned/sources/shared.txt").apply { parentFile.mkdirs(); writeText("shared") }
        val audio = File(root, "owned/audio.wav").apply { writeText("delete") }
        leases.tombstone("owned")
        requireNotNull(leases.tryCleanupLease("owned")).use {
            leases.removeOwnedFiles("owned", setOf(shared.toPath().toAbsolutePath().normalize()))
        }
        assertEquals("shared", shared.readText()); assertFalse(audio.exists())
    }
    @Test fun anotherProcessLeaseBlocksCleanupAndProcessDeathReleasesIt() {
        val root = temp.newFolder("episodes"); val leases = EpisodeFileLeases(root)
        leases.acquire("owned").close() // Materialize the stable lock inode.
        val lock = File(root.parentFile, root.name + "-lifecycle/owned/lease.lock")
        val child = ProcessBuilder("/usr/bin/python3", "-u", "-c",
            "import fcntl,sys; f=open(sys.argv[1],'r+'); fcntl.lockf(f,fcntl.LOCK_SH); print('LEASED',flush=True); sys.stdin.read()", lock.path).start()
        try {
            val ready = java.util.concurrent.CompletableFuture.supplyAsync { child.inputStream.bufferedReader().readLine() }
            assertEquals("LEASED", ready.get(3, java.util.concurrent.TimeUnit.SECONDS))
            leases.tombstone("owned"); assertNull(leases.tryCleanupLease("owned"))
            child.destroyForcibly(); assertTrue(child.waitFor(3, java.util.concurrent.TimeUnit.SECONDS))
            requireNotNull(leases.tryCleanupLease("owned")).use { leases.removeOwnedFiles("owned") }
        } finally { child.destroyForcibly(); child.waitFor(3, java.util.concurrent.TimeUnit.SECONDS) }
    }
    @Test fun cleanupRequiresTombstoneAndExclusiveLease() {
        val leases = EpisodeFileLeases(temp.newFolder("episodes"))
        assertThrows(IllegalStateException::class.java) { leases.tryCleanupLease("owned") }
        leases.tombstone("owned")
        assertThrows(IllegalStateException::class.java) { leases.removeOwnedFiles("owned") }
        requireNotNull(leases.tryCleanupLease("owned")).use { assertNull(leases.tryCleanupLease("owned")) }
    }
}
