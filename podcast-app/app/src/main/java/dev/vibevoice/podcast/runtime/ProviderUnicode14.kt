package dev.vibevoice.podcast.runtime

import java.io.DataInputStream
import java.security.MessageDigest

/** Exact Unicode14 global NFKD, independent of the Android/JVM Unicode database version. */
internal object ProviderUnicode14 {
    const val TABLE_SHA256 = "e77ed73ff2a4dfb12e7273ce959adf554b8d5aff559d77a2a81aaf3be127a456"
    private val decompositions = HashMap<Int, IntArray>()
    private val combiningClasses = HashMap<Int, Int>()
    private val wordRanges = IntArray(734 * 2)
    init {
        val bytes = requireNotNull(javaClass.getResourceAsStream("/provider-frontend/unicode14-nfkd.bin")).use { it.readBytes() }
        val hash = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        check(hash == TABLE_SHA256) { "Pinned provider Unicode data changed" }
        DataInputStream(bytes.inputStream()).use { input ->
            check(input.readInt() == 0x50553134)
            val mappings = input.readInt(); check(mappings == 16967)
            repeat(mappings) { val cp = input.readInt(); val size = input.readInt(); check(size in 1..32)
                decompositions[cp] = IntArray(size) { input.readInt() } }
            val classes = input.readInt(); check(classes == 912)
            repeat(classes) { combiningClasses[input.readInt()] = input.readInt() }
            check(input.readInt() == 734)
            wordRanges.indices.forEach { wordRanges[it] = input.readInt() }
            check(input.read() == -1)
        }
    }
    fun isWord(cp: Int): Boolean {
        var low = 0; var high = wordRanges.size / 2 - 1
        while (low <= high) {
            val mid = (low + high) ushr 1
            if (cp < wordRanges[mid * 2]) high = mid - 1
            else if (cp > wordRanges[mid * 2 + 1]) low = mid + 1
            else return true
        }
        return false
    }
    fun normalize(text: String): String = buildString {
        val marks = ArrayList<Int>()
        fun flush() {
            // Stable ordering preserves equal-class order; avoids quadratic insertion on adversarial mark runs.
            marks.sortWith(compareBy { combiningClasses[it] ?: 0 })
            marks.forEach { appendCodePoint(it) }; marks.clear()
        }
        text.codePoints().forEach { cp ->
            val values = decompositions[cp] ?: intArrayOf(cp)
            for (value in values) {
                if ((combiningClasses[value] ?: 0) == 0) { flush(); appendCodePoint(value) }
                else marks += value
            }
        }
        flush()
    }
}
