# Podcast-generation app architecture proposal

**Status:** Discussion draft

**Scope:** Pragmatic Android MVP architecture; no implementation commitment

**Selected runtimes:** Gemma LiteRT GPU for script generation; Supertonic external-context QNN/HTP for speech

## Summary

Build a greenfield Android application with three clear boundaries:

1. an application process for UI, playback, and user control;
2. durable Room and file-backed state for jobs and artifacts;
3. an isolated generation process that loads the LLM and TTS runtimes sequentially.

The proposed MVP pipeline is:

> Add one or more sources → provide one free-text instruction → generate a chaptered script → optionally review and edit through agent chat → lock → generate audio → listen with a synchronized transcript

Use **Gemma 4 E2B through LiteRT GPU** as the single MVP LLM route. Use the **Supertonic 3 external-context QNN/HTP route** as the single MVP TTS runtime. Start with one narrator. Keep both selections fixed; the MVP has no inference fallback routes.

## 1. Selected runtime stack

### 1.1 Script generation

`GemmaLiteRtEngine` is the app's only LLM implementation. It runs through LiteRT GPU in the isolated generation process.

The coordinator keeps one loaded Engine while it generates source notes, an episode outline, and then each complete chapter in one generation request. Every chapter request receives the shared outline and relevant source material so the model can produce coherent long-form prose without sentence-level stitching. Each logical request uses a fresh Session. The Engine is closed before TTS starts to release model and GPU resources. Initialization or inference failure fails the job; there is no alternate LLM route.

### 1.2 Speech generation

`SupertonicQnnEngine` is the app's only TTS implementation. It runs the external-context Supertonic graphs through QNN/HTP in the isolated generation process. The MVP uses one narrator with the M1/SID5 voice configuration.

The coordinator loads TTS once after the script is locked, renders each complete chapter in one QNN generation call, and closes it after every chapter audio file is committed. Chapters are rendered sequentially so only one QNN generation is active at a time. The MVP does not split chapters into sentence-sized TTS requests.

## 2. Supertonic QNN/HTP runtime integration

The QNN implementation is a native C++ library exposed to Kotlin through a small JNI adapter:

```text
Generation coordinator
        │
        ▼
SupertonicQnnEngine (Kotlin)
        │ JNI: load / render / close
        ▼
Native Supertonic runtime
        ├── text and style preparation on CPU
        ├── duration EPContext session on HTP
        ├── text EPContext session on HTP
        ├── vector EPContext session on HTP
        └── vocoder EPContext session on HTP
        │
        ▼
Mono float/PCM audio returned to the chapter writer
```

### Runtime package

The installed Supertonic model pack contains:

- the four external context descriptors and binaries;
- tokenizer, Unicode indexer, voice, and style assets;
- a manifest with exact filenames, sizes, hashes, and runtime compatibility;
- the graph-shape and input limits required by the native adapter.

The APK supplies the matched native ONNX Runtime/QNN integration and JNI library. Model-pack installation is complete only after every artifact passes manifest verification.

### Session lifecycle

1. The generation process verifies the model pack.
2. `SupertonicQnnEngine.load()` creates all four sessions with CPU fallback disabled.
3. A short readiness check confirms that every context can initialize.
4. The same loaded sessions render every chapter in the episode sequentially.
5. `close()` releases all sessions before the worker completes or the process exits.

The engine is not loaded in the UI process and is not shared by concurrent jobs.

### Input contract

The Kotlin coordinator passes one frozen chapter transcript to the native adapter without pre-splitting it. The adapter performs the text normalization, indexing, masks, duration handling, and tensor preparation required by the selected Supertonic QNN route. It never silently truncates or rewrites a chapter.

The first runtime slice explicitly tests whether a complete target-length chapter can run through one QNN call. If the selected graph contract cannot represent or synthesize it, the call fails clearly. Chunking, shape buckets, overlap, and stitching are deliberately deferred until a real chapter-length failure shows which workaround is necessary.

### Output contract

