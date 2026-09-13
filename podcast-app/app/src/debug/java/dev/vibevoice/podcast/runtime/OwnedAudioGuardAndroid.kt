package dev.vibevoice.podcast.runtime

import android.app.Application
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Process
import dev.vibevoice.podcast.PodcastApplication
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream

internal object OwnedAudioGuardAndroid {
    fun startTicks(pid:Int)=AudioGuardPolicy.startTicks(File("/proc/$pid/stat").readText())
    fun sample(identity:AudioGuardIdentity):AudioGuardSample {
        val text=File("/proc/meminfo").readText();require(text.length<65536)
        val memory=requireNotNull(Regex("(?m)^MemAvailable:\\s*(\\d+) kB$").find(text)).groupValues[1].toLong()
        return AudioGuardSample(identity.copy(pid=Process.myPid(),startTicks=startTicks(Process.myPid())),System.nanoTime(),memory,Double.NaN)
    }
    fun actualSample(context:Context,identity:AudioGuardIdentity):AudioGuardSample {
        val memory=sample(identity)
        val battery=requireNotNull(context.registerReceiver(null,IntentFilter(Intent.ACTION_BATTERY_CHANGED)))
        require(battery.hasExtra(BatteryManager.EXTRA_TEMPERATURE))
        return memory.copy(monotonicNs=System.nanoTime(),temperatureC=battery.getIntExtra(BatteryManager.EXTRA_TEMPERATURE,Int.MIN_VALUE)/10.0)
    }
    fun write(file:File,value:JSONObject,append:Boolean=false) {
        require(file.parentFile!!.let { it.isDirectory || it.mkdirs() })
        require(file.length()<524288)
        FileOutputStream(file,append).use { it.write((value.toString()+"\n").toByteArray());it.fd.sync() }
    }
    fun trace(root:File,event:String,sample:AudioGuardSample?,reason:AudioGuardStop?) = write(File(root,"guard-events.jsonl"),JSONObject()
        .put("event",event).put("monotonicNs",System.nanoTime()).put("reason",reason?.name)
        .put("sampleNs",sample?.monotonicNs).put("availableKiB",sample?.availableKiB).put("temperatureC",sample?.temperatureC),true)

    fun create(context:Context,binding:AudioAttemptBinding,ownsLease:()->Boolean):AudioExecutionGuard? {
        val app=context.applicationContext as PodcastApplication
        val marker=File(context.filesDir,"provider-integration/active.json")
        if(!marker.isFile) return null
        require(marker.length() in 1..8192)
        val control=JSONObject(marker.readText())
        if(!control.optBoolean("ownedMemoryGuard") || control.optString("episodeId")!=binding.episodeId) return null
        require(Application.getProcessName()==context.packageName+":generation")
        require(RuntimeDiagnostics.retainProviderIntermediates()) { "Owned guard was not authenticated before job claim" }
        val run=control.getString("runId");require(Regex("provider-app-[a-z0-9-]{1,48}").matches(run))
        val root=File(marker.parentFile,run)
        val proof=JSONObject(File(root,"job-identity.json").readText())
        require(proof.getString("jobId")==binding.jobId && proof.getString("episodeId")==binding.episodeId && proof.getInt("pid")==Process.myPid())
        require(proof.getString("revisionId")==binding.revisionId && proof.getString("revisionSha256")==binding.revisionSha256 && proof.getString("packSha256")==binding.packSha256)
        require(proof.getString("appApkSha256")==control.getString("appApkSha256"))
        val plan=app.artifacts.resolveEpisodeFile("${binding.episodeId}/audio-plans/${binding.jobId}.json")
        require(app.artifacts.sha256(plan)==binding.jobId)
        val identity=AudioGuardIdentity(binding,binding.jobId,Process.myPid(),startTicks(Process.myPid()))
        write(File(root,"guard-identity.json"),JSONObject().put("bindingSha256",ProgressiveAudio.bindingHash(binding))
            .put("planSha256",identity.planSha256).put("pid",identity.pid).put("pidStartTicks",identity.startTicks)
            .put("appApkSha256",control.getString("appApkSha256")).put("startFloorKiB",AudioGuardPolicy.START_KIB)
            .put("stopFloorKiB",AudioGuardPolicy.STOP_KIB).put("emergencyReserveKiB",AudioGuardPolicy.EMERGENCY_KIB)
            .put("inFlightQnnCancelSupported",false))
        return OwnedAudioGuard(identity,
            sample={actualSample(context,identity)},
            ownsLease={ownsLease() && Process.myPid()==identity.pid && startTicks(identity.pid)==identity.startTicks && app.artifacts.sha256(plan)==identity.planSha256},
            persistFailure={reason -> runBlocking { withContext(NonCancellable) { app.repository.abortOwnedAudio(binding,reason.name) } }},
            terminateSelf={Process.killProcess(identity.pid)},
            receipt={event,sample,reason -> trace(root,event,sample,reason)})
    }
}
