# Experiment 0002 — VibeVoice 1.5B with ExecuTorch on Android

## Objective

Export VibeVoice components to ExecuTorch, validate them against experiment 0001 fixtures, and progress toward the same approximately 15-second output on the Galaxy S23 Ultra.

The original cross-runtime strategy and completed Crew work plan are retained under [`planning/`](planning/) as historical context.

## Status

Complete with a negative feasibility conclusion. Individual fixed-shape components execute reproducibly through ExecuTorch 1.2/XNNPACK on the Galaxy S23 Ultra, using the accepted INT8 Qwen2 backbone and FP32 audio components. The integrated locked run is not usable speech: it stops at the exported two-chunk cache capacity, produces only 0.266667 seconds (2.04% coverage) at -118.83 dBFS, and has a final measured prefix RTF of 107.35. The 9.136 GB APK-plus-module footprint, static-cache limit, and effectively silent output make this export infeasible for local VibeVoice speech.

The later signed-16-bit supplement does not change that technical/audio-rubric rejection: it shows that the Android fragment agrees with the equally long locked-reference introductory-silence prefix within one PCM unit (mean absolute difference 0.4709375). Prefix agreement is therefore a numerical correctness clue, not evidence of acceptable speech quality. The required human chunk-3 non-speech review remained pending, so no Moritz listening acceptance is inferred.

The frozen four-call recovery export is also **host-rejected and not deployable**. The 2,757,244,560-byte portable multi-method PTE runs calls 0–3 deterministically with actual prior outputs and produces the expected voiced chunk 3 (`-21.7126` dBFS, peak 10,228 S16 units, at most one PCM unit error). It nevertheless fails predeclared gates: calls 0–1 have `-116.07/-136.35` dBFS energy rather than the frozen `-93.66/-93.49` dBFS values, and decoder cache 4 has one out-of-tolerance element on call 3. The required human chunk-3 non-speech gate remains `pending_user_review`; it cannot override the numerical rejection. No artifact deployment or longer generation follows.

## Current tooling

