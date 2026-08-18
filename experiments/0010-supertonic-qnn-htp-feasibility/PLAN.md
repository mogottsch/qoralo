# Experiment 0010 execution plan

## Goal

Select and validate a text-to-speech model that can become the local voice of a future NotebookLM-like Android experience. It should sound pleasant and natural over sustained listening, with podcast-like delivery rather than merely intelligible speech.

A convincing two-speaker conversation is desirable but not required. A strong narrator or persistent voices generated turn by turn can also meet the goal if the deployment remains practical on a modern phone.

The current model is Supertonic 3, selected from the completed listening and Android experiments. The current runtime question is whether Qualcomm HTP acceleration improves the working CPU deployment enough to justify its extra complexity.

## Phase map

These phases belong to experiment [`0010: Supertonic QNN/HTP feasibility`](README.md). Detailed evidence and resume instructions live in the experiment [`README`](README.md), [`HANDOFF`](HANDOFF.md), and [`phone checkpoint`](results/phone-probe-checkpoint.json).

| Phase | Status | Purpose |
|---|---|---|
| Phase 1: vocoder HTP feasibility | **Complete — bounded negative result** | Physical HTP execution succeeded, but the frozen full-tensor numerical gate failed. |
| Phase 2: vector-estimator value | **Not started — closed by Phase 1 failure** | Do not test the vector estimator from this rejected vocoder path. |
| Phase 3: complete accelerated synthesis | **Not started — not justified** | The incorrect vocoder output blocks accelerated end-to-end synthesis. |
| Phase 4: deployment decision | **Complete for this route — retain CPU** | Keep the working CPU deployment; this experiment supports no HTP speedup claim. |

## Current position

| State | Work item | Result or gate |
|---|---|---|
| **Done** | Tiny physical-HTP control | A six-node QDQ graph executed on the S23 Ultra's HTP v73 with CPU fallback disabled. This proves the device path only. |
| **Done** | Patched host runtime | ONNX Runtime 1.27.1 with the Pad-selector backport was rebuilt against QAIRT 2.49 and reproduced the retained library hash. |
| **Done** | Models and fixtures | Official Supertonic INT8 models, deterministic fixtures, and the fixed and folded vocoder derivatives were restored and hash-verified. |
| **Done** | Folded-vocoder negative gate | The folded vocoder exposes 338 supported nodes and eight unsupported `Erf` nodes. Session creation is rejected with fallback disabled; no inference runs. |
| **Done** | Explicit GELU derivative | Eight verified standard GELU decompositions were replaced by explicit `com.microsoft.Gelu`; the full 731,136-element CPU output is bit-identical to the folded/fixed reference. |
| **Done** | Explicit GELU host gate | With CPU fallback disabled, patched host ORT assigns the complete optimized graph to one QNN partition (304/304 nodes) and initializes successfully. This is host capability evidence only. |
| **Done** | Android runtime build | Patched arm64-v8a/API 27 ONNX Runtime + QNN was rebuilt, validated, and reused for the scoped physical explicit-GELU vocoder probe. |
| **Done** | Scoped physical HTP execution | The exact authorized S23 Ultra executed three vocoder iterations with fallback disabled. Detailed profiles contain RPC, QNN accelerator, accelerator-cycle, and four-HVX-thread evidence. |
| **Failed** | Frozen physical numerical gate | All 731,136 finite samples were compared, but cosine `0.865454`, SNR `5.716 dB`, max error `0.595960`, mean error `0.012167`, and RMSE `0.029311` fail the predeclared limits. Output and audio are rejected. |
| **Done** | Cleanup and stop gate | The unique scoped device directory was removed, the phone lock was released, and no vector-estimator work began. |
| **Done** | Layer-level numerical bisection | The first material observable boundary is the composite embed `Pad → QDQ` transition. An exact-real-input QDQ microprobe is non-material, while exposing raw embed `Conv` breaks full delegation; the evidence is fusion/context dependent and does not establish an operator defect. |

The current boundary is therefore clear: **the explicit-GELU vocoder physically executed on the SM8550 HTP with CPU fallback disabled, but its output failed the frozen numerical policy and is not accepted audio. No same-device CPU baseline was collected, so no speedup claim is supported.**

When a phase finishes, its detailed result stays in experiment `0010`, its condensed outcome moves to [`docs/history.md`](../../docs/history.md) and the [history HTML](../../docs/history.html), and it is removed from this plan.

## Phase 1: establish vocoder HTP feasibility

The former blocker was eight `Erf` nodes inside standard decomposed GELU patterns. A narrow, source-hash-locked rewrite replaced only those verified patterns with explicit `com.microsoft.Gelu`; it passed bit-identical CPU equivalence and complete fail-closed host QNN assignment. The subsequent physical run proved accelerator execution but failed numerical correctness, producing the bounded negative result for this route.

Completed preparation:

- rebuilt and validated the patched host runtime;
- restored the official models, fixtures, and fixed-shape derivatives;
- reproduced the fail-closed support report;
- rebuilt the patched Android arm64 runtime and runner;
- re-established authorized ADB transport without accessing phone data.

Completed derivative and host gates:

- created a separately labeled derivative that replaces only the eight verified `Div → Erf → Add → Mul → Mul` patterns with explicit `com.microsoft.Gelu` nodes;
- recorded all replacements, exact float32 constants, source/output hashes, fixed shapes, and consumer-safety checks;
- produced a bit-identical full-tensor result against the folded/fixed vocoder using the same patched ORT 1.27.1 CPU runtime;
- initialized the host QNN session with CPU fallback disabled, one complete QNN partition, and no unsupported operators.

