package dev.vibevoice.podcast.ui

import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.vibevoice.podcast.data.ArtifactStore
import dev.vibevoice.podcast.data.PlaybackStateEntity
import dev.vibevoice.podcast.runtime.*
import kotlinx.coroutines.delay
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.io.RandomAccessFile

/** Synthetic muted PCM + real ExoPlayer. No neural calls or user database/playback writes. */
@RunWith(AndroidJUnit4::class)
class ProgressivePlayerRegressionTest {
    @get:Rule val rule=createComposeRule()
    @Test fun delayedChunksWaitResumeRespectPauseAndFinalizeWithoutReplacingPlayer() {
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        val root=File(context.cacheDir,"progressive-test-${System.nanoTime()}").apply { mkdirs() }
        val artifacts=ArtifactStore(File(root,"episodes"),File(root,"models"))
        val binding=AudioAttemptBinding("synthetic", "a".repeat(64),"revision","revision-hash","pack")
        val publisher=ProgressiveAudio.create(artifacts,binding);val reader=ProgressiveAudio.Reader(artifacts,binding)
        var index=0
        fun append(ms:Int):AudioAvailability {
            val file=File(root,"raw-${index}.wav");wave(file,ms*44100/1000)
            publisher.append(0,"c1",index++,file,WavInspector.inspectSupertonicOutput(file))
            return reader.read(AudioAvailabilityState.GENERATING)
        }
        var session by mutableStateOf<EpisodePlayerSession?>(null)
        var saved:PlaybackStateEntity?=null
        rule.setContent {
            Text("Synthetic progressive playback")
            val active=session
            LaunchedEffect(active) { if(active!=null) while(true) { active.tick();delay(50) } }
        }
        try {
            val first=append(400)
            rule.runOnIdle {
                session=EpisodePlayerSession(context,"synthetic",null,first,null,0) { p,s,t -> saved=PlaybackStateEntity("synthetic",p,s,t,1) }
                session!!.player.volume=0f
            }
            val original=session!!;val player=original.player
            Thread.sleep(150)
            rule.runOnIdle { assertFalse(original.wantsPlayback);assertFalse(original.isPlaying);assertEquals(0L,original.positionMs);original.togglePlay() }
            rule.waitUntil(10_000) { original.waiting }
            val frontier=original.positionMs;assertEquals(400L,frontier)
            rule.runOnIdle { original.pause(PlaybackStopReason.USER_PAUSE) }
            val second=append(1500)
            rule.runOnIdle { original.update(second) }
            Thread.sleep(200)
            rule.runOnIdle { assertFalse(original.wantsPlayback);assertFalse(original.isPlaying);assertEquals(frontier,original.positionMs);original.togglePlay() }
            rule.waitUntil(10_000) { original.isPlaying && original.positionMs>800 }
            rule.runOnIdle { original.seek(second.availableMs-50) }
            rule.waitUntil(10_000) { original.waiting }
            val third=append(1500)
            rule.runOnIdle { original.update(third) }
            rule.waitUntil(10_000) { original.isPlaying && original.positionMs>second.availableMs+350 }
            rule.runOnIdle { assertSame(player,original.player);assertTrue(original.positionMs>=second.availableMs);original.pause(PlaybackStopReason.SLEEP) }
            val paused=original.positionMs
            val fourth=append(400)
            rule.runOnIdle { original.update(fourth) }
            Thread.sleep(150)
            rule.runOnIdle { assertFalse(original.wantsPlayback);assertEquals(paused,original.positionMs) }
            // These are simulated pause events; actual focus/noisy listener wiring is separately source-checked.
            for(reason in listOf(PlaybackStopReason.AUDIO_FOCUS,PlaybackStopReason.NOISY_ROUTE)) {
                rule.runOnIdle { original.togglePlay() }
                rule.waitUntil(10_000) { original.isPlaying }
                rule.runOnIdle { original.pause(reason) }
                val state=append(300)
                rule.runOnIdle { original.update(state);assertFalse(original.wantsPlayback);assertFalse(original.isPlaying) }
            }
            val all=reader.read(AudioAvailabilityState.GENERATING)
            publisher.finish(all.availableFrames,"synthetic-master")
            val finished=reader.read(AudioAvailabilityState.COMPLETE,"synthetic-master")
            val beforeFinal=original.positionMs
            rule.runOnIdle { original.update(finished);assertSame(player,original.player);assertEquals(beforeFinal,original.positionMs);assertFalse(original.wantsPlayback)
                original.changeSpeed(1.5f);original.showTranscript(true);original.close();session=null }
            val persisted=requireNotNull(saved)
            rule.runOnIdle {
                session=EpisodePlayerSession(context,"synthetic",null,finished,persisted,0) { _,_,_ -> }
                session!!.player.volume=0f
            }
            Thread.sleep(150)
            rule.runOnIdle { assertFalse(session!!.wantsPlayback);assertFalse(session!!.isPlaying);assertEquals(1.5f,session!!.speed);assertTrue(session!!.transcript)
                assertTrue(kotlin.math.abs(session!!.positionMs-persisted.positionMs)<=2) }
        } finally { rule.runOnIdle { session?.let { retainState(it);it.close() };session=null };root.deleteRecursively() }
    }