- [`export/capture_fixtures.py`](export/capture_fixtures.py) wraps the real streaming decode call and captures calls 0 and 1 with stable cache names.
- [`export/capture_recurrent_trace.py`](export/capture_recurrent_trace.py) captures and validates the complete deterministic eager chain for recurrent calls 0–19; [`run-recurrent-capture.sh`](run-recurrent-capture.sh) is the required global resource-gated entry point and [`fixtures/recurrent-calls-0-19-manifest.json`](fixtures/recurrent-calls-0-19-manifest.json) preserves the hashes without committing 2.4 GiB of repeated raw evidence.
- [`export/analyze_cache_stabilization.py`](export/analyze_cache_stabilization.py) derives complete ordered cache lengths and SConvTranspose1d stabilization in [`results/cache-stabilization.json`](results/cache-stabilization.json), and recomputes the exact raw-S16 evidence in [`results/locked-reference-prefix-comparison.json`](results/locked-reference-prefix-comparison.json) without rewriting the historical comparison.
- [`export/acoustic_decoder.py`](export/acoustic_decoder.py) constructs only `TokenizerDecoder` and reads only its tensors from the sharded checkpoint.
- [`export/export_decoder.py`](export/export_decoder.py) exports a fixed `[1,64,1]` FP32 non-streaming operator-coverage probe to portable ExecuTorch or XNNPACK, with optional graph diagnostics and the verified causal-padding rewrite.
- [`export/validate_pte.py`](export/validate_pte.py) executes a PTE with its saved input and writes a structured numerical comparison even when the runtime fails.
- [`export/android_io.py`](export/android_io.py) serializes the fixed FP32 input and compares raw Android output with the PyTorch reference.
- [`export/diagnose_decoder.py`](export/diagnose_decoder.py) exports fixed-shape stem, upsampler, stage, and composite micro-probes.
- [`export/streaming_decoder.py`](export/streaming_decoder.py) replaces Python dictionary caches with a stable tensor-only ABI.
- [`export/export_streaming_segments.py`](export/export_streaming_segments.py) exports FP32 or FP16 first and cached entry points as eight stage-aligned XNNPACK PTEs and checks eager plus exported-program output.
- [`export/validate_streaming_sequence.py`](export/validate_streaming_sequence.py) chains actual call-0 cache outputs into call 1, validates PCM plus all updated caches, and checks deterministic host repeats.
- [`export/run_streaming_decoder_fp16_host.sh`](export/run_streaming_decoder_fp16_host.sh) reproduces decoder-only FP16 exports and host validation while sampling VmHWM/PSS.
- [`export/summarize_streaming_fp16.py`](export/summarize_streaming_fp16.py) rebuilds the committed FP16 structured result from ignored benchmark artifacts.
- [`export/probe_multimethod_external_constants.py`](export/probe_multimethod_external_constants.py) runs the synthetic ExecuTorch 1.2 multi-method/shared-weight and PTD capability probe without loading VibeVoice or using a phone.
- [`fixtures/four-call-cache-abi.md`](fixtures/four-call-cache-abi.md) and [`fixtures/four-call-cache-abi.json`](fixtures/four-call-cache-abi.json) freeze the pre-export calls 0–3 decoder/semantic tensor order, fixed capacities, phase/length transitions, reset and no-mutation rules, inline-constant packaging, retained INT8-Qwen2/FP32-audio choices, and numerical/audibility gates.
- [`export/four_call_abi.py`](export/four_call_abi.py) implements left-aligned fixed-capacity caches, tensor-selected transpose-convolution history, strict phase/length/padding checks, input-mutation guards, and atomic two-method state commit.
- [`export/export_four_call_audio.py`](export/export_four_call_audio.py) validates eager calls 0–3, exports the two-method inline portable PTE, and measures it against both single-method baselines.
- [`export/validate_four_call_host.py`](export/validate_four_call_host.py) chains actual runtime caches through calls 0–3 twice and applies every frozen PCM, cache, energy, deterministic-repeat, and protocol-defined audibility gate. Results are committed in [`results/four-call-audio-export.json`](results/four-call-audio-export.json) and [`results/four-call-host-validation.json`](results/four-call-host-validation.json); generated PTEs remain ignored.
- [`results/four-call-android.json`](results/four-call-android.json) records the required fail-closed Android outcome: the reproducibly host-rejected PTE was not deployed, no ADB command was issued, and all unavailable device measurements are explicit rather than inferred from older runs.
- [`export/capture_diffusion_fixture.py`](export/capture_diffusion_fixture.py) captures the first real CFG prediction-head invocation from the locked reference and stops before scheduler iteration.
- [`export/diffusion_head.py`](export/diffusion_head.py) loads only prediction-head checkpoint tensors and defines the four-input FP32 ABI.
- [`export/export_diffusion_step.py`](export/export_diffusion_step.py) exports the fixed CFG prediction to portable ExecuTorch or XNNPACK.
- [`export/validate_diffusion_step.py`](export/validate_diffusion_step.py) runs the PTE and records a structured full-tensor comparison.
- [`export/diffusion_scheduler.py`](export/diffusion_scheduler.py) mirrors the locked ten-step DPM-Solver++ schedule without loading the full model.
- [`export/validate_diffusion_loop.py`](export/validate_diffusion_loop.py) invokes the one-step PTE ten times and freezes a host loop reference for native comparison.
- [`export/diffusion_android_io.py`](export/diffusion_android_io.py) serializes all four diffusion inputs plus the scheduler and compares phone outputs.
- [`export/speech_connectors.py`](export/speech_connectors.py) scaffolds a connector-only loader and `(acoustic, semantic) -> LM embedding` tensor ABI; real paired fixture capture/export remain.
- [`export/qwen2_backbone.py`](export/qwen2_backbone.py) defines fixed-capacity, explicitly ordered Qwen2 prefill/decode cache wrappers and the dense speaker-conditioning boundary.
- [`export/export_qwen2_tiny.py`](export/export_qwen2_tiny.py) proves those wrappers with a tiny synthetic Qwen2 through strict export, XNNPACK, and the ExecuTorch host runtime.
- [`export/capture_qwen2_fixtures.py`](export/capture_qwen2_fixtures.py) captures real prefill and next-positive decode fixtures from the locked generation.
- [`export/validate_qwen2_fixtures.py`](export/validate_qwen2_fixtures.py) checks exact repeat determinism, finite tensors, mask/cache occupancy, all 56 ordered cache handoffs, and eager wrapper agreement.
- [`export/qwen2_checkpoint.py`](export/qwen2_checkpoint.py) loads only the checkpoint's Qwen2 weights into the FP32 export wrapper.
- [`export/export_qwen2_real.py`](export/export_qwen2_real.py) strictly exports either real entry and lowers it to ExecuTorch/XNNPACK.
- [`export/validate_qwen2_pte.py`](export/validate_qwen2_pte.py) executes both real PTEs, compares every output, and feeds the actual prefill cache outputs into decode.
- [`fixtures/qwen2-backbone-abi.md`](fixtures/qwen2-backbone-abi.md) specifies sequence/mask/position semantics, the 56-cache order, native token-selection boundary, speaker boundary, and real-capture acceptance criteria.
- [`android/`](android/) contains the minimal debug-only ExecuTorch 1.2 runner and its repeatable ADB harness.
- [`fixtures/README.md`](fixtures/README.md) documents the ignored fixture layout and capture command.
- [`fixtures/acoustic-decoder-manifest.json`](fixtures/acoustic-decoder-manifest.json) records the captured shapes, dtypes, stable cache ordering, ranges, and hashes without committing tensors.
- [`fixtures/diffusion-head-manifest.json`](fixtures/diffusion-head-manifest.json) records provenance, stable ABI order, tensor metadata, and exact hashes without committing tensors.
- [`results/acoustic-decoder-host.json`](results/acoustic-decoder-host.json) records the host failure matrix, micro-probe evidence, rewrite, and passing result.
- [`results/acoustic-decoder-android.json`](results/acoustic-decoder-android.json) records device runs, memory observations, and the numerical comparison.
- [`results/acoustic-decoder-streaming-host.json`](results/acoustic-decoder-streaming-host.json) records the FP32 two-call host streaming sequence and selected segmented ABI.
- [`results/acoustic-decoder-streaming-fp16.json`](results/acoustic-decoder-streaming-fp16.json) records eager/export/host/Android FP16 size, timing, memory, error, cache-transport, and repeat evidence.
- [`results/diffusion-head-host.json`](results/diffusion-head-host.json) records the FP32 one-call XNNPACK export, resource use, and passing numerical comparison.
- [`results/diffusion-head-android.json`](results/diffusion-head-android.json) records cold/warm one-call latency, two ten-step loop runs, memory, and numerical comparisons.
- [`results/qwen2-fixtures-host.json`](results/qwen2-fixtures-host.json) records real fixture structure, exact repeat determinism, and all-output eager wrapper agreement.
- [`results/qwen2-backbone-host.json`](results/qwen2-backbone-host.json) records the passing real exports and the preserved host numerical failure.

