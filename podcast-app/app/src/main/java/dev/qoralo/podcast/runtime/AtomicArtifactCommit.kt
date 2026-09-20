package dev.qoralo.podcast.runtime

import java.io.File
import java.io.FileOutputStream
import java.nio.file.CopyOption
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardCopyOption

object AtomicArtifactCommit {
    fun commitDirectory(
        temporary: File,
        destination: File,
        move: (Path, Path, Array<CopyOption>) -> Path = { source, target, options -> Files.move(source, target, *options) },
    ) {
        require(temporary.isDirectory) { "Temporary generation directory does not exist" }
        require(!destination.exists()) { "Generation destination already exists" }
        require(temporary.parentFile?.canonicalFile == destination.parentFile?.canonicalFile) { "Atomic commit requires one filesystem directory" }
        temporary.walkBottomUp().filter(File::isFile).forEach { file -> FileOutputStream(file, true).use { it.fd.sync() } }
        move(temporary.toPath(), destination.toPath(), arrayOf(StandardCopyOption.ATOMIC_MOVE))
        require(destination.isDirectory && !temporary.exists()) { "Atomic generation commit did not complete" }
    }

    fun commit(
        temporary: File,
        destination: File,
        move: (Path, Path, Array<CopyOption>) -> Path = { source, target, options -> Files.move(source, target, *options) },
    ) {
        require(temporary.isFile) { "Temporary artifact does not exist" }
        require(temporary.parentFile?.canonicalFile == destination.parentFile?.canonicalFile) { "Atomic commit requires one filesystem directory" }
        FileOutputStream(temporary, true).use { it.fd.sync() }
        move(
            temporary.toPath(),
            destination.toPath(),
            arrayOf(StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING),
        )
        require(destination.isFile && !temporary.exists()) { "Atomic artifact commit did not complete" }
        FileOutputStream(destination, true).use { it.fd.sync() }
    }
}
