package dev.vibevoice.podcast.runtime

import android.app.*
import android.content.Intent
import android.database.sqlite.SQLiteDatabase
import android.os.*
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.atomic.AtomicBoolean

/** Dedicated, non-sticky, non-neural process. Never opens the user's podcast database or a model. */
class OwnedAudioGuardProbeService:Service() {
    private val active=AtomicBoolean(false)
    override fun onBind(intent:Intent?) = null
    override fun onStartCommand(intent:Intent?,flags:Int,startId:Int):Int {
        if(!active.compareAndSet(false,true)) return START_NOT_STICKY
        val manager=getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel("owned-guard-probe","Owned guard test",NotificationManager.IMPORTANCE_LOW))
        startForeground(4117,Notification.Builder(this,"owned-guard-probe").setSmallIcon(dev.vibevoice.podcast.R.drawable.ic_notification).setContentTitle("Testing owned guard; no model").build())
        Thread({
            try {
                require(Application.getProcessName()==packageName+":guard_probe")
                val run=requireNotNull(intent?.getStringExtra("run"));require(Regex("provider-app-[a-z0-9-]{1,48}").matches(run))
                val root=File(filesDir,"owned-guard-probe/$run");val plan=File(root,"plan.json")
                require(plan.length() in 1..8192)
                val json=JSONObject(plan.readText());require(json.getString("runId")==run && json.getBoolean("nonNeural"))
                fun hash(file:File):String {val digest=MessageDigest.getInstance("SHA-256");file.inputStream().use { input ->val bytes=ByteArray(65536);while(true){val count=input.read(bytes);if(count<0)break;digest.update(bytes,0,count)}};return digest.digest().joinToString(""){"%02x".format(it)} }
                require(hash(File(applicationInfo.sourceDir))==json.getString("appApkSha256"))
                val planHash=hash(plan);val pid=Process.myPid();val ticks=OwnedAudioGuardAndroid.startTicks(pid)
                val binding=AudioAttemptBinding(run,planHash,"synthetic-revision","synthetic-content","no-model-pack")
                val identity=AudioGuardIdentity(binding,planHash,pid,ticks)
                val database=SQLiteDatabase.openOrCreateDatabase(File(root,"worker.db"),null)
                database.execSQL("CREATE TABLE IF NOT EXISTS worker(plan TEXT PRIMARY KEY,pid INTEGER,ticks INTEGER,state TEXT)")
                require(android.database.DatabaseUtils.longForQuery(database,"SELECT COUNT(*) FROM worker",null)==0L) { "Never restart a prior probe" }
                database.execSQL("INSERT INTO worker VALUES(?,?,?,?)",arrayOf<Any>(planHash,pid,ticks,"RUNNING"))
                OwnedAudioGuardAndroid.write(File(root,"worker-identity.json"),JSONObject().put("pid",pid).put("startTicks",ticks).put("planSha256",planHash).put("modelConstructions",0).put("modelCalls",0))
                val blocked=AtomicBoolean(false)
                val guard=OwnedAudioGuard(identity,
                    sample={
                        val live=OwnedAudioGuardAndroid.actualSample(this,identity)
                        OwnedAudioGuardAndroid.write(File(root,"live-samples.jsonl"),JSONObject().put("monotonicNs",live.monotonicNs).put("availableKiB",live.availableKiB).put("temperatureC",live.temperatureC).put("injectedLow",blocked.get()),true)
                        live.copy(availableKiB=if(blocked.get()) 1024L*1024 else 4096L*1024)
                    },
                    ownsLease={active.get() && Process.myPid()==pid && OwnedAudioGuardAndroid.startTicks(pid)==ticks && hash(plan)==planHash},
                    persistFailure={reason ->
                        database.beginTransaction()
                        val changed=try {
                            val update=database.compileStatement("UPDATE worker SET state='FAILED' WHERE plan=? AND pid=? AND ticks=? AND state='RUNNING'")
                            val count=update.use {it.bindString(1,planHash);it.bindLong(2,pid.toLong());it.bindLong(3,ticks);it.executeUpdateDelete()}
                            database.setTransactionSuccessful();count==1
                        } finally {database.endTransaction()}
                        if(changed) OwnedAudioGuardAndroid.write(File(root,"failure-durable.json"),JSONObject().put("reason",reason.name).put("planSha256",planHash).put("pid",pid).put("startTicks",ticks).put("monotonicNs",System.nanoTime()).put("workerWasBlocked",blocked.get()))
                        changed
                    },terminateSelf={Process.killProcess(pid)},receipt={event,sample,reason->OwnedAudioGuardAndroid.trace(root,event,sample,reason)})
                guard.start()
                OwnedAudioGuardAndroid.write(File(root,"blocked-worker.json"),JSONObject().put("monotonicNs",System.nanoTime()).put("nonNeural",true))
                blocked.set(true)
                SystemClock.sleep(600_000) // Deliberately blocked, independent of the sampler/watchdog.
                error("Guard failed to terminate its owned blocking worker")
            } catch(error:Throwable) {
                runCatching {val run=intent?.getStringExtra("run");if(run!=null && Regex("provider-app-[a-z0-9-]{1,48}").matches(run)) OwnedAudioGuardAndroid.write(File(filesDir,"owned-guard-probe/$run/private-failure.json"),JSONObject().put("type",error.javaClass.simpleName))}
                stopSelf(startId)
            }
        },"owned-blocking-probe").start()
        return START_NOT_STICKY
    }
    override fun onDestroy() {active.set(false);super.onDestroy()}
}