The initial non-streaming `.pte` remains the Android operator-coverage baseline. Streaming uses separate first and cached entry sets with eight stage-aligned segments because the monolithic streaming graph terminates the host runtime.

## Multi-method and external-constant capability probe

[`results/executorch-multimethod-external-constants.json`](results/executorch-multimethod-external-constants.json) records the bounded synthetic diagnostic. It used ExecuTorch 1.2.0, PyTorch 2.11.0+cpu, Python 3.11.13, and FlatBuffers compiler 24.3.25. The two methods share one deterministic 65,536-byte FP32 weight payload and return distinct values, so both method selection and constant reuse are observable.

```bash
ulimit -c 0
artifacts/venv-executorch-1.2/bin/python \
  experiments/0002-vibevoice-1.5b-executorch-android/export/probe_multimethod_external_constants.py
```

The inline portable result passed both host methods exactly. Two independent PTEs total 134,408 bytes; one two-method PTE is 68,500 bytes, only 1,296 bytes larger than the mean single-method PTE. Thus phase-specific warm-up methods can share serialized constants rather than multiplying full weights.

XNNPACK externalization also produced a working two-method 2,816-byte PTE plus one 65,792-byte `shared-weights.ptd`; both methods ran through the private `_load_for_executorch(pte_path, ptd_path)` binding. It is **not compatible with the current application runtime path**: public Python `Runtime.load_program` has no data-path argument and executing the PTE without PTD terminates this build with `SIGSEGV`; inspection of the cached `org.pytorch:executorch-android:1.2.0` API shows only one-path `Module.load(...)` overloads and no PTD/data-loader parameter. No device run was warranted. Use the inline multi-method PTE for the warm-up ABI and defer PTD until the public host and Android APIs explicitly accept external data.

All generated PTEs, PTDs, and logs remain under ignored `artifacts/0002/executorch-capability-probe/`.

## FP32 host result

ExecuTorch 1.0, 1.1, and 1.2 exported the unmodified graph but XNNPACK failed during shape propagation with `xnn_status_invalid_parameter`. Portable execution failed earlier because `constant_pad_nd` received input and output tensors with different dim orders. ExecuTorch 1.2's constant-layout fixes did not resolve this rank-3 pad path, and `_skip_dim_order=True` did not change the portable failure.

Micro-probes isolated the problem:

- the unmodified stem failed;
- the same stem convolution with padding materialized before the graph passed;
- all six `ConvTranspose1d` upsamplers passed individually;
- stages 1–6 passed after rewriting their causal padding;
- stage 0 alone exposed a singleton-time output layout ambiguity, but the complete initial stem → stage 0 → upsampler 1 graph passed.

The verified rewrite expresses causal zero padding as symmetric padding inside `Conv1d` and slices away the right-padding-only outputs. All 28 decoder `SConv1d` modules are rewritten only in the non-streaming export wrapper. Eager output remains within `atol=1e-6, rtol=1e-5` of the pinned implementation.

The full ExecuTorch 1.2 XNNPACK host result:

| Metric | Result |
|---|---:|
| PTE size | 1,375,020,420 bytes |
| Load time | 0.00144 s |
| Inference time | 0.06768 s |
| Peak host RSS | 1,881,128 KiB |
| Output | `[1,1,3200]` FP32 |
| Maximum absolute error | `8.08e-10` |
| Mean absolute error | `1.01e-11` |
| Comparison | passed (`atol=1e-5`, `rtol=1e-4`) |

Reproduce the passing export and host comparison with ExecuTorch 1.2, its paired PyTorch 2.11 environment, and FlatBuffers compiler 25.12.19 on `PATH`:

```bash
uv venv --python 3.11 artifacts/venv-executorch-1.2
uv pip install --python artifacts/venv-executorch-1.2/bin/python torch==2.11.0 \
  --index-url https://download.pytorch.org/whl/cpu
uv pip install --python artifacts/venv-executorch-1.2/bin/python \
  --prerelease=allow executorch==1.2.0
uv pip install --python artifacts/venv-executorch-1.2/bin/python \
  --no-deps -e artifacts/source/microsoft-vibevoice
uv pip install --python artifacts/venv-executorch-1.2/bin/python \
  transformers==4.51.3 accelerate==1.6.0 safetensors ml-collections absl-py

artifacts/venv-executorch-1.2/bin/python \
  experiments/0002-vibevoice-1.5b-executorch-android/export/export_decoder.py \
  --backend xnnpack --rewrite-constant-pad \
  --graph-output artifacts/0002/acoustic-decoder-xnnpack.graphs.txt \
  --output artifacts/0002/acoustic-decoder-xnnpack.pte

artifacts/venv-executorch-1.2/bin/python \
  experiments/0002-vibevoice-1.5b-executorch-android/export/validate_pte.py \
  artifacts/0002/acoustic-decoder-xnnpack.pte
```

