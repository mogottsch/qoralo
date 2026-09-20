package dev.qoralo.podcast.runtime

import dev.qoralo.podcast.data.ArtifactStore
import org.json.JSONObject
import java.io.File
import java.io.RandomAccessFile
import java.nio.file.Files
import java.security.MessageDigest
import java.util.UUID

/** Logical timeline identity. PCM availability must never cross any of these boundaries. */
data class AudioAttemptBinding(val episodeId: String, val jobId: String, val revisionId: String, val revisionSha256: String, val packSha256: String,
    val frontendVersion: String? = null)
enum class AudioPassageKind { PROVIDER_SEGMENT, COMPLETE_CHAPTER }
data class TranscriptPassage(val chapterId: String, val chapterPosition: Int, val segmentIndex: Int,
    val sourceStartUtf16: Int, val sourceEndUtf16: Int, val speechStartFrame: Long, val endFrame: Long)
data class AvailableAudioChunk(
    val index: Int, val chapterPosition: Int, val chapterId: String, val segmentIndex: Int,
    val file: File, val sha256: String, val startFrame: Long, val frameCount: Long, val gapBeforeFrames: Long,
    val passageKind: AudioPassageKind = AudioPassageKind.COMPLETE_CHAPTER, val sourceStartUtf16: Int? = null, val sourceEndUtf16: Int? = null,
) {
    val endFrame: Long get() = startFrame + frameCount
    val speechStartFrame: Long get() = startFrame + gapBeforeFrames
}
enum class AudioAvailabilityState { GENERATING, COMPLETE, FAILED, STALE }
data class AudioAvailability(val binding: AudioAttemptBinding, val chunks: List<AvailableAudioChunk>, val state: AudioAvailabilityState, val problem: String? = null) {
    val availableFrames: Long get() = chunks.lastOrNull()?.endFrame ?: 0
    val availableMs: Long get() = availableFrames * 1000L / 44100L
    val canListen: Boolean get() = chunks.isNotEmpty() && state != AudioAvailabilityState.STALE
}

/** Append-only hash-linked metadata + closed immutable PCM files. No growing WAV is exposed. */
class ProgressiveAudio private constructor(private val artifacts: ArtifactStore, val binding: AudioAttemptBinding, private val directory: File) {
    private var count = 0
    private var frames = 0L
    private var previousChapter = -1
    private var previousSegment = -1
    private var previousHash = hash(File(directory,"binding.json").readBytes())

    fun append(chapterPosition: Int, chapterId: String, segmentIndex: Int, source: File, metadata: AudioMetadata,
        passageKind: AudioPassageKind = AudioPassageKind.COMPLETE_CHAPTER, sourceStartUtf16: Int? = null, sourceEndUtf16: Int? = null): AvailableAudioChunk {
        if (passageKind == AudioPassageKind.PROVIDER_SEGMENT) require(binding.frontendVersion == ProviderTextFrontend.VERSION && sourceStartUtf16 != null && sourceEndUtf16 != null && sourceStartUtf16 >= 0 && sourceEndUtf16 > sourceStartUtf16)
        else require(sourceStartUtf16 == null && sourceEndUtf16 == null)
        require(WavInspector.inspectSupertonicOutput(source) == metadata && source.length() == 44 + metadata.frameCount * 2)
        val gap = when {
            count == 0 -> { require(chapterPosition == 0 && segmentIndex == 0); 0L }
            chapterPosition == previousChapter -> { require(segmentIndex == previousSegment + 1); 13230L }
            else -> { require(chapterPosition == previousChapter + 1 && segmentIndex == 0); 30870L }
        }
        val media = File(directory,"${count.toString().padStart(6,'0')}.wav")
        require(!media.exists())
        val temporary = File(directory,".media-${UUID.randomUUID()}.tmp")
        try {
            withLeadingGap(source,metadata,temporary,gap)
            val ready = WavInspector.inspectSupertonicOutput(temporary)
            require(ready.frameCount == gap + metadata.frameCount)
            AtomicArtifactCommit.commit(temporary,media)
            val mediaReadyNs = System.nanoTime()
            val entry = JSONObject().put("schemaVersion",1).put("bindingSha256",bindingHash(binding))
                .put("mediaClosedAndVerifiedNs",mediaReadyNs)
                .put("index",count).put("chapterPosition",chapterPosition).put("chapterId",chapterId).put("segmentIndex",segmentIndex)
                .put("media",media.name).put("sha256",ready.sha256).put("bytes",media.length()).put("startFrame",frames)
                .put("frameCount",ready.frameCount).put("gapBeforeFrames",gap).put("previousSha256",previousHash)
                .put("passageKind",passageKind.name).put("sourceStartUtf16",sourceStartUtf16 ?: JSONObject.NULL).put("sourceEndUtf16",sourceEndUtf16 ?: JSONObject.NULL)
            val bytes = entry.toString().toByteArray(Charsets.UTF_8)
            writeNew(File(directory,"${count.toString().padStart(6,'0')}.json"),bytes)
            val result = AvailableAudioChunk(count,chapterPosition,chapterId,segmentIndex,media,ready.sha256,frames,ready.frameCount,gap,passageKind,sourceStartUtf16,sourceEndUtf16)
            previousHash = hash(bytes);count++;frames += ready.frameCount;previousChapter=chapterPosition;previousSegment=segmentIndex
            return result
        } finally { temporary.delete() }
    }

