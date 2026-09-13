package dev.vibevoice.podcast.runtime

import dev.vibevoice.podcast.model.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import org.json.JSONArray
import java.io.File
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import java.util.UUID

/** Four reusable HTP contexts; CPU work is only the provider frontend, indices/RNG and WAV assembly. */
class ProviderQnnEngine(private val retainIntermediates: Boolean = false) : TtsEngine {
    private var handle = 0L
    private var indexer = IntArray(0)
    private var contract: SupertonicModelContract? = null
    private var packHash: String? = null
    override var provenance: RuntimeProvenance? = null
        private set

    override suspend fun load(pack: VerifiedModelPack, voiceId: String) = withContext(Dispatchers.IO) {
        require(handle == 0L && voiceId == "M1/SID5")
        require(pack.route == ModelRoute.SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP)
        val shape = pack.contract as? SupertonicModelContract ?: error("Provider contract missing")
        require(shape.providerPipeline != null && shape.textLength == 320 && shape.latentLength == 512 && shape.diffusionSteps == 8)
        val source = pack.files.single { it.role == ModelFileRole.SUPERTONIC_UNICODE_INDEXER }
        val bytes = source.file.readBytes()
        require(bytes.size == 65536 * 4 && sha256(bytes) == source.sha256) { "Provider indexer changed" }
        val view = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        indexer = IntArray(65536) { view.int }
        try {
            currentCoroutineContext().ensureActive()
            NativeAppRuntime.ensureLoaded()
            handle = ProviderNative.create(pack.root.absolutePath)
            currentCoroutineContext().ensureActive()
            require(handle != 0L) { "Provider contexts did not initialize" }
            val actual = validateProvenance(ProviderNative.provenance(handle), "SUPERTONIC_3_PROVIDER_PIPELINE", "QNN_HTP",
                setOf("duration_context", "text_context", "vector_context", "vocoder_context", "htp", "native_text_edges", "native_latent_edges", "numpy_legacy_rng"))
            provenance = requireMatchingSupertonicContract(shape, actual)
            contract = shape; packHash = pack.manifestSha256
        } catch (cancelled: CancellationException) { close();throw cancelled }
        catch (error: Throwable) { close(); throw InferenceRouteException("Provider HTP initialization failed; no CPU fallback", error) }
    }

    override suspend fun renderChapter(chapter: FrozenChapter, output: File, onProgress: suspend (TtsSegmentProgress) -> Unit): AudioMetadata = withContext(Dispatchers.IO) {
        val config = requireNotNull(contract)
        require(handle != 0L)
        val segments = ProviderTextFrontend.prepare(chapter.text, indexer)
        require(segments.isNotEmpty() && segments.all { it.textExtent <= config.textLength }) { "A provider sentence segment exceeds the authenticated text capacity; no forced split" }
        require(output.parentFile?.let { it.isDirectory || it.mkdirs() } == true)
        val scratch = File(output.parentFile, ".provider-${UUID.randomUUID()}"); require(scratch.mkdir())
        val pieces = mutableListOf<Pair<File, AudioMetadata>>()
        val temp = File(scratch, "complete-chapter.wav")
        val records = JSONArray()
        val started = System.nanoTime()
        var published = false
        fun receipt(status: String) = JSONObject().put("schemaVersion", 1).put("status", status)
            .put("packSha256", packHash).put("frontendVersion", ProviderTextFrontend.VERSION)
            .put("rawChapterSha256", sha256(chapter.text.toByteArray(Charsets.UTF_8))).put("chapterId", chapter.id)
            .put("steps", 8).put("speedHundredths", 105).put("gapFrames", 13230).put("randomSeed", 20260911)
            .put("provider", "QNN_HTP").put("cpuFallback", false).put("profilingEnabled", false)
            .put("segments", records).put("startedMonotonicNs", started).put("elapsedMs", (System.nanoTime() - started) / 1_000_000.0)
        try {
            ProviderNative.beginChapter(handle)
            var completedFrames = 0L
            var consumedNoise = 0L
            onProgress(TtsSegmentProgress(0, segments.size, 0))
            segments.forEachIndexed { i, segment ->
                currentCoroutineContext().ensureActive()
                val file = File(scratch, "segment-$i.wav")
                val record = JSONObject(ProviderNative.renderSegment(handle, segment.ids, file.absolutePath))
                currentCoroutineContext().ensureActive()
                val metadata = WavInspector.inspectSupertonicOutput(file)
                val nativeL = record.getLong("nativeLatentLength")
                require(record.getInt("nativeTextLength") == segment.textExtent && nativeL in 1..config.latentLength.toLong())
                require(metadata.frameCount == nativeL * 3072 && metadata.frameCount == record.getLong("frameCount"))
                require(record.getLong("noiseOffset") == consumedNoise && record.getLong("noiseConsumed") == 144 * nativeL)
                consumedNoise += 144 * nativeL
                record.put("index", i).put("idsSha256", ProviderAudioPlan.idsHash(segment.ids))
                    .put("processedSha256", sha256(segment.processed.toByteArray(Charsets.UTF_8)))
                    .put("rawSegmentSha256", sha256(segment.raw.toByteArray(Charsets.UTF_8)))
                    .put("waveSha256", metadata.sha256).put("completedAtMs", (System.nanoTime() - started) / 1_000_000.0)
                records.put(record)
                File(scratch, "progress.json").writeText(receipt("rendering").toString(2))
                pieces += file to metadata
                completedFrames += metadata.frameCount + if (i > 0) 13230 else 0
                onProgress(TtsSegmentProgress(i + 1, segments.size, completedFrames, file, metadata))
            }
            ProviderWaveAssembly.assemble(pieces, temp, requireNotNull(config.providerPipeline).gapFrames)
            val result = WavInspector.inspectSupertonicOutput(temp)
            require(result.frameCount == completedFrames)
            val summary = File(scratch, "provider-receipt.json")
            summary.writeText(receipt("complete_chapter").put("frameCount", result.frameCount).put("waveSha256", result.sha256).toString(2))
            ProviderPublication.publish(summary, File(output.parentFile, output.name + ".provider.json"), ProviderPublication.hash(summary))
            ProviderPublication.publish(temp, output, result.sha256)
            published = true
            result
        } catch (cancelled: CancellationException) {
            runCatching { File(scratch,"cancelled.json").writeText(receipt("cancelled").toString(2)) }
            throw cancelled
        } catch (error: Throwable) {
            // Failure artifacts stay private for diagnosis; never delete the first failed waveform/receipt.
            runCatching { File(scratch, "private-failure.json").writeText(receipt("failed").put("error", error.stackTraceToString()).toString(2)) }
            throw InferenceRouteException("Provider chapter synthesis failed; no alternate route, text truncation or forced duration", error)
        } finally {
            // Successful scratch chunks are private intermediates, not user chapters or independently replayable parts.
            if (published && !retainIntermediates) scratch.deleteRecursively()
        }
    }

