package dev.vibevoice.podcast.wiring

import android.content.Context
import dev.vibevoice.podcast.runtime.SupertonicTextNormalizer
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

internal class TtsOnlyContract private constructor(val json: JSONObject, val text: String, val isLongProbe: Boolean) {
    fun deadlineMs(stage: String) = json.getJSONObject("deadlineSeconds").getLong(stage) * 1000L
    val voice get() = json.getString("voice")
    val chapterId get() = json.getString("chapterId")
    val manifestSha get() = json.getString("supertonicManifestSha256")
    val sha256 get() = if (isLongProbe) LONG_SHA256 else SHA256
    val assetDirectory get() = if (isLongProbe) "tts-long" else "tts-only"
    val packId get() = if (isLongProbe) json.getString("packId") else "supertonic-3"
    val outputName get() = "$chapterId.wav"
    val driverMs get() = json.getLong("driverSeconds") * 1000L

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
        const val LONG_SHA256 = "66f8dcd5e753acabd4f69040496ef476b709c2317ebc41a5d5d926b13c353a87"
        fun approvedHash(value: String?) = value == SHA256 || value == LONG_SHA256
        fun validRunId(value: String, approvedSha: String = SHA256): Boolean = when (approvedSha) {
            SHA256 -> value.matches(Regex("tts-only-[a-z0-9-]{1,64}"))
            LONG_SHA256 -> value.matches(Regex("tts-long-[a-z0-9-]{1,64}"))
            else -> false
        }
        fun load(context: Context, approvedSha: String = SHA256): TtsOnlyContract {
            require(approvedHash(approvedSha))
            val directory = if (approvedSha == LONG_SHA256) "tts-long" else "tts-only"
            return parseVariant(approvedSha) { context.assets.open("$directory/$it").use { input -> input.readBytes() } }
        }
        internal fun parse(read: (String) -> ByteArray) = parseVariant(SHA256, read)
        internal fun parseVariant(approvedSha: String, read: (String) -> ByteArray): TtsOnlyContract {
            require(approvedHash(approvedSha))
            val isLong = approvedSha == LONG_SHA256
            val bytes = read("contract.json"); require(WiringContract.hash(bytes) == approvedSha)
            val json = JSONObject(bytes.toString(Charsets.UTF_8))
            val input = json.getJSONObject(if (isLong) "input" else "canonical")
            val text = read(if (isLong) "narration.txt" else "canonical.txt")
            require(text.size == input.getInt("bytes") && WiringContract.hash(text) == input.getString("sha256"))
            if (isLong) {
                require(json.getString("packId") == "supertonic-3-t2048-l2048-parity")
                val normalized = SupertonicTextNormalizer.normalize(text.toString(Charsets.UTF_8))
                val count = normalized.codePointCount(0, normalized.length)
                require(count == input.getInt("normalizedCodepoints") && count < 2039)
                require(WiringContract.hash(normalized.toByteArray(Charsets.UTF_8)) == input.getString("normalizedSha256"))
            } else {
                require(text.size == 226 && input.getString("sha256") == TEXT_SHA)
            }
            return TtsOnlyContract(json, text.toString(Charsets.UTF_8), isLong)
        }
    }
}
