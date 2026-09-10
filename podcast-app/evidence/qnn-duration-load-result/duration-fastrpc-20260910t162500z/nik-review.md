# Nik saved-evidence review — successful manifest-only duration load/close

**APPROVED as evidence that the one duration external-context session was created and closed successfully with the public FastRPC declaration. This is not neural execution, TTS readiness, four-context readiness, or product-E2E evidence.**

Original collection: `podcast-app/.local/duration-phone/duration-fastrpc-20260910t162500z/`.
Archive SHA-256: `0a12c1fb1ad987d8bc8e5facdf7ef51c6aabc62e6e7afeb5a16d7b124e5bac1d`.
Native stderr SHA-256: `e4a6b03bbc6b13117da707516618ad5762b63c69effa59143f80c025f7ccd412`.

## Exact boundary verified

- Manifest-only candidate: `ac4d325f7f5b66ca5ff144590b991775d616c18bfb9ac56065f3c66c6af89fb2`.
- Observed installed app: `78488901d63032b87d2d575c6bec5b7f578b3a7ee38c92e3c633ed943dcb96ab`.
- Unchanged test APK: `120420d6925283ccf44478b58aef29a12e4575bbf6f1027df9a3d98e83cf2c8c`.
- Host guard: `3ad4c644a7733d1f1feeb7bbbe83532cc0be0f727f32f59dda00c951dd6e202d`, recorded non-inheritable lock FD.
- Namespace exception: committed2935059 JSON SHA `c9e43b07ff7b6b4a0d983ddbce51f8749775cf7f23bc352b9e3f010989b65c84` binds this candidate/app/test to the sole optional libcdsprpc.so declaration.
- Embedded contract SHA `51edc271c52b43e14f901169315136f29298c29f7e8954eb6b99d6fe21954f02` is the retained baseline record; its old namespacePolicy is overridden only by that explicit exception.
- Driver PID21389; actual :generation PID21510, UID10755.
- Verified Supertonic manifest `dc4ac737924d7d62e57ff5e166707198095c49e51d77cfed04a44d9e9435952d`, unchanged T239/L238/144/five-step contract.
- All nine recorded on-device packaged-library hashes/sizes match the reviewed manifest-only APK. All18 inventory entries match actual archived bytes.

The previous watched-PID pre-install stop and Pi's separate package-only maintenance are distinct events. Neither is relabelled as this successful constructor attempt.

## Actual loader/backend/context success

Original logcat:

- **4798:** clns-9 now lists `uses_libraries=libOpenCL.so:libcdsprpc.so`.
- **4952:** FastRPC reports `libcdsprpc.so loaded`.
- After-duration process maps contain both `/vendor/lib64/libcdsprpc.so` and the packaged `libQnnHtpV73Stub.so`, unlike the earlier dependency-resolution failure.

Archived native-stderr line references:

- **59:** queried backend build remains `v2.49.0.260730134355`.
- **150–152:** packaged V73 stub opens; first QNN stub connection established.
- **168–170:** RPC memory initialization succeeds.
- **248/252:** QnnDevice_create status0x0 and CreateDevice succeed.
- **260:** QNN SetupBackend succeeds.
- **723/747/783:** context deserialized, QnnContext_createFromBinary succeeds and cached QNN context load completes.
- **827:** the single EPContext wrapper node is assigned to QNNExecutionProvider. This is placement, not a kernel execution event.
- **834–835:** session successfully initialized; constructor RETURNED with3 inputs/1 output and explicit no-Run statement.
- **968–970:** existing contexts/graphs return to0 and context free succeeds.
- **1032–1036:** transport teardown status0, RPC memory deinitialized, device free status0x0.

Native return is `duration_session_created_and_closed_without_run`; service status is `duration_session_created_no_run`, error=null. This run does not contain the prior stub-not-found/INVALID_CONFIG rejection. The controlled manifest change is supported as removing that observed namespace dependency barrier for this duration-load path; no ADSP/LD/SoC/runtime/context/native-byte change was needed.

## Execution limitations

Exactly one constructor BEGIN and one RETURNED record; one instrumentation invocation; no automatic retry. Source path and retained records show zero Session::Run, Gemma, other-context, TTS/WAV or capacity calls.

- ORT profile: two Session events only (`model_loading_uri`, `session_initialization`), no Node execution events.
- QNN CSV: four load-binary rows—RPC load, QNN accelerator load, accelerator load, and overall QNN load. None is an execute/cycle inference record.
- The additional QNN binary profiling log is preserved as binary; it is not misclassified as malformed text or used to invent execution counts.

RPC/DSP initialization and context deserialization did occur; zero neural graph execution does not mean zero hardware/control activity. Driver elapsed2165ms and begin→native-return293ms include this diagnostic lifecycle/logging and are not TTS latency/RTF or benchmark campaign results.

## Guard/privacy/cleanup audit

All three guard checkpoints have matching within-run DB/WAL/SHM hash summaries, matching paired snapshots and an eligible zero-episode/zero-generation-history summary. The copied candidate matches the frozen candidate, and all installs/dispatch occur after the required checks. I did not open private DB contents.

Six raw DB snapshots remain local under700/600 permissions and are excluded from the diagnostic archive. Settings-before/after maps are identical. Cleanup errors/settingsErrors are empty; exact internal app/generation/test pidof checks return1 with empty stdout/stderr after scoped force-stop. Logcat6278/6364 records generation PID21510 killed/exited. No scratch root was created; controller reports lock release.

No ADB, phone lock, install, rerun, code change or model work was performed by Nik for this saved review.

## Next boundary

The accepted result supports moving to a separately reviewed TTS-only candidate that loads the other unchanged contexts and attempts one full canonical text render, with explicit bounds/evidence and no Gemma/retry/splitting/capacity workaround. It does not authorize that phone run or eliminate the whole-chapter T239/L238 limitation. The original failures and this successful load-only collection remain immutable and separately classified.
