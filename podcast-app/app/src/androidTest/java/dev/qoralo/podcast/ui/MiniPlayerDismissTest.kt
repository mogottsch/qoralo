package dev.qoralo.podcast.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.qoralo.podcast.data.EpisodeEntity
import dev.qoralo.podcast.data.EpisodePhase
import dev.qoralo.podcast.data.PlaybackStateEntity
import dev.qoralo.podcast.runtime.AudioAttemptBinding
import dev.qoralo.podcast.runtime.AudioAvailability
import dev.qoralo.podcast.runtime.AudioAvailabilityState
import dev.qoralo.podcast.runtime.AvailableAudioChunk
import dev.qoralo.podcast.ui.theme.QoraloTheme
import kotlinx.coroutines.delay
import org.junit.After
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.Closeable
import java.io.File
import java.io.RandomAccessFile

/** Actual shared host + muted synthetic PCM. No models, generation jobs or user database. */
@RunWith(AndroidJUnit4::class)
class MiniPlayerDismissTest {
    @get:Rule val rule = createComposeRule()
    private lateinit var host: PlaybackHost
    private lateinit var root: File
    private lateinit var file: File
    private lateinit var density: Density
    private var saved: PlaybackStateEntity? = null
    private var leasesClosed = 0
    private var opens = 0
    private val episode = EpisodeEntity("mini-dismiss", "Synthetic episode with a long title", EpisodePhase.FROZEN_READY,
        "", true, "revision", "revision", "synthetic-hash", 1, null, 60_000, null, null, null, 1, 1)

    @After fun cleanup() {
        rule.runOnIdle { if (::host.isInitialized) host.close() }
        if (::root.isInitialized) root.deleteRecursively()
    }

    @Test fun closingPlayingMiniStopsReleasesAndReopensAtSavedPositionWithoutAutoplay() {
        render()
        val original = host.active!!.session
        rule.onNodeWithContentDescription("Play").performClick()
        rule.waitUntil(10_000) { original.isPlaying && original.positionMs > 12_200 }
        val before = rule.runOnIdle { original.player.currentPosition }
        rule.onNodeWithContentDescription("Close player").assertHasClickAction().performClick()
        assertClosed(original)
        val position = requireNotNull(saved).positionMs
        assertTrue("Close must retain the actual cursor", position in before..before + 2_000)
        rule.runOnIdle {
            open(saved)
            val reopened = host.active!!.session
            assertNotSame(original, reopened)
            assertEquals(position, reopened.positionMs)
            assertEquals(1.25f, reopened.speed)
            assertFalse(reopened.isPlaying)
            assertFalse(reopened.wantsPlayback)
            assertEquals(0, opens)
        }
        rule.onNodeWithContentDescription("Close player").assertIsDisplayed()
    }

    @Test fun closeHasItsOwn48dpTargetAt320dpAndDoubleFontWithoutStealingOpenOrPlay() {
        render(width = 320, fontScale = 2f)
        val close = rule.onNodeWithContentDescription("Close player").assertIsDisplayed().assertIsEnabled().assertHasClickAction()
        val closeBounds = close.fetchSemanticsNode().boundsInRoot
        val minimum = with(density) { 48.dp.toPx() } - 1f
        assertTrue(closeBounds.width >= minimum && closeBounds.height >= minimum)
        val title = rule.onNodeWithContentDescription("Open player: ${episode.title}").assertIsDisplayed().fetchSemanticsNode().boundsInRoot
        val play = rule.onNodeWithContentDescription("Play").assertIsDisplayed().fetchSemanticsNode().boundsInRoot
        assertTrue("Close crowds the title", closeBounds.left - title.right >= with(density) { 8.dp.toPx() } - 1f)
        assertFalse("Close overlaps Play", closeBounds.overlaps(play))
        val original = host.active!!.session
        close.performClick()
        assertClosed(original)
        assertEquals(12_000, requireNotNull(saved).positionMs)
        assertEquals(0, opens)
    }

    @Test fun closingAtLiveTailCancelsPlaybackIntentAndIgnoresLateAudio() {
        val initial = render(live = true)
        val original = host.active!!.session
        rule.onNodeWithContentDescription("Play").performClick()
        rule.waitUntil(10_000) { original.waiting && original.positionMs >= 1_000 }
        rule.onNodeWithContentDescription("Close player").performClick()
        assertClosed(original)
        rule.runOnIdle {
            val next = initial!!.chunks.single().copy(index = 1, segmentIndex = 1, startFrame = 44_100)
            original.update(initial.copy(chunks = initial.chunks + next))
            original.togglePlay()
            original.tick()
            assertNull(host.active)
            assertFalse(original.wantsPlayback)
            assertEquals(1, original.availableChunks.size)
        }
        rule.onNodeWithContentDescription("Close player").assertDoesNotExist()
    }