Each render call returns one complete chapter waveform plus its sample rate, frame count, and channel count. The chapter writer validates it and commits one chapter audio artifact before the next chapter starts. The native engine does not own episode files or database state.

### Failure boundary

A native crash is contained to the isolated generation process. QNN initialization or inference failure records the exact affected phase and chapter. There is no CPU TTS fallback. Pause, recovery, cancellation UX, and retry behavior are outside the current MVP design.

## 3. Application boundaries

```text
┌──────────────── Android app process ────────────────┐
│ Compose UI                                           │
│ Library, source, instructions, and script screens    │
│ Agent editing, generation progress, and playback     │
│ Repository and use-case API                          │
└─────────────────────────┬─────────────────────────────┘
                          │ durable commands and state
┌─────────────────────────▼─────────────────────────────┐
│ Room + app-internal artifact store                    │
│ Episodes, sources, chapters, jobs, and artifact refs  │
└─────────────────────────┬─────────────────────────────┘
                          │
┌──────────── isolated :generation process ─────────────┐
│ Generation coordinator                               │
│ LlmEngine adapter → LiteRT-LM/JNI                     │
│ TtsEngine adapter → ORT + QNN/HTP/JNI                 │
│ Audio assembler → WAV / MediaCodec / MediaMuxer       │
└───────────────────────────────────────────────────────┘
```

The UI process should not own native inference sessions. Isolating generation in `:generation` provides:

- UI survival if a native runtime crashes or is killed;
- reclaimable model and GPU memory;
- native failure containment;
- enforcement of one loaded heavy runtime at a time.

The inference boundary should be expressed through small interfaces, for example:

```kotlin
interface LlmEngine {
    suspend fun load(model: InstalledModel)
    suspend fun generate(request: ScriptRequest): GeneratedScript
    suspend fun close()
}

interface TtsEngine {
    suspend fun load(model: InstalledModel, voice: Voice)
    suspend fun renderChapter(chapter: FrozenChapter, output: File): AudioMetadata
    suspend fun close()
}
```

The selected Gemma GPU and Supertonic QNN implementations remain behind these interfaces so backend details do not leak into the UI or episode model. The abstraction exists for clean boundaries and testing, not to add fallback routing.

## 4. On-device generation pipeline

### 4.1 Ingest

The MVP accepts one or more sources. The UX exposes pasted text and file selection; the exact supported file formats remain a technical scope decision.

The application copies each source into app-internal storage, normalizes it deterministically, records its identity, byte length, and SHA-256, and rejects empty or excessively large input with an actionable message. Sources remain individually visible and removable until script creation starts.

PDF parsing, web extraction, OCR, retrieval, and citation systems should be separate later slices. They would obscure whether the core generation pipeline works.

### 4.2 Prepare the source

Normalize Unicode and line endings, remove clearly unusable control characters, and split large input into bounded chunks. Preserve the immutable normalized source so that later script revisions remain reproducible.

For source material that does not fit one model request, use a bounded two-stage strategy:

1. generate notes or an outline for each source chunk;
2. generate the final script from those bounded intermediate results.

The application should never send arbitrarily large input directly to the model.

### 4.3 Generate a chaptered script

The user supplies exactly one free-text initial-instructions value. Hint chips only insert text into that field; they do not create hidden configuration fields.

Gemma first emits an episode outline, then generates each complete chapter as one unit. The persisted script stays simple:

```json
{
  "schemaVersion": 1,
  "title": "Episode title",
  "chapters": [
    {
      "id": "chapter-1",
      "title": "Chapter title",
      "text": "The complete spoken chapter transcript..."
    }
  ]
}
```

Validate the schema, chapter IDs, nonempty titles and text, requested chapter order, malformed repetition, and absence of hidden reasoning or generation metadata. Persist only complete chapters and a complete valid script revision.

### 4.4 Apply the review toggle

The review toggle defines the branch after script generation:

- **Review on:** retain the script as an editable draft and show its chapters.
- **Review off:** automatically lock the generated revision and start audio generation.

Review is read-only. There is no direct transcript editor, chapter drag handle, or per-chapter regenerate action.

### 4.5 Edit through agent chat

