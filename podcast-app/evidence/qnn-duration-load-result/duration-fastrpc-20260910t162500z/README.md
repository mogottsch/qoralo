# Manifest declaration: duration session created and closed, no Run

**One authorized duration constructor succeeded and closed. No neural inference was requested.** This establishes the observed duration load/close boundary only—not four-context readiness, HTP execution, speech, chapter capacity, model quality or product E2E.

## Exact candidate and namespace exception

- Fresh run: `duration-fastrpc-20260910t162500z`.
- Candidate: `ac4d325f7f5b66ca5ff144590b991775d616c18bfb9ac56065f3c66c6af89fb2`.
- App: `78488901d63032b87d2d575c6bec5b7f578b3a7ee38c92e3c633ed943dcb96ab`; reused test: `120420d6925283ccf44478b58aef29a12e4575bbf6f1027df9a3d98e83cf2c8c`.
- Host guard: `3ad4c644a7733d1f1feeb7bbbe83532cc0be0f727f32f59dda00c951dd6e202d`.
- Explicit exception: `authorized-namespace-exception.json`, SHA `c9e43b07ff7b6b4a0d983ddbce51f8749775cf7f23bc352b9e3f010989b65c84`.

The old embedded contract remains byte-identical, but its descriptive `namespacePolicy` is **overridden** by the reviewed sole optional public `libcdsprpc.so` declaration. We do not claim an unchanged namespace. All code/DEX/resources/nine native payloads, test APK, context, SoC43, runtime versions, ADSP/LD options, disabled CPU fallback and deadlines are otherwise unchanged.

## Observed success passages

Original `device/native-stderr.txt`, SHA **`e4a6b03bbc6b13117da707516618ad5762b63c69effa59143f80c025f7ccd412`**:

- Line248: `QnnDevice_create done. device = 0x1. status 0x0`.
- Line252: `CreateDevice succeed.`
- Line260: `QNN SetupBackend succeed`.
- Line827: `All nodes placed on [QNNExecutionProvider]. Number of nodes: 1`.
- Line834: `Session successfully initialized.`
- Line835: `constructor RETURNED; inputCount=3 outputCount=1; Session::Run never called`.

`native-return.txt` reports `duration_session_created_and_closed_without_run`; service status is `duration_session_created_no_run`, stage `completed-without-run`, PID21510. Driver elapsed2165ms is total collection time, not isolated constructor latency.

There is one constructor BEGIN and one RETURNED, zero Run/Gemma/other-context/TTS/capacity calls and no retry. Context/session initialization and QNN node placement are not executed-kernel proof. The tiny ORT/QNN profiling records are retained without upgrading load events to neural execution.

## Separate prior stop and maintenance

The earlier `duration-fastrpc-20260910t162216z` attempt stopped before any install on a watched PID. That record is unchanged. Pi separately identified PID13154 as only `.internal.test`, force-stopped only that package under his own lock and verified all three actual names absent. His receipt is retained separately in `../pi-test-package-maintenance/`. Only after Pi explicitly granted a fresh slot did this invocation proceed. It is not an automatic retry or a reinterpretation of the stopped attempt.

## Cleanup / evidence

The guarded identity/idle/stable snapshot checks passed before both installs and instrumentation. Original `host/cleanup.json` has no errors, settings readbacks match and app/generation/test PID absence is proven with the actual `.internal` names. The controller released the lock after cleanup; no follow-on device action occurred.

The original app-owned diagnostic archive SHA is `0a12c1fb1ad987d8bc8e5facdf7ef51c6aabc62e6e7afeb5a16d7b124e5bac1d`. `retained-manifest.json` binds287 public originals/extracted members (2,019,654 bytes). Six DB snapshot archives and unfiltered logcat remain local-only; no private DB content is published or changed. The raw embedded baseline contract is preserved alongside its explicit authorized exception.

Nik's saved-evidence audit is separate from this initial retention. Next work is source/build-only planning for four unchanged contexts plus one complete canonical TTS request through the existing render path, with no Gemma/splitting/retry/capacity probe. No additional phone call is authorized here.
