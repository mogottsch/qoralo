# Nik — source-only profile-OFF diagnostic mapping

**Mapping confirmed; Pi's conditional SOURCE/BUILD preparation gate is satisfied.** Janek owns the minimal new debug variant. A fresh exact-candidate review and separate Pi phone release are still required. No native/model graph/version change, runtime call or device action was performed or authorized by this mapping review.

## Existing switch and smallest honest change

The exact failed b860/e9cc candidate's TtsOnlyService unconditionally calls RuntimeDiagnostics.enableTtsOnly before loading the engine. RuntimeDiagnostics.qnnProfileDirectory returns a nonempty per-run directory when enabled, otherwise the existing empty string. NativeEngines.load passes that string directly to SupertonicNative.create.

Unchanged CPP SessionOptions lines94–118 enable BOTH ORT tracing and QNN `profiling_level=detailed`/profiling_file_path only when the directory/prefix is nonempty. Engine passes the same enabled/disabled mode to all four contexts. Its destructor only explicitly EndProfiles them when profile_dir is nonempty. There is no public intent/CLI profile-OFF switch in frozen b860.

The minimal honest variant therefore adds one freshly pinned debug-contract boolean, collectProfiles=false, and gates only enableTtsOnly before tts.load. Older canonical behavior defaults true. Preserve independent stdio/text/reconstruction/process/stage/WAV/OS-cleanup capture. Do not change the existing primary-error-versus-finally-close ordering as a second fix. Do not secretly reinterpret the old contract hash or rewrite its frozen evidence.

Keep the exact227-word/raw1327B narration, normalized1324 codepoints, chapter IDlong-library-01/seed6650004215380126392, pack116fda…84066, all13 data bytes, native-nine payloads, M1/SID5/five steps/speed1, backend/shape/thread/fallback settings and deadlines. Fresh contract/candidate/run identity is necessary provenance, not a different speech workload. Vector-only profiling control would require additional native changes and is outside this minimal scope.

## ORT/QNN profile lifecycle

Inspected ORT source checkout HEAD `df2ba1cf8108aa63627cf4cdf8f807880b938616`; relevant target files are clean. This is source interpretation aligned to the retained runtime pins, not a newly instrumented binary trace.

- qnn_execution_provider.cc:383–405 defaults profiling to OFF and ETW to INVALID; ETW override is Windows-only. With no profiling provider keys on this Android route, OFF remains selected.
- qnn_backend_manager.h:profile_backend_handle_ initializes nullptr. InitializeProfiling at665–715 returns before profileCreate for OFF/INVALID; DETAILED otherwise creates a detailed profile. profileSetConfig is only in the OPTRACE branch here, so6006 does not establish a failing application-side profileSetConfig call.
- qnn_model.cc:530–565 passes the stored handle to graphExecute, resets per-thread power state, attempts profiling extraction, and only then tests execute_status. Consequently the Node interval includes wrapper/post-call work and the final error-log timestamp is not a direct SDK-return timestamp.
- ExtractBackendProfilingInfo immediately returns for OFF. Profile release checks the handle for null. ReleaseResources releases contexts before profileFree, then device/backend/log resources.
- Context-free already receives a null per-call profile argument; disabling collection does not repair or otherwise change that context-free argument.
- QnnGraph.h:605–609 explicitly permits a NULL graphExecute profile handle to disable collection. A reused nonnull handle normally resets its collected values.

With the existing empty-string branch, no ORT tracing is enabled, QNN creates no profile handle, graphExecute receives nullptr and collection/explicit EndProfiling are skipped. This confirms a viable existing control path without claiming it will prevent6006 or the observed cDSP cleanup-side exception.

## Evidence lost and retained

Unavailable by design: ORT Session/Node trace files and per-component attempt/count/timings; QNN load/execute RPC, accelerator cycles/time, HVX and operator-profile records. Planned constructor/run counts must not be promoted to observations. A successful WAV in this mode would not supply the direct per-component HTP proof absent from this run, and old duration/text proof must not be transferred to vector/vocoder.

Retain exact input/hash and explicitly reconstructed—not captured—IDs/masks/seed, authenticated pack/APK identities, wall/stage setup/render timing, actual WAV format/frame/duration/hash if emitted, process memory snapshots, raw errors, private global logcat, whitelisted conditions and host cleanup. Report every deliberately missing profile field as unavailable-by-design, not zero or a generic unexplained gap. Only Moritz accepts an exact new WAV.

Success would support investigation of observability-path involvement, not isolate the proprietary backend cause or demonstrate numerical fidelity. The failed profiled attempt,6006, later1003 and cDSP TLBMISS/teardown observations remain separate from clean host PID/settings/scratch cleanup. No RAM, graph, tensor-capacity or vocoder-tiling change is justified by this proposal.
