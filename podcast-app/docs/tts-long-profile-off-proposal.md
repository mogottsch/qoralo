# One profile-OFF long diagnostic — source-only proposal

**Status:** Nik confirmed the mapping and Pi authorized the minimal source/build preparation. The debug source is prepared; no profile-OFF candidate has been run. An exact new candidate review and fresh Pi phone release are still required.

## Question, not a claimed fix

The profiled run `tts-long-20260910t202609z` loaded four contexts, executed duration/text, and failed its first vector invocation with6006. QAIRT2.49's pinned QnnGraph.h calls6006 `QNN_GRAPH_ERROR_SET_PROFILE` (“Failure to set profile”). Subsequent cDSP user-PD crash/context-free errors are distinct from clean OS/settings/PID/scratch handback. The code does not establish OOM, an input mismatch, or a proven profiling-off remedy.

Proposed question: **Does one otherwise identical whole request return a WAV when the existing coupled ORT/QNN profiling mode is disabled?** A success would support profiling-path involvement, not identify the exact proprietary backend fault or establish a general production fix. A failure remains an immutable first outcome, not grounds for an automatic retry.

## Existing switch and lifecycle

App source is bound by the exact failed candidate `b86008708cc459c855149eee49c58a7468e079d24c9de4842eab56a5bcef325d` and its reviewed source/native-nine proof.

1. `TtsOnlyService.kt` unconditionally calls `RuntimeDiagnostics.enableTtsOnly(evidence)` before verification/load. `RuntimeDiagnostics.kt` stores the TTS evidence object; `qnnProfileDirectory()` returns a fresh `qnn-profiles` directory while enabled, otherwise the already-supported empty string.
2. `NativeEngines.kt` passes that string directly to `SupertonicNative.create`. Main runtime source need not change.
3. `podcast_runtime.cpp`, `SessionOptions`94–118: a nonempty profile path enables **both** ORT `EnableProfiling` and QNN `profiling_level=detailed` plus CSV path. Empty path skips both. Intra/inter threads1, sequential execution, optimization, disabled CPU fallback, burst, SoC43, APK backend and ADSP path remain unchanged.
4. Each of the four session constructions receives its component profile path. No public intent/CLI/contract switch in the frozen b860 APK suppresses the unconditional hook. A new small debug APK is necessary; there is no honest command-line-only toggle of that APK.
5. Cached ORT1.27.1 source at commit `df2ba1cf8108aa63627cf4cdf8f807880b938616` maps the path as follows (these source files were unmodified when inspected):
   - `qnn_execution_provider.cc`382–413 defaults QNN profiling OFF, ETW INVALID; Windows-only ETW is not an Android override.
   - `qnn_backend_manager.h`538 initializes the profile handle to null. `InitializeProfiling`665–713 returns immediately for OFF/INVALID; otherwise `profileCreate`692 creates the detailed handle.
   - Context loading1501–1519 passes that handle to `contextCreateFromBinary`, then extracts load profiling.
   - `qnn_model.cc`530–567 obtains the handle, calls `graphExecute`535–541, restores power settings, extracts backend profiling, and finally reports nonzero execute status. The observed6006 is not by itself a CSV-write error.
   - `ExtractBackendProfilingInfo`1855 onward immediately returns when OFF; otherwise reads events and emits CSV/binary profiler records.
   - `ReleaseResources`1818–1852 releases contexts before the profile handle, then device/backend/logger/library. `ReleaseProfilehandle`719–727 calls profileFree only for a nonnull handle. Context freeing2251 uses `contextFree(raw_context_handle, nullptr)` and logs errors rather than making the host cleanup JSON fail.
6. App `~Engine` ends ORT profiling only with a nonempty profile directory, before normal member/session destruction. Empty mode therefore also skips these EndProfiling calls. Session/context destruction still happens; off mode does not bypass normal cleanup.
7. On render failure the existing service writes its terminal error **before** the finally-close path. The diagnostic must retain that ordering and its native-cleanup limitation; changing failure publication/cleanup coordination would be a second behavioral intervention and is not proposed here.

This source mapping is not a capture of native profile-handle pointer values or proprietary backend execution. The same binaries remain independently hash-bound; no ORT, SDK or graph rebuild is proposed.

## Smallest controlled implementation