Physical result:

- exact authorized device identity passed and all staging remained inside one unique `/data/local/tmp` directory;
- patched ORT/QNN created the session in `4.82669 s` and completed three runs with CPU fallback disabled;
- first inference was `0.313119 s`; the two-run warm mean was `0.198222 s`;
- detailed profiles recorded QNN accelerator execution of `297517`, `186278`, and `185925` µs, corresponding RPC execution, accelerator cycles, and four HVX threads on every run;
- the physical tensor was finite and had the expected `[1,731136]` shape, but failed every non-finite-independent frozen metric: cosine `0.865454 < 0.995`, SNR `5.716 < 20 dB`, max absolute error `0.595960 > 0.05`, mean absolute error `0.012167 > 0.002`, and RMSE `0.029311 > 0.005`;
- the scoped device directory was removed and the repository phone lock was released.

**Completed as a bounded negative result:** physical HTP execution is proven, but numerical correctness is rejected. Do not loosen the policy, accept the output as audio, rerun this derivative, start the vector estimator, or claim speedup/end-to-end success.

### Layer-level localization

A scoped coarse-to-fine diagnostic campaign used the unchanged latent fixture, patched runtime, fail-closed QNN sessions, and predeclared intermediate rules. These rules classify localization evidence only; they do not replace final-waveform policy SHA `7116c522…`, which remains failed.

Facts:

- Full-output cross-correlation finds a best lag of exactly zero within ±4,096 samples, so a simple alignment shift does not explain the rejected waveform.
- Error is temporally concentrated and grows with reference amplitude, but neither fact identifies an operator.
- The fully delegated coarse wave first crosses the material rule between the predecoder affine output and the embed Conv output after QDQ.
- The fully delegated fine boundaries are non-material through embed `Pad`, then first become material after embed input QDQ: normalized RMSE rises from `0.000294` at `Pad` to `0.010376` after QDQ; post-QDQ cosine remains `0.999946`.
- Exposing the raw embed Conv output changes QNN fusion/assignment. The fail-closed session rejects that tap before inference, so it supplies no numerical evidence and cannot isolate Conv-before-QDQ.
- An exact-input two-node `QuantizeLinear → DequantizeLinear` microprobe uses the actual CPU embed-Pad tensor, scale `0.007331503`, and zero point `102`. It fully executes on physical HTP but is non-material: normalized RMSE `0.005996`, cosine `0.999982`, SNR `44.442 dB`, and max error `0.004008`.

Bounded conclusion: **the narrowest observable composite interval is embed `Pad → QDQ`, but isolated QDQ does not reproduce the material prefix result. The leading evidence is fusion/context-dependent quantization behavior or amplification of a small upstream perturbation, not a confirmed QDQ, Conv, GELU, or general QNN implementation defect.** Physical profiles do not expose definitive intermediate HTP precision, so reduced-precision accumulation remains possible but unconfirmed.

All diagnostic phone stages were unique experiment-0010 paths, all cleanup attempts succeeded, and the phone lock was released. No vector-estimator work began.

## Phase 2: test vector-estimator value

This phase is closed because Phase 1 did not pass numerical correctness. Do not start the vector estimator from this derivative result. If a future separately authorized experiment revisits acceleration, it must define a new rationale and gates rather than treating physical execution alone as success.

The previously planned work was to test the exact released vector-estimator graph first and preserve any unsupported-operator result before considering a derived graph.

Measure graph finalization, first and warm execution, tensor transfers, memory, partition coverage, and numerical error. CPU fallback remains disabled for the HTP session.

**Complete when:** physical HTP execution and numerical correctness are proven, and the measured warm benefit is large enough to justify startup, transfer, package, and integration costs. If it runs but offers no practical benefit, stop the accelerator path.

## Phase 3: run complete accelerated Android synthesis

The component result does not justify integration, so this phase remains unstarted. Build no accelerated hybrid from the rejected physical output.

The previously planned integration contract was to build the smallest explicit hybrid path that preserves complete Supertonic behavior.

- Use the frozen experiment `0008` transcript and SID 5 / M1 English voice.
- Run text preparation, duration prediction, text encoding, five-step denoising, vocoding, and audio assembly without fixture substitution.
- Keep orchestration and non-targeted graphs explicitly on CPU.
- Keep fallback disabled inside every component claimed to run on HTP.
- Retain profiles proving HTP execution during the complete run.
- Compare final audio, cold and warm timing, callback behavior, memory, and package cost with the experiment [`0008` CPU baseline](../0008-sherpa-onnx-android-tts-benchmark/).

**Complete when:** Android produces a complete valid WAV, HTP use is proven in context, audio and numerical gates pass, and the equivalent CPU comparison shows whether acceleration helps.

## Phase 4: make the deployment decision

The completed experiment selects the reproducible negative result for this HTP route: retain the simpler Supertonic CPU deployment. The explicit-GELU vocoder reaches physical HTP, but its numerical error is unacceptable and no same-device CPU baseline exists from which to claim speedup.

Judge the result against the listening goal, not accelerator novelty. Pleasant speech, sustained generation, latency, memory, storage, thermals, and integration cost all matter. If CPU already meets the practical target, reject an HTP path that adds complexity without a useful listener-facing improvement.

**Complete when:** the experiment, history, README, and dashboard state one current deployment conclusion and link back to the canonical evidence.
