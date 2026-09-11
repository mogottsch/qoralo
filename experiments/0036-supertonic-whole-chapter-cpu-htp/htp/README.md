# Full unchanged product-reference chapter — HTP arm

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
or long-text quality proof. No vocoder lowering is assumed before the natural
CPU duration/common L is known.

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
and1800s bounds; the0.5s RSS sampler stops only its own process above3GiB. Sampling
is not a hard device-wide memory limit and excludes DSP/VTCM allocation. Raw
thermal-service snapshots are private; battery/charging-history data is not read.

## Evidence so far

- T3200 duration and text source derivatives have byte-identical learned weights
  and computation nodes; exhaustive initializer and shape checks pass.
- Both new QNN constructors exported single-node external contexts with exact ABI,
  runtime/source pin rechecks, zero Run calls and no cgroup OOM events.
- The duration export succeeded, but the first launcher's generic `docker inspect`
  absence classifier returned a false negative after successful removal. A separate
  `docker container inspect` proved that exact CID absent. The launcher was fixed;
  duration was not compiled again. Text's normal cleanup check passed.
- Seven source/structural tests pass and the Android runner builds with
  `-Wall -Wextra -Werror`. This is not a synthesis/listening result.
- Final latent extent, vector/vocoder contexts and the first physical full render
  await the CPU natural-duration capacity measurement and sequential phone slot.

Only Moritz can accept/reject an exact WAV. Listening verdict is `not_reviewed`.
