# Progressive audio, persistent player and transcript timing

## User contract

As soon as a complete valid speech chunk exists, generation exposes **Listen**. Opening the player is paused; only explicit Play starts audio. The player shows actual available audio, playing/paused/buffering and generation status separately from the not-yet-known total duration. A live-tail underrun waits at the absolute frontier and resumes on newly published audio only while playback intent remains active. Explicit Pause, sleep expiry, audio-focus loss, noisy-route events, closure or stale-attempt detection clear that intent.

Seeking and chapter skips are limited to already available audio. Reaching a live tail is not a request to restart at0. Generation completion neither replaces the live playlist nor resets/recreates its player; canonical master playback/export remain available for later completed sessions. Failed/cancelled generation exposes only its valid partial prefix, never false Ready or partial export.

Jens's persistent top mini-player shares **one EpisodePlayerSession** through PlaybackHost above navigation. Minimizing, browsing Library/Settings/sources and reopening do not create another ExoPlayer. Episode switching explicitly closes the previous player before creating a replacement. Active playback observers/ticks belong to the active binding, not the currently browsed episode. No background-service or process-death autoplay claim is made; persisted positions restore paused.

## Immutable publication and absolute timeline

The generation worker publishes a separate closed PCM16/44.1kHz WAV for each available item. It never exposes a growing WAV header. Each item includes its exact leading gap:0 for the first speech,13,230 zero frames between provider segments,30,870 zero frames before a new chapter. Those bytes produce the same logical timeline as the final master, with no additional app-created gap or repetition.

Under `episode/audio-stream/attempt/`, an immutable binding names episode, attempt, locked revision/hash, pack and frontend version. Immutable, sequential hash-linked entry files reference validated media hashes/extents, cumulative frame positions and passage metadata. An entry appears only after its PCM file is atomically published. Readers accept a contiguous verified prefix and never combine attempts. Published stream files are retained independently of disposable synthesis scratch files.

Finalization writes an immutable completion marker whose frame count/last entry/master hash agree with the canonical completed episode. Playback stays on the existing playlist until the active session closes; a later ordinary open can use the master. Absolute positions derive from cumulative PCM frames, not a sum of rounded per-item milliseconds.

Per-attempt playback state is stored separately with the binding hash, absolute position, speed and transcript preference. It never imports another attempt's position or restores autoplay intent. Once the matching attempt is fully Ready, canonical playback persistence can use the same absolute position. Old completed files and legacy database rows remain compatible; no database schema migration is required.

## Transcript precision

Provider-segment entries have authenticated frontend version, explicit passage kind and exact source UTF-16 spans in the immutable chapter. Whole-chapter/legacy items are labelled as such; a segment index is not blindly assumed to identify a provider sentence group. Highlighting uses `speechStartFrame <= position < endFrame`; added silence has no passage highlight. No word-level timing is invented.

For final masters, the repository reads timing off-main only when stream ledgers or hash-bound provider publication-recovery receipts validate against the current revision/plan/WAV. The existing recovered2194sample can use its immutable receipt chain. Otherwise the UI falls back explicitly to chapter-only timing. Manual transcript scrolling disables automatic following until the user chooses Follow playback. Metadata verification failure does not fabricate alignment.

## Validation boundaries

Synthetic tests cover immutable publication, malformed/growing sources, exact gap bytes, delayed availability, stale/tampered attempts, absolute seeks, tail wait/resume, explicit pause/sleep/focus/noisy intent, finalization and paused state restoration. Android synthetic tests use real ExoPlayer with muted/silent PCM, plus Jens's minimized/navigation/reopen and manual-follow regressions. Default and narrow/font2 profiles precede any genuine model run; user settings are restored exactly.

One newly owned normal AUDIO job will then use a labelled copy of the real487-word chapter. It must prove explicit muted Play and actual advancement while generation is still running; actual live-tail wait/resume and pause-during-buffering; one session across minimize/Settings/reopen/speed/transcript/manual-follow; and unchanged session/position through Ready. The same generated audio is reused for all UI checks. No new SCRIPT/EDIT inference or duplicate TTS run is needed for Jens.

Private telemetry distinguishes first complete media/Listen availability from first observed player advancement (scripted/muted TTFA), not microphone-confirmed speaker output. User audio/calls must be quiescent before any test. Full phone.lock, fresh identity/job/data/resource checks and independent cleanup protect existing podcasts, histories and the2194synthesis/recovery evidence. No memory-lock admission, autoplay, unrelated process termination, data clearing or publication of raw user text/recordings.

Physical outcomes and exact deployed identities will be retained separately; source/build tests are not an E2E or deployment verdict.
