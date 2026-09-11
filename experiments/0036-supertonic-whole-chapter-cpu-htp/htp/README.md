# Full unchanged product-reference chapter — HTP arm

**Blocked on physical text-context load; no HTP WAV.** The first neural attempt
completed its own HTP duration stage, then text EPContext loading failed with QNN
error1002 before text/vector/vocoder execution. Host exports alone were insufficient.
The phone lock is released, the unique remote stage removed, and the installed app
and its data untouched. No neural retry or CPU fallback was used.

Noncanonical experiment0036. This is **not** the226-byte campaign and does not
produce warm-median or registry claims. All private text, token arrays, intermediate
features, audio, transcripts and execution logs stay in `.local/`.

## Frozen interface

- Official Supertonic3 FP32 weights, revision
  `724fb5abbf5502583fb520898d45929e62f02c0b`; source pins inherited from0011/0023.
- Same common normalized text/IDs/mask as CPU: T3200,3167 active positions,
  zero-filled inactive IDs and mask; exact M1 style (product SID5), speed1, five steps.
- The shared raw noise has one final `[1,144,L]` layout. Each route independently
  predicts duration, constructs its own natural latent mask, then masks the same
  raw noise. Same seed alone is not treated as equivalent noise.
- Each full arm performs its own duration1/text1/vector5/vocoder1 stages. CPU
  duration is used only for capacity planning, never substituted into HTP inference.
- No synthesis chunks, stitching, repair, stretch, forced duration or shortened text.
  Natural PCM frame count is `floor(float32_duration * float32(44100))`; active
  latent length is `ceil(frames/3072)`. Exceeding the frozen capacity fails rather
  than silently cropping.

## Implementation and bounds

`tools/materialize.py` reuses source-only0023 validation helpers but does not alter
old graphs or consume old release files. New static shapes are genuine derivatives.
Vector extends only the nonlearned INT64 arange table to `max(3200,L)`, preserving
its1000-element prefix, theta and all learned initializers. The retained seven-node
stable Softplus identity is explicit. This is not claimed to be a neutral reshape
or long-text quality proof. CPU's natural duration29.56986237s/425 active latents
informed the frozen common L512 (35.66585034s capacity); it is not used as HTP's
prediction. The original-op L512 vocoder compiled without parity lowering.

`tools/compile_context.py` constructs one fresh external QNN EPContext per stage:
ORT1.27.1, QAIRT2.49.0.260730, SoC43/v73, burst, IO-quantization offload0,
CPU fallback disabled, profiling off. It uses the existing pinned container/runtime
under `artifacts/locks/heavy-ram.lock`,4CPUs/8GiB/no extra swap/no network,520s
worker timeout and bounded immutable-container-ID cleanup. Constructor success
is not physical-phone execution proof. The old per-attempt approval machinery is
historical; experiment0036 is a separately assigned full-route task.

`phone/runner.cc` is a standalone counterpart of the0036 CPU runner, preserving
its raw-input/layout/masking/PCM semantics. It sequentially loads/runs/releases
the four external QNN contexts, with no source ONNX staged and no neural CPU
fallback. Inference profiling is deliberately **off**, avoiding the prior
SET_PROFILE6006 failure. Accelerator cycles/HVX/RPC timing remain unavailable
unless independent compatible evidence exists; no callback-derived claim is made.
CPU profiling is on, a disclosed measurement-setting difference.

`tools/run_phone.sh` requires a scheduled phone slot and holds the full
`artifacts/locks/phone.lock` during checks, transfer, execution, retrieval and
cleanup. Only serial R5CW81PR8SY and a unique owned `/data/local/tmp/` directory
are used. No APK install/uninstall, app-data operation, playback, reboot, global
process kill or active-job interruption occurs. The runner has5GiB address-space
and1800s bounds; the0.5s sampler stops only its own process above3GiB RSS or below
600MiB device MemAvailable. Initial preflight requires3GiB MemAvailable and current
battery temperature below42C. Sampling is not a hard device-wide memory limit and
excludes DSP/VTCM allocation. Raw thermal-service snapshots are private; only the
current numeric battery temperature is extracted, not raw battery/charging history.

## Evidence so far

- T3200 duration and text source derivatives have byte-identical learned weights
  and computation nodes; exhaustive initializer and shape checks pass.
- Both new QNN constructors exported single-node external contexts with exact ABI,
  runtime/source pin rechecks, zero Run calls and no cgroup OOM events.
- The duration export succeeded, but the first launcher's generic `docker inspect`
  absence classifier returned a false negative after successful removal. A separate
  `docker container inspect` proved that exact CID absent. The launcher was fixed;
  duration was not compiled again. Text's normal cleanup check passed.
- Nine source/structural/preflight tests pass and the Android runner builds with
  `-Wall -Wextra -Werror`. Synthetic/parser tests are not native execution proof.
- NEW T3200/L512 vector and L512 vocoder constructors also passed:167.617s /
  5,978,578,944B cgroup peak and2.501s /602,632,192B respectively; no OOM, containers
  absent, zero Run. All four contexts are ready in a295,512,880B private standalone
  stage. No source ONNX or host prepare library is staged.
- Direct CPU/HTP source-graph comparison found exact computation-node, public ABI
  and learned-initializer byte equality. The vector positional table alone uses
  different protobuf storage (`raw_data` versus `int64_data`), with all3200 integer
  values exactly equal. See `results/common-source-equivalence.json`.
- Shared immutable noise is `[1,144,512]`, SHA `aa7653d857cfcd894800d172d0f4ef80801871493f17e7faca2b0412dafa6c40`.
  All staged tensor hashes were checked against the frozen common manifest.
- First scheduled preflight refused before staging or model calls because an
  overly broad current-temperature parser also matched timestamp rows. It was
  corrected to an anchored field plus immediate exit; resource limits were not
  relaxed. That private failed preflight remains preserved.
- The first neural attempt then ran own HTP duration successfully:
  **29.578126907348633s**,1,304,395 natural frames,425 active latents. Its text-session
  constructor failed with `LoadCachedQnnContextFromBuffer` / QNN1002. No text,
  vector or vocoder Run followed; no WAV exists. Own-PID observed VmHWM66,136KiB,
  sampled PSS62,863KiB, minimum sampled device MemAvailable2,443,788KiB; no live
  safety guard fired. These measurements do not identify the failing allocation
  or rule out DSP/VTCM/address-space limits. Error1002 alone is not a root cause.
- See `results/phone-first-attempt-blocked.json`; all content-bearing logs and
  exact scalar remain private under `.local/phone-full-attempt-02/`. Cleanup0 and
  phone-lock release are verified. Awaiting a decision on a bounded profile-off
  text-load diagnosis, not silently retrying the failed neural route.
- The487-word chapter's approximately29.57s CPU natural prediction and qualified
  negative CPU ASR coverage result are serious content concerns, not a duration
  to override or repair. No HTP coverage comparison can be claimed without a WAV.

Only Moritz can accept/reject an exact WAV. Listening verdict is `not_reviewed`.
