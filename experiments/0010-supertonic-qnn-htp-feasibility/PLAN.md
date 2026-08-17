# Experiment 0010 execution plan

## Goal

Select and validate a text-to-speech model that can become the local voice of a future NotebookLM-like Android experience. It should sound pleasant and natural over sustained listening, with podcast-like delivery rather than merely intelligible speech.

A convincing two-speaker conversation is desirable but not required. A strong narrator or persistent voices generated turn by turn can also meet the goal if the deployment remains practical on a modern phone.

The current model is Supertonic 3, selected from the completed listening and Android experiments. The current runtime question is whether Qualcomm HTP acceleration improves the working CPU deployment enough to justify its extra complexity.

## Phase map

These phases belong to experiment [`0010: Supertonic QNN/HTP feasibility`](README.md). Detailed evidence and resume instructions live in the experiment [`README`](README.md), [`HANDOFF`](HANDOFF.md), and [`phone checkpoint`](results/phone-probe-checkpoint.json).

| Phase | Experiment | Status | Purpose |
|---|---|---|---|
| Phase 1: vocoder HTP feasibility | [`0010`](README.md) | Active | Make the vocoder run wholly on physical HTP and determine whether its output is correct. |
| Phase 2: vector-estimator value | [`0010`](README.md) | Gated by Phase 1 | Test the repeatedly invoked component most likely to produce a useful acceleration benefit. |
| Phase 3: complete accelerated synthesis | [`0010`](README.md) | Gated by Phases 1 and 2 | Integrate only the justified HTP components and generate a complete Android WAV. |
| Phase 4: deployment decision | [`0010`](README.md) | Gated by Phase 3 or a conclusive negative result | Decide whether CPU or a CPU/HTP hybrid should remain the technical default. |

When a phase finishes, its detailed result stays in experiment `0010`, its condensed outcome moves to [`docs/history.md`](../../docs/history.md) and the [history HTML](../../docs/history.html), and it is removed from this plan.

## Phase 1: establish vocoder HTP feasibility

The active blocker is eight `Erf` nodes inside standard decomposed GELU patterns. The patched ONNX Runtime 1.27.1 host build avoids the earlier Pad selector crash but still rejects the vocoder when CPU fallback is disabled.

Next steps:

1. Create a separately labeled derivative that replaces only the eight verified `Div → Erf → Add → Mul → Mul` patterns with explicit `com.microsoft.Gelu` nodes.
2. Record every replacement, transformation command, model hash, and fixed tensor shape.
3. Compare the derivative with the fixed released-vocoder derivative on the same CPU runtime.
4. Freeze the numerical and audio acceptance thresholds before inspecting HTP output.
5. Require the patched host QNN session to initialize with CPU fallback disabled.
6. Incrementally relink the preserved Android runtime with the accepted ONNX Runtime patch.
7. Run the vocoder on the Galaxy S23 Ultra with detailed HTP profiling.
8. Record session creation, first and warm execution, memory, output validity, numerical comparison, and relevant artifact hashes.

**Complete when:** the vocoder executes on physical HTP with fallback disabled, profiling proves accelerator execution, output passes the frozen numerical gate, and cold and warm measurements are complete.

## Phase 2: test vector-estimator value

Start only after Phase 1 passes. Test the exact released vector-estimator graph first and preserve any unsupported-operator result before considering a derived graph.

Measure graph finalization, first and warm execution, tensor transfers, memory, partition coverage, and numerical error. CPU fallback remains disabled for the HTP session.

**Complete when:** physical HTP execution and numerical correctness are proven, and the measured warm benefit is large enough to justify startup, transfer, package, and integration costs. If it runs but offers no practical benefit, stop the accelerator path.

## Phase 3: run complete accelerated Android synthesis

Start only when the component results justify integration. Build the smallest explicit hybrid path that preserves complete Supertonic behavior.

- Use the frozen experiment `0008` transcript and SID 5 / M1 English voice.
- Run text preparation, duration prediction, text encoding, five-step denoising, vocoding, and audio assembly without fixture substitution.
- Keep orchestration and non-targeted graphs explicitly on CPU.
- Keep fallback disabled inside every component claimed to run on HTP.
- Retain profiles proving HTP execution during the complete run.
- Compare final audio, cold and warm timing, callback behavior, memory, and package cost with the experiment [`0008` CPU baseline](../0008-sherpa-onnx-android-tts-benchmark/).

**Complete when:** Android produces a complete valid WAV, HTP use is proven in context, audio and numerical gates pass, and the equivalent CPU comparison shows whether acceleration helps.

## Phase 4: make the deployment decision

Choose the result supported by the completed experiment:

- keep the simpler Supertonic CPU deployment;
- use the measured CPU/HTP hybrid because its benefit justifies its cost; or
- stop HTP work with a reproducible negative result.

Judge the result against the listening goal, not accelerator novelty. Pleasant speech, sustained generation, latency, memory, storage, thermals, and integration cost all matter. If CPU already meets the practical target, reject an HTP path that adds complexity without a useful listener-facing improvement.

**Complete when:** the experiment, history, README, and dashboard state one current deployment conclusion and link back to the canonical evidence.
