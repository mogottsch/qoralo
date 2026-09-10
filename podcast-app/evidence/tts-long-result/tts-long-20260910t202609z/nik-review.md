# Nik — first actual long-TTS Android attempt

## Verdict

**Valid bounded collection; long synthesis FAILED on the first vector invocation. No WAV exists.** All four new external contexts loaded on the Galaxy S23 Ultra; duration and text executions are established by ORT Node plus typed positive QNN RPC/accelerator evidence. The vector Node event is a failed attempt, not success; the parity vocoder was never executed.

This is a real runtime failure, distinct from the earlier pre-run process/terminal-history stops. No retry, ADB, model call or device operation was performed by Nik. No long-speech, duration, RTF, fidelity or listening acceptance follows.

## Exact binding and collection

Run root: `podcast-app/.local/tts-long-phone/tts-long-20260910t202609z/`.

- Private archive:793,088 bytes; SHA256 `4490efa68acb8b9c447748e5c8fb39a2a4cef30711498822fa09ee9acfd8a921`.
- Frozen candidate: `b86008708cc459c855149eee49c58a7468e079d24c9de4842eab56a5bcef325d`.
- Observed app/test hashes match the approved e9cc95…a71be /fc19bf…22c9b pair; driver PID7928 and generation PID8003.
- New guard closure5ca6be91…f2c425 is explicitly bound by override `60dd58885efdc8406049365d92c26838fdedf4db99f568638479a1f71e1b046d`, retained in the associated20260910t202606z setup receipt. Caller a87b…815a4 and privacy dependency a62…bec3c remain unchanged.
- Long contract66f8…53a87 and runtime-verified pack116fda…84066 match approval. Native payload provenance follows the observed exact APK and the already reviewed native-nine identity; no new device-native-file hash claim is invented.

Actual raw input is the exact1327-byte narration; actual normalized input is1324 bytes/codepoints. Saved reconstructed tokens match the pinned indexer:1333 active positions,715 zero pads,2048 IDs/mask values and chapter seed `6650004215380126392`. This remains a source-bound reconstruction, not captured native tensor buffers. Actual duration/active-latent length/embedding/noise values were not retained and must not be backfilled from labels or the90s target.

Three stable guarded snapshots retained the same file hashes and known schema, two episodes, one FAILED job and no QUEUED/RUNNING work. One new-pack push, two installs and one instrumentation dispatch are recorded. The device verifier authenticated the new pack before native loading. No data clear or repair was performed to satisfy eligibility.

## Observed execution sequence

Each of the four per-component ORT files has one completed session initialization and QNN load-binary timing evidence. The saved load-stage begin→complete bracket is3585ms; the usual full-success load/render metrics file is absent, so this is a diagnostic stage bracket, not a substituted benchmark field.

| Component | ORT Node attempts | Successful execution evidence | RPC execute us | Accelerator cycles |
|---|---:|---|---:|---:|
| Duration |1|Established|535,779|836,379,701|
| Text |1|Established|5,148,862|5,974,079,122|
| Vector |1|FAILED; not established|Unavailable|Unavailable|
| Vocoder |0|Not reached|Unavailable|Unavailable|

Duration/text Node events name QNNExecutionProvider and have matching BACKEND/ROOT execute rows with finite positive US/CYCLES values. Their continuation into the following steps is consistent with the bound source's output/capacity checks; it does not create missing value captures.

Vector has a2,897,105us Node interval and declared input/output shapes, but its invocation returns an error. Its CSV contains load timings and an HVX-thread count4, **no RPC-execute or accelerator-execute/cycle row**. Neither the Node interval, allocated output shape nor HVX count proves a successful result. Vocoder has session/load records only. Counts are1/1/1-attempt/0, not successful1/1/5/1.

Driver terminal collection completes in13,863ms with nativeOutcome=tts_failed/render. No deadline limit was hit and no audio duration/RTF can be calculated. Optional-evidence/inventory/after-render records were not reached. Empty native stdout/stderr are retained; relevant runtime details came from saved profiles and logcat.

