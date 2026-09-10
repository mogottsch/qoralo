# First long-vector failure: profiling source map and a minimal diagnostic proposal

**Source/saved evidence only. No constructor, model/SDK call, phone action, graph change, app edit or new candidate build by Ben.** Janek owns any later separately scoped debug variant/build; Pi owns a fresh phone release. This is a proposed controlled configuration contrast, **not a claimed profiling-off fix**.

## Observed failure and the limits of attribution

Janek's first physical long request `tts-long-20260910t202609z` loaded all four contexts. Duration/text have actual successful QNN Node/RPC/cycle evidence. The **first vector invocation failed** with graphExecute6006; its ORT Node duration is2.897105s and its QNN CSV has load rows/HVX-count4 but no successful RPC-execute/cycle rows. Vocoder has load-only evidence and no Node Run; no WAV exists. These are not successful1/1/5/1 counts.

Nik maps6006 to `QNN_GRAPH_ERROR_SET_PROFILE` (“Failure to set profile”), not generic OOM or invalid tensors. The reported cDSP user-PD TLBMISS RW/BadVA0x40 in V73skel follows the error report; the reported crash thread matches cleanup-side app thread8025 rather than Node thread8030. Stripped nearest-symbol labels include Graph destruction/`apply_graph_patch`; large offsets do not establish an exact internal faulting function. Later contextFree1003/FastRPC errors are retained separately. Host PID/settings/scratch handback was verified; healthy/clean native teardown was not.

No raw private global logcat or private conditions/database contents are copied here. The safe saved error/profile files and source bindings are listed in `source-evidence.json`; Janek retains the private original, Nik the independent sequence audit. The earlier **vocoder compiler VTCM** failure is not the diagnosis of this **vector runtime** failure.

## Exact profiling path for this candidate

1. Debug `TtsOnlyService` unconditionally calls `RuntimeDiagnostics.enableTtsOnly(evidence)` before loading. That object's `qnnProfileDirectory()` returns a new `qnn-profiles` directory when capture is active, otherwise an empty string. No existing intent/contract option in the failed candidate selectively disables it.
2. `SupertonicQnnHtpEngine.load()` passes that directory to unchanged native `Engine`. All four sessions are created once; native `SessionOptions` enables both **ORT profiling** and **QNN `profiling_level=detailed`/CSV path** when the directory is nonempty. With an empty directory the existing branch does neither. Normal evidence writers, request/normalization capture, stage deadlines and WAV validation are outside this toggle.
3. Pinned ORT defaults QNN profiling OFF. Current app options do not enable context generation/sharing or VTCM backup-buffer sharing; under these options a separate backend manager is constructed for each session. Each manager's profile handle starts null. `InitializeProfiling()` calls `profileCreate(...DETAILED...)`; a failed create would reject session initialization. The **detailed** path does not call `profileSetConfig`: that additional call is for OPTRACE, not this candidate.
4. Binary load uses the stored profile handle and extracts load metrics. Later `QnnModel::ExecuteGraph` binds inputs/outputs, takes its graph-execution mutex, gets that handle, sets per-thread power settings, and passes it to synchronous `graphExecute`.
5. **After `graphExecute` returns, ORT restores per-thread power settings and extracts backend profiling information before checking the saved execute status.** The visible6006 is that saved graphExecute status, not proof of a frontend `profileSetConfig` error. Node2.897s includes the wrapper/post-call work; it is not accelerator timing. Error-log ordering does not reveal the precise SDK-return/crash timeline.
6. Native `Engine` destruction first ends ORT profiling for all sessions when its stored directory is nonempty. Backend resource release clears contexts before `profileFree`; the context deleter already calls `contextFree(handle, nullptr)`. The later contextFree failure is not evidence that this cleanup call supplied a nonnull profiling argument. Public ORT/QNN headers inspected here do not provide the SDK's internal `apply_graph_patch` implementation.

The QNN API explicitly allows a null per-call handle to disable collection and says reusing a handle resets it for the current call. That alone does not establish a misuse here. The generic MAX_EVENTS documentation says events stop being stored at the limit; no observed event-limit failure/default capacity or mapping from such a limit to6006 is established. Do not turn these interfaces into an OOM or event-capacity diagnosis.

## Complementary vector ABI/input-lifetime check

