# Full unchanged product-reference chapter — HTP arm

**One full depth-partitioned HTP WAV produced; Moritz rejected it as gibberish.**
The original single text context failed after duration prediction; that first
attempt and the allocation diagnostics remain preserved below. The lower-memory
route later completed all10 own QNN calls once, with no CPU fallback or input/
duration repair. The phone lock is released, the unique remote stage removed,
and the installed app and its data untouched. The later exact-hash human verdict
is `rejected`; original execution/ASR snapshots retain their capture-time status.

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
- Fifteen source/structural/preflight tests pass and the Android runner builds with
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
  phone-lock release are verified. Pi assigned a fresh profile-off TEXT-only
  constructor/close diagnostic with DP absent and zero Run, prepared for a separate
  short phone slot; this is not a repeated full synthesis.
- Exact SDK headers map1002 to `QNN_COMMON_ERROR_MEM_ALLOC`. Offline QNN System
  binary metadata reports text DDR tensor storage2,210,381,312B and spill/fill
  415,039,488B; duration reports577,374,464B and789,577,728B. Text exceeds2GiB in
  one reported storage category, but this alone does not prove the failing
  allocation. See `results/context-allocation-metadata.json`. The original runner
  already reset its duration session before creating text, so the fresh process
  tests persistent backend/lifetime effects versus standalone text load failure.
  The diagnostic keeps exact context/runtime hashes,5GiB AS and live memory guards;
  verbose native logging is enabled, profiling remains off, native alarm180s.
- The487-word chapter's approximately29.57s CPU natural prediction and qualified
  negative CPU ASR coverage result are serious content concerns, not a duration
  to override or repair. The subsequent completed HTP WAV and its separate failed
  coverage check are recorded below.

## Signed-size diagnosis and lower-memory candidate

Both fresh TEXT-only constructor/close controls failed under5GiB and8GiB Linux
`RLIMIT_AS`, with zero Run calls and no DP context/input tensors present. The8GiB
control's owned-PID Android logcat gives the concrete chain: `rpcmem_alloc_internal`
fails its `size >= 0` predicate for2,666,528,768B (`0x9ef00000`) and2,245,001,216B
(`0x85d00000`) requests, both above `INT32_MAX`; `apps_mem_request_mmap64` returns
0x68 before context deserialization5005/top-level1002. This is an evidenced RPC
signed-size rejection path, not merely an RSS or Linux virtual-limit inference.
Later native failover/teardown connection-reset/SSR-dead warnings remain private.
The unique remote directories were removed and locks released; no further limit
bumps or fallback are used. See `results/text-load-controls.json`.

The candidate partitions **network depth**, never input positions: prefix+encoder
block0 → blocks1–2 → block3+style conditioning. Each attention block keeps the
entireT3200 sequence and full key/value context. Two existing full
`[1,256,3200]` feature edges and the original residual skip carry state between
parts; no word, phoneme, latent/audio time segment is synthesized separately.
All1934 original nodes and146 initializers remain byte-identical; only the seven
nonlearned mask/control nodes are repeated across graph boundaries. CPU original
versus the composed pipeline is **bitwise identical** on the exact reference
inputs (ORT1.23.2, not a new Android CPU benchmark). Validation features stay
private and are never staged as HTP inputs.

A two-way split was exported/proved first but not phone-tested: its first part's
~2.03GB declared storage left inadequate margin. The three-way candidate uses
six physical contexts for four logical TTS stages: duration1, text3_a1, text3_b1,
text3_c1, vector5 and vocoder1. Each loads/runs/closes sequentially; interleaved
setup and host-buffer costs must be disclosed separately from stage-only timing.
The original CPU evidence and all failed HTP attempts remain untouched.

