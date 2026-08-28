package dev.vibevoice.podcast.ui

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.ClosedCaption
import androidx.compose.material.icons.filled.FileDownload
import androidx.compose.material.icons.filled.Forward10
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Replay10
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material.icons.filled.Timer
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.net.toUri
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import dev.vibevoice.podcast.data.ChapterAudioEntity
import dev.vibevoice.podcast.data.ChapterEntity
import dev.vibevoice.podcast.data.EpisodeEntity
import dev.vibevoice.podcast.data.PlaybackStateEntity
import kotlinx.coroutines.delay
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
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
    val player = remember(file.absolutePath) {
        ExoPlayer.Builder(context).build().apply {
            setMediaItem(MediaItem.fromUri(file.toUri()))
            prepare()
            playback?.let { seekTo(it.positionMs); setPlaybackSpeed(it.speed) }
        }
    }
    var position by remember { mutableLongStateOf(playback?.positionMs ?: 0L) }
    var duration by remember { mutableLongStateOf(episode.durationMs ?: 0L) }
    var playing by remember { mutableStateOf(false) }
    var transcript by remember { mutableStateOf(playback?.transcriptVisible ?: false) }
    var speed by remember { mutableStateOf(playback?.speed ?: 1f) }
    var sleepMinutes by remember { mutableStateOf<Int?>(null) }
    val export = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("audio/wav")) { uri -> uri?.let(onExport) }

    DisposableEffect(player) {
        val listener = object : Player.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) { playing = isPlaying }
        }
        player.addListener(listener)
        onDispose {
            onPersist(player.currentPosition, speed, transcript)
            player.removeListener(listener)
            player.release()
        }
    }
    LaunchedEffect(player) {
        while (true) {
            position = player.currentPosition.coerceAtLeast(0)
            if (player.duration > 0) duration = player.duration
            delay(300)
        }
    }
    LaunchedEffect(sleepMinutes) {
        val minutes = sleepMinutes ?: return@LaunchedEffect
        delay(minutes * 60_000L)
        player.pause()
        sleepMinutes = null
    }

    val currentAudio = audio.lastOrNull { position >= it.startFrame * 1_000L / it.sampleRateHz }
        ?: audio.firstOrNull()
    val currentChapter = currentAudio?.let { item -> chapters.firstOrNull { it.stableChapterId == item.stableChapterId } }
        ?: chapters.firstOrNull()
    val chapterNumber = currentChapter?.position?.plus(1) ?: 1

    PhoneContent {
        Scaffold(topBar = {
            TopAppBar(
                title = { Text("Now playing") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.KeyboardArrowDown, "Close player") } },
                actions = { IconButton(onClick = { export.launch("${episode.title.sanitizedFileName()}.wav") }) { Icon(Icons.Default.FileDownload, "Export episode") } },
            )
        }) { padding ->
            LazyColumn(
                Modifier.fillMaxSize().padding(padding),
                contentPadding = PaddingValues(horizontal = 20.dp, vertical = 6.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                item { VibeArtwork(Modifier.fillMaxWidth().height(300.dp), episode.title) }
                item {
                    Column(Modifier.fillMaxWidth().padding(top = 20.dp)) {
                        Text("CHAPTER $chapterNumber OF ${chapters.size}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                        Text(currentChapter?.title ?: episode.title, style = MaterialTheme.typography.headlineSmall, maxLines = 2, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 4.dp))
                        Text("${formatDuration(duration)} · ${chapters.size} chapters", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                item {
                    Slider(
                        value = position.toFloat().coerceIn(0f, duration.coerceAtLeast(1).toFloat()),
                        onValueChange = { position = it.toLong() },
                        onValueChangeFinished = { player.seekTo(position) },
                        valueRange = 0f..duration.coerceAtLeast(1).toFloat(),
                        modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                    )
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(formatDuration(position), style = MaterialTheme.typography.labelSmall)
                        Text(formatDuration(duration), style = MaterialTheme.typography.labelSmall)
                    }
                }
                item {
                    Row(Modifier.fillMaxWidth().padding(top = 12.dp), horizontalArrangement = Arrangement.SpaceEvenly, verticalAlignment = Alignment.CenterVertically) {
                        IconButton(onClick = { player.seekTo((position - 10_000L).coerceAtLeast(0)) }) { Icon(Icons.Default.Replay10, "Back 10 seconds") }
                        IconButton(onClick = { seekAdjacentChapter(player, audio, currentAudio, -1) }) { Icon(Icons.Default.SkipPrevious, "Previous chapter") }
                        FilledIconButton(onClick = { if (player.isPlaying) player.pause() else player.play() }, modifier = Modifier.size(64.dp)) {
                            Icon(if (playing) Icons.Default.Pause else Icons.Default.PlayArrow, if (playing) "Pause" else "Play", modifier = Modifier.size(32.dp))
                        }
                        IconButton(onClick = { seekAdjacentChapter(player, audio, currentAudio, 1) }) { Icon(Icons.Default.SkipNext, "Next chapter") }
                        IconButton(onClick = { player.seekTo((position + 10_000L).coerceAtMost(duration)) }) { Icon(Icons.Default.Forward10, "Forward 10 seconds") }
                    }
                }
                item {
                    Row(Modifier.fillMaxWidth().padding(top = 16.dp, bottom = 24.dp), horizontalArrangement = Arrangement.SpaceEvenly) {
                        AssistChip(onClick = {
                            speed = when (speed) { 1f -> 1.25f; 1.25f -> 1.5f; 1.5f -> 2f; else -> 1f }
                            player.setPlaybackSpeed(speed)
                        }, label = { Text("${speed}× Speed") })
                        AssistChip(onClick = { transcript = true }, leadingIcon = { Icon(Icons.Default.ClosedCaption, null) }, label = { Text("Transcript") })
                        AssistChip(onClick = { sleepMinutes = when (sleepMinutes) { null -> 15; 15 -> 30; else -> null } }, leadingIcon = { Icon(Icons.Default.Timer, null) }, label = { Text(sleepMinutes?.let { "$it min" } ?: "Sleep") })
                    }
                }
            }
        }
    }

    if (transcript && currentChapter != null) TranscriptSheet(
        chapter = currentChapter,
        chapterNumber = chapterNumber,
        chapterCount = chapters.size,
        chapterAudio = currentAudio,
        positionMs = position,
        onSeek = { player.seekTo(it) },
        onDismiss = { transcript = false; onPersist(position, speed, false) },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TranscriptSheet(
    chapter: ChapterEntity,
    chapterNumber: Int,
    chapterCount: Int,
    chapterAudio: ChapterAudioEntity?,
    positionMs: Long,
    onSeek: (Long) -> Unit,
    onDismiss: () -> Unit,
) {
    val paragraphs = chapter.text.split(Regex("(?<=[.!?])\\s+(?=[A-Z])")).filter(String::isNotBlank)
    val start = chapterAudio?.let { it.startFrame * 1_000L / it.sampleRateHz } ?: 0L
    val end = chapterAudio?.let { it.endFrame * 1_000L / it.sampleRateHz } ?: (start + 1)
    val ratio = ((positionMs - start).toDouble() / (end - start).coerceAtLeast(1)).coerceIn(0.0, .999)
    val current = (ratio * paragraphs.size).toInt()
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = MaterialTheme.colorScheme.primaryContainer) {
        Column(Modifier.fillMaxWidth().navigationBarsPadding()) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("Chapter $chapterNumber · ${chapter.title}", style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f))
                IconButton(onClick = onDismiss) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Close transcript") }
            }
            LazyColumn(Modifier.fillMaxWidth().weight(1f), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(22.dp)) {
                itemsIndexed(paragraphs) { index, paragraph ->
                    Text(
                        paragraph,
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = if (index == current) 1f else .34f),
                        modifier = Modifier.clickable {
                            val fraction = index.toDouble() / paragraphs.size.coerceAtLeast(1)
                            onSeek(start + ((end - start) * fraction).toLong())
                        },
                    )
                }
            }
            Row(Modifier.fillMaxWidth().padding(20.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Follows playback", style = MaterialTheme.typography.labelMedium)
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