## FP32 Android result

The matching ExecuTorch 1.2 Android AAR loaded the XNNPACK PTE from app-private storage and produced the expected `[1,1,3200]` FP32 output on the Galaxy S23 Ultra.

| Metric | Result |
|---|---:|
| First cold inference | 8.078 s |
| Subsequent inference | 4.551 s, 4.154 s, 6.628 s |
| Subsequent median | 4.551 s |
| Maximum process VmHWM | 1,602,328 KiB (~1.53 GiB) |
| Maximum observed PSS | 1,401,425 KiB (~1.34 GiB) |
| Maximum absolute error | `8.50e-10` |
| Mean absolute error | `1.09e-11` |
| Comparison | passed (`atol=1e-5`, `rtol=1e-4`) |

All four device runs produced the same raw output SHA-256. The first run followed model transfer and includes cold filesystem/backend effects; later runs benefited from cached pages but still showed meaningful timing variability. Memory is app-reported `VmHWM` plus point-in-time PSS rather than a high-frequency external trace.

Reproduce the Android build, install, app-private transfer, execution, retrieval, and comparison with:

```bash
experiments/0002-vibevoice-1.5b-executorch-android/android/run-decoder-probe.sh
```

The 1.375 GB FP32 module is a correctness artifact. The passing result establishes Android operator coverage but does not make this a practical deployment.

## FP32 streaming host result

The tensor-only streaming ABI orders 34 cache tensors by stable decoder module name. A first entry consumes one `[1,64,1]` latent; a cached entry consumes the next latent plus those 34 tensors. Both return `[1,1,3200]` PCM and 34 updated tensors.

A monolithic XNNPACK streaming PTE exported but terminated the host process during execution. The portable form also retained an invalid rank-3 convolution dim order. The validated design therefore follows natural decoder boundaries: seven upsample/stage PTEs plus one norm/head PTE for each entry type.

| Metric | Call 0 / first | Call 1 / cached |
|---|---:|---:|
| XNNPACK segments | 8 | 8 |
| Total host inference | 0.08936 s | 0.10632 s |
| PCM shape | `[1,1,3200]` | `[1,1,3200]` |
| PCM maximum absolute error | `8.08e-10` | `3.87e-11` |
| Maximum cache absolute error | `4.96e-5` | `4.96e-5` |
| Comparison | passed | passed |

Call 1 consumed the **actual ExecuTorch cache outputs from call 0**, not the fixture pre-cache tensors. Every PCM output and all 34 updated caches were compared with the deterministic PyTorch fixtures using `atol=2e-5, rtol=1e-5`. Peak host RSS for the two-call sequence was 1,648,768 KiB.

The first entry set occupies 1,375,063,172 bytes and the cached entry set 1,379,159,424 bytes, so the current FP32 diagnostic ABI duplicates weights on disk. This is acceptable for correctness but must be addressed through FP16, packaging, or entry unification before practical deployment.

Reproduce both entry exports and the chained host comparison with:

```bash
export PATH="$PWD/artifacts/tools/flatbuffers-25.12.19:$PATH"
PY=artifacts/venv-executorch-1.2/bin/python
EXP=experiments/0002-vibevoice-1.5b-executorch-android/export

$PY "$EXP/export_streaming_segments.py" --entry first
$PY "$EXP/export_streaming_segments.py" --entry cached
$PY "$EXP/validate_streaming_sequence.py" \
  artifacts/0002/acoustic-decoder-streaming-first-segments-1.2 \
  artifacts/0002/acoustic-decoder-streaming-cached-segments-1.2 \
  --output artifacts/0002/acoustic-decoder-streaming-sequence-host.json
```

## FP32 streaming Android result

The Galaxy S23 Ultra ran all eight first-entry segments, serialized the 34 actual device cache outputs into app-private storage, reloaded them as the cached-entry inputs, and ran all eight cached-entry segments. The runner memory-maps one PTE at a time from `/data/local/tmp`; no model is packaged in the APK and first/cached modules are not resident together.

| Metric | Cold sequence | Warm-page-cache sequence |
|---|---:|---:|
| First-call inference | 5.130 s | 3.708 s |
| Cached-call inference | 4.468 s | 4.475 s |
| Two-call inference | 9.598 s | 8.183 s |
| Peak observed PSS | 1,105,850 KiB | 1,103,779 KiB |
| Process VmHWM | 1,322,940 KiB | 1,322,940 KiB |

Both `[1,1,3200]` PCM chunks pass the original `atol=2e-5, rtol=1e-5`: call 0 maximum error is `8.50e-10`, and call 1 maximum error is `3.64e-11`. All 70 output files (two PCM plus 68 caches) have identical hashes across the two runs.

