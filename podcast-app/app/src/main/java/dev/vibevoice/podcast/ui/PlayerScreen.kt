package dev.vibevoice.podcast.ui

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.net.toUri
import androidx.media3.common.MediaItem
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import dev.vibevoice.podcast.data.ChapterAudioEntity
import dev.vibevoice.podcast.data.ChapterEntity
import dev.vibevoice.podcast.data.EpisodeEntity
import dev.vibevoice.podcast.data.PlaybackStateEntity
import kotlinx.coroutines.delay
import java.io.File

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun PlayerScreen(
    episode: EpisodeEntity,
    chapters: List<ChapterEntity>,
    audio: List<ChapterAudioEntity>,
    playback: PlaybackStateEntity?,
    file: File,
    onBack: () -> Unit,
    onExport: (Uri) -> Unit,
    onPersist: (Long, Float, Boolean) -> Unit,
) {
    val context = LocalContext.current
    val largeText = LocalDensity.current.fontScale >= 1.4f
    val player = remember(file.absolutePath) {
        ExoPlayer.Builder(context).build().apply {
            setAudioAttributes(AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_SPEECH).build(), true)
            setHandleAudioBecomingNoisy(true)
            setMediaItem(MediaItem.fromUri(file.toUri()))
            prepare()
            playback?.let { seekTo(it.positionMs); setPlaybackSpeed(it.speed) }
        }
    }
    var restored by remember(file.absolutePath) { mutableStateOf(playback != null) }
    var playbackPosition by remember(file.absolutePath) { mutableLongStateOf(playback?.positionMs ?: 0L) }
    var dragPosition by remember(file.absolutePath) { mutableStateOf<Long?>(null) }
    val position = dragPosition ?: playbackPosition
    var duration by remember(file.absolutePath) { mutableLongStateOf(episode.durationMs ?: 0L) }
    var playing by remember { mutableStateOf(false) }
    var transcript by rememberSaveable(episode.id) { mutableStateOf(playback?.transcriptVisible ?: false) }
    var speed by rememberSaveable(episode.id) { mutableFloatStateOf(playback?.speed ?: 1f) }
    var sleepMinutes by rememberSaveable(episode.id) { mutableStateOf<Int?>(null) }
    // Keep the write target bound to this player/episode even during an A→B recomposition.
    val persist = remember(player, episode.id) { onPersist }
    val export = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("audio/wav")) { uri -> uri?.let(onExport) }

    LaunchedEffect(playback, player) {
        if (!restored && playback != null) {
            player.seekTo(playback.positionMs)
            player.setPlaybackSpeed(playback.speed)
            playbackPosition = playback.positionMs
            speed = playback.speed
            transcript = playback.transcriptVisible
            restored = true
        }
    }
    DisposableEffect(player) {
        val listener = object : Player.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) {
                playing = isPlaying
                if (!isPlaying && restored) persist(player.currentPosition, speed, transcript)
            }
        }
        player.addListener(listener)
        onDispose {
            // The caller captures the immutable episode ID; navigation may already have cleared selection.
            persist(player.currentPosition, speed, transcript)
            player.removeListener(listener)
            player.release()
        }
    }
    LaunchedEffect(player) {
        var ticks = 0
        while (true) {
            playbackPosition = player.currentPosition.coerceAtLeast(0)
            if (player.duration > 0) duration = player.duration
            if (playing && ++ticks % 10 == 0) persist(player.currentPosition, speed, transcript)
            delay(300)
        }
    }
    LaunchedEffect(sleepMinutes) {
        val minutes = sleepMinutes ?: return@LaunchedEffect
        delay(minutes * 60_000L)
        player.pause()
        sleepMinutes = null
    }
    val currentAudio = audio.lastOrNull { position >= it.startFrame * 1_000L / it.sampleRateHz } ?: audio.firstOrNull()
    val currentChapter = currentAudio?.let { item -> chapters.firstOrNull { it.stableChapterId == item.stableChapterId } } ?: chapters.firstOrNull()
    val chapterNumber = currentChapter?.position?.plus(1) ?: 1

    PhoneContent {
        Scaffold(
            topBar = {
                TopAppBar(title = { Text("Now playing") },
                    navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.KeyboardArrowDown, "Close player") } },
                    actions = { IconButton(onClick = { export.launch("${episode.title.sanitizedFileName()}.wav") }) { Icon(Icons.Default.FileDownload, "Export episode") } })
            },
            bottomBar = {
                Surface(color = MaterialTheme.colorScheme.surface) {
                    Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 20.dp, vertical = 8.dp)) {
                        Slider(value = position.toFloat().coerceIn(0f, duration.coerceAtLeast(1).toFloat()),
                            onValueChange = { restored = true; dragPosition = it.toLong() },
                            onValueChangeFinished = {
                                val target = dragPosition ?: playbackPosition
                                player.seekTo(target)
                                playbackPosition = target
                                dragPosition = null
                                persist(target, speed, transcript)
                            },
                            valueRange = 0f..duration.coerceAtLeast(1).toFloat(),
                            modifier = Modifier.fillMaxWidth().semantics { contentDescription = "Playback position" })
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(formatDuration(position), style = MaterialTheme.typography.labelSmall)
                            Text(formatDuration(duration), style = MaterialTheme.typography.labelSmall)
                        }
                        Row(Modifier.fillMaxWidth().padding(vertical = 10.dp), horizontalArrangement = Arrangement.SpaceEvenly, verticalAlignment = Alignment.CenterVertically) {
                            IconButton(onClick = { restored = true; player.seekTo((position - 15_000L).coerceAtLeast(0)) }) { Text("−15", style = MaterialTheme.typography.labelLarge, modifier = Modifier.semantics { contentDescription = "Back 15 seconds" }) }
                            IconButton(onClick = { restored = true; seekAdjacentChapter(player, audio, currentAudio, -1) }) { Icon(Icons.Default.SkipPrevious, "Previous chapter") }
                            FilledIconButton(onClick = {
                                restored = true
                                if (player.isPlaying) player.pause() else {
                                    if (player.playbackState == Player.STATE_ENDED) player.seekTo(0)
                                    player.play()
                                }
                            }, modifier = Modifier.size(64.dp)) {
                                Icon(if (playing) Icons.Default.Pause else Icons.Default.PlayArrow, if (playing) "Pause" else "Play", modifier = Modifier.size(32.dp))
                            }
                            IconButton(onClick = { restored = true; seekAdjacentChapter(player, audio, currentAudio, 1) }) { Icon(Icons.Default.SkipNext, "Next chapter") }
                            IconButton(onClick = { restored = true; player.seekTo((position + 15_000L).coerceAtMost(duration)) }) { Text("+15", style = MaterialTheme.typography.labelLarge, modifier = Modifier.semantics { contentDescription = "Forward 15 seconds" }) }
                        }
                        FlowRow(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            AssistChip(onClick = {
                                restored = true
                                speed = when (speed) { 1f -> 1.25f; 1.25f -> 1.5f; 1.5f -> 2f; else -> 1f }
                                player.setPlaybackSpeed(speed); persist(position, speed, transcript)
                            }, label = { Text("${speed}× Speed") }, modifier = Modifier.heightIn(min = 48.dp))
                            AssistChip(onClick = { restored = true; transcript = true }, leadingIcon = { Icon(Icons.Default.ClosedCaption, null) }, label = { Text("Transcript") }, modifier = Modifier.heightIn(min = 48.dp))
                            AssistChip(onClick = { sleepMinutes = when (sleepMinutes) { null -> 15; 15 -> 30; else -> null } },
                                leadingIcon = { Icon(Icons.Default.Timer, null) }, label = { Text(sleepMinutes?.let { "$it min" } ?: "Sleep") }, modifier = Modifier.heightIn(min = 48.dp))
                        }
                    }
                }
            },
        ) { padding ->
            LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(horizontal = 20.dp, vertical = 8.dp)) {
                item { VibeArtwork(Modifier.fillMaxWidth().height(if (largeText) 136.dp else 260.dp), episode.title) }
                item {
                    Column(Modifier.fillMaxWidth().padding(top = 16.dp)) {
                        Text("CHAPTER $chapterNumber OF ${chapters.size}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                        Text(currentChapter?.title ?: episode.title, style = MaterialTheme.typography.headlineSmall, modifier = Modifier.padding(top = 4.dp))
                        Text("${formatDuration(duration)} · ${chapters.size} chapters", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
    if (transcript && currentChapter != null) TranscriptSheet(currentChapter, chapterNumber, chapters.size) {
        transcript = false; persist(position, speed, false)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TranscriptSheet(chapter: ChapterEntity, chapterNumber: Int, chapterCount: Int, onDismiss: () -> Unit) {
    val paragraphs = chapter.text.split(Regex("(?<=[.!?])\\s+(?=[A-Z])")).filter(String::isNotBlank)
    val listState = androidx.compose.foundation.lazy.rememberLazyListState()
    LaunchedEffect(chapter.stableChapterId) { listState.scrollToItem(0) }
    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true), containerColor = MaterialTheme.colorScheme.primaryContainer) {
        Column(Modifier.fillMaxSize().navigationBarsPadding()) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("Chapter $chapterNumber · ${chapter.title}", style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f))
                IconButton(onClick = onDismiss) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Close transcript") }
            }
            LazyColumn(Modifier.fillMaxWidth().weight(1f), state = listState, contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(22.dp)) {
                itemsIndexed(paragraphs) { _, paragraph -> Text(paragraph, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onPrimaryContainer) }
            }
            Row(Modifier.fillMaxWidth().padding(20.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Frozen chapter transcript", style = MaterialTheme.typography.labelMedium, modifier = Modifier.weight(1f))
                Text("$chapterNumber / $chapterCount", style = MaterialTheme.typography.labelMedium)
            }
        }
    }
}

private fun seekAdjacentChapter(player: ExoPlayer, audio: List<ChapterAudioEntity>, current: ChapterAudioEntity?, delta: Int) {
    if (audio.isEmpty()) return
    val index = current?.let(audio::indexOf)?.coerceAtLeast(0) ?: 0
    val target = audio[(index + delta).coerceIn(0, audio.lastIndex)]
    player.seekTo(target.startFrame * 1_000L / target.sampleRateHz)
}
private fun String.sanitizedFileName(): String = lowercase().replace(Regex("[^a-z0-9]+"), "-").trim('-').ifBlank { "episode" }
