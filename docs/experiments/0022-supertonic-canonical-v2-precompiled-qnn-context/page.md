---
experiment: 0022-supertonic-canonical-v2-precompiled-qnn-context
status: stopped
summary: The experiment aimed to shorten Supertonic's QNN startup with precompiled contexts, but the current benchmark text did not fit the accepted fixed-shape graphs without changing their meaning. Work stopped before context generation or phone testing.
registry: 0022-supertonic-t239-padding-blocked
---

# Experiment 0022 — Supertonic canonical-v2 precompiled QNN context

## Experiment description

Supertonic could run on QNN, but compiling its model sessions at startup was slow. Experiment 0022 was meant to test the obvious improvement: compile those sessions ahead of time, load the precompiled contexts on the phone, and compare that startup with the normal source-ONNX path using the project's current benchmark text.

Before spending time generating contexts or running the phone, the experiment checked whether the accepted fixed-shape Supertonic graphs could represent that newer text without changing the calculation. They could not. The compatibility check therefore answered an earlier, more basic question and stopped the planned startup comparison before it began.

The intended comparison had two matched arms: creating four sessions from source ONNX, with QNN compilation inside startup, and loading four independently validated external contexts, with context generation reported as a separate offline cost. Both were meant to use the accepted stable-Softplus all-HTP lineage with CPU fallback disabled.

Before any context or Android work, the route had to reconcile two frozen requirements. Canonical v2 plus the complete `<en>…</en>` wrapper produces a text extent of 235 positions, while the historical accepted graph identities are specialized to 239. The predeclared policy therefore tested whether four right-side filler positions with a zero mask could preserve the canonical dynamic-T235 calculation without changing the accepted T239 graph hashes.

This was a host ONNX Runtime 1.27.1 CPU compatibility test, not QNN assignment or phone HTP evidence. It compared the dynamic-T235 canonical oracle with a dynamic-T239 masked input, then checked whether the exact frozen T239 duration and text graphs reproduced that padded T239 calculation. The scope and stop conditions are in the [experiment contract](../../../experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/protocol/experiment-contract.json) and [padding compatibility policy](../../../experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/protocol/padding-compatibility-policy.json).

## Progress

1. **August 21, 2026: comparison contract prepared.** The two startup arms, graph identities, canonical transcript, runtime and QAIRT baseline, provider restrictions, phone identity, and evidence gates were frozen. Context generation was explicitly separated from arm-B startup.
2. **August 22, 2026: exact graphs reconstructed.** The duration, text, stable-Softplus vector, and vocoder graphs were reconstructed locally and verified against the required hashes. The compatibility inputs, T235 oracle, filler probe, metrics, tolerances, and mandatory stop action were fixed before the proof ran.
3. **August 22, 2026: first gate failed.** Zero masks made all seven tested filler IDs byte-identical, so filler payload was irrelevant. Increasing the sequence extent itself was not neutral: duration and the semantic text-embedding prefix moved beyond every locked limit.
4. **August 22, 2026: route stopped.** The exact frozen T239 graphs reproduced the altered dynamic-T239 computation within specialization tolerances, not the canonical dynamic-T235 oracle. Under the frozen policy, runner implementation, EPContext work, output generation, and phone access became forbidden.

The [terminal plan](../../../experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/PLAN.md), [preflight state](../../../experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/results/preflight-state.json), and [machine-readable compatibility proof](../../../experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/results/t235-t239-masked-padding-compatibility.json) preserve the negative result and the abandoned route. Reproducing the proof is allowed; continuing past its failed gate is not part of experiment 0022.

## Results

The gate produced a useful terminal result. Canonical T235 duration was **15.8623657 seconds**; dynamic masked T239 duration was **15.6378775 seconds**, for absolute change **0.2244883** against a limit of `0.00001`. Across the first 235 text-embedding positions, maximum absolute change was **0.1110139**, RMSE was **0.00629053**, and cosine similarity was **0.99988716**. All failed their predeclared limits.

| Evidence class | What 0022 established |
|---|---|
| Technical execution | A host CPU compatibility proof ran. No route runner, QNN session, EPContext, Android process, or physical accelerator execution existed. |
| Structural audio | Unavailable. The stop occurred before generation, so no PCM or WAV exists. |
| Numerical/acoustic comparison | Filler-ID invariance passed, but T235-to-T239 semantic equivalence failed. The exact frozen graphs matched the changed T239 calculation. |
| Exact-sample listening | Unavailable. No sample exists, and no verdict from another Supertonic WAV transfers to this route. |

The result is narrow: **exact canonical-v2 T235 semantics and these exact frozen T239 graph identities are jointly incompatible under the tested masked-padding policy**. It does not show that Supertonic, ONNX Runtime, QNN, HTP, Android, or precompiled contexts are generally incompatible.

No startup latency, RTF, memory figure, provider assignment, context size, physical RPC/accelerator/cycle/HVX trace, or listening evidence is available. Those values are unavailable because the required first gate stopped the work, not because they measured zero. Using the legacy transcript, generating differently hashed graphs, or labeling masked-T239 output as exact canonical-v2 output would have changed the frozen experiment rather than resolved it.