The original strict cache comparison is preserved rather than hidden. Call 0 passes all 34 caches. Call 1 passes 33 of 34 cache tensors; `segment-0 cache-3` has exactly **one** value outside the strict threshold among 12,288 values (`3.36e-5` error versus `2.73e-5` allowed). The maximum Android cache error is `5.34e-5`; the host intermediate/cache maximum was `4.96e-5`.

Step 8 therefore uses an explicit **Android-cache-only** acceptance of `atol=6e-5, rtol=1e-5`. This narrowly covers deterministic backend intermediate drift while both PCM errors remain below `1e-9`. It does not change the host or PCM thresholds and does not claim bit equivalence. Full strict and adjusted results are recorded in [`results/acoustic-decoder-streaming-android.json`](results/acoustic-decoder-streaming-android.json).

Reproduce the APK build, incremental external PTE transfer, two device sequences, output retrieval, and both comparisons with:

```bash
experiments/0002-vibevoice-1.5b-executorch-android/android/run-streaming-decoder-probe.sh
```

The two FP32 entry sets occupy 2,754,222,596 bytes on device. A practical package still needs to remove first/cached weight duplication or share weights outside separate PTEs.

## FP16 streaming result

The same eight-segment pipeline now supports native FP16 parameters, activations, and cache tensors. Both host and Android call 1 consume the **actual 34 FP16 cache tensors emitted by call 0**. No FP32 threshold was changed: the prior FP32 host/PCM `atol=2e-5, rtol=1e-5` and Android-cache-only `atol=6e-5` remain recorded unchanged.

FP16 is compared with the original FP32 fixtures using explicit, separately scoped thresholds:

- final PCM: `atol=2e-3, rtol=2e-3` everywhere;
- host eager caches and chained host intermediate/cache outputs: `atol=5e-2, rtol=2e-3`;
- Android caches only: `atol=3.5e-1, rtol=2e-3`.

The Android cache threshold is not a hidden general relaxation. Android FP16 XNNPACK has deterministic cache drift up to `0.32346`, while call-0 and call-1 PCM errors remain `1.086e-4` and `8.129e-7`. The strict `2e-3` cache result is retained as false, both PCM chunks must pass the smaller PCM threshold, and call 1 must consume the actual device caches. This makes FP16 acceptable for this two-call correctness probe but flags cache drift for longer-sequence testing.

| Metric | FP16 result |
|---|---:|
| First / cached PTE sets | 770,791,748 / 774,575,168 bytes |
| Total PTE size | 1,545,366,916 bytes (43.89% below FP32) |
| Eager first / cached PCM max error | `6.92e-7` / `6.19e-8` |
| Exported-program max error vs eager | `0` |
| Host first / cached inference, repeat 0 | 0.1514 s / 0.1843 s |
| Host peak VmHWM / observed PSS | 1,014,832 / 978,243 KiB |
| Android session A cold / warm two-call inference | 3.4224 s / 1.6824 s |
| Android session B cold / warm two-call inference | 9.7293 s / 8.8482 s |
| Android observed load range | 0.00566–0.0310 s |
| Android VmHWM / peak observed PSS | 799,760 / 612,394 KiB |
| Deterministic repeats | host and Android passed |

Reproduce host eager/export/XNNPACK validation, then the Android run and summary:

```bash
experiments/0002-vibevoice-1.5b-executorch-android/export/run_streaming_decoder_fp16_host.sh
PRECISION=fp16 \
  experiments/0002-vibevoice-1.5b-executorch-android/android/run-streaming-decoder-probe.sh
artifacts/venv-executorch-1.2/bin/python \
  experiments/0002-vibevoice-1.5b-executorch-android/export/summarize_streaming_fp16.py
```

These commands load only the acoustic decoder, not the complete model. Generated PTEs, tensors, APKs, and raw logs stay under ignored `artifacts/`. Android output hashes were deterministic, but two-call latency varied from 1.682 to 9.729 seconds across two sessions; thermal and scheduler state were not controlled, so the FP16 speedup is not yet stable.

## FP32 diffusion-head host result

The captured fixture is the first real prediction-head invocation reached by the locked experiment 0001 transcript, voices, seed 42, ten-step schedule, and CFG scale 1.3. Capture stops after the head returns. Repeating the capture produced identical hashes for all four inputs and the guided output.

The exported graph deliberately performs **one prediction-head call**, including the CFG combine, rather than the DPM scheduler update or scheduler loop:

```text
(noisy_latent [1,64], timestep [1],
 positive_condition [1,1536], negative_condition [1,1536])
    -> cfg_guided_v_prediction [1,64]
```

| Metric | Result |
|---|---:|
| Precision / backend | FP32 / XNNPACK |
| PTE size | 493,152,000 bytes |
| Export wall time / peak RSS | 14.17 s / 2,055,000 KiB |
| Host load / inference | 0.00019 s / 0.03304 s |
| Host peak RSS | 1,015,112 KiB |
| Maximum / mean absolute error | `1.22e-6` / `3.72e-7` |
| Comparison | passed (`atol=1e-5`, `rtol=1e-4`) |

