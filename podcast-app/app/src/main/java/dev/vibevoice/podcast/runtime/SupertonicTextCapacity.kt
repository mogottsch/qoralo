package dev.vibevoice.podcast.runtime

import dev.vibevoice.podcast.BuildConfig

/** Input-text admission only. Passing does NOT prove waveform capacity, runtime success, duration or speech coverage. */
data class ChapterTextCapacity(val position: Int, val normalizedCodePoints: Int?, val activeCodePoints: Int?, val fits: Boolean)
data class ScriptTextCapacity(val textLength: Int?, val chapters: List<ChapterTextCapacity>) {
    val maxNormalizedCodePoints: Int? get() = textLength?.minus(SupertonicTextCapacity.LANGUAGE_TAG_CODEPOINTS)
    val fits: Boolean get() = textLength != null && chapters.isNotEmpty() && chapters.all { it.fits }
    val message: String get() = if (textLength == null) {
        "Audio input capacity is unknown for the configured voice pack. Your full draft stays editable; nothing is locked or queued."
    } else {
        "This voice supports at most $maxNormalizedCodePoints normalized characters per chapter. " +
            "${chapters.count { !it.fits }} of ${chapters.size} chapters cannot be submitted. " +
            "Your full draft stays editable; nothing is shortened, split, locked or queued."
    }
}

class AudioTextCapacityException(val capacity: ScriptTextCapacity) : IllegalStateException(capacity.message)

object SupertonicTextCapacity {
    // Exactly native PrepareText: DecodeUtf8("<en>" + normalized + "</en>").
    const val LANGUAGE_TAG_CODEPOINTS = 9
    const val SHORT_MANIFEST = "dc4ac737924d7d62e57ff5e166707198095c49e51d77cfed04a44d9e9435952d"
    const val LONG_MANIFEST = "116fda95a907f6dc35bfe7c2144fe2818ed438cc109c1faa3f95cafc2fc84066"

    /** Shapes are tied to exact app-pinned, previously verified manifests, not an untrusted on-disk declaration. */
    fun textLengthForManifest(manifestSha256: String): Int? = when (manifestSha256) {
        SHORT_MANIFEST -> 239
        LONG_MANIFEST -> 2048
        else -> null // A new pack needs an explicit reviewed capacity binding; never assume it is unlimited.
    }
    fun configured(texts: List<String>): ScriptTextCapacity = assess(texts, textLengthForManifest(BuildConfig.SUPERTONIC_MANIFEST_SHA256))

    fun assess(texts: List<String>, textLength: Int?): ScriptTextCapacity {
        require(textLength == null || textLength > LANGUAGE_TAG_CODEPOINTS)
        return ScriptTextCapacity(textLength, texts.mapIndexed { index, text ->
            val normalized = runCatching { SupertonicTextNormalizer.normalize(text) }.getOrNull()
                ?.trimEnd { it == ' ' || it in '\t'..'\r' } // Native C-locale trailing ASCII whitespace removal.
            val count = normalized?.takeIf { it.isNotEmpty() }?.let { it.codePointCount(0, it.length) }
            val active = count?.plus(LANGUAGE_TAG_CODEPOINTS)
            ChapterTextCapacity(index, count, active, textLength != null && active != null && active <= textLength)
        })
    }
    fun requireFits(texts: List<String>) {
        val result = configured(texts)
        if (!result.fits) throw AudioTextCapacityException(result)
    }
}
