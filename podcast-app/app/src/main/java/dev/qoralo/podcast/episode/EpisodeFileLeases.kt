package dev.qoralo.podcast.episode

import java.io.Closeable
import java.io.File
import java.io.RandomAccessFile
import java.nio.channels.FileLock
import java.nio.file.Files
import java.nio.file.LinkOption.NOFOLLOW_LINKS
import java.nio.file.SimpleFileVisitor
import java.nio.file.FileVisitResult
import java.nio.file.Path
import java.nio.file.attribute.BasicFileAttributes
import java.util.concurrent.ConcurrentHashMap

class EpisodeDeletedException : IllegalStateException("This episode has been deleted")

/** Shared OS leases survive coroutine cancellation, but are released by process death. A blocked
 * native worker retains its lease until native teardown returns. Never remove/recreate lock files.
 * One shared lock per process is ref-counted to avoid Java's overlapping-lock exception.
 */
class EpisodeFileLeases(private val episodes: File) {
    private val root = File(episodes.absoluteFile.parentFile, episodes.name + "-lifecycle")
    private fun control(id: String): File {
        require(Regex("[A-Za-z0-9][A-Za-z0-9_-]{0,127}").matches(id)) { "Invalid episode identity" }
        require(!Files.isSymbolicLink(root.toPath()))
        require(root.isDirectory || root.mkdirs())
        val dir = File(root, id)
        require(!Files.isSymbolicLink(dir.toPath()))
        require(dir.isDirectory || dir.mkdir())
        return dir
    }
    private fun state(id: String): LocalState {
        val file = File(control(id), "lease.lock")
        require(!Files.isSymbolicLink(file.toPath()))
        return states.computeIfAbsent(file.canonicalPath) { LocalState(file) }
    }
    fun isDeleted(id: String): Boolean = Files.exists(File(control(id), "deleted").toPath(), NOFOLLOW_LINKS)
    fun requireLive(id: String) { if (isDeleted(id)) throw EpisodeDeletedException() }

    /** Does not wait for a model. Durable before the UI acknowledges deletion. */
    fun tombstone(id: String) {
        val directory = control(id)
        val file = File(directory, "deleted")
        synchronized(state(id)) {
            if (!Files.exists(file.toPath(), NOFOLLOW_LINKS)) {
                // The marker carries no text, title, paths, job content or performance data.
                RandomAccessFile(file, "rw").use { it.write(byteArrayOf(1)); it.fd.sync() }
                java.nio.channels.FileChannel.open(directory.toPath()).use { it.force(true) }
            }
        }
    }
    fun tombstonedIds(): List<String> = root.listFiles().orEmpty().filter {
        !Files.isSymbolicLink(it.toPath()) && it.isDirectory && Regex("[A-Za-z0-9][A-Za-z0-9_-]{0,127}").matches(it.name) &&
            Files.exists(File(it, "deleted").toPath(), NOFOLLOW_LINKS)
    }.map { it.name }

    fun acquire(id: String): Closeable {
        val state = state(id)
        synchronized(state) {
            requireLive(id)
            if (state.references == 0) {
                val file = RandomAccessFile(state.file, "rw")
                try {
                    state.lock = file.channel.lock(0, Long.MAX_VALUE, true)
                    state.handle = file
                    requireLive(id) // A deletion may have finished while this lock was waiting.
                } catch (error: Throwable) {
                    state.lock?.release(); state.lock = null; state.handle = null; file.close(); throw error
                }
            }
            state.references++
        }
        return object : Closeable {
            private var closed = false
            override fun close() = synchronized(state) {
                if (!closed) {
                    closed = true
                    check(state.references > 0)
                    if (--state.references == 0) {
                        try { state.lock?.release() } finally { state.handle?.close(); state.lock = null; state.handle = null }
                    }
                }
            }
        }
    }

    /** Cleanup cannot race any leased writer/export/player. No waiting, PID guesses or kills. */
    fun tryCleanupLease(id: String): Closeable? {
        val state = state(id)
        synchronized(state) {
            check(isDeleted(id)) { "Deletion must be durable before cleanup" }
            if (state.references != 0 || state.cleaning) return null
            val file = RandomAccessFile(state.file, "rw")
            val lock = try { file.channel.tryLock() } catch (error: Throwable) { file.close(); throw error }
            if (lock == null) { file.close(); return null }
            state.cleaning = true
            return object : Closeable {
                private var closed = false
                override fun close() = synchronized(state) {
                    if (!closed) { closed = true; try { lock.release() } finally { file.close(); state.cleaning = false } }
                }
            }
        }
    }

    /** Called only with the exclusive cleanup lease. Never follow links or delete outside one ID. */
    fun removeOwnedFiles(id: String, preservedPaths: Set<Path> = emptySet()) {
        check(isDeleted(id))
        val state = state(id)
        synchronized(state) { check(state.cleaning) }
        require(!Files.isSymbolicLink(episodes.toPath()))
        val target = File(episodes, id).toPath()
        if (!Files.exists(target, NOFOLLOW_LINKS)) return
        Files.walkFileTree(target, object : SimpleFileVisitor<Path>() {
            override fun visitFile(file: Path, attrs: BasicFileAttributes): FileVisitResult {
                if (file.toAbsolutePath().normalize() !in preservedPaths) Files.delete(file)
                return FileVisitResult.CONTINUE
            }
            override fun postVisitDirectory(dir: Path, error: java.io.IOException?): FileVisitResult {
                if (error != null) throw error
                if (Files.newDirectoryStream(dir).use { !it.iterator().hasNext() }) Files.delete(dir)
                return FileVisitResult.CONTINUE
            }
        })
    }
    private class LocalState(val file: File) {
        var references = 0
        var cleaning = false
        var handle: RandomAccessFile? = null
        var lock: FileLock? = null
    }
    companion object { private val states = ConcurrentHashMap<String, LocalState>() }
}
