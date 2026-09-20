package dev.qoralo.podcast.gallery

import android.content.Intent
import android.os.Bundle
import android.os.Process
import android.os.SystemClock
import android.view.inspector.WindowInspector
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.platform.LocalDensity
import dev.qoralo.podcast.data.*
import dev.qoralo.podcast.ui.*
import dev.qoralo.podcast.ui.theme.QoraloTheme
import org.json.JSONObject
import org.json.JSONArray
import java.io.File
import java.io.RandomAccessFile

/** Debug-only :ui_gallery process. No repositories, dispatchers, jobs, engines or model packs. */
class SyntheticGalleryActivity : ComponentActivity() {
    private var frame by mutableStateOf("library")
    private var token by mutableStateOf("")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (intent.getBooleanExtra("finish", false)) { finish(); return }
        enableEdgeToEdge()
        accept(intent)
        setContent {
            QoraloTheme {
                var draftText by rememberSaveable { mutableStateOf(fixtureEpisode(EpisodePhase.INSTRUCTIONS).instructions) }
                var draftReview by rememberSaveable { mutableStateOf(true) }
                val draft = fixtureEpisode(EpisodePhase.INSTRUCTIONS).copy(instructions = draftText, reviewEnabled = draftReview)
                val sources = remember { mutableStateListOf(fixtureSource()) }
                var savedPosition by rememberSaveable { mutableLongStateOf(12_000L) }
                var savedSpeed by rememberSaveable { mutableFloatStateOf(1.5f) }
                var savedTranscript by rememberSaveable { mutableStateOf(false) }
                val savedPlayback = PlaybackStateEntity("ui-episode", savedPosition, savedSpeed, savedTranscript, 1)
                val chapters = remember { fixtureChapters() }
                val wav = remember { syntheticWav() }
                val audio = remember { chapters.mapIndexed { index, chapter ->
                    val start = index * 441_000L
                    ChapterAudioEntity("ui-audio-$index", "ui-episode", "ui-revision", chapter.stableChapterId, index,
                        wav.path, "synthetic-not-model-audio", wav.length(), 44_100, 1, 441_000, start, start + 441_000)
                } }
                val messages = remember { mutableStateListOf(
                    AgentMessageEntity("ui-message-1", "ui-episode", AgentRole.USER, "Focus chapter 2 on flooding today.", "ui-revision", null, 1),
                    AgentMessageEntity("ui-message-2", "ui-episode", AgentRole.AGENT, "Synthetic UI fixture: chapter 2 shortened. No model was run.", "ui-revision", "ui-revision-2", 2),
                ) }
                val largeText = LocalDensity.current.fontScale
                BackHandler(enabled = frame != "library") { frame = if (frame == "instructions") "sources" else "library" }
                key(token, frame) {
                    when (frame) {
                        "library", "library-empty" -> LibraryScreen(
                            if (frame == "library-empty") emptyList() else listOf(fixtureEpisode(EpisodePhase.FROZEN_READY)),
                            { frame = "sources" }, { frame = "player" }, { frame = "library-empty" },
                            playbackStates = listOf(savedPlayback))
                        "sources", "sources-empty", "paste" -> {
                            SourcesScreen(if (frame == "sources-empty") emptyList() else sources, { frame = "library" },
                                { title, text -> sources += fixtureSource().copy(id = "ui-source-${sources.size}", title = title.ifBlank { "Pasted text" }, wordCount = text.split(Regex("\\s+")).size) },
                                {}, { sources.remove(it) }, { frame = "instructions" })
                            if (frame == "paste") PasteSourceDialog({ frame = "sources" }) { _, _ -> frame = "sources" }
                        }
                        "instructions" -> InstructionsScreen(draft, { frame = "sources" }, { _, review -> frame = if (review) "review" else "generating" },
                            onDraftChanged = { text, review -> draftText = text; draftReview = review })
                        "review", "agent", "agent-error", "lock" -> ReviewScreen(chapters, messages,
                            if (frame == "agent-error") GenerationJobEntity("ui-error", "ui-episode", JobKind.AGENT_EDIT, JobStatus.FAILED, "ui-revision", 0, 3,
                                "Draft unchanged", "Synthetic validation error: the proposed revision did not match the current draft. No changes were applied.", 1, 2) else null,
                            frame.startsWith("agent"), frame == "lock", { frame = "library" }, { frame = "agent" }, { frame = "review" },
                            { request -> messages += AgentMessageEntity("ui-message-${messages.size}", "ui-episode", AgentRole.USER, request, "ui-revision", null, messages.size.toLong()) },
                            { frame = "lock" }, { frame = "review" }, { frame = "generating" })
                        "generating", "script-loading" -> GeneratingScreen(fixtureEpisode(if (frame == "script-loading") EpisodePhase.GENERATING_SCRIPT else EpisodePhase.GENERATING_AUDIO),
                            GenerationJobEntity("ui-job", "ui-episode", if (frame == "script-loading") JobKind.SCRIPT else JobKind.AUDIO, JobStatus.RUNNING,
                                "ui-revision", 2, 3, if (frame == "script-loading") "Writing the complete chapter" else "Creating What flooding remembers", null, 1, 2), { frame = "library" })
                        "failure" -> GeneratingScreen(fixtureEpisode(EpisodePhase.FAILED).copy(failurePhase = "qnn-load",
                            failureMessage = "Synthetic UI failure: audio could not start. The selected QNN backend rejected device initialization. The locked chapter text is unchanged. No alternate model, CPU route, or hidden chapter splitting was attempted. This message deliberately spans several lines to test readability at larger font sizes."), null, { frame = "library" })
                        "player", "transcript" -> PlayerScreen(fixtureEpisode(EpisodePhase.FROZEN_READY), chapters, audio,
                            savedPlayback.copy(transcriptVisible = frame == "transcript"), wav, { frame = "library" }, {},
                            { position, speed, visible -> savedPosition = position; savedSpeed = speed; savedTranscript = visible })
                    }
                }
                LaunchedEffect(frame, token) {
                    // Read actual platform accessibility IDs from this process's attached decor
                    // views (including dialogs). Never infer identity from a requested window title,
                    // insert marker nodes, or change production Compose accessibility semantics.
                    withFrameNanos { }; withFrameNanos { }
                    while (isActive) {
                        val windows = JSONArray()
                        WindowInspector.getGlobalWindowViews().filter { it.isAttachedToWindow && it.isShown }.forEach { view ->
                            val node = view.createAccessibilityNodeInfo()
                            val id = node?.windowId ?: -1
                            if (id >= 0) windows.put(JSONObject().put("windowId", id).put("rootPackage", node?.packageName?.toString())
                                .put("focused", view.hasWindowFocus()).put("rootClass", view.javaClass.name))
                        }
                        val snapshot = JSONObject().put("frame", frame).put("token", token)
                            .put("pid", Process.myPid()).put("process", android.app.Application.getProcessName()).put("fontScale", largeText)
                            .put("observedWindows", windows).put("sampledAtElapsedMs", SystemClock.elapsedRealtime())
                            .put("syntheticUiOnly", true).put("media", "30-second test tone; not model audio")
                        val temporary = File(filesDir, "ui-gallery-ready.tmp")
                        temporary.writeText(snapshot.toString())
                        check(temporary.renameTo(File(filesDir, "ui-gallery-ready.json")))
                        delay(GalleryCapturePolicy.POLL_MS)
                    }
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        if (intent.getBooleanExtra("finish", false)) { finish(); return }
        setIntent(intent); accept(intent)
    }
    private fun accept(intent: Intent) {
        frame = intent.getStringExtra("frame").orEmpty().also { require(it in FRAMES) }
        token = intent.getStringExtra("token").orEmpty().also { require(it.matches(Regex("ui-[a-z0-9-]{1,100}"))) }
    }

    private fun syntheticWav(): File {
        val output = File(cacheDir, "synthetic-ui-gallery-30s.wav")
        if (output.isFile) return output
        RandomAccessFile(output, "rw").use { wav ->
            val frames = 30 * 44_100
            wav.writeBytes("RIFF"); wav.u32(36L + frames * 2L); wav.writeBytes("WAVEfmt "); wav.u32(16)
            wav.u16(1); wav.u16(1); wav.u32(44_100); wav.u32(88_200); wav.u16(2); wav.u16(16)
            wav.writeBytes("data"); wav.u32(frames * 2L)
            val samples = ByteArray(frames * 2)
            repeat(frames) { index ->
                val sample = (kotlin.math.sin(index * 2.0 * Math.PI * 220.0 / 44100.0) * 800).toInt()
                samples[index * 2] = sample.toByte(); samples[index * 2 + 1] = (sample shr 8).toByte()
            }
            wav.write(samples)
        }
        return output
    }

    private fun RandomAccessFile.u16(value: Int) { write(value and 255); write((value ushr 8) and 255) }
    private fun RandomAccessFile.u32(value: Long) { u16((value and 65535).toInt()); u16(((value ushr 16) and 65535).toInt()) }

    companion object {
        val FRAMES = listOf("library", "library-empty", "sources", "sources-empty", "paste", "instructions", "review", "agent", "agent-error", "lock", "generating", "script-loading", "failure", "player", "transcript")
        private fun fixtureEpisode(phase: String) = EpisodeEntity(
            id = "ui-episode", title = "Why cities remember rivers", phase = phase,
            instructions = "Focus on flooding today. Explain whether cities can restore buried rivers.", reviewEnabled = true,
            activeRevisionId = "ui-revision", lockedRevisionId = if (phase in setOf(EpisodePhase.GENERATING_AUDIO, EpisodePhase.FROZEN_READY, EpisodePhase.FAILED)) "ui-revision" else null,
            lockedContentHash = null, lockedAtEpochMs = null, finalAudioPath = null, durationMs = 30_000,
            currentChapterPosition = null, failurePhase = null, failureMessage = null, createdAtEpochMs = 1, updatedAtEpochMs = 2)
        private fun fixtureSource() = EpisodeSourceEntity("ui-source-1", "ui-episode", "The forgotten waterways beneath us", "text/plain", "synthetic-only", 4860, 24000, "synthetic-only", 1)
        private fun fixtureChapters() = listOf(
            ChapterEntity("ui-row1", "ui-revision", "chapter-1", 0, "Before the street grid", "Every city carries the shape of the water that made it. Long before roads fixed our routes, streams determined where people settled, moved, and built. Some remain visible. Others were redirected underground, but their influence did not disappear.", 60),
            ChapterEntity("ui-row2", "ui-revision", "chapter-2", 1, "What flooding remembers", "When heavy rain arrives, water does not care where the modern street grid says it should go. It follows the older landscape, collecting along the paths of streams that were buried generations ago.", 120),
            ChapterEntity("ui-row3", "ui-revision", "chapter-3", 2, "Can cities bring rivers back?", "Some cities are reopening former waterways, replacing culverts with parks and flood plains. Restoration needs space and careful planning, and it cannot eliminate every source of flood risk.", 120),
        )
    }
}
