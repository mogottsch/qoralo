package dev.vibevoice.podcast.wiring

import android.content.Context
import dev.vibevoice.podcast.runtime.SupertonicTextNormalizer
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

internal class TtsOnlyContract private constructor(val json: JSONObject, val text: String) {
    fun deadlineMs(stage: String) = json.getJSONObject("deadlineSeconds").getLong(stage) * 1000L
    val voice get() = json.getString("voice")
    val chapterId get() = json.getString("chapterId")
    val manifestSha get() = json.getString("supertonicManifestSha256")

    /** Exact pure native PrepareText reconstruction, NOT observed native tensor memory. */
    fun reconstructedTokens(packRoot: File): JSONObject {
        val normalized = SupertonicTextNormalizer.normalize(text)
        val wrapped = "<en>$normalized</en>"
        val codepoints = wrapped.codePoints().toArray()
        val length = json.getInt("textLength")
        require(codepoints.size <= length)
        val file = File(packRoot, "assets/unicode-indexer.i32")
        val bytes = file.readBytes(); require(bytes.size == 65536 * 4)
        val indexer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asIntBuffer()
        val ids = LongArray(length)
        val mask = FloatArray(length)
        codepoints.forEachIndexed { i, cp ->
            require(cp in 0 until indexer.limit() && indexer.get(cp) >= 0)
            ids[i] = indexer.get(cp).toLong(); mask[i] = 1f
        }
        var seed = 1469598103934665603uL
        chapterId.toByteArray(Charsets.UTF_8).forEach { seed = (seed xor it.toUByte().toULong()) * 1099511628211uL }
        seed = seed xor 20260813uL
        return JSONObject().put("evidenceKind", "deterministic reconstruction from actual request, pinned indexer and unchanged native PrepareText source; not native-buffer capture")
            .put("normalized", normalized).put("wrapped", wrapped).put("wrappedCodepoints", codepoints.size)
            .put("idsDtype", "INT64").put("idsShape", JSONArray(listOf(1, length))).put("ids", JSONArray(ids.toList()))
            .put("maskDtype", "FLOAT32").put("maskShape", JSONArray(listOf(1, 1, length))).put("mask", JSONArray(mask.toList()))
            .put("indexerSha256", WiringEvidence.sha256(file)).put("voiceSha256", WiringEvidence.sha256(File(packRoot, "assets/voice.bin")))
            .put("chapterId", chapterId).put("seedUint64Decimal", seed.toString()).put("seedXor", 20260813)
            .put("rng", "unchanged app chapter-seeded xorshift64star + Box-Muller; fresh per-request arrays")
            .put("speed", 1.0).put("steps", 5).put("voice", voice)
    }

    companion object {
        const val SHA256 = "5844320c0ce2442e16d2d837fc1239bf8e9da05ede672d1249f125d91fdf57ca"
        const val TEXT_SHA = "424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67"
        const val DRIVER_MS = 345_000L
        fun validRunId(value: String) = value.matches(Regex("tts-only-[a-z0-9-]{1,64}"))
        fun load(context: Context): TtsOnlyContract = parse { context.assets.open("tts-only/$it").use { input -> input.readBytes() } }
        internal fun parse(read: (String) -> ByteArray): TtsOnlyContract {
            val bytes = read("contract.json"); require(WiringContract.hash(bytes) == SHA256)
            val json = JSONObject(bytes.toString(Charsets.UTF_8))
            val text = read("canonical.txt"); require(text.size == 226 && WiringContract.hash(text) == TEXT_SHA)
            require(json.getJSONObject("canonical").getString("sha256") == TEXT_SHA)
            return TtsOnlyContract(json, text.toString(Charsets.UTF_8))
        }
    }
}
