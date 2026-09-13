package dev.vibevoice.podcast.runtime

import org.junit.Assert.*
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger

class OwnedAudioGuardTest {
    private val id=AudioGuardIdentity(AudioAttemptBinding("e","a".repeat(64),"r","h","pack"),"a".repeat(64),42,1234)
    private fun sample(mem:Long=AudioGuardPolicy.PRE_CONTEXT_KIB,temp:Double=35.0,ns:Long=100)=AudioGuardSample(id,ns,mem,temp)
    @Test fun exactAdmissionAndProactiveThresholdsKeepEmergencyReserveSeparate() {
        assertEquals(3072L*1024,AudioGuardPolicy.WHOLE_START_KIB)
        assertEquals((2048L+600L)*1024,AudioGuardPolicy.PRE_CONTEXT_KIB)
        assertNull(AudioGuardPolicy.stop(id,sample(),100,true))
        assertEquals(AudioGuardStop.ADMISSION,AudioGuardPolicy.stop(id,sample(AudioGuardPolicy.PRE_CONTEXT_KIB-1),100,true))
        assertNull(AudioGuardPolicy.stop(id,sample(3_045_628),100,true)) // No credit for the prior global drop; full budget+reserve recharged.
        assertNull(AudioGuardPolicy.stop(id,sample(AudioGuardPolicy.STOP_KIB),100,false))
        assertEquals(AudioGuardStop.LOW_MEMORY,AudioGuardPolicy.stop(id,sample(AudioGuardPolicy.STOP_KIB-1),100,false))
        assertEquals(AudioGuardStop.LOW_MEMORY,AudioGuardPolicy.stop(id,sample(AudioGuardPolicy.EMERGENCY_KIB),100,false))
    }
    @Test fun thermalUnknownFutureAndStaleSamplesStop() {
        assertEquals(AudioGuardStop.THERMAL,AudioGuardPolicy.stop(id,sample(temp=42.0),100,false))
        assertEquals(AudioGuardStop.UNKNOWN_SAMPLE,AudioGuardPolicy.stop(id,null,100,false))
        assertEquals(AudioGuardStop.UNKNOWN_SAMPLE,AudioGuardPolicy.stop(id,sample(temp=Double.NaN),100,false))
        assertEquals(AudioGuardStop.STALE_SAMPLE,AudioGuardPolicy.stop(id,sample(ns=101),100,false))
        assertEquals(AudioGuardStop.STALE_SAMPLE,AudioGuardPolicy.stop(id,sample(),2_000_000_101,false))
    }
    @Test fun pidReuseOrPlanAttemptChangeNeverMatches() {
        for(other in listOf(id.copy(startTicks=1235),id.copy(pid=43),id.copy(planSha256="other"),id.copy(binding=id.binding.copy(jobId="other"))))
            assertEquals(AudioGuardStop.IDENTITY,AudioGuardPolicy.stop(id,sample().copy(identity=other),100,false))
    }
    @Test fun procStartTickParserHandlesSpacesAndParentheses() {
        val fields=MutableList(20){"0"};fields[0]="S";fields[19]="98765"
        assertEquals(98765L,AudioGuardPolicy.startTicks("42 (worker (owned name)) "+fields.joinToString(" ")))
    }
    @Test fun independentThreadStopsBlockedWorkOnlyAfterDurableFailure() {
        val low=AtomicBoolean(false);val saved=AtomicBoolean(false);val stopped=CountDownLatch(1)
        val guard=OwnedAudioGuard(id,{sample(if(low.get()) 1000000 else 4000000,ns=System.nanoTime())},{true},
            {saved.set(true);true},{assertTrue(saved.get());stopped.countDown()},{_,_,_->})
        try {guard.start();low.set(true);assertTrue(stopped.await(3,TimeUnit.SECONDS));assertThrows(AudioGuardCancellation::class.java){guard.check()}}
        finally {runCatching {guard.close()}}
    }
    @Test fun blockedSamplerCannotHideStalenessFromIndependentWatchdog() {
        val calls=AtomicInteger();val block=CountDownLatch(1);val stopped=CountDownLatch(1)
        val guard=OwnedAudioGuard(id,{
            if(calls.incrementAndGet()>1) block.await(10,TimeUnit.SECONDS)
            sample(4000000,ns=System.nanoTime())
        },{true},{assertEquals(AudioGuardStop.STALE_SAMPLE,it);true},{stopped.countDown()},{_,_,_->})
        try {guard.start();assertTrue(stopped.await(4,TimeUnit.SECONDS))} finally {block.countDown();runCatching {guard.close()}}
    }
    @Test fun lostLeaseOrUncommittedFailureRefusesTermination() {
        for(owns in listOf(false,true)) {
            val low=AtomicBoolean(false);val refusal=CountDownLatch(1);val kills=AtomicInteger()
            val guard=OwnedAudioGuard(id,{sample(if(low.get()) 1000000 else 4000000,ns=System.nanoTime())},{owns},
                {false},{kills.incrementAndGet()},{event,_,_->if(event=="termination_refused")refusal.countDown()})
            try {guard.start();low.set(true);assertTrue(refusal.await(3,TimeUnit.SECONDS));assertEquals(0,kills.get())}
            finally {runCatching {guard.close()}}
        }
    }
    @Test fun managedLowMemoryUnwindKeepsGuardAliveThroughBlockingEngineClose() {
        val low=AtomicBoolean(false);val teardown=CountDownLatch(1);val release=CountDownLatch(1);val terminated=CountDownLatch(1)
        val guard=OwnedAudioGuard(id,{sample(if(low.get()) 1000000 else 4000000,ns=System.nanoTime())},{true},
            {assertTrue(teardown.await(2,TimeUnit.SECONDS));true},{terminated.countDown();release.countDown()},{_,_,_->})
        guard.start()
        val worker=Thread {
            runCatching {
                try {
                    low.set(true)
                    while(true) {guard.check();Thread.sleep(5)}
                } finally {
                    closeGuardedAudio(guard) {teardown.countDown();release.await(10,TimeUnit.SECONDS)}
                }
            }
        }.apply {start()}
        try {assertTrue(terminated.await(3,TimeUnit.SECONDS));assertEquals(0L,teardown.count)}
        finally {release.countDown();worker.join(3000);runCatching {guard.close()}}
        assertFalse(worker.isAlive)
    }
    @Test fun closeRevokesLeaseAndDoesNotKillLaterWork() {
        val low=AtomicBoolean(false);val kills=AtomicInteger()
        val guard=OwnedAudioGuard(id,{sample(if(low.get()) 1000000 else 4000000,ns=System.nanoTime())},{true},{true},{kills.incrementAndGet()},{_,_,_->})
        guard.start();guard.close();low.set(true);Thread.sleep(600);assertEquals(0,kills.get())
    }
}