Use one pinned debug contract choice, for example `collectProfiles:false`, with defaulttrue for existing contracts. Gate only the existing `RuntimeDiagnostics.enableTtsOnly(evidence)` call before `tts.load`; leave RuntimeDiagnostics disabled for the new variant. All other `WiringEvidence` writes/snapshots and `NativeStdioCapture` are independent of this hook and remain enabled.

Prepared contract: `app/src/debug/assets/tts-long-profile-off/contract.json`, SHA `8d6b93557a2ac9d191b731735015bad6ce9d95c9b605861dc3c930cf9c82cd35`. The narration is byte-identical to the retained original. The separate caller `tools/run_tts_profile_off_gate.py`, SHA `2a43becadc897a47c6c50424479e68fa996a05c0f70787be802ff6b2bf8b742d`, is AST-equivalent to the original a87 caller apart from variant pins/labels and explicit unavailable telemetry fields. `prepare_tts_profile_off_gate.py` asserts exactly six app/src paths differ from b860's effective tree and reuses native9. Seven focused JVM methods (four canonical contract regressions +three profile-OFF mode/hook tests) are selected; no repeated full data-pack verifier method or broad suite. Four new host scope tests pass.

Give this mode its own immutable contract/candidate and fresh run/output. Retain the original profiled contract/assets/APKs/controller/evidence. Minimal selector plumbing may add a profile-off long contract asset and hash; this is not a new runtime abstraction. Do not change chapter ID to label the variant: it participates in the RNG seed. Use the run ID/contract for the label instead.

The variant must preserve:

- Exact1327-byte narration SHA `f25655b54ad4e8d5e782dedf069867d6c201f1ea48327724527356d0f35aea37`,1324 normalized codepoints, and chapter ID `long-library-01`/reconstructed seed `6650004215380126392`.
- Same single T2048/L2048/144 pack manifest `116fda95a907f6dc35bfe7c2144fe2818ed438cc109c1faa3f95cafc2fc84066`, all13 data files, native9, ORT1.27.1/QAIRT2.49, M1/SID5,5steps,speed1 and fresh request arrays.
- Same four constructors and one whole logical request; no vector-only/profile-level/basic/verbosity/native changes, no Gemma, chunks, stretching or retry.
- Verify60/load120/render180/close30, service420/driver435/host instrumentation450; separate staging push180/copy120/install180/pull120 bounds. Existing exact device/durable-state5ca guard, privacy, ordinary app/test closure, lock/FD and raw-first handling.
- Existing old/new pack roots: no new model pack, reexport, data rewrite or replacement of partial staging. Reuse the already staged exact pack after normal authentication.

A new debug app/test pair and contract/controller identity are expected; **native payloads are reused byte-for-byte without CMake**. New candidate can bind guard5ca directly rather than rewriting the profiled candidate's old guard reference. Tests should focus only on mode selection/defaults, unchanged text/seed/bounds, canonical separation and proof-unavailability labels. No broad UI/JVM matrix or redundant model/load gate.

## Evidence intentionally unavailable

The existing native switch couples two profilers. Keeping ORT Node events while disabling only QNN detailed profiling would require a native change, and is not this experiment.

Unavailable by design:

- ORT per-graph Session/Node profiling records, Node counts and kernel durations;
- QNN load/execute CSV/binary profiler data, RPC timings, accelerator cycles, HVX/op breakdown.

Preserve explicit `disabled_by_protocol` metadata. Do not fabricate zero measured Runs, borrow counters from the failed run, or call source-expected1/1/5/1 directly observed execution. APK/provider configuration and mapped libraries are not substitutes for physical RPC/cycle proof.

Retain actual raw/normalized text and labelled source/indexer reconstruction; whole WAV/hash/format/duration if returned; separate host load/render clocks; available proc/memory snapshots with their real method; raw errors, private global logcat and condition/DB originals; labelled public extracts, exact APK/pack/native/protocol identities and host cleanup. Deeper QNN callback verbosity is not exposed by this existing switch and must not be quietly added as another variable.

If a valid WAV exists, retain it before optional metrics and hand its stable exact identity to Kate immediately. Listening begins `not_reviewed`; Moritz decides only that hash. The result can establish bounded whole-request operability/listening, **not the earlier direct per-graph HTP/RPC/cycle evidence standard**. Native teardown/DSP health remain separate from host cleanup. No page/tab for failure; one status-board line instead. Pushes remain held.
