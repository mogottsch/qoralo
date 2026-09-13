package dev.vibevoice.podcast.runtime

import kotlinx.coroutines.CancellationException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/** Provisional diagnostic guard, not a global admission rule or an in-flight QNN cancellation API. */
data class AudioGuardIdentity(val binding: AudioAttemptBinding, val planSha256: String, val pid: Int, val startTicks: Long)
data class AudioGuardSample(val identity: AudioGuardIdentity, val monotonicNs: Long, val availableKiB: Long, val temperatureC: Double)
enum class AudioGuardStop { ADMISSION, LOW_MEMORY, THERMAL, STALE_SAMPLE, UNKNOWN_SAMPLE, IDENTITY, DEADLINE }
class AudioGuardCancellation(val reason: AudioGuardStop) : CancellationException("Owned audio guard stopped: ${reason.name}")

object AudioGuardPolicy {
    const val WHOLE_START_KIB = 3072L * 1024
    const val PRE_CONTEXT_KIB = (2048L + 600L) * 1024
    const val STOP_KIB = 1280L * 1024
    const val EMERGENCY_KIB = 600L * 1024
    const val MAX_SAMPLE_AGE_NS = 2_000_000_000L
    const val MAX_RUN_NS = 600_000_000_000L
    fun stop(expected: AudioGuardIdentity, sample: AudioGuardSample?, now: Long, admission: Boolean): AudioGuardStop? = when {
        sample == null -> AudioGuardStop.UNKNOWN_SAMPLE
        sample.identity != expected -> AudioGuardStop.IDENTITY
        sample.monotonicNs > now || now - sample.monotonicNs > MAX_SAMPLE_AGE_NS -> AudioGuardStop.STALE_SAMPLE
        sample.availableKiB <= 0 || !sample.temperatureC.isFinite() || sample.temperatureC !in -20.0..80.0 -> AudioGuardStop.UNKNOWN_SAMPLE
        sample.temperatureC >= 42.0 -> AudioGuardStop.THERMAL
        sample.availableKiB < STOP_KIB -> AudioGuardStop.LOW_MEMORY
        admission && sample.availableKiB < PRE_CONTEXT_KIB -> AudioGuardStop.ADMISSION
        else -> null
    }
    /** /proc stat comm may contain spaces/parentheses. Field22 is offset19 after its last closing parenthesis. */
    fun startTicks(stat: String): Long {
        val tail=stat.substring(stat.lastIndexOf(')')+1).trim().split(Regex("\\s+"))
        require(tail.size>=20)
        return tail[19].toLong().also { require(it>0) }
    }
}

interface AudioExecutionGuard : AutoCloseable {
    fun start()
    fun check()
}

/** Native destruction is part of the guarded lifetime, including cancellation unwinds. */
fun closeGuardedAudio(guard: AudioExecutionGuard?, destroyEngine: () -> Unit) {
    try { destroyEngine() } finally { guard?.close() }
}

/** Two independent threads: a blocked sampler cannot prevent the watchdog detecting a stale sample.
 * Termination is self-only, serialized with close; it requires durable failure AND a still-current
 * process/attempt lease. Missing ownership never authorizes killing a replacement worker.
 */
class OwnedAudioGuard(
    private val identity: AudioGuardIdentity,
    private val sample: () -> AudioGuardSample,
    private val ownsLease: () -> Boolean,
    private val persistFailure: (AudioGuardStop) -> Boolean,
    private val terminateSelf: () -> Unit,
    private val receipt: (String, AudioGuardSample?, AudioGuardStop?) -> Unit,
    private val now: () -> Long = System::nanoTime,
) : AudioExecutionGuard {
    private val lock=Any()
    @Volatile private var closed=false
    private val latest=AtomicReference<AudioGuardSample?>()
    private val reason=AtomicReference<AudioGuardStop?>()
    private val first=CountDownLatch(1)
    private val started=now()
    private var sampler: Thread?=null
    private var watchdog: Thread?=null

    override fun start() {
        check(sampler==null && !closed)
        sampler=Thread({
            while(!closed && reason.get()==null) {
                try {
                    val value=sample();latest.set(value);receipt("sample",value,null);first.countDown()
                } catch (_: InterruptedException) { return@Thread }
                catch (_: Throwable) { requestStop(AudioGuardStop.UNKNOWN_SAMPLE);first.countDown();return@Thread }
                try { Thread.sleep(500) } catch (_: InterruptedException) { return@Thread }
            }
        },"owned-audio-sampler").apply { isDaemon=true;start() }
        // No native constructor is entered until an initial bounded, valid sample is available.
        if(!first.await(2,TimeUnit.SECONDS)) requestStop(AudioGuardStop.STALE_SAMPLE)
        AudioGuardPolicy.stop(identity,latest.get(),now(),true)?.let(::requestStop)
        check()
        watchdog=Thread({
            while(!closed && reason.get()==null) {
                val stop=if(now()-started>AudioGuardPolicy.MAX_RUN_NS) AudioGuardStop.DEADLINE
                    else AudioGuardPolicy.stop(identity,latest.get(),now(),false)
                if(stop!=null) { requestStop(stop);return@Thread }
                try { Thread.sleep(100) } catch (_: InterruptedException) { return@Thread }
            }
        },"owned-audio-watchdog").apply { isDaemon=true;start() }
    }
    private fun requestStop(value: AudioGuardStop) {
        synchronized(lock) {
            if(closed || reason.get()!=null) return
            reason.set(value)
        }
        runCatching { receipt("stop_requested",latest.get(),value) }
        // Persist off the JNI execution thread. Never kill on an unverified/failed ownership transaction.
        val durable=runCatching { ownsLease() && persistFailure(value) }.getOrDefault(false)
        synchronized(lock) {
            if(!closed && durable && runCatching(ownsLease).getOrDefault(false)) {
                runCatching { receipt("owned_failure_durable_terminating_self",latest.get(),value) }
                terminateSelf()
            } else runCatching { receipt("termination_refused",latest.get(),value) }
        }
    }
    override fun check() { reason.get()?.let { throw AudioGuardCancellation(it) };if(closed) throw CancellationException("Audio guard closed") }
    override fun close() {
        val stopped=synchronized(lock) { closed=true;reason.get() }
        sampler?.interrupt();watchdog?.interrupt()
        runCatching { receipt("closed",latest.get(),stopped) }
        stopped?.let { throw AudioGuardCancellation(it) }
    }
}