    override fun close() {
        if (handle != 0L) runCatching { ProviderNative.destroy(handle) }
        handle = 0; contract = null; packHash = null; provenance = null; indexer = IntArray(0)
    }
    private fun sha256(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
}

internal object ProviderNative {
    @JvmStatic external fun create(packRoot: String): Long
    @JvmStatic external fun beginChapter(handle: Long)
    @JvmStatic external fun renderSegment(handle: Long, ids: LongArray, outputPath: String): String
    @JvmStatic external fun provenance(handle: Long): String
    @JvmStatic external fun destroy(handle: Long)
    @JvmStatic external fun gaussianProbe(count: Int): FloatArray
}

/** Joins full native wave extents byte-for-byte, with only the prescribed between-segment silence. */
internal object ProviderWaveAssembly {
    fun assemble(pieces: List<Pair<File, AudioMetadata>>, output: File, gapFrames: Int) {
        require(pieces.isNotEmpty() && gapFrames == 13230 && !output.exists())
        val frames = pieces.sumOf { it.second.frameCount } + (pieces.size - 1).toLong() * gapFrames
        require(frames > 0 && frames * 2 <= 0xffff_ffffL - 36)
        RandomAccessFile(output, "rw").use { out ->
            fun u16(value: Int) { out.write(value and 255); out.write((value ushr 8) and 255) }
            fun u32(value: Long) { u16((value and 65535).toInt()); u16(((value ushr 16) and 65535).toInt()) }
            out.writeBytes("RIFF");u32(36 + frames * 2);out.writeBytes("WAVEfmt ");u32(16)
            u16(1);u16(1);u32(44100);u32(88200);u16(2);u16(16);out.writeBytes("data");u32(frames * 2)
            val zeros = ByteArray(gapFrames * 2); val buffer = ByteArray(65536)
            pieces.forEachIndexed { i, (file, metadata) ->
                require(metadata.sampleRateHz == 44100 && metadata.channelCount == 1 && file.length() == 44 + metadata.frameCount * 2)
                require(WavInspector.inspectSupertonicOutput(file) == metadata) { "Provider segment changed before assembly" }
                if (i > 0) out.write(zeros)
                file.inputStream().use { input ->
                    require(input.skip(44) == 44L)
                    var remaining = metadata.frameCount * 2
                    while (remaining > 0) {
                        val count = input.read(buffer, 0, minOf(buffer.size.toLong(), remaining).toInt())
                        require(count > 0) { "Incomplete provider segment" };out.write(buffer, 0, count);remaining -= count
                    }
                    require(input.read() == -1)
                }
            }
            out.fd.sync()
            require(out.length() == 44 + frames * 2)
        }
    }
}

/** Keeps legacy packs readable while routing the new provider contract explicitly, never as fallback. */
class ConfiguredTtsEngine : TtsEngine {
    private var engine: TtsEngine? = null
    override val provenance: RuntimeProvenance? get() = engine?.provenance
    override suspend fun load(pack: VerifiedModelPack, voiceId: String) {
        require(engine == null)
        val next = if ((pack.contract as? SupertonicModelContract)?.providerPipeline != null) ProviderQnnEngine(RuntimeDiagnostics.retainProviderIntermediates()) else SupertonicQnnHtpEngine()
        engine = next
        next.load(pack, voiceId)
    }
    override suspend fun renderChapter(chapter: FrozenChapter, output: File, onProgress: suspend (TtsSegmentProgress) -> Unit): AudioMetadata =
        requireNotNull(engine).renderChapter(chapter, output, onProgress)
    override fun close() { engine?.close(); engine = null }
}
