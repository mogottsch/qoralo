# Nik — saved profile-OFF whole-input result

## Verdict

**PASS for bounded whole-input-to-valid-WAV operability. The approximately90-second target was NOT met; spoken coverage and listening quality remain unreviewed.** This run submitted the complete227-word input and returned a structurally valid29.7969-second WAV. It does not establish that all227 words were spoken, that content was truncated, or that the intended full-length chapter works correctly.

Profiling was deliberately disabled. No direct per-component ORT/QNN/RPC/cycle execution claim, measured1/1/5/1 counts, warm median, fidelity or product E2E approval is made. No playback, model call, ADB or phone action was performed by Nik. No audible autoplay.

## Exact identities

Run: `tts-long-profile-off-20260910t205719z`.

- Local root: `podcast-app/.local/tts-profile-off-phone/tts-long-profile-off-20260910t205719z/`.
- Archive:3,850,752 bytes, SHA256 `fa47b20dc893678aaa4e9bc434766f72fcc33d1c4f9e7243f8e0fade896709a3`.
- Candidate: `efdb831a8f987d4a32ef21d121f065ea26f40c9dfdd8f7f6f946b6ec3b484c7b`.
- Observed app: `59e33847e9ff94f1ea8fdbd07d7881543bb90a80031a585cb6178be2c5e1842e`; observed test: `6d97d38d7c3acb3d65234f289fe53114e4aaa98fc32afd6356bb96eddc8aa49b`.
- Driver PID23451; generation PID23519/UID10755.
- Contract8d6b…cd35, caller2a43…742d, direct guard5ca6…c425, privacy a62…bec3c and pack116fda…84066 agree with the exact approved candidate.

Actual request1327 bytes and normalized text1324 codepoints match the approved narration. Reconstructed IDs/mask match the pinned indexer,1333 active plus715 padded positions and unchanged seed6650004215380126392. These remain reconstructed inputs, not native buffer captures. No text, chapter ID, voice, step/speed or pack/native byte change is inferred from the profiler switch.

## WAV and measured timing

Exact file: `long-library-01.wav`, SHA256 **`bb61a552d5a631d05aee7aaa79695946f8a53aa01ebd4d82a9060bab95714d98`**. Archive and extracted local copies are identical.

| Field | Independently checked value |
|---|---:|
| File bytes |2,628,128|
| Frames |1,314,042|
| Format |44,100Hz,mono,PCM16|
| Actual audio seconds |29.79687074829932|
| Four-context adapter load |3832.259686ms|
| Whole render wall time |23697.614053ms|
| First-request RTF |0.7953054618781592|
| Driver elapsed |35,544ms|
| PCM normalized RMS |0.05245404578941115|
| Peak absolute integer sample |16,264|
| Full-scale samples |0|

The RIFF/data length matches exactly44+2×frames; output is non-silent PCM with no full-scale samples. These checks do not establish intelligibility, completeness or voice quality. Render timing includes normalization/native work/WAV validation-publication and excludes verification/load/close; it is not neural-only throughput or a warm median.

The29.8s output is not an observed render timeout or30s close guard: render completed in23.7s and close also returned. Bound source uses predicted duration to determine emitted frames; no capacity truncation/stretch/splitting was introduced. Actual predicted scalar/latent mask values were not captured, so inferred quantities must stay labelled source arithmetic, not observed tensors. The90s prose target is merely an estimate and was materially missed.

## Intentional proof loss

profiling-policy.json records collectProfiles=false, ORT/QNN profiling disabled and observedPerComponentRuns=null. No qnn-profiles directory or QNN CSV/ORT trace appears in the archive. The successful source route's expected call counts are not measured counters. Runtime-reported QNN_HTP/readiness and native-library maps are declarations/configuration corroboration, not replacements for missing per-component execution evidence.

Service status is tts_complete/finished, driver nativeOutcome matches, and all verify/load/render/close stages complete. Optional warnings are empty. Twenty-seven inventory entries were independently size/hash verified. Missing profiler data is explicitly unavailable-by-design and does not erase the valid WAV.

## Guard, cleanup and native observations

Three stable pre-launch checkpoints have identical private DB file hashes, two existing episodes/one FAILED history row, no queued/running jobs, and the reviewed known-terminal eligibility policy. Two installs and one instrumentation invocation occurred. The existing correct new pack was reused: no push/copy, overwrite or transfer scratch was needed. The generation-process verifier authenticated it before loading.

Host cleanup has no errors/settings errors; actual app/generation/test PIDs are proven absent and before/after settings match. Process VmHWM after load/render/close is418,016 kernel-reported kB: whole-process lifetime resident high-water, not PSS, model-only memory or DSP/VTCM memory.

The collected app-relevant log has no previous6006 graph-execute/contextFree1003 failure pattern or cDSP crash report. The close stage returns and after-close snapshots exist. FastRPC setup and shutdown messages still occur, including worker-exit notifications; no universal native teardown or global DSP-health guarantee is inferred merely from host cleanup or absent error patterns.

Full DB/condition/global-log originals remain private; labelled conditions bind the originals by SHA and private filesystem permissions are retained. No private DB contents or full condition text were inspected by Nik. Old failed attempts and the profiled crash remain intact. Push/publication hold remains.

## What this permits us to say next

This is a real usable WAV artifact and a completed whole-input diagnostic call. It is not yet a demonstrated90-second/full-spoken-chapter result. The changed outcome supports investigating observability-path involvement, not a single proven proprietary-backend cause or a general profiling-off fix.

Only Moritz can accept/reject listening quality for this exact hash. Any separate coverage/numerical diagnostic requires its own scope. Production UI/dispatcher/Room/lock/two-chapter assembly/Player/SAF workflow remains a distinct exact-candidate and evidence gate; no diagnostic result should be relabelled as product E2E.