The C++/main-engine source bytes match the failed candidate's retained source-proof blobs and unchanged native9 provenance. The failed Node declares seven FLOAT inputs totaling **3,344,392B**, exactly matching two masks16,384B +latent1,179,648B +embedding2,097,152B +style51,200B +two scalars8B. Its declared output is1,179,648B. This is logical metadata, not measured target memory or proof of produced output. Internal Node input order need not equal public feed order; C++ feeds by names. No declared shape/byte-count mismatch was found.

Input backing vectors remain in scope through synchronous `Session.Run`; `latent` is replaced only after `RunFloat` returns and copies/checks its output. No obvious source-level dangling input was found for the first call. Reaching vector implies duration/active-capacity and finite/text-size gates were passed under normal execution of the bound source. **Actual duration, activeL, embedding and noise arrays were not captured**; their values/hashes remain unknown. Do not regenerate purported actual vector inputs from text/seed alone or label every input finite from a shape trace.

## Smallest proposed diagnostic: existing empty-directory path, all four off

Use a **new exact pinned debug-only contract/candidate**, preserving the old failed candidate and run:

```text
profile mode = off_all_four
before tts.load: leave RuntimeDiagnostics disabled (existing disable() hook)
qnnProfileDirectory() -> ""
native9 unchanged -> no ORT EnableProfiling and no QNN detailed/file option
ORT OFF default -> no profileCreate, graphExecute(..., profileHandle=nullptr, ...)
```

A narrow service condition can select `RuntimeDiagnostics.disable()` for that one new pinned contract and retain `enableTtsOnly(evidence)` for the existing contracts. This is a source proposal, not an applied patch. No arbitrary unpinned intent/property switch. The current e9cc APK cannot acquire this behavior through a documented existing launch flag; a reviewed debug-only APK overlay is required, but all nine native libraries remain byte-identical.

**All four sessions change profiling together** under the existing native interface. Vector-only profiling disable would require a further native/control change and is not proposed. Disabling diagnostics after load is too late: native session options and `Engine.profile_dir` have already been captured.

Everything else remains fixed:

- Same exact1327B narration SHA `f25655b54ad4e8d5e782dedf069867d6c201f1ea48327724527356d0f35aea37`, normalized SHA `7add3140f7c8d871d0291e30ac1ca79546ad5fec9792ef78428e7eda9484c8b9`, chapter ID `long-library-01`.
- Same schema2 pack SHA `116fda95…84066`, all eight contexts and five companions, T2048/L2048/144, positional/parity provenance, runtime/native9, M1/SID5/five steps/speed1 and StableSeed/xorshift64*/Box–Muller.
- Same CPU-fallback-disabled route, burst/SoC43/offload0, threads and original complete-request behavior. No model/shape/SDK change, chunking, stitching, duration forcing or fallback.
- Same verify60/load120/render180/close30; service420/driver435/host450, one request, no retry. Fresh candidate/contract/output/run identity and explicit later phone slot; no staging repair, reboot or health probe is implied.
- Keep raw exception/WAV/OS-cleanup/native-teardown classifications separate. No profile-absence failure gate for a deliberately disabled mode.

This is one **diagnostic configuration** variable, with two observability mechanisms coupled by the existing native switch. It does not isolate QNN profiling from ORT tracing. Also, identical text/seed/config does not prove identical vector input bytes: the prior duration/text outputs and activeL were not saved. A successful future contrast would show operability under that condition, not sole causality or numeric fidelity.

## Evidence deliberately unavailable with profiling off

Mark these **unavailable by design**, not zero or successful: ORT per-session Node/model-run counts/timings, QNN RPC/accelerator/cycle/HVX/per-op profile rows and finalized profile logs. Expected internal call counts remain source expectations, not observed successful counts. Registered QNN plus disabled CPU fallback is configuration evidence, not independent physical accelerator proof.

Retain the unchanged higher-level stage events, setup/render wall times, input/pack/native identity, source-derived call sequence, process snapshots/error logs and any atomically completed finite-PCM WAV with actual duration/hash. A valid WAV and first-request RTF can be reported if a separately released run succeeds; warm median, canonical benchmark, product E2E and listening acceptance cannot. Moritz alone accepts an exact WAV.

## Review gate

Nik reviews this source/lifecycle/observability proposal. Janek alone implements/builds a new bounded debug variant **if separately scoped by Pi**. Exact new contract/candidate/guard and the deliberate evidence-loss policy need review before a fresh Pi phone release. No profiling-off run or any implementation is authorized by this document.
