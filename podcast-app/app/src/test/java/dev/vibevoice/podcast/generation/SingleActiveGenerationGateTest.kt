package dev.vibevoice.podcast.generation

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SingleActiveGenerationGateTest {
    @Test fun secondServiceCommandIsRejectedWithoutReleasingActiveCommand() {
        val gate = SingleActiveGenerationGate()
        assertTrue(gate.tryAcquire())
        assertFalse(gate.tryAcquire())
        assertTrue(gate.isActive())
        gate.release()
        assertTrue(gate.tryAcquire())
    }
}