    @Test fun staleAudioCanStillBeClosedWhenTransportIsDisabled() {
        val initial = render(live = true)
        val original = host.active!!.session
        rule.runOnIdle { original.update(initial!!.copy(state = AudioAvailabilityState.STALE)) }
        rule.onNodeWithContentDescription("Play").assertIsNotEnabled()
        rule.onNodeWithContentDescription("Close player").assertIsEnabled().performClick()
        assertClosed(original)
    }

    private fun assertClosed(session: EpisodePlayerSession) {
        rule.onNodeWithContentDescription("Close player").assertDoesNotExist()
        rule.onNodeWithContentDescription("Open player: ${episode.title}").assertDoesNotExist()
        rule.onNodeWithText("No active player").assertIsDisplayed()
        rule.runOnIdle {
            assertNull(host.active)
            assertTrue(session.isReleased)
            assertFalse(session.isPlaying)
            assertFalse(session.wantsPlayback)
            assertEquals(1, leasesClosed)
            assertTrue("Closing must not delete episode media", file.isFile)
        }
    }

    private fun render(width: Int = 360, fontScale: Float = 1f, live: Boolean = false): AudioAvailability? {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        root = File(context.cacheDir, "mini-dismiss-${System.nanoTime()}").also { check(it.mkdirs()) }
        file = File(root, "synthetic-silence.wav").also { writeSilence(it, if (live) 44_100 else 60 * 44_100) }
        val stream = if (live) AudioAvailability(
            AudioAttemptBinding(episode.id, "synthetic-job", "revision", "synthetic-revision", "synthetic-pack"),
            listOf(AvailableAudioChunk(0, 0, "chapter", 0, file, "synthetic-pcm", 0, 44_100, 0)),
            AudioAvailabilityState.GENERATING,
        ) else null
        rule.runOnIdle { host = PlaybackHost(context, acquireFiles = { Closeable { leasesClosed++ } }) }
        rule.setContent {
            val platform = LocalDensity.current
            density = Density(platform.density, fontScale)
            CompositionLocalProvider(LocalDensity provides density) {
                QoraloTheme {
                    Surface(color = MaterialTheme.colorScheme.surface) {
                        Box(Modifier.fillMaxSize().safeDrawingPadding(), contentAlignment = Alignment.TopCenter) {
                            Column(Modifier.requiredWidth(width.dp)) {
                                val active = host.active
                                if (active != null) {
                                    MiniPlayer(active.episode.title, active.session, onOpen = { opens++ }, onClose = host::close)
                                } else Text("No active player")
                                Text("Synthetic library")
                                LaunchedEffect(active) {
                                    while (active != null && host.active === active) {
                                        active.session.tick()
                                        delay(50)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        rule.runOnIdle {
            host.open(episode, emptyList(), emptyList(), stream?.binding?.jobId, if (live) null else file, stream,
                if (live) null else PlaybackStateEntity(episode.id, 12_000, 1.25f, false, 1), ::persist)
            host.active!!.session.player.volume = 0f
        }
        return stream
    }

    private fun open(state: PlaybackStateEntity?) {
        host.open(episode, emptyList(), emptyList(), null, file, null, state, ::persist)
        host.active!!.session.player.volume = 0f
    }

    private fun persist(position: Long, speed: Float, transcript: Boolean) {
        saved = PlaybackStateEntity(episode.id, position, speed, transcript, 1)
    }

    private fun writeSilence(file: File, frames: Int) {
        RandomAccessFile(file, "rw").use { out ->
            val bytes = frames * 2L
            fun u16(value: Int) { out.write(value and 255); out.write((value ushr 8) and 255) }
            fun u32(value: Long) { u16((value and 65535).toInt()); u16(((value ushr 16) and 65535).toInt()) }
            out.setLength(44 + bytes); out.seek(0)
            out.writeBytes("RIFF"); u32(36 + bytes); out.writeBytes("WAVEfmt "); u32(16)
            u16(1); u16(1); u32(44_100); u32(88_200); u16(2); u16(16); out.writeBytes("data"); u32(bytes)
        }
    }
}
