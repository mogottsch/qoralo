# Nik — first short production attempt, initial UI stop

**Attempt consumed; no rerun of this tuple.** Exact candidate1f7a4503…61700 installed app8ffae458…3d851/test911897a3…369400. Driver PID16630 failed its15-second Compose wait for `New episode` before creating an episode, arming the control or invoking a model. This is not a Gemma/TTS/model-budget failure and not a production E2E pass.

Private archive142,336 bytes, SHA256 `10f7132d4e154877e8b7cba259bc4915d85e4e7b185883d1f21e846598326acc`, contains contract/identity/failure and private UI capture only. No ownership record, job evidence or WAV exists. Preservation reports existing two episodes, one source, one FAILED job and one artifact unchanged, with zero additions. Host PID/settings cleanup is clean; control is absent with no host deletion. No ADB, UI replay, model execution or original-data mutation by Nik.

## Concrete cause

The saved PNG shows the normal Library and a visibly rendered New episode FAB, not a lockscreen, permission overlay or startup crash. Window9435's accessibility tree includes Library/Settings but no New episode label. This is an actual missing action name in the current wide-layout path, not a request to extend timeout or bypass a hidden screen.

The exact cached Material3 Android1.3.1 AAR SHA256 is `752473d4ea271f822858c313ec0d857ab05249021906f3005b30f2b1fcd0dcc0`. Local javap inspection of its classes shows ExtendedFloatingActionButton's animated text lambda calling clearAndSetSemantics, whose receiver lambda is empty. LibraryScreen supplies a null contentDescription on the accompanying Icon and no outer accessible name. Therefore the visible label is cleared from semantics with no replacement. The existing narrow/large-text PrimaryAction path differs.

No network/runtime was needed for this diagnosis. Local bytecode evidence is fab-bytecode.txt (clearAndSetSemantics call at extracted line31, empty receiver at268–270). The private screenshot/tree are retained locally with restrictive permissions and must not be published as safe UI evidence.

## Smallest correction

Give the actual FAB Icon or outer action a stable accessible `New episode` name, preserving visuals and the existing onClick. Update the test's initial wait and click to the named clickable action, allowing contentDescription or normal text for both layouts. Do not use coordinate taps, unmerged hidden-label tricks or direct repository episode creation as if the accessibility issue were solved.

This is a tiny real app/test semantics change and requires new app/test candidate hashes; native/model/property data remains unchanged. Update the host's expected prior-installed tuple to the observed8ff/911 pair for the fresh attempt, not stale59e/6d97. Original failed attempt and APKs remain sealed. The following fresh flow requires its new exact delta review/release; no blind unchanged retry or broader baseline matrix is needed.
