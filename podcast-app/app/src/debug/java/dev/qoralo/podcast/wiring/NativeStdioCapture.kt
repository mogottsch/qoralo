package dev.qoralo.podcast.wiring

import android.os.ParcelFileDescriptor
import android.system.Os
import java.io.Closeable
import java.io.File
import java.io.FileDescriptor

/** Capture native stdout/stderr in :generation; successful runs restore descriptors. */
internal class NativeStdioCapture(root: File) : Closeable {
    private val saved = mutableListOf<Pair<FileDescriptor, Int>>()
    init {
        try {
            for ((name, original, target) in listOf(
                Triple("native-stdout.txt", FileDescriptor.out, 1),
                Triple("native-stderr.txt", FileDescriptor.err, 2),
            )) {
                val file = File(root, name)
                check(file.createNewFile())
                val duplicate = Os.dup(original)
                saved += duplicate to target
                ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_WRITE_ONLY or ParcelFileDescriptor.MODE_APPEND).use {
                    Os.dup2(it.fileDescriptor, target)
                }
            }
        } catch (error: Throwable) { close(); throw error }
    }

    override fun close() {
        var failure: Throwable? = null
        saved.asReversed().forEach { (descriptor, target) ->
            try { Os.dup2(descriptor, target) } catch (error: Throwable) { failure = error }
            finally { try { Os.close(descriptor) } catch (error: Throwable) { failure = error } }
        }
        saved.clear()
        failure?.let { throw it }
    }
}