While a script is still a draft, the user may request changes only through the editing agent. Each successful agent operation creates a new complete script revision and a structured summary of renamed, rewritten, split, combined, added, or removed chapters. Agent conversation messages and the resulting revision ID are persisted together.

The agent may mutate a draft but cannot lock it. Only the user-facing lock action can cross the irreversible boundary.

### 4.6 Lock the script

Locking is one database transaction that:

1. selects the final script revision;
2. records its immutable content hash and `lockedAt` time;
3. marks the episode as locked;
4. creates the audio-generation job for that revision.

After this transaction, repository APIs reject every chapter or transcript mutation. Audio generation always reads the frozen revision.

### 4.7 Render one chapter per TTS call

For each frozen chapter:

1. pass the complete chapter text to `renderChapter()`;
2. let Supertonic predict and generate its natural chapter waveform;
3. write to a temporary chapter file;
4. validate the WAV container, sample rate, channel count, sample count, finite values, silence, and clipping;
5. calculate size and SHA-256;
6. atomically commit the chapter audio artifact.

The generation screen reports the same chapter currently being rendered. There is no sentence-level render plan in the initial architecture.

### 4.8 Assemble chapters

The assembler streams complete chapter WAV files into the episode master and inserts a fixed chapter pause. It records each chapter's cumulative start and end frame.

The result consists of:

- mono PCM16 44.1 kHz master audio;
- optional AAC-LC M4A produced through `MediaCodec` and `MediaMuxer`;
- chapter start and end times;
- the frozen chapter transcript used by the transcript panel;
- final frame-count, duration, and structural validation.

The MVP transcript panel follows the current chapter. Fine-grained sentence alignment is deferred rather than adding a forced-alignment or timing-estimation subsystem. Export uses `ACTION_CREATE_DOCUMENT`; the app does not assume unrestricted shared-storage access.

## 5. Persistence and artifacts

Suggested Room entities:

- `Episode`;
- `EpisodeSource`;
- `EpisodeInstructions`;
- `GenerationJob`;
- `ScriptRevision`;
- `Chapter`;
- `AgentConversation` and `AgentMessage`;
- `ChapterAudio`;
- `PlaybackState`;
- `Artifact`;
- `InstalledModel`.

Room should contain paths, hashes, sizes, state, and provenance—not model bytes or audio blobs.

Suggested internal layout:

```text
files/
  models/
    gemma-4-e2b/
      <version>/
        manifest.json
        model.litertlm
    supertonic-3/
      <version>/
        manifest.json
        ...

  episodes/
    <episode-id>/
      sources/
        source-001.txt
        source-002.txt
      script/
        revision-001.json
        revision-002.json
      chapters/
        chapter-001.wav
        chapter-002.wav
      final/
        episode.wav
        episode.m4a
        chapter-timeline.json
      manifest.json
```

The episode manifest should pin:

- every source identity and hash;
- initial instructions and review-toggle value;
- frozen script revision and hash;
- chapter identities and transcript hashes;
- model, artifact, runtime, backend, and voice identities;
- chapter-audio hashes;
- final audio and chapter-timeline hashes.

Model packs should use resumable, hash-verified downloads. The multi-gigabyte LLM should not be bundled in the APK.

## 6. Episode lifecycle

The persisted lifecycle mirrors the confirmed UX:

```text
SOURCES
→ INSTRUCTIONS
→ GENERATING_SCRIPT
→ SCRIPT_DRAFT          when review is enabled
→ LOCKED
→ GENERATING_AUDIO
→ FROZEN_READY
```

Agent editing creates new revisions while the episode remains `SCRIPT_DRAFT`; it does not add another user-visible lifecycle stage. When review is disabled, `GENERATING_SCRIPT` proceeds directly to `LOCKED` and `GENERATING_AUDIO`.

`FAILED` is an operational outcome attached to the phase that failed. Pause, recovery, cancellation, and post-generation correction are not MVP lifecycle states.

The database is authoritative. Advance a phase only after its corresponding transaction or artifact commit completes.

## 7. Background execution

