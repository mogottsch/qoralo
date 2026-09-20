package dev.qoralo.podcast.wiring

import android.content.Context
import org.json.JSONObject
import java.security.MessageDigest

class WiringContract private constructor(val json: JSONObject, val inputs: Map<String, String>) {
    fun deadlineMs(stage: String): Long = json.getJSONObject("deadlineSeconds").getLong(stage) * 1000L
    val totalMs get() = json.getLong("serviceTimeoutSeconds") * 1000L
    val maxEvidenceBytes get() = json.getLong("maxEvidenceBytes")
    val maxRequestUtf8Bytes get() = json.getJSONObject("gemma").getLong("maxRequestUtf8Bytes")
    val maxRawResponseBytes get() = json.getJSONObject("gemma").getLong("maxRawResponseBytes")
    fun outputTokens(mode: String): Int = when (mode) {
        "outline" -> json.getJSONObject("gemma").getInt("outlineMaxOutputTokens")
        "chapter" -> json.getJSONObject("gemma").getInt("chapterMaxOutputTokens")
        else -> error("Wiring gate does not authorize request mode $mode")
    }

    companion object {
        const val SHA256 = "301408dab967315bf8d5f7bb0dcc83face54438dc139d221e7699ce5dc6b0393"
        const val ACK_TIMEOUT_MS = 30_000L
        const val INSTRUMENTATION_TIMEOUT_MS = 1_230_000L

        fun load(context: Context): WiringContract = parse { context.assets.open("wiring/$it").use { stream -> stream.readBytes() } }

        internal fun parse(readAsset: (String) -> ByteArray): WiringContract {
            val raw = readAsset("contract.json")
            require(hash(raw) == SHA256) { "Wiring contract hash mismatch" }
            val json = JSONObject(raw.toString(Charsets.UTF_8))
            val files = json.getJSONObject("inputs")
            val inputs = files.keys().asSequence().associateWith { name ->
                val bytes = readAsset(name)
                val identity = files.getJSONObject(name)
                require(bytes.size.toLong() == identity.getLong("bytes") && hash(bytes) == identity.getString("sha256")) {
                    "Wiring input identity mismatch: $name"
                }
                bytes.toString(Charsets.UTF_8)
            }
            return WiringContract(json, inputs)
        }

        fun hash(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        fun validRunId(value: String): Boolean = value.matches(Regex("wiring-[a-z0-9-]{1,64}"))
    }
}
