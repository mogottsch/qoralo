# Same paired K-cache fixture on physical SM8550/v73

**Complete: one actual device forward, zero warmups, no model recompile or execution retry. Both complete device outputs are byte-identical to the host outputs in `773ba60`.** This reproduces the selected synthetic consumer behavior on the target; it is not merely a host libnative-v79 artifact. It does not establish internal-node deletion, a full-model root cause or a quantization repair.

## Artifact/input and physical-route evidence

The unchanged97,904-byte PTE has SHA `d88182196544514ee3dc888b05a68a3eab11d7be90f4f5befd4a8580a01faf0d`. The four FLOAT32 inputs are the same16MiB sparse arrays used by the host probe: state3/K3 affected cache, zero new key, state15/K15 same-layout **unequal-domain** control, zero new key. One exact input-list line names all four files in order. Explicit flags set`--warm_up=0 --iteration=1 --shared_buffer=false --profile_level=0`; no default-input path was entered.

An existing54,279,656-byte ARM64 `qnn_executor_runner` and its linked QNN backend were reused without rebuilding. All13 staged files—including PTE, runner, Android runtime libraries, four inputs, list and invocation script—passed SHA checks both before and after the run. Native bytes remain LOCAL-ONLY/migration-required at the paths in `native-file-bindings.json`; staged identities are not a capture of arbitrary internal DSP tensors.

This is physical **SM-S918B / SM8550 / arm64-v8a Android**, not the earlier x86 host. The retained runner log explicitly records:

- `QnnDsp`/`HtpProvider` and **RouterFastRPC**, rather than RouterX86;
- the exact staged `libQnnHtpV73Stub.so` absolute path and successful RPC initialization;
- DSP graph architecture73 and restoration of the existing context, with on-device graph construction disabled;
- zero warmups, one input-list inference, one `QnnGraph_execute` start;
- `transport execute dmahandles [status = 0]`, then `QnnGraph_execute done. status 0x0`;
- successful context free.

`device-execution-evidence.json` retains the exact passages and log hash. The host PTE's oneQnnBackend delegate/zeroET KernelCalls remains the structural zero-tensor-fallback proof; the device/FastRPC/execute observations supply the separate physical execution evidence. They do not prove every internal SDK operation's placement or reveal internal integer codes.

## Full output comparison

| Output | Bytes / finite FLOAT32 values | Device SHA256 | Host equality |
|---|---:|---|---|
|K3 Cat|8,388,608 /2,097,152|`a864b3ed7101a39e538f5126f663334df92fdf6cff48d6caa33f2f4ca32462b7`|Every byte identical|
|K15 Cat|8,388,608 /2,097,152|`0edcd20726e3ef20d667e8df6d9ac2e624b967484f221a790df6b0dbf5c9575a`|Every byte identical|

At coordinate `[0,1,24,0]`:

| | Actual host AND device | Fullchain QDQ reference | Cat-only hypothesis | Plain float Cat |
|---|---:|---:|---:|---:|
|K3 affected|10.028992652893066|6.853916168212891|10.028990745544434|10.028990745544434|
|K15 control|1.0001479387283325|0.9998471736907959|1.000147819519043|1.0|

There are only **three nonzero output positions** across this sparse fixture. The two complete native outputs are within2ULP/1ULP of the Cat-only hypothesis, but not byte-identical to that hypothesis. The entire native outputs match the host, including the remaining zeros and the separate in-range K3 point.

A useful caution comes from saved-array arithmetic, requiring no model forward: ordinary float concatenation preserves the K3 anchor10.0289907455. The native error there is1.907e−6, while the fullchain reference loses about3.175. **Making this toy match the narrow input clamp is therefore not an established FP32-fidelity repair.** The plain-float comparison is only this weight-free concatenation, not full attention, a transformer-layer reference or a full-model FP32 result.

## Scheduling, the retained preflight and cleanup

Janek's user-app work had priority. The first lock reservation/preflight (`attempt-01`) stopped before any staging or forward because a broad process-presence guard misclassified Room's long-lived `MultiInstanceInvalidationService` as a job. Its raw observation had no foreground-service start and no ongoing calls. This was a scheduling-guard false positive, **not a model failure**. The original controller, binding, raw preflight and release are preserved.

The narrowed guard passed six source-only tests: an idle Room binder is allowed; active foreground/ongoing or unknown services still cause a yield; unavailable service observations cannot be classified idle. Foreground visibility is recorded, not equated with generation. Janek then completed his app reproduction and explicitly handed over a safely released idle phone. Fresh preflight02 took full`artifacts/locks/phone.lock`, repeated the live checks, and ran exactly one standalone fixture.

Runner exit0; both outputs and logs were pulled before cleanup. The process was proven absent, only the created private `/data/local/tmp/vibevoice-0032-kcache-20260911-02` root was removed, and the lock was released after2.721311s. Janek was immediately notified and resumed app work. No app stop/install/navigation, app file, database, episode, source or user-data mutation was performed by this controller; this is an action-scope statement, not a separate app-database byte audit. No phone call was made for post-run analysis.

## Measurement and retention limits

- The generic driver's single method-execution interval is9.625ms. This is one tiny fixture, not setup/TTFT/prefill/decode throughput, a warm median or a canonical campaign. Setup-ready timing was not independently measured.
- QNN profiling stayed off. Exact accelerator cycles and profile-based RPC/accelerator splits remain null. Transport success is execution evidence; initialization/transport log durations are not summed into invented performance metrics.
- Device process peak PSS/RSS was not captured. SDK graph/PD/VTCM estimates are not measured memory peaks. Battery/thermal raw observations are retained without converting this test into a benchmark campaign.
- Both raw device arrays remain local and are also retained as fully hash-verified lossless zstd files. The complete local bindings, first preflight, corrected controller, input-list/invocation bytes, stage checks, stdout/stderr,424-byte ETDump, exit, lock and cleanup receipts are retained. No model/PTE/library bytes are placed in Git.

The paired consumer investigation is now complete through the host/target contrast. No identical host/device replay is useful merely for nicer agreement. Any later Qwen work must address a genuinely different question—such as same-input full-model FP32 fidelity or a supported way to preserve quantization semantics—rather than treating a synthetic own-QDQ mismatch as a demonstrated model defect. All original model/physical baselines and the completed Conv sweep remain unchanged. Push/history-rewrite hold remains; no agents or Nik review.
