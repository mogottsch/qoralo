package dev.qoralo.podcast.generation

import java.util.concurrent.atomic.AtomicBoolean

/** Process-local guard; durable Room claim remains the cross-process authority. */
class SingleActiveGenerationGate {
    private val active = AtomicBoolean(false)
    fun tryAcquire(): Boolean = active.compareAndSet(false, true)
    fun release() { active.set(false) }
    fun isActive(): Boolean = active.get()
}
