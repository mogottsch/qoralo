package dev.qoralo.podcast.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.gestures.animateScrollBy
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.input.nestedscroll.NestedScrollConnection
import androidx.compose.ui.input.nestedscroll.NestedScrollSource
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.scrollBy
import kotlinx.coroutines.launch
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TranscriptSheet(
    episodeId: String,
    timeline: TranscriptTimeline,
    positionMs: Long,
    isPlaying: Boolean,
    waiting: Boolean,
    onDismiss: () -> Unit,
) {
    // Keep all chapters in one stable list. Advancing a chapter must not replace text
    // under a person reading an earlier passage.
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()
    var following by rememberSaveable(episodeId) { mutableStateOf(true) }
    val activeIndex = timeline.activeIndex(positionMs)
    val largeText = LocalDensity.current.fontScale >= 1.4f
    val status = when {
        waiting -> "Waiting for more audio"
        activeIndex == null -> "No timed speech at this position"
        timeline.passages[activeIndex].precision == TranscriptPrecision.CHAPTER -> if (isPlaying) "Current chapter" else "Paused in this chapter"
        isPlaying -> "Current passage"
        else -> "Paused at this passage"
    }
    val scrollObserver = remember {
        object : NestedScrollConnection {
            override fun onPreScroll(available: Offset, source: NestedScrollSource): Offset {
                if (source == NestedScrollSource.UserInput && available.y != 0f) following = false
                return Offset.Zero
            }
        }
    }
    LaunchedEffect(following, activeIndex) {
        val target = TranscriptFollowPolicy(following).target(activeIndex) ?: return@LaunchedEffect
        // Jump only at a real passage boundary (or explicit resume). No per-tick animation,
        // word interpolation, or automatic chapter reset that fights manual scrolling.
        val visible = listState.layoutInfo.visibleItemsInfo.firstOrNull { it.index == target }
        val viewport = listState.layoutInfo
        val requiredVisibleHeight = visible?.size?.coerceAtMost((viewport.viewportEndOffset - viewport.viewportStartOffset) / 2) ?: 0
        if (visible == null || visible.offset < viewport.viewportStartOffset || visible.offset + requiredVisibleHeight > viewport.viewportEndOffset) listState.scrollToItem(target)
    }
    ModalBottomSheet(onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = MaterialTheme.colorScheme.primaryContainer) {
        Column(Modifier.fillMaxSize().navigationBarsPadding()) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("Frozen chapter transcript", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                IconButton(onClick = onDismiss) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Close transcript") }
            }
            if (largeText) Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp)) {
                Text(status, style = MaterialTheme.typography.bodySmall, minLines = 2, maxLines = 2, overflow = TextOverflow.Ellipsis)
                TextButton(onClick = { following = !following }, modifier = Modifier.heightIn(min = 48.dp).align(Alignment.End)) {
                    Text(if (following) "Following · stop" else "Follow playback")
                }
            } else Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp), verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(status, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f), minLines = 2, maxLines = 2, overflow = TextOverflow.Ellipsis)
                TextButton(onClick = { following = !following }, modifier = Modifier.heightIn(min = 48.dp)) {
                    Text(if (following) "Following · stop" else "Follow playback")
                }
            }
            if (timeline.passages.isEmpty()) Text("Transcript is not available for this audio revision.", Modifier.padding(20.dp))
            LazyColumn(Modifier.fillMaxWidth().weight(1f).testTag("Transcript passages").nestedScroll(scrollObserver).semantics {
                // TalkBack/keyboard accessibility scrolling may not dispatch a touch drag.
                scrollBy { _, y ->
                    following = false
                    scope.launch { listState.animateScrollBy(y) }
                    true
                }
            }, state = listState,
                contentPadding = PaddingValues(horizontal = 20.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                itemsIndexed(timeline.passages, key = { _, row -> row.key }) { index, passage ->
                    val active = index == activeIndex
                    Column {
                        if (index == 0 || timeline.passages[index - 1].chapterId != passage.chapterId) {
                            Text("Chapter ${passage.chapterPosition + 1} · ${passage.chapterTitle}",
                                style = MaterialTheme.typography.titleSmall,
                                modifier = Modifier.padding(top = if (index == 0) 0.dp else 16.dp, bottom = 12.dp).semantics { heading() })
                        }
                        Surface(color = if (active) MaterialTheme.colorScheme.surface else MaterialTheme.colorScheme.primaryContainer,
                            shape = MaterialTheme.shapes.medium,
                            modifier = Modifier.fillMaxWidth().semantics {
                                if (active) stateDescription = if (passage.precision == TranscriptPrecision.CHAPTER) "Current chapter, chapter timing only" else "Current passage, segment timing"
                            }) {
                            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                // Keep the marker's measured space even when inactive. Inserting a
                                // header (or changing text weight) reflows long font2 passages and
                                // moves the reader although follow scrolling is disabled.
                                Row(modifier = Modifier.alpha(if (active) 1f else 0f)
                                    .then(if (active) Modifier else Modifier.clearAndSetSemantics {}),
                                    verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                    Icon(Icons.Default.PlayArrow, null, Modifier.size(18.dp), tint = MaterialTheme.colorScheme.primary)
                                    Text(if (passage.precision == TranscriptPrecision.CHAPTER) "Current chapter" else "Current passage",
                                        style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                                }
                                // A chapter-only interval highlights this entire container. Splitting its
                                // paragraphs is typography, never fabricated sentence-level timing.
                                val paragraphs = if (passage.precision == TranscriptPrecision.CHAPTER)
                                    passage.text.split(Regex("(?<=[.!?])\\s+(?=[A-Z])")).filter(String::isNotBlank) else listOf(passage.text)
                                paragraphs.forEach { paragraph ->
                                    Text(paragraph, style = MaterialTheme.typography.headlineSmall,
                                        fontWeight = FontWeight.Medium,
                                        color = if (active) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onPrimaryContainer)
                                }
                                // Arrival changes availability, not the row's measured height.
                                val unavailable = passage.precision == TranscriptPrecision.UNAVAILABLE
                                Text("Audio timing unavailable", style = MaterialTheme.typography.labelSmall,
                                    modifier = Modifier.alpha(if (unavailable) 1f else 0f)
                                        .then(if (unavailable) Modifier else Modifier.clearAndSetSemantics {}))
                            }
                        }
                    }
                }
            }
            Text("Highlights follow available segment or chapter timing, not individual words.",
                style = MaterialTheme.typography.labelSmall, modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 12.dp))
        }
    }
}