    @Test fun completedMasterEndsWithoutStuckPlaybackIntentAndReplaysOnlyOnExplicitPlay() {
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        val root=File(context.cacheDir,"completed-player-test-${System.nanoTime()}").apply { mkdirs() }
        val file=File(root,"complete.wav");wave(file,44100)
        var session by mutableStateOf<EpisodePlayerSession?>(null)
        rule.setContent { Text("Synthetic completed playback");val current=session;LaunchedEffect(current) { if(current!=null) while(true) {current.tick();delay(50)} } }
        try {
            rule.runOnIdle { session=EpisodePlayerSession(context,"complete",file,null,null,1000) { _,_,_ -> };session!!.player.volume=0f;session!!.togglePlay() }
            rule.waitUntil(10_000) { session!!.isPlaying }
            rule.waitUntil(10_000) { !session!!.wantsPlayback && !session!!.isPlaying && session!!.positionMs>=990 }
            val same=session!!.player
            Thread.sleep(150)
            rule.runOnIdle { assertSame(same,session!!.player);assertFalse(session!!.wantsPlayback);session!!.togglePlay() }
            rule.waitUntil(10_000) { session!!.isPlaying && session!!.positionMs<990 }
        } finally { rule.runOnIdle { session?.close();session=null };root.deleteRecursively() }
    }

    private fun retainState(session:EpisodePlayerSession) {
        val args=InstrumentationRegistry.getArguments()
        val run=args.getString("diagnosticRun") ?: return
        val profile=args.getString("profile") ?: return
        require(listOf(run,profile).all { Regex("[a-zA-Z0-9_-]{1,96}").matches(it) })
        val root=File(InstrumentationRegistry.getInstrumentation().targetContext.filesDir,"player-ui-captures/$run/$profile/core-${System.nanoTime()}").apply { mkdirs() }
        File(root,"synthetic-final-state.json").writeText(org.json.JSONObject()
            .put("positionMs",session.positionMs).put("availableMs",session.durationMs).put("wantsPlayback",session.wantsPlayback)
            .put("waiting",session.waiting).put("playing",session.isPlaying).put("state",session.player.playbackState)
            .put("itemIndex",session.player.currentMediaItemIndex).put("playWhenReady",session.player.playWhenReady).put("error",session.error).toString(2))
    }

    private fun wave(file:File,frames:Int) {
        RandomAccessFile(file,"rw").use { out ->
            fun u16(v:Int){out.write(v and 255);out.write((v ushr 8) and 255)}
            fun u32(v:Int){u16(v and 65535);u16((v ushr 16) and 65535)}
            out.writeBytes("RIFF");u32(36+frames*2);out.writeBytes("WAVEfmt ");u32(16);u16(1);u16(1);u32(44100);u32(88200);u16(2);u16(16);out.writeBytes("data");u32(frames*2)
            repeat(frames) { u16(if(it%100<50) 600 else -600) }
        }
    }
}