All three new exports passed. After adding128MiB planning allowance and rounding
up to64MiB, text-part estimates are1,744,830,464B /1,879,048,192B /1,342,177,280B;
the smallest signed-size margin is268,435,455B. DP/vector/vocoder also pass. This
is conservative static planning, **not** a proven proprietary allocation formula,
actual memory peak or phone-load guarantee. See
`results/text-depth-three-allocation-plan.json`, the structural/CPU proofs and
`results/text-depth-constructors.json`.

The complete private candidate stage is298,264,197B, includes no source ONNX,
original failing text context or CPU validation outputs, and keeps the frozen
common tensors/noise. Fifteen tests pass; the Android candidate builds with
`-Werror`. Its one full physical candidate render subsequently completed.

## Completed HTP WAV: execution passed, coverage failed

`results/full-depth-render-01.json` retains the full result. Own duration prediction
was29.57812691s; emitted audio is **1,304,395 frames /29.57811791s**, PCM16 mono44.1kHz.
The exact private WAV is `.local/phone-depth-full-attempt-01/evidence/run/htp.wav`,
SHA `3ae276f2d61eae37b05df23c334704e69434700dbd9360f74768c075ad40a69c`.

- **10 own neural calls:** DP1, text3, vector5, vocoder1; all QNN, CPU fallback
  disabled. No source ONNX or CPU validation features were staged.
- Setup2.454394s; summed model Run intervals8.395049s; full pipeline11.156496s.
  Setup-excluded pipeline8.702102s /RTF0.294207. These are interleaved constructors,
  runs and releases, not a warmed or all-sessions-resident benchmark. CPU profiling
  was on; HTP profiling was off.
- Own-PID Linux peak RSS181,740KiB excludes DSP/shared allocations. Minimum sampled
  device MemAvailable3,032,852KiB, with no live guard firing; this is not an
  attributable model-memory measurement. Battery27.9→27.9C; thermal status0.
- All frozen input hashes match CPU. Own active mask425 and initial masked noise
  also match CPU byte-for-byte. The different365 emitted frames arise from each
  route's own duration prediction, not a shared/forced scalar.
- Owned-PID logs show `libQnnHtpV73Skel.so` and cDSP transport. Profiling was off,
  so accelerator/HVX/RPC timing counters remain null, not fabricated.
- Remote cleanup0, phone lock released, installed app/data unchanged. No playback.

The same qualified unprompted offline Whisper-small setup decoded this exact WAV
**once**. Against the same normalized495-word reference as CPU, its unchanged
saved hypothesis contains122 words: **88.69% WER**,373 deletions,66 substitutions,
56 exact aligned matches and only2/last30 matched. `results/asr-depth-full-01.json`
contains numeric evidence only. The initial post-decoding raw-reference alignment
had506 words; it remains private. Recomputing alignment against CPU's frozen
normalized reference did not rerun ASR, condition decoding or edit the hypothesis.

**Full intelligible chapter coverage is not demonstrated; the automatic check
strongly fails.** Both genuine CPU and HTP WAVs now exist, but neither is a
listening-accepted whole-chapter solution. See `results/comparison-01.json` and the
[combined experiment README](../README.md). No duration forcing, text/audio
chunking, stitching, stretch, repair or further synthesis was performed.

## Later exact-hash human review

Moritz explicitly **rejected** HTP WAV
`3ae276f2d61eae37b05df23c334704e69434700dbd9360f74768c075ad40a69c`:
“okay so htp sample is same jibberish.” The authoritative additive record is
`results/listening-review-20260911.json`. CPU's separate exact-hash rejection is
recorded in `../cpu/results/listening-review-20260911.json`; current aggregate
verdicts are in `results/comparison-listening-review-20260911.json`.

Original execution, ASR and comparison snapshots are preserved as pre-review
records. The **tested unchanged whole-input configuration failed on both routes**.
This is not a universal verdict on Supertonic or proof of duration prediction as
the sole cause. The separately authorized0037 experiment follows the provider's
prescribed segmentation/assembly; no0036 audio is repaired, modified or rerun.
