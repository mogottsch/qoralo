package dev.moket.ttsbench;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;

import java.util.Map;
import org.junit.Test;

/** Focused regression test for the sweep-only descriptor extension. */
public final class FourThreadDescriptorTest {
    private static String hash(char value) {
        return String.valueOf(value).repeat(64);
    }

    private static BenchmarkDescriptor descriptor(int threads) {
        return new BenchmarkDescriptor(
                "pocket",
                "protocol/transcript.txt",
                hash('a'),
                "models/pocket/sherpa-config.json",
                Map.of(
                        "protocol/transcript.txt", hash('a'),
                        "models/pocket/sherpa-config.json", hash('b')),
                "cpu",
                threads,
                3,
                0,
                "en");
    }

    @Test
    public void acceptsOnlySweepThreadCounts() {
        assertEquals(1, descriptor(1).numThreads());
        assertEquals(2, descriptor(2).numThreads());
        assertEquals(4, descriptor(4).numThreads());
        assertThrows(IllegalArgumentException.class, () -> descriptor(0));
        assertThrows(IllegalArgumentException.class, () -> descriptor(3));
        assertThrows(IllegalArgumentException.class, () -> descriptor(8));
    }
}
