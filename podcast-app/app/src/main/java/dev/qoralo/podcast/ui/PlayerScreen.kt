package dev.qoralo.podcast.ui

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.unit.dp
import dev.qoralo.podcast.data.ChapterAudioEntity
import dev.qoralo.podcast.data.ChapterEntity
import dev.qoralo.podcast.data.EpisodeEntity
import dev.qoralo.podcast.data.PlaybackStateEntity
import kotlinx.coroutines.delay
import java.io.File

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun PlayerScreen(
    episode: EpisodeEntity,
    chapters: List<ChapterEntity>,
    audio: List<ChapterAudioEntity>,
    playback: PlaybackStateEntity?,
    file: File?,
    onBack: () -> Unit,
    onExport: (Uri) -> Unit,
    onPersist: (Long, Float, Boolean) -> Unit,
    liveAudio: dev.qoralo.podcast.runtime.AudioAvailability? = null,
    sharedPlayback: ActivePlayback? = null,
) {
    val context = LocalContext.current
    val largeText = LocalDensity.current.fontScale >= 1.4f
    val separateSeekRow = largeText || LocalConfiguration.current.screenWidthDp < 360
    val sessionKey = sharedPlayback?.identity ?: liveAudio?.binding?.jobId ?: requireNotNull(file).absolutePath
    // Standalone gallery/tests retain their local lifecycle; the app always supplies the host.
    val session = sharedPlayback?.session ?: remember(episode.id, sessionKey) {
        EpisodePlayerSession(context, episode.id, file, liveAudio, playback, episode.durationMs ?: 0L, onPersist)
    }
    var dragPosition by remember(session) { mutableStateOf<Long?>(null) }
    val position = dragPosition ?: session.positionMs
    val duration = session.durationMs
    val playing = session.wantsPlayback || session.isPlaying
    val speed = session.speed
    val transcript = session.transcript
    val sleepMinutes = session.sleepMinutes
    val canExport = episode.phase == dev.qoralo.podcast.data.EpisodePhase.FROZEN_READY && episode.finalAudioPath != null
    val export = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("audio/wav")) { uri -> if (canExport) uri?.let(onExport) }
    if (sharedPlayback == null) {
        LaunchedEffect(playback, session) { session.restore(playback) }
        LaunchedEffect(liveAudio, session) { liveAudio?.let(session::update) }
        DisposableEffect(session) { onDispose { session.close() } }
        LaunchedEffect(session) {
            var ticks = 0
            while (true) { session.tick();if (session.isPlaying && ++ticks % 10 == 0) session.checkpoint();delay(300) }
        }
    }
    val currentAudio = audio.lastOrNull { position >= it.startFrame * 1_000L / it.sampleRateHz } ?: audio.firstOrNull()
    val currentChapter = session.currentChapterPosition(position)?.let { n -> chapters.firstOrNull { it.position == n } }
        ?: currentAudio?.let { item -> chapters.firstOrNull { it.stableChapterId == item.stableChapterId } } ?: chapters.firstOrNull()
    val chapterNumber = currentChapter?.position?.plus(1) ?: 1
    fun adjacent(delta: Int): Long? {
        if (liveAudio != null) return session.adjacentChapter(position, delta)
        val index = currentAudio?.let(audio::indexOf) ?: return null
        return audio.getOrNull(index + delta)?.let { it.startFrame * 1000L / it.sampleRateHz }
    }
    val previousTarget = adjacent(-1)
    val nextTarget = adjacent(1)
    val canSeek = duration > 0 && session.streamState != dev.qoralo.podcast.runtime.AudioAvailabilityState.STALE

    PhoneContent {
        Scaffold(
            topBar = {
                TopAppBar(title = { Text("Now playing") },
                    navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.KeyboardArrowDown, "Minimize player") } },
                    actions = { IconButton(enabled = canExport, onClick = { export.launch("${episode.title.sanitizedFileName()}.wav") }) { Icon(Icons.Default.FileDownload, "Export episode") } })
            },
            bottomBar = {
                Surface(color = MaterialTheme.colorScheme.surface) {
                    Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = if (largeText) 12.dp else 20.dp, vertical = 8.dp)) {
                        Slider(value = position.toFloat().coerceIn(0f, duration.coerceAtLeast(1).toFloat()),
                            onValueChange = { session.markInteraction(); dragPosition = it.toLong() },
                            enabled = canSeek,
                            onValueChangeFinished = {
                                val target = dragPosition ?: session.positionMs
                                session.seek(target)
                                dragPosition = null
                            },
                            valueRange = 0f..duration.coerceAtLeast(1).toFloat(),
                            modifier = Modifier.fillMaxWidth().semantics { contentDescription = "Playback position" })
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(formatDuration(position), style = MaterialTheme.typography.labelSmall)
                            Text(if (liveAudio != null) "${formatDuration(duration)} available" else formatDuration(duration), style = MaterialTheme.typography.labelSmall)
                        }
                        FlowRow(Modifier.fillMaxWidth().padding(vertical = 10.dp), horizontalArrangement = Arrangement.SpaceEvenly,
                            verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            if (!separateSeekRow) TextButton(enabled = canSeek && position > 0, onClick = { session.seek((position - 15_000L).coerceAtLeast(0)) },
                                modifier = Modifier.widthIn(min = 64.dp).heightIn(min = 48.dp).align(Alignment.CenterVertically)
                                    .semantics { contentDescription = "Back 15 seconds" }, contentPadding = PaddingValues(horizontal = 8.dp, vertical = 12.dp)) {
                                Text("−15", style = MaterialTheme.typography.labelLarge, maxLines = 1, softWrap = false)
                            }
                            IconButton(enabled = previousTarget != null, onClick = { previousTarget?.let(session::seek) }, modifier = Modifier.align(Alignment.CenterVertically)) { Icon(Icons.Default.SkipPrevious, "Previous chapter") }
                            FilledIconButton(enabled = session.streamState != dev.qoralo.podcast.runtime.AudioAvailabilityState.STALE, onClick = session::togglePlay, modifier = Modifier.size(64.dp).align(Alignment.CenterVertically)) {
                                Icon(if (playing) Icons.Default.Pause else Icons.Default.PlayArrow, if (playing) "Pause" else "Play", modifier = Modifier.size(32.dp))
                            }
                            IconButton(enabled = nextTarget != null, onClick = { nextTarget?.let(session::seek) }, modifier = Modifier.align(Alignment.CenterVertically)) { Icon(Icons.Default.SkipNext, "Next chapter") }
                            if (!separateSeekRow) TextButton(enabled = canSeek && position < duration, onClick = { session.seek((position + 15_000L).coerceAtMost(duration)) },
                                modifier = Modifier.widthIn(min = 64.dp).heightIn(min = 48.dp).align(Alignment.CenterVertically)
                                    .semantics { contentDescription = "Forward 15 seconds" }, contentPadding = PaddingValues(horizontal = 8.dp, vertical = 12.dp)) {
                                Text("+15", style = MaterialTheme.typography.labelLarge, maxLines = 1, softWrap = false)
                            }
                        }
                        if (separateSeekRow) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            TextButton(enabled = canSeek && position > 0, onClick = { session.seek((position - 15_000L).coerceAtLeast(0)) },
                                modifier = Modifier.weight(1f).heightIn(min = 48.dp).semantics { contentDescription = "Back 15 seconds" },
                                contentPadding = PaddingValues(horizontal = 8.dp, vertical = 8.dp)) {
                                Text("−15", style = MaterialTheme.typography.labelLarge, maxLines = 1, softWrap = false)
                            }
                            TextButton(enabled = canSeek && position < duration, onClick = { session.seek((position + 15_000L).coerceAtMost(duration)) },
                                modifier = Modifier.weight(1f).heightIn(min = 48.dp).semantics { contentDescription = "Forward 15 seconds" },
                                contentPadding = PaddingValues(horizontal = 8.dp, vertical = 8.dp)) {
                                Text("+15", style = MaterialTheme.typography.labelLarge, maxLines = 1, softWrap = false)
                            }
                        }
                        FlowRow(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            AssistChip(onClick = {
                                session.changeSpeed(when (speed) { 1f -> 1.25f; 1.25f -> 1.5f; 1.5f -> 2f; else -> 1f })
                            }, label = { Text("${speed}× Speed") }, modifier = Modifier.heightIn(min = 48.dp))
                            AssistChip(onClick = { session.showTranscript(true) }, leadingIcon = { Icon(Icons.Default.ClosedCaption, null) }, label = { Text("Transcript") }, modifier = Modifier.heightIn(min = 48.dp))
                            AssistChip(onClick = session::cycleSleepTimer,
                                leadingIcon = { Icon(Icons.Default.Timer, null) }, label = { Text(sleepMinutes?.let { "$it min" } ?: "Sleep") }, modifier = Modifier.heightIn(min = 48.dp))
                        }
                    }
                }
            },
        ) { padding ->
            LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(horizontal = 20.dp, vertical = 8.dp)) {
                if (liveAudio != null) item {
                    Column(Modifier.fillMaxWidth().padding(bottom = 12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        val status = when {
                            session.error != null -> session.error!!
                            session.waiting -> "Waiting for more audio…"
                            session.isPlaying -> "Playing"
                            session.wantsPlayback -> "Buffering"
                            else -> "Paused"
                        }
                        Text(status, style = MaterialTheme.typography.titleMedium,
                            modifier = Modifier.semantics { liveRegion = androidx.compose.ui.semantics.LiveRegionMode.Polite })
                        Text(when (session.streamState) {
                            dev.qoralo.podcast.runtime.AudioAvailabilityState.GENERATING -> "Still generating"
                            dev.qoralo.podcast.runtime.AudioAvailabilityState.FAILED -> "Partial audio · generation stopped. Export unavailable."
                            dev.qoralo.podcast.runtime.AudioAvailabilityState.COMPLETE -> "Episode complete"
                            else -> "Audio attempt is no longer current"
                        }, style = MaterialTheme.typography.bodySmall)
                    }
                }
                item { VibeArtwork(Modifier.fillMaxWidth().height(if (largeText) 136.dp else 260.dp), episode.title) }
                item {
                    Column(Modifier.fillMaxWidth().padding(top = 16.dp)) {
                        Text("CHAPTER $chapterNumber OF ${chapters.size}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                        Text(currentChapter?.title ?: episode.title, style = MaterialTheme.typography.headlineSmall, modifier = Modifier.padding(top = 4.dp))
                        if (liveAudio == null) Text("${chapters.size} chapters", style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 4.dp))
                    }
                }
            }
        }
    }
    if (transcript) {
        val verified = sharedPlayback?.verifiedPassages ?: emptyList()
        val timeline = remember(episode.id, episode.lockedRevisionId, chapters, audio, liveAudio, verified) {
            if (liveAudio != null) TranscriptTiming.progressive(episode.id, chapters, liveAudio)
            else TranscriptTiming.finalAudio(episode.id, episode.lockedRevisionId ?: episode.activeRevisionId, chapters, audio, verified)
        }
        TranscriptSheet(episode.id, timeline, session.positionMs, session.isPlaying, session.waiting) { session.showTranscript(false) }
    }
}

private fun String.sanitizedFileName(): String = lowercase().replace(Regex("[^a-z0-9]+"), "-").trim('-').ifBlank { "episode" }
