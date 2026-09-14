package dev.vibevoice.podcast.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import dev.vibevoice.podcast.data.GenerationJobEntity
import org.json.JSONObject
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun EpisodeDiagnosticsScreen(title: String, attempts: List<Pair<GenerationJobEntity, JSONObject?>>?, error: String?, onBack: () -> Unit) {
    PhoneContent {
        Scaffold(topBar = { TopAppBar(title = { Text("Episode details") }, navigationIcon = {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back to library") }
        }) }) { padding ->
            LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                item {
                    Text(title, style = MaterialTheme.typography.headlineSmall)
                    Text("Local generation diagnostics", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 16.dp))
                    Text("Only timings and runtime counters are saved here. No prompt or response text. Missing measurements are not estimated, and opening these details never runs a model.",
                        style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 8.dp))
                }
                if (error != null) item { Text(error, color = MaterialTheme.colorScheme.error) }
                else if (attempts == null) item { Text("Loading diagnostics…") }
                else if (attempts.isEmpty()) item { Text("No generation attempts yet.") }
                else itemsIndexed(attempts, key = { _, item -> item.first.id }) { index, (job, data) ->
                    AttemptDiagnostics(index + 1, job, data)
                }
            }
        }
    }
}

@Composable
private fun AttemptDiagnostics(number: Int, job: GenerationJobEntity, data: JSONObject?) {
    val recovered = data?.optString("kind") == "PUBLICATION_RECOVERY"
    val kind = if (recovered) "Audio publication recovery" else when (job.kind) { "AUDIO" -> "Speech synthesis"; "SCRIPT" -> "Script generation"; else -> "Script edit" }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        HorizontalDivider()
        Text("Attempt $number · $kind", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 8.dp))
        Text("${job.status.lowercase().replaceFirstChar { it.titlecase() }} · ${job.id.take(12)}", style = MaterialTheme.typography.bodySmall)
        if (data == null) {
            Text("Measurements were not recorded for this attempt. Existing history is kept without replaying generation.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            if (recovered) Text("Saved audio was published without new synthesis. No new synthesis throughput or RTF is claimed.")
            if (data.optString("outcome") == "running" && job.status !in setOf("QUEUED", "RUNNING")) {
                Text("Recording ended before a final timing was saved. Partial measurements below are retained.")
            }
            Metric("Job wall time", data.time("wallMs"))
            Text("Coordinator entry through teardown and publication; queue wait excluded.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Metric("Model setup", data.time("setupMs"))
            if (job.kind == "AUDIO") {
                Metric("Chapter render time", data.time("renderMs"))
                Metric("Final assembly & publication", data.time("finalizationMs"))
                Metric("Native teardown", data.time("teardownMs"))
                Metric(if (job.status == "COMPLETE") "Audio duration" else "Available partial audio", data.time("audioDurationMs"))
                if (!recovered) {
                    Metric("Wall RTF", data.number("wallRtf", "", "Not recorded"))
                    Metric("Render RTF", data.number("renderRtf", "", "Not recorded"))
                }
                Text("RTF = elapsed time ÷ actual audio duration. Lower is faster. Duration includes prescribed silence between segments and chapters; render time includes publication callbacks.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                Metric("Prefill throughput · job aggregate", data.number("llmPrefillTokensPerSecond", " tokens/s", "Runtime doesn't report"))
                Metric("Decode throughput · job aggregate", data.number("llmDecodeTokensPerSecond", " tokens/s", "Runtime doesn't report"))
                Text("Aggregated from each request's runtime-reported token counts and rates. Unavailable if any request lacks counters; not an end-to-end job speed.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                val requests = data.optJSONArray("requests")
                var expanded by remember(job.id) { mutableStateOf(false) }
                var requestPage by remember(job.id) { mutableIntStateOf(0) }
                if (requests != null && requests.length() > 0) {
                    TextButton(onClick = { expanded = !expanded }) { Text(if (expanded) "Hide requests" else "Show ${requests.length()} requests") }
                    if (expanded) {
                    val start = (requestPage * 10).coerceAtMost((requests.length() - 1).coerceAtLeast(0))
                    val end = minOf(start + 10, requests.length())
                    Text("Requests ${start + 1}–$end of ${requests.length()}", style = MaterialTheme.typography.bodySmall)
                    for (i in start until end) {
                        val request = requests.getJSONObject(i)
                        HorizontalDivider()
                        Text("Request ${i + 1} · ${request.optString("mode").replace('_', ' ')} · ${request.optString("outcome")}", style = MaterialTheme.typography.titleSmall)
                        Metric("Request wall time", request.time("totalMs"))
                        Metric("Conversation setup", request.time("conversationSetupMs"))
                        Metric("Send wall time", request.time("sendWallMs"))
                        Metric("Prefill", request.number("prefillTokensPerSecond", " tokens/s", "Runtime doesn't report"))
                        Metric("Prefill tokens", request.number("prefillTokens", "", "Runtime doesn't report", 0))
                        Metric("Decode", request.number("decodeTokensPerSecond", " tokens/s", "Runtime doesn't report"))
                        Metric("Decoded tokens", request.number("decodeTokens", "", "Runtime doesn't report", 0))
                        Metric("Runtime TTFT", request.time("runtimeTtftMs", "Runtime doesn't report"))
                        Metric("Runtime initialization", request.time("runtimeInitMs", "Runtime doesn't report"))
                        Text("TTFT/init and last-prefill/decode counters are reported by LiteRT-LM for this fresh conversation. Request wall time also includes conversation close and JSON parsing.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    if (start > 0) TextButton(onClick = { requestPage-- }) { Text("Previous requests") }
                    if (end < requests.length()) TextButton(onClick = { requestPage++ }) { Text("Next requests") }
                    }
                }
            }
        }
    }
}

@Composable
private fun Metric(label: String, value: String) {
    Column(Modifier.fillMaxWidth().padding(vertical = 2.dp)) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyLarge)
    }
}
private fun JSONObject.time(key: String, absent: String = "Not recorded"): String =
    if (isNull(key)) absent else String.format(Locale.getDefault(), "%.3f s", getDouble(key) / 1000.0)
private fun JSONObject.number(key: String, unit: String, absent: String, decimals: Int = 3): String =
    if (isNull(key)) absent else String.format(Locale.getDefault(), "%.$decimals" + "f", getDouble(key)) + unit