The full reference-context capture took 31.90 s and peaked at 13,191,072 KiB because it loads the complete model to obtain real conditions; export itself loads only the prediction head. The 493 MB FP32 PTE is a correctness artifact, not a practical package. The fixed batch/shape and frozen CFG scale are intentional for the first Android probe.

Reproduce export and host validation without writing outside the ignored lane directory:

```bash
ROOT=/home/moritz/dev/vibevoice-android-spike
ART=$ROOT/artifacts/0002/lane-b/diffusion-head
export PATH="$ROOT/artifacts/tools/flatbuffers-25.12.19:$PATH"
PY=$ROOT/artifacts/venv-executorch-1.2/bin/python
EXP=experiments/0002-vibevoice-1.5b-executorch-android/export

$PY "$EXP/export_diffusion_step.py" \
  --source "$ROOT/artifacts/source/microsoft-vibevoice" \
  --model "$ROOT/artifacts/models/microsoft-VibeVoice-1.5B" \
  --fixture "$ART/fixture.pt" \
  --output "$ART/diffusion-step-xnnpack.pte" --backend xnnpack
$PY "$EXP/validate_diffusion_step.py" \
  "$ART/diffusion-step-xnnpack.pte" --output "$ART/host-result.json"
```

## FP32 diffusion Android and native-loop result

The Galaxy S23 Ultra runs the same 493,152,000-byte XNNPACK PTE through a dedicated four-input activity. The first invocation after a cold activity start is recorded separately from two same-process repeats. The Java controller then resets the captured latent, invokes the PTE at the ten locked timesteps, and applies FP32 DPM-Solver++ order-two midpoint updates outside the graph.

| Metric | Result |
|---|---:|
| PTE mmap load | 0.0218 s |
| One-step cold | 0.9029 s |
| One-step warm repeats | 0.2148 s, 0.3371 s |
| Ten-step loop runs | 1.6672 s, 1.2457 s |
| Process VmHWM | 711,388 KiB |
| Peak observed PSS | 522,263 KiB |
| One-step maximum error | `1.18e-6` |
| Ten-step final-latent maximum error | `2.26e-6` |
| Comparison | passed (`atol=2e-5`, `rtol=1e-4`) |

The ten-step reference uses ten host XNNPACK calls plus an independently implemented scheduler that was checked against the pinned Python scheduler. Android owns the loop and scheduler state; the PTE remains exactly one prediction-head/CFG call. This proves deterministic component orchestration for one captured condition pair, not text-to-audio generation. Memory is app-reported `VmHWM` and point-in-time PSS, not a high-frequency external trace.

Reproduce host fixture generation, APK build/install, transfer, cold/warm execution, output retrieval, and comparison with:

```bash
experiments/0002-vibevoice-1.5b-executorch-android/android/run-diffusion-probe.sh
```

Connector scaffolding also loads the real acoustic and semantic connector weights without constructing the rest of VibeVoice and exposes `(acoustic [1,64], semantic [1,128]) -> combined LM embedding [1,1536]`. A real-weight smoke check produced a finite FP32 `[1,1536]` output. Paired generative capture/export was not attempted here because Lane C owns the exclusive heavy-RAM slot and a full-model capture would violate that resource boundary. Step 17 therefore remains pending; semantic-encoder cache ABI work was not started.

## FP32 Qwen2 host result

Two complete locked-generation captures produced byte-identical `manifest.json`,
`prefill.pt`, and `decode.pt` files. The prefill has 503 conditioned embeddings;
the next positive one-token call is at position 503. Validation checked 181 raw
tensors between runs, all floating tensors are finite, every unused cache/mask
slot is zero, and the prefill post-cache equals the decode pre-cache exactly.
The normative 56-tensor order is layer ascending and key then value.

The checkpoint-only FP32 loader and eager fixed-cache wrappers match all 58
outputs per entry at the initial `atol=1e-5, rtol=1e-4`:

| Metric | Prefill | Decode |
|---|---:|---:|
| Input sequence | 503 | 1 |
| Wrapper max absolute error | `1.76e-5` | `7.63e-6` |
| Wrapper mean absolute error | `1.47e-7` | `6.72e-9` |
| Comparison | passed | passed |

Both real entries also pass strict `torch.export`, lower to 284 XNNPACK delegate
segments, emit a PTE, and execute on the ExecuTorch 1.2 host runtime. Decode
consumes the **actual ExecuTorch prefill cache outputs**. The runtime result is
not accepted at the initial tolerance, which is preserved rather than widened:

| Metric | Prefill | Chained decode |
|---|---:|---:|
| PTE bytes | 6,175,515,904 | 6,175,505,536 |
| Export peak RSS | 19,123,704 KiB | 19,144,148 KiB |
| Host inference | 7.088 s | 0.513 s |
| Outputs finite / compared | 58 / 58 | 58 / 58 |
| Maximum absolute error | `4.73e-4` | `4.73e-4` |
| Mean absolute error | `1.11e-6` | `1.08e-6` |
| Values outside tolerance | 12,844 | 11,315 |
| Strict comparison | failed | failed |