Recommended initial approach:

- the user starts generation while the application is visible;
- a foreground generation component runs in `:generation`;
- its notification shows the episode and current chapter progress;
- native models never load in the UI process;
- leaving the generation screen does not define pause, cancel, or recovery behavior in this architecture.

Operational rules:

- verify sufficient free storage before starting;
- do not begin when the battery is critically low;
- recommend charging for long episodes without making it mandatory;
- require no network after the source and models are available;
- allow only one model-heavy generation job at a time;
- unload the LLM before loading TTS.

The initial episode target should be bounded, for example 10–20 minutes, rather than supporting arbitrarily long jobs from the first release.

## 8. Frozen-episode integrity

The lock boundary is enforced below the UI:

- `ScriptRevision` rows become immutable when selected by a lock transaction;
- chapter mutation APIs require an unlocked draft;
- the audio job references one frozen revision ID and content hash;
- generated chapter audio and playback timing reference the same chapter IDs;
- temporary files are never exposed as completed artifacts;
- an episode becomes `FROZEN_READY` only after final audio and transcript timing are committed.

Post-generation editing and partial rerendering are intentionally unsupported. Pause and recovery behavior are also outside the current MVP; the architecture records failures without inventing additional lifecycle UX.

## 9. Thin implementation slices

### Slice 0: Runtime integration spike

- Minimal Android shell.
- Model-pack verification.
- One fixed Gemma request.
- One fixed Supertonic sentence through the external QNN contexts.
- Reusable engine adapters.
- No complete product workflow.

This proves that the existing native runtimes can be embedded behind the app's engine interfaces.

### Slice 1: TTS-first vertical path

- Paste source text.
- A fixed chaptered script.
- Persisted audio-generation job.
- One Supertonic QNN/HTP call per complete chapter.
- Chapter-aware WAV assembly.
- Chapter timeline and transcript panel.
- Playback and export.

This establishes the complete artifact and audio pipeline without depending on LLM quality.

### Slice 2: Script generation

- Gemma GPU adapter.
- Source preparation and episode outline.
- One full Gemma generation request per chapter.
- Schema and length validation.
- One free-text instructions field and hint insertion.
- Optional review toggle and automatic lock branch.
- Separate transcript-quality evaluation.

### Slice 3: Draft, lock, and playback lifecycle

- Agent-only script editing with revision history.
- Irreversible lock transaction.
- Isolated generation process and foreground notification.
- Chapter progress.
- Lyrics-like transcript following the current chapter.
- Playback-position persistence.
- M4A encoding and export.

### Slice 4: Product expansion

Only after the core pipeline is reliable:

- PDF and web ingestion;
- multiple voices;
- streaming previews;
- background music;
- broader device support.

## 10. Decisions required

| Decision | Recommended MVP default |
|---|---|
| Source model | One or more sources, followed by one free-text instructions field |
| Narration | Single narrator, M1/SID5 |
| Script review | Optional; enabled stops at review, disabled auto-locks |
| Script editing | Agent chat only while draft |
| Lock | Irreversibly freezes chapters and transcript before audio |
| Primary LLM | Gemma LiteRT GPU; no fallback route |
| TTS | Supertonic 3 external-context QNN/HTP; no fallback route |
| Playback | Chapter navigation plus toggleable synchronized transcript |
| Still open: source formats | Decide which file formats accompany pasted text |
| Still open: episode target | Recommended initial bound of 10–20 minutes |
| Still open: model delivery | Download policy and packaging |
| Still open: export | M4A/WAV product behavior |
| Still open: distribution | Play Store versus internal/sideload |
| Still open: code location | This repository versus a separate product repository |

## Recommended MVP decision

Proceed with a **one-complete-chapter-in, one-chapter-audio-out Supertonic QNN/HTP vertical slice**. Do not design chunking or stitching before that simple route is tested. Then add Gemma outline generation, one full generation request per chapter, the optional review branch, agent-only draft revisioning, and the irreversible lock transaction. Multiple voices, richer ingestion, fine-grained transcript alignment, and broader device support remain later work.