    fun finish(totalFrames: Long, masterSha256: String) {
        require(totalFrames == frames && count > 0) { "Live timeline differs from canonical episode" }
        writeNew(File(directory,"completion.json"),JSONObject().put("schemaVersion",1).put("bindingSha256",bindingHash(binding))
            .put("chunks",count).put("frames",frames).put("lastEntrySha256",previousHash).put("masterSha256",masterSha256).toString().toByteArray())
    }

    /** Validation reader caches immutable entries, not speculative/generated duration. */
    class Reader(private val artifacts: ArtifactStore, val binding: AudioAttemptBinding) {
        private val directory = root(artifacts,binding)
        private val entries = mutableListOf<AvailableAudioChunk>()
        private var previousHash = bindingHash(binding)
        private val recordHashes = mutableListOf<String>()
        private val mediaTimes = mutableListOf<Long>()
        @Synchronized fun read(state: AudioAvailabilityState, expectedMasterSha256: String? = null): AudioAvailability {
            if (!directory.isDirectory) return AudioAvailability(binding,emptyList(),state)
            return try {
                val header=File(directory,"binding.json")
                require(header.isFile && header.length() in 1..8192 && header.readBytes().contentEquals(bindingBytes(binding))) { "Audio stream identity changed" }
                entries.forEachIndexed { i, entry ->
                    val record=File(directory,"${i.toString().padStart(6,'0')}.json")
                    require(record.isFile && record.length() in 1..16384 && hash(record.readBytes())==recordHashes[i]) { "Published audio entry changed" }
                    require(entry.file.isFile && entry.file.length()==44+entry.frameCount*2) { "Published audio disappeared" }
                    if(entry.file.lastModified()!=mediaTimes[i]) {
                        require(WavInspector.inspectSupertonicOutput(entry.file).sha256==entry.sha256) { "Published audio changed" }
                        mediaTimes[i]=entry.file.lastModified()
                    }
                }
                while (true) {
                    val file=File(directory,"${entries.size.toString().padStart(6,'0')}.json")
                    if (!file.isFile) break // Next entry has not been atomically published yet.
                    require(file.length() in 1..16384 && !Files.isSymbolicLink(file.toPath()))
                    val bytes=file.readBytes();val value=JSONObject(bytes.toString(Charsets.UTF_8));val index=entries.size
                    require(value.getInt("schemaVersion")==1 && value.getString("bindingSha256")==bindingHash(binding) && value.getInt("index")==index && value.getString("previousSha256")==previousHash)
                    val media=File(directory,value.getString("media"));require(media.parentFile?.canonicalFile==directory.canonicalFile && media.name=="${index.toString().padStart(6,'0')}.wav" && !Files.isSymbolicLink(media.toPath()))
                    require(media.length()==value.getLong("bytes"))
                    val metadata=WavInspector.inspectSupertonicOutput(media)
                    require(metadata.sha256==value.getString("sha256") && metadata.frameCount==value.getLong("frameCount"))
                    val chapter=value.getInt("chapterPosition");val segment=value.getInt("segmentIndex");val prior=entries.lastOrNull()
                    val expectedGap=when {
                        prior==null -> {require(chapter==0 && segment==0);0L}
                        prior.chapterPosition==chapter -> {require(segment==prior.segmentIndex+1);13230L}
                        else -> {require(chapter==prior.chapterPosition+1 && segment==0);30870L}
                    }
                    val start=prior?.endFrame ?: 0L
                    require(value.getLong("startFrame")==start && value.getLong("gapBeforeFrames")==expectedGap && metadata.frameCount>expectedGap && media.length()==44+metadata.frameCount*2)
                    if(prior != null && prior.chapterPosition == chapter) require(value.getString("chapterId") == prior.chapterId)
                    if(expectedGap > 0) RandomAccessFile(media,"r").use { audio ->
                        audio.seek(44);val gap=ByteArray((expectedGap*2).toInt());audio.readFully(gap);require(gap.all { it == 0.toByte() })
                    }
                    val kind = AudioPassageKind.valueOf(value.getString("passageKind"))
                    val sourceStart = if(value.isNull("sourceStartUtf16")) null else value.getInt("sourceStartUtf16")
                    val sourceEnd = if(value.isNull("sourceEndUtf16")) null else value.getInt("sourceEndUtf16")
                    if(kind == AudioPassageKind.PROVIDER_SEGMENT) require(binding.frontendVersion == ProviderTextFrontend.VERSION && sourceStart != null && sourceEnd != null && sourceStart >= 0 && sourceEnd > sourceStart)
                    else require(sourceStart == null && sourceEnd == null)
                    entries += AvailableAudioChunk(index,chapter,value.getString("chapterId"),segment,media,metadata.sha256,start,metadata.frameCount,expectedGap,kind,sourceStart,sourceEnd)
                    previousHash=hash(bytes)
                    recordHashes += previousHash;mediaTimes += media.lastModified()
                }
                if (state == AudioAvailabilityState.COMPLETE) {
                    val final=JSONObject(File(directory,"completion.json").readText())
                    require(final.getString("bindingSha256")==bindingHash(binding) && final.getInt("chunks")==entries.size &&
                        final.getLong("frames")==(entries.lastOrNull()?.endFrame ?: 0L) && final.getString("lastEntrySha256")==previousHash)
                    if(expectedMasterSha256!=null) require(final.getString("masterSha256")==expectedMasterSha256)
                }
                AudioAvailability(binding,entries.toList(),state)
            } catch (_: Exception) {
                // Keep previously verified immutable media available, but never append untrusted new entries.
                AudioAvailability(binding,entries.toList(),AudioAvailabilityState.STALE,"Available audio failed its identity or integrity check")
            }
        }
    }