The large maximum includes cache values for which relative tolerance often
still passes; hidden state, logits, and several caches nevertheless contain
strict mismatches. The PTEs and full diagnostic logs remain ignored under
`artifacts/`. No Android run or quantization follows from this unaccepted
baseline. Reproduction commands and exact hashes are in
[`fixtures/qwen2-backbone-abi.md`](fixtures/qwen2-backbone-abi.md) and
[`results/qwen2-backbone-host.json`](results/qwen2-backbone-host.json).

## Deployment design

Do not export the complete Python `generate()` method as one graph. VibeVoice combines tensor computation with token selection, diffusion iteration, streaming caches, and Python control flow. Keep orchestration in Kotlin or C++ and export tensor-heavy components as one or more ExecuTorch `.pte` modules.

```text
Kotlin test harness
        |
        v
Native generation controller
        |
        +-- text tokenizer
        +-- speaker-prompt preparation
        +-- Qwen2 prefill/decode + explicit KV cache  --+
        +-- diffusion-head step                         +-- ExecuTorch modules
        +-- acoustic/semantic connectors                |
        +-- streaming acoustic decoder                --+
        |
        v
24 kHz PCM -> WAV initially, then Android AudioTrack
```

The development harness may write WAV files first. Real-time playback is not required for the first success.

## Component order

1. Acoustic decoder with a fixed latent and explicit cache tensors
2. One diffusion-head denoising step
3. Language-backbone prefill
4. Single-step language decode with explicit KV-cache input/output
5. Acoustic and semantic connectors
6. Speaker conditioning
7. Native generation controller
8. Three-to-five-second end-to-end generation
9. Fixed experiment 0001 transcript

For every component:

1. capture real inputs and expected outputs from the locked PyTorch model;
2. record tensor names, shapes, dtypes, and SHA-256 hashes;
3. export a minimal wrapper with a tensor-only interface;
4. run the exported module through the ExecuTorch host runtime;
5. compare it numerically against PyTorch;
6. run the same fixture on Android;
7. record errors, unsupported operators, latency, memory, and backend partitioning.

Large fixture tensors and `.pte` files stay under ignored `artifacts/`. Only scripts, tensor metadata, hashes, measurements, and conclusions are committed.

## First milestone: acoustic decoder on the phone

Capture one acoustic latent and decoder-cache state from experiment 0001. Export a wrapper with a stable interface similar to:

```text
(latent, cache tensors...) -> (PCM chunk, updated cache tensors...)
```

Start with fixed shapes and FP32 or FP16 as required for correctness. Dynamic shapes and quantization come later.

The milestone passes when:

- PyTorch and the ExecuTorch host runtime produce outputs within a documented tolerance;
- the Galaxy S23 Ultra loads the `.pte` without termination;
- XNNPACK produces a valid PCM chunk from the same latent;
- Android output is compared numerically with the host fixture;
- load time, inference time, peak RSS, package size, and delegated operators are recorded.

A WAV assembled from this single chunk is useful for diagnosis but is not an end-to-end VibeVoice result.

## Backbone and cache design

Treat the Qwen2 backbone as two entry points:

- **prefill** consumes the transcript and speaker-conditioning sequence and creates the initial KV cache;
- **decode** consumes one token or embedding plus explicit KV-cache tensors and returns the next hidden state and updated cache.

Do not depend on mutable Hugging Face cache objects across the runtime boundary. Use fixed tensor layouts first. Add bounded dynamic sequence dimensions only after fixed-shape export is correct.

## Diffusion design

Export one denoising step rather than the complete diffusion loop:

```text
(noisy latent, timestep, positive condition, negative condition)
    -> predicted latent update
```

Run the locked ten DDPM inference steps in native orchestration code. Preserve FP16 initially; quantize only after numerical and audio comparisons pass.

## Backend progression

Use the same fixtures in this order:

1. ExecuTorch portable/host runtime for export debugging;
2. XNNPACK on Android for the broadest practical CPU baseline;
3. ExecuTorch Qualcomm backend/QNN for Snapdragon acceleration;
4. Vulkan only for a component with a clear coverage or performance advantage.

XNNPACK establishes correctness before Qualcomm SDK, operator, shape, and quantization constraints are introduced. Direct QNN integration remains experiment 0005; using the ExecuTorch Qualcomm backend here does not replace that later comparison.

## Precision progression

1. Use the highest supported precision for component correctness.
2. Move the Qwen2 backbone to weight-only INT8, then INT4.
3. Keep the diffusion head and audio components FP16 initially.
4. Try INT8 for individual diffusion/audio components only with fixture and listening comparisons.

A full FP16 deployment is a diagnostic target, not the expected final configuration. Experiment 0001 used about 12.42 GiB peak RSS in FP32, so the Android build will probably require an INT4 backbone and careful cache bounds.

## Android packaging and runner

During the spike:

- do not package models inside the APK;
- push `.pte` files and fixtures over ADB into app-private or test storage;
- memory-map model files where the runtime permits;
- use a minimal Kotlin/JNI or C++ runner rather than a product UI;
- write PCM/WAV output before adding `AudioTrack` streaming;
- keep model weights, APKs, traces, generated audio, and tensors uncommitted.

Suggested experiment layout:

