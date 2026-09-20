package dev.qoralo.podcast.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import dev.qoralo.podcast.data.GenerationJobEntity
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
                    DetailsDisclosure("About measurements") {
                        Text("Saved locally. No prompt or response text. Missing values are not estimated; opening this screen never runs a model.")
                        Text("Job wall time includes teardown and publication, but not queue wait. Request wall time includes conversation close and JSON parsing.")
                        Text("Token counts, rates, TTFT and initialization come from LiteRT-LM for each fresh conversation. Aggregate rates require every request’s counters; they are not end-to-end speed.")
                        Text("RTF = elapsed time ÷ audio duration; lower is faster. Duration includes prescribed gaps. Render time includes publication callbacks. Recovered audio has no new synthesis RTF.")
                    }
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
        Text(job.status.lowercase().replaceFirstChar { it.titlecase() }, style = MaterialTheme.typography.bodySmall)
        if (data == null) {
            Text("No measurements recorded.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            if (recovered) Text("Recovered saved audio · no new synthesis.")
            if (data.optString("outcome") == "running" && job.status !in setOf("QUEUED", "RUNNING")) {
                Text("Partial measurements · recording was interrupted.")
            }
            Metric("Job wall time", data.time("wallMs"))
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
            } else {
                Metric("Prefill throughput · job aggregate", data.number("llmPrefillTokensPerSecond", " tokens/s", "Runtime doesn't report"))
                Metric("Decode throughput · job aggregate", data.number("llmDecodeTokensPerSecond", " tokens/s", "Runtime doesn't report"))
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
