package dev.vibevoice.podcast.runtime

import dev.vibevoice.podcast.data.ArtifactStore
import dev.vibevoice.podcast.data.ChapterDraft
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.RandomAccessFile
import java.nio.file.Files

/** Explicit new publication attempt for already-complete whole chapters. Never calls a model or rewrites failed history. */
internal object ProviderPublicationRecovery {
    const val KIND = "PROVIDER_PUBLICATION_RECOVERY"
    data class Chapter(val source: File, val receipt: File, val metadata: AudioMetadata)
    private fun planFile(a: ArtifactStore, episode: String, job: String) = a.resolveEpisodeFile("$episode/audio-plans/$job.json")
    private fun load(a: ArtifactStore, episode: String, job: String): JSONObject {
        require(Regex("[a-f0-9]{64}").matches(job))
        val file=planFile(a,episode,job)
        require(file.isFile && file.length() in 1..8_388_608 && ProviderPublication.hash(file)==job) { "Publication plan integrity mismatch" }
        return JSONObject(file.readText())
    }
    fun isRecovery(a: ArtifactStore, episode: String, job: String): Boolean = load(a,episode,job).optString("kind")==KIND

    private fun complete(a: ArtifactStore, episode: String, path: String, expectedHash: String, expected: JSONObject): Chapter {
        require(path.startsWith("$episode/chapters/.provider-") && path.endsWith("/complete-chapter.wav")) { "Recovery requires a complete owned provider chapter" }
        val source=a.resolveEpisodeFile(path)
        require(!Files.isSymbolicLink(source.toPath()) && ProviderPublication.hash(source)==expectedHash) { "Saved chapter changed" }
        val metadata=WavInspector.inspectSupertonicOutput(source)
        val receipt=File(source.parentFile,"provider-receipt.json")
        require(receipt.isFile && receipt.length() in 1..8_388_608 && !Files.isSymbolicLink(receipt.toPath()))
        val info=JSONObject(receipt.readText())
        require(info.getString("status")=="complete_chapter" && info.getString("packSha256")==ProviderAudioPlan.PACK_SHA256 &&
            info.getString("frontendVersion")==ProviderTextFrontend.VERSION && info.getString("chapterId")==expected.getString("id") &&
            info.getString("rawChapterSha256")==expected.getString("textSha256") && info.getString("waveSha256")==expectedHash &&
            info.getLong("frameCount")==metadata.frameCount && info.getInt("steps")==8 && info.getInt("speedHundredths")==105 &&
            info.getInt("gapFrames")==13230 && info.getInt("randomSeed")==20260911 && !info.getBoolean("cpuFallback") && info.getString("provider")=="QNN_HTP") { "Incomplete or mismatched provider receipt" }
        val segments=info.getJSONArray("segments");val inputs=expected.getJSONArray("segments")
        require(segments.length()>0 && segments.length()==inputs.length())
        var frames=0L;var noise=0L
        RandomAccessFile(source,"r").use { joined ->
            require(source.length()==44+metadata.frameCount*2);joined.seek(44)
            val buffer=ByteArray(65536);val actual=ByteArray(65536)
            repeat(segments.length()) { i ->
                val s=segments.getJSONObject(i);val input=inputs.getJSONObject(i)
                val latent=s.getLong("nativeLatentLength")
                require(s.getInt("index")==i && latent in 1..512 && s.getLong("frameCount")==latent*3072 &&
                    s.getString("idsSha256")==input.getString("idsSha256") && s.getString("processedSha256")==input.getString("processedSha256") &&
                    s.getString("rawSegmentSha256")==input.getString("rawSha256") && s.getInt("neuralCalls")==11 &&
                    s.getInt("nativeTextLength")==input.getInt("nativeTextLength") && s.getLong("noiseOffset")==noise && s.getLong("noiseConsumed")==144*latent)
                noise+=144*latent
                if(i>0) { val gap=ByteArray(13230*2);joined.readFully(gap);require(gap.all { it==0.toByte() });frames+=13230 }
                val segment=File(source.parentFile,"segment-$i.wav")
                val part=WavInspector.inspectSupertonicOutput(segment)
                require(part.sha256==s.getString("waveSha256") && part.frameCount==latent*3072 && segment.length()==44+part.frameCount*2)
                segment.inputStream().use { stream ->
                    require(stream.skip(44)==44L);var remaining=part.frameCount*2
                    while(remaining>0) {
                        val n=stream.read(buffer,0,minOf(remaining,buffer.size.toLong()).toInt());require(n>0)
                        joined.readFully(actual,0,n);require((0 until n).all { buffer[it]==actual[it] }) { "Completed PCM differs from retained native segments" };remaining-=n
                    }
                }
                frames+=part.frameCount
            }
            require(frames==metadata.frameCount && joined.filePointer==joined.length())
        }
        return Chapter(source,receipt,metadata)
    }

    fun save(a: ArtifactStore, episode: String, revision: String, revisionHash: String, sourceJob: String, nonce: String,
             chapters: List<ChapterDraft>, paths: List<Pair<String,String>>): ProviderAudioPlan.Saved {
        ProviderAudioPlan.verify(a,episode,sourceJob,revision,revisionHash,ProviderAudioPlan.PACK_SHA256,chapters)
        val base=load(a,episode,sourceJob);require(paths.size==chapters.size)
        val entries=paths.mapIndexed { i,(path,sha) ->
            val chapter=complete(a,episode,path,sha,base.getJSONArray("chapters").getJSONObject(i))
            JSONObject().put("path",path).put("sha256",sha).put("receiptSha256",ProviderPublication.hash(chapter.receipt))
        }
        val json=JSONObject().put("schemaVersion",1).put("kind",KIND).put("nonce",nonce).put("episodeId",episode)
            .put("revisionId",revision).put("revisionSha256",revisionHash).put("packSha256",ProviderAudioPlan.PACK_SHA256)
            .put("sourceJobId",sourceJob).put("chapters",JSONArray(entries))
        val bytes=json.toString().toByteArray(Charsets.UTF_8)
        val hash=java.security.MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        val file=planFile(a,episode,hash);require(!file.exists());a.writeAtomically(file,bytes)
        return ProviderAudioPlan.Saved(hash,file)
    }

    fun verify(a: ArtifactStore, episode: String, job: String, revision: String, revisionHash: String, chapters: List<ChapterDraft>): Pair<String,List<Chapter>> {
        val json=load(a,episode,job)
        require(json.getInt("schemaVersion")==1 && json.getString("kind")==KIND && json.getString("episodeId")==episode &&
            json.getString("revisionId")==revision && json.getString("revisionSha256")==revisionHash && json.getString("packSha256")==ProviderAudioPlan.PACK_SHA256)
        val previous=json.getString("sourceJobId")
        ProviderAudioPlan.verify(a,episode,previous,revision,revisionHash,ProviderAudioPlan.PACK_SHA256,chapters)
        val base=load(a,episode,previous);val entries=json.getJSONArray("chapters");require(entries.length()==chapters.size)
        val result=List(entries.length()) { i ->
            val entry=entries.getJSONObject(i)
            val complete=complete(a,episode,entry.getString("path"),entry.getString("sha256"),base.getJSONArray("chapters").getJSONObject(i))
            require(ProviderPublication.hash(complete.receipt)==entry.getString("receiptSha256"));complete
        }
        return previous to result
    }
}