## Earliest reported error and pinned meanings

Raw global logcat SHA256: `966936004a6dbf01461c0a9d862f0ab91e5d5d5da4264e3da0fc9deb3efe1f2d` (private).

Line4052, PID8003/TID8030:

> `Non-zero status code returned while running QNN_10407250622357638584_1 ... QNN graph execute error. Error code: 6006`

Pinned `/home/moritz/opt/qairt/2.49.0.260730/include/QNN/QnnGraph.h`, SHA256 `82b74873514bfa937f3bf888529c457829791e8ba8600374b2ba160edf32c8dd`, lines61–62:

> `/// Failure to set profile`
> `QNN_GRAPH_ERROR_SET_PROFILE = QNN_MIN_ERROR_GRAPH + 6`

The same header's graphExecute return documentation repeats “set profile failed” at684. QnnCommon.h line83 sets graph base6000. That header SHA256 is `1edba00ea13e509a3a2a28c1864afe13675898175147056df13aa782e8ba8ecf`.

ORT's qnn_model.cc passes the profile handle to graphExecute, attempts backend profiling extraction, then reports the nonzero execute_status. The observed6006 therefore identifies QNN's profile-setting failure class, not an inferred input-memory, tensor-shape, unsupported-op or vocoder-VTCM diagnosis. It also does not prove that disabling profiling will make the model work or establish how much DSP computation occurred before the error.

## cDSP crash and teardown are separate observations

Immediately after the6006, lines4054–4080 report a **cDSP user-process crash**, TLBMISS RW, in `libQnnHtpV73Skel.so`; fault PC0x2048F600, BadVA0x40. The printed thread is `fr/7/8025`. The reported trace includes Graph destructor/apply_graph_patch symbols; large nearest-symbol offsets are not an exact internal-source attribution. This report does not equate a user-PD crash with a proven whole-DSP/subsystem reboot.

The crash report follows the vector error and names the cleanup-side host thread8025 rather than vector Node thread8030, so teardown/error-path involvement is plausible. The chronology does not prove a precise causal ordering inside the proprietary backend. Subsequent FastRPC0x8000040d/0x27 failures and line4425 `qnn_interface.contextFree() failed ... error handle:1003` must remain visible. In QnnCommon.h lines197–198,1003 is the common SYSTEM error class (“platform / OS services”), not memory allocation1002.

A narrow safe excerpt is retained at `qnn-dsp-crash-extract.json`, SHA256 `db93a1299b8270201f65437ebb6947a4b4077f2db1f2cae52327059e0e98e4bb`. It contains only the app/QNN/cDSP failure chain, labels itself a derived excerpt, and binds the private global log. `independent-audit.json` includes the header hashes and exact line passages.

## Cleanup, privacy and next scope

Host cleanup passed: actual app/generation/test PIDs absent, settings restored/read back, confirmed-owned transfer scratch removed, packages/new pack retained and no controller cleanup errors. **That does not mean native context-free succeeded or that cDSP state is independently known healthy.** No fresh DSP/phone probe was made by Nik.

Before/after labelled core-condition files bind their private originals by hash; DB/condition directories/files have private permissions. Private DB contents and full condition text were not inspected. Global logcat remains private; only the narrow technical excerpts are suitable for scoped retention. Existing stopped attempts and this runtime failure remain unchanged; pushes remain held.

The smallest justified next scope is a targeted source-level review of vector invocation/profile-handle setup and error/teardown paths, followed only if separately authorized by a controlled debug observability/profiling experiment using the same data/context/whole input. Add genuine QNN callback visibility before treating a profile-mode change as a fix; preserve any basic/off profiling evidence gap explicitly. No graph rewrite, RAM increase, new vocoder correction, input-chunk workaround or replay is justified from6006 alone. Ben's parallel source/ABI/lifetime review is complementary; no obvious declared-byte/shape mismatch is established by the saved metadata.