    companion object {
        fun root(artifacts: ArtifactStore,binding: AudioAttemptBinding): File = artifacts.resolveEpisodeFile("${binding.episodeId}/audio-stream/${binding.jobId}")
        fun bindingBytes(b: AudioAttemptBinding): ByteArray = JSONObject().put("schemaVersion",1).put("episodeId",b.episodeId).put("jobId",b.jobId)
            .put("revisionId",b.revisionId).put("revisionSha256",b.revisionSha256).put("packSha256",b.packSha256).put("frontendVersion",b.frontendVersion ?: JSONObject.NULL).toString().toByteArray(Charsets.UTF_8)
        fun bindingHash(b: AudioAttemptBinding): String = hash(bindingBytes(b))
        fun create(artifacts: ArtifactStore,binding: AudioAttemptBinding): ProgressiveAudio {
            val directory=root(artifacts,binding)
            require(!directory.exists()) { "Audio attempt already has a stream; never replay it into the same timeline" }
            require(directory.mkdirs())
            writeNew(File(directory,"binding.json"),bindingBytes(binding))
            return ProgressiveAudio(artifacts,binding,directory)
        }
        private fun hash(bytes: ByteArray)=MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        private fun writeNew(destination: File,bytes: ByteArray) {
            require(!destination.exists());val temp=File(destination.parentFile,".entry-${UUID.randomUUID()}.tmp")
            try { temp.outputStream().use { it.write(bytes);it.fd.sync() };AtomicArtifactCommit.commit(temp,destination) }
            finally { temp.delete() }
        }
        private fun withLeadingGap(source: File,metadata: AudioMetadata,destination: File,gap: Long) {
            val frames=metadata.frameCount+gap;require(frames*2<=0xffff_ffffL-36 && !destination.exists())
            RandomAccessFile(destination,"rw").use { out ->
                fun u16(x:Int){out.write(x and 255);out.write((x ushr 8) and 255)}
                fun u32(x:Long){u16((x and 65535).toInt());u16(((x ushr 16) and 65535).toInt())}
                out.writeBytes("RIFF");u32(36+frames*2);out.writeBytes("WAVEfmt ");u32(16);u16(1);u16(1);u32(44100);u32(88200);u16(2);u16(16);out.writeBytes("data");u32(frames*2)
                if(gap>0) out.write(ByteArray((gap*2).toInt()))
                source.inputStream().use { input ->
                    require(input.skip(44)==44L);val bytes=ByteArray(65536);var left=metadata.frameCount*2
                    while(left>0){val n=input.read(bytes,0,minOf(left,bytes.size.toLong()).toInt());require(n>0);out.write(bytes,0,n);left-=n}
                    require(input.read()==-1)
                }
                out.fd.sync()
            }
        }
    }
}
