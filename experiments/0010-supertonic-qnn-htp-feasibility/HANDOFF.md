# Experiment 0010 final handoff — bounded hybrid result

## Status and decision

Experiment 0010 is complete. The canonical result is [`results/e2e-hybrid-cpu-checkpoint.json`](results/e2e-hybrid-cpu-checkpoint.json); the detailed narrative is [`PLAN.md`](PLAN.md) and its [HTML mirror](PLAN.html). Earlier host, phone-vocoder, and vector checkpoints remain immutable stage evidence.

The fixed-transcript Supertonic path ran end to end on the authorized Galaxy S23 Ultra (`SM-S918B`, `SM8550`): text preparation, duration prediction, text encoding, five recursive vector-estimator calls, vocoding, trimming, and WAV writing. The matched CPU and hybrid routes used M1/SID5, English, seed `20260813`, T239/L238, and `729746` output samples at 44.1 kHz. Duration prediction executed and reported `16.9202 s`; QNN's concrete-shape deployment retained the predeclared L238 contract rather than dynamically rebuilding graphs.

**Retained decision:** keep CPU as the supported technical reference deployment. Preserve the hybrid as a bounded research baseline only. Moritz reported no audible CPU/hybrid difference for one reviewed utterance, but no separate listening-quality acceptance was recorded for either sample. The hybrid is not full HTP, arbitrary-shape, numerically accepted, listening-quality accepted, or production-ready.

No follow-up experiment, source export, conversion route, or full-HTP plan is approved here.

## Provider routes and physical proof

CPU route:

- duration predictor: CPU;
- text encoder: CPU;
- vector estimator ×5: CPU;
- vocoder: CPU.

Hybrid route:

- duration predictor and text encoder: CPU;
- each vector-estimator call: explicitly mixed, 21 QNN/HTP partitions plus 136 CPU nodes;
- explicit-GELU vocoder: one QNN/HTP partition with CPU fallback disabled.

Across four complete hybrid generations, the ORT profiles record:

- vector estimator: `420` QNN partition events and `2720` CPU events across 20 calls;
- vocoder: four QNN events and zero CPU events;
- all `424` QNN events: RPC, accelerator execution time/cycles, and four-HVX-thread evidence.

This proves physical hybrid execution. It must never be described as full HTP.

## Latency and startup

| Measurement | CPU | Hybrid | Interpretation |
|---|---:|---:|---|
| Session creation | `0.611356 s` | `26.965 s` | hybrid `44.107×` longer |
| First generation after sessions | `5.84446 s` | `4.33056 s` | hybrid `25.903%` lower |
| Warm median | `6.06733 s` | `3.80935 s` | hybrid `2.25798 s` / `37.215%` lower, `1.593×` |
| Setup + first generation | `6.456 s` | `31.296 s` | CPU wins a fresh-process single generation |
| Setup + all four generations | `24.649 s` | `42.590 s` | CPU still wins this measured fresh-process batch |

Hybrid session creation is dominated by vector QNN (`21.9854 s`) and vocoder QNN (`4.74756 s`) setup. QNN partitions, optimizes, compiles, and finalizes graphs; prepares weights and layouts; and establishes RPC/shared buffers. The cost is generally paid once only while sessions remain resident. Dividing additional setup by the observed warm saving gives an illustrative break-even near 12 retained-process generations, not a controlled amortization result.

Campaign caveats: one fresh process per route, CPU first then hybrid, four generations each, non-randomized order, and no explicit thermal telemetry.

## Memory

`ru_maxrss` high-water marks:

| Point | CPU | Hybrid |
|---|---:|---:|
| After sessions | `217420 KiB` | `1028044 KiB` |
| After runs | `459432 KiB` | `1154172 KiB` |

The final hybrid/CPU ratio is `2.512×`. These are process-lifetime peaks, not steady live PSS or complete DSP-private memory. Hybrid retains the ORT CPU graph and fallback route while adding QNN prepared/compiled graph and weight representations, metadata, RPC/shared buffers, detailed profiling state, and possible transient setup allocations.

## Audio evidence

Both outputs are structurally valid, finite, non-silent, unclipped mono PCM16 WAVs with `729746` frames at 44.1 kHz. This does not establish perceptual usability.

The frozen end-to-end numerical gate remains **failed and immutable**:

- cosine: `0.405431`;
- SNR: `-0.592623 dB`;
- normalized RMSE: `1.07061`;
- RMSE: `0.0593432`;
- mean absolute error: `0.0302192`;
- maximum absolute error: `0.641157`.

After the run, Moritz used the randomized E2E A/B report and reported no audible difference between the CPU and hybrid samples. Record this as a comparison observation from one listener and one utterance, not acceptance of either sample's quality. It does not turn the waveform comparison into a numerical pass or identify an operator defect.

Ignored local convenience artifacts:

- `work/e2e/samples/supertonic-m1-cpu.wav` — SHA-256 `7e83537630b3e354f7586b9887f7a8359d62e438c9addeea61d87d878b2a84ff`;
- `work/e2e/samples/supertonic-m1-hybrid-htp.wav` — SHA-256 `9b0d488776b144c972e8be4e9434fac14ce3ceddfcfa5a10d137fca41b772668`;
- `work/e2e/latencies/e2e-latencies.json`;
- `work/e2e/e2e-analysis.json`;
- `work/e2e/e2e-report.html` — SHA-256 `ab7d97a78c818522da83b68d9b026efe75b0402101676d3e4327901be96f2a59`.

The HTML report, WAVs, raw tensors, profiles, models, binaries, and QNN libraries are ignored convenience or restricted evidence, not committed durable dependencies.

## Technical history retained

- A six-node QDQ graph first proved physical HTP execution with fallback disabled.
- ONNX Runtime 1.27.1 crashed in `PadNodeGroupSelector::Check`; the exact upstream fix was retained as [`patches/onnxruntime-a08e17-pad-empty-dq.patch`](patches/onnxruntime-a08e17-pad-empty-dq.patch).
- The explicit-GELU vocoder became fully delegable and physically ran on HTP, but failed its immutable numerical policy. Moritz later heard no difference in its isolated A/B.
- The shape-only vector derivative preserved all source nodes and initializers. Full delegation remained blocked by 136 optimized nodes, so the authorized final vector route was explicitly mixed.
- Vocoder localization narrowed the first observable material boundary to composite embed `Pad → QDQ`; isolated exact-input QDQ was non-material. No defective operator was established.

## Retained local state and safety

Large generated and proprietary state remains ignored beneath `.local/` and `work/`, including the exact patched ORT source/builds, QAIRT libraries, models, fixtures, profiles, raw tensors, and phone logs. Do not commit or publish those files.

All scoped phone directories were removed, cleanup succeeded, and `artifacts/locks/phone.lock` is not held. No root, device tuning, firmware change, or system-library mutation occurred. Any future phone use, Qualcomm login, new terms, consent, or export gate requires fresh explicit authorization.
