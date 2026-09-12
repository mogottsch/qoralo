package dev.vibevoice.podcast.runtime

import dev.vibevoice.podcast.data.ArtifactStore
import dev.vibevoice.podcast.data.PlaybackStateEntity
import org.json.JSONObject
import java.io.File

/** Per-attempt absolute position. Playback intent is deliberately not restored as autoplay after process death. */
object StreamPlaybackStore {
    fun read(artifacts: ArtifactStore,binding: AudioAttemptBinding): PlaybackStateEntity? = runCatching {
        val file=File(ProgressiveAudio.root(artifacts,binding),"playback.json")
        if(!file.isFile) return@runCatching null
        require(file.length() in 1..8192)
        val value=JSONObject(file.readText())
        require(value.getString("bindingSha256")==ProgressiveAudio.bindingHash(binding))
        val speed=value.getDouble("speed").toFloat();require(speed.isFinite() && speed in 0.25f..4f)
        PlaybackStateEntity(binding.episodeId,value.getLong("absolutePositionMs").coerceAtLeast(0),speed,value.getBoolean("transcript"),value.getLong("updatedAtEpochMs"))
    }.getOrNull()
    fun save(artifacts: ArtifactStore,binding: AudioAttemptBinding,positionMs: Long,speed: Float,transcript: Boolean,now: Long) {
        require(positionMs>=0 && speed.isFinite() && speed in 0.25f..4f)
        val root=ProgressiveAudio.root(artifacts,binding);require(root.isDirectory)
        val value=JSONObject().put("schemaVersion",1).put("bindingSha256",ProgressiveAudio.bindingHash(binding))
            .put("absolutePositionMs",positionMs).put("speed",speed).put("transcript",transcript).put("updatedAtEpochMs",now)
        artifacts.writeAtomically(File(root,"playback.json"),value.toString().toByteArray(Charsets.UTF_8))
    }
}
