# Current plan

## Goal

Select and productize a local Android text-to-speech route for a NotebookLM-like listening experience. Pleasant, natural long-form speech is the primary goal. A convincing two-speaker conversation is useful but optional; a strong narrator or persistent voices generated turn by turn can meet the goal.

## Evidence language

Keep these claims separate:

1. **Technical execution** — the declared route completed on the stated runtime/device with the required provider evidence.
2. **Structurally valid WAV** — the file met format, length, finiteness, silence, and clipping checks.
3. **Objective/descriptive comparison** — numerical or acoustic metrics passed or failed a named policy.
4. **Moritz listening verdict** — only explicit feedback can accept or reject the exact reviewed route and WAV hash.

None implies another. A route-specific verdict never becomes a model-family verdict. Missing evidence remains null with a reason.

## Comparable benchmark contract

New comparable routes use [`protocols/android-tts-benchmark/transcript.txt`](../protocols/android-tts-benchmark/transcript.txt): canonical v2, 226 bytes, no trailing newline, SHA-256 `424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67`.

Follow [the Android TTS benchmark skill](../.agents/skills/android-tts-benchmark/SKILL.md): report setup separately, one first complete generation, at least five additional same-session warm generations with complete state reset, actual emitted-duration RTF, memory semantics, thermal/runtime/provider provenance, a validated hashed WAV, and exact listening status.

Historical legacy-v1 and model-specific-text routes remain valid evidence but are not text-matched to canonical v2.

## Current product direction

Moritz's current favorite is the Supertonic 3 official-source, stable-Softplus, all-HTP route from experiment [`0011`](../experiments/0011-supertonic-official-fp32-phone-comparison/). Its exact legacy-v1 HTP WAV was accepted, and Moritz finds it somewhat more natural than Pocket.

Measured experiment-0011 properties:

- setup: `22.8147 s`;
- warm median RTF: `0.170316`;
- process VmHWM: `1,407,393,792 B`;
- all four neural components ran fallback-disabled on physical HTP;
- the route failed its prospective numerical policy, despite its accepted listening result.

Supertonic is therefore the leading production candidate, but the product decision remains open until its canonical-v2 HTP route and production startup behavior are measured. CPU remains useful as a low-setup fallback for short requests; HTP is favored for longer generation when session reuse amortizes setup.

## Active work

### 0017 — Kokoro canonical-v2 QNN/HTP

Experiment [`0017`](../experiments/0017-kokoro-onnx-qnn-htp-android/) has a complete official-frontend canonical-v2 CPU/export/decomposition proof:

- tokens `[1,235]`, style row 232;
- 15.05-second CPU oracle;
- fixed FP32 compatibility graph;
- 18 stages covering all 1,685 nodes;
- bit-exact staged CPU recomposition.

The first canonical fallback-disabled host QNN batch completed stages 1–15. A requested WSL restart externally interrupted stage 16 during graph sequencing at 12%; stage 16 did not finalize or execute, stages 17–18 were not attempted, and no canonical QNN audio exists. This is not an OOM or stage failure.

Next gate:

```bash
RUN_ID=canonical-v2-rerun \
  experiments/0017-kokoro-onnx-qnn-htp-android/host/run_canonical_v2_staged_host_qnn.sh
```

Reconstruct and hash-check ignored assets using the experiment's [`REPRODUCING.md`](../experiments/0017-kokoro-onnx-qnn-htp-android/REPRODUCING.md). Restart from stage 1; never resume the partial stage-16 attempt. Phone work is forbidden until all 18 host stages execute fallback-disabled with zero CPU events and structurally valid final audio.

### 0022 — Supertonic precompiled-context startup

Experiment [`0022`](../experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/) compares two matched all-HTP startup routes:

1. source ONNX compiled/finalized by QNN at runtime;
2. precompiled external QNN contexts loaded through ORT EPContext.

The purpose is to determine whether production-style contexts materially reduce the experiment-0011 `22.8147 s` setup. Both arms require at least three cold processes, per-session/total readiness, first plus five warm generations, memory/thermal/package-size evidence, fail-closed provider proof, physical RPC/accelerator/cycle/HVX evidence, and exact output/listening handling.

The first design gate is unresolved: frozen experiment-0011 graphs require wrapped `T239/L238`, while canonical-v2 wraps naturally to `T235`. Prove that four masked padding positions preserve canonical semantics and the exact graph identities, or report the constraints incompatible. Never substitute the legacy transcript or silently regenerate differently shaped graphs. Continue from the experiment's [`PLAN.md`](../experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/PLAN.md).

## Completed routes carried forward

- **Pocket canonical v2:** experiment [`0014`](../experiments/0014-pocket-fp-onnx-qnn-htp/) completed accepted Android CPU and physical fallback-disabled HTP routes. Warm median RTF is `0.414234` CPU and `0.181643` HTP; physical proof is 344 QNN / 0 CPU events with matching RPC/accelerator/cycle/HVX records. This is a fixed-Alba route, not voice cloning.
- **Supertonic canonical-v2 CPU:** experiment [`0021`](../experiments/0021-supertonic-canonical-v2-android-cpu/) completed at warm median RTF `0.395615`; its exact WAV was accepted “good.”
- **Supertonic historical refresh:** experiment [`0020`](../experiments/0020-historic-android-benchmark-refresh/) reproduced the legacy-v1 CPU route at warm median RTF `0.393086`; it remains a nested historical remeasurement, not canonical v2.
- **MOSS canonical-v2 HTP feasibility:** experiment [`0019`](../experiments/0019-moss-tts-nano-qnn-htp-android/) passed CPU equivalence and host QNN/context gates but failed at physical QNN `CreateDevice` before session assignment or inference. It has no HTP WAV, RTF, memory result, or listening verdict.

The complete normalized Android evidence is in the [benchmark dashboard](android-benchmarks/index.html) and its [registry](android-benchmarks/registry.json).

## After active accelerator work

Run a matched longer-form listening bake-off among accepted Supertonic, Pocket, Kokoro if it becomes viable, and any other technically complete route. Evaluate:

- sustained naturalness and listener fatigue;
- paragraph/chapter seams and prosody;
- multiple voices if dialogue is required;
- cold startup, session lifetime, storage, memory, thermal behavior, and battery;
- a practical app policy such as CPU for short previews and persistent HTP sessions for long documents.

Do not choose a production route from RTF alone. Moritz's listening preference and deployment practicality are both required.