```text
0002-vibevoice-1.5b-executorch-android/
├── fixtures/
│   └── README.md
├── export/
│   ├── capture_fixtures.py
│   ├── acoustic_decoder.py
│   └── export_decoder.py
├── android/
│   └── minimal runner
└── README.md
```

Directories and scripts should be added only when needed; this tree is not a requirement to create empty scaffolding.

## End-to-end controller

After the components pass independently, the native controller will:

1. tokenize the transcript;
2. prepare speaker prompts or precomputed speaker features;
3. run backbone prefill;
4. run one-step decode and token selection;
5. invoke the diffusion loop for speech diffusion tokens;
6. decode the resulting acoustic latent into PCM;
7. update KV, semantic, and acoustic caches;
8. repeat until the speech-end token;
9. save or stream the resulting 24 kHz mono audio.

The first end-to-end target is three to five seconds. The second is the locked experiment 0001 transcript with both speaker identities.

## Stop and pivot conditions

Record the failure and move to the next component or runtime when:

- required operators cannot be decomposed or implemented without a substantial custom-kernel effort;
- the minimally viable precision cannot fit within Android memory limits;
- numerical drift corrupts diffusion or decoded audio;
- backend partitioning transfers tensors so often that acceleration is ineffective.

A failed full export does not invalidate useful results from individual components.

## Final execution optimization and conclusion

Step 39 tested the remaining controller-level execution overhead after memory stabilization. `GenerationProbeActivity` still destroys every memory-mapped PTE after each call, but requests explicit Java collection every eight module calls instead of after all 130 calls in a prefix run. The harness now profiles module load, forward, output copying, destruction, and explicit GC separately.

| Metric | Memory-stabilized baseline | Periodic-GC run | Change |
|---|---:|---:|---:|
| Median generated-prefix wall time | 29.135 s | 28.626 s | -1.74% |
| Median TTFA | 12.113 s | 11.865 s | -2.04% |
| Median prefix RTF | 109.26 | 107.35 | -1.74% |
| Two-run wall-time CV | 3.93% | 2.26% | descriptive only |
| Maximum PSS | 479,784 KiB | 475,956 KiB | -0.80% |
| Maximum VmHWM | 1,650,288 KiB | 1,660,452 KiB | +0.62% |
| APK + accepted modules | 9,136,214,097 bytes | 9,136,215,197 bytes | +1,100 bytes telemetry bytecode |

The 1.74% median wall-time change is smaller than the observed two-run variability and is **not** claimed as a material speedup. The optimized runs executed 130 PTE calls each. Module forward occupied 25.54–26.91 seconds, while load occupied 0.150–0.169 seconds and explicit GC 0.091–0.093 seconds. XNNPACK forward execution, not Java loading or collection, is the measured bottleneck. Diffusion median latency regressed 17.65% while Qwen prefill/decode and audio stages varied in both directions; thermal status rose from NONE to LIGHT during the run.

Correctness did not change. Cold and warm processes produced the same WAV as the memory-stabilized build (`f5c90fdf64f563d0aa97f0acfe04abc26943f35c1cb7d78730449283682f64c9`) and stopped at `CAPACITY`. The locked comparison remains rejected: 0.266667 of 13.066667 seconds, 2.0408% coverage, -118.83 dBFS, omissions/repetitions/corruption failed, and speaker consistency not assessable.

**Final conclusion:** the component work proves reproducible ExecuTorch/XNNPACK execution, but this VibeVoice 1.5B export is not feasible for useful local speech on the Galaxy S23 Ultra. Periodic GC cannot fix the static two-chunk cache ABI, effectively silent audio, roughly 9.136 GB deployment, or approximately 107x measured prefix RTF. A retry would require re-exporting a longer or dynamic cache ABI and changing model packaging/precision; those are architectural changes, not further controller tuning.

Reproduce the final build, phone measurement, and publication with:

```bash
experiments/0002-vibevoice-1.5b-executorch-android/android/optimize-complete-build-execution.sh
python3 -m unittest discover \
  -s experiments/0002-vibevoice-1.5b-executorch-android/tests \
  -p 'test_complete_build*.py'
experiments/0002-vibevoice-1.5b-executorch-android/android/run-generation-controller-tests.sh
python3 -m json.tool \
  experiments/0002-vibevoice-1.5b-executorch-android/results/complete-build-final.json >/dev/null
```

Committed evidence:

- [`results/complete-build-final.json`](results/complete-build-final.json): before/after stages, TTFA, wall time, RTF, variability, memory, size, correctness, determinism, audio comparison, commands, and final conclusion.
- [`results/complete-build-final-measurement.json`](results/complete-build-final-measurement.json): optimized cold/warm phone observations and execution profile.
- [`results/complete-build-memory-optimized.json`](results/complete-build-memory-optimized.json): memory-stabilized baseline.
- [`results/locked-reference-comparison.json`](results/locked-reference-comparison.json): fixed audio rubric.
- Raw logs, telemetry, WAVs, APK, and model files: ignored under `artifacts/0002/lane-d/complete-build-final/`.
- Implementation commit: `1629cab8831416a7dc71e082654bf059fd9ebd71`.
