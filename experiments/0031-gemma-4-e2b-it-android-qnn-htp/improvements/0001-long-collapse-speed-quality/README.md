# Improvement 0001: long-output fidelity and speed

## Boundary

This is a new improvement track. It does not modify, replace, or relabel the completed canonical campaign in commit `37a2953` or its publication in `e91b3f5`.

The accepted route remains the baseline. Any new conversion, host diagnostic, hybrid, or phone run must use a distinct artifact identity and run ID. A hybrid must select and label its backend before a complete logical request; hidden tensor- or provider-level fallback is forbidden.

## Goal

Improve both practical completion speed and long-output fidelity while preserving exact workload identity and honest provider boundaries.

## Plan

1. **Baseline localization — complete.** Quantify repetition onset and periodic structure in all retained QNN long outputs, compare accepted LiteRT GPU/CPU trajectories on the same rendered bytes, and rank causes/candidates without inferring numerical state from text.
2. **Fallback-free HTP precision probe.** Rebuild the narrowest candidate first: identical FP16 value-cache I/O for the three global-attention layers in both AR variants, leaving all compute on HTP. Inspect datatype contracts, conversion count, context size, compilation time, and any host-executable trajectory evidence. Expand to all 15 value caches only if the global-only candidate is insufficient.
3. **Explicit request-level hybrid design.** Specify short/medium on accepted QNN HTP and long on accepted LiteRT GPU. Bind both route setups, tokenizers, memory costs, and provider proof separately. This is a request-level product policy, not fallback.
4. **Divergence instrumentation.** Design bounded capture around generated tokens 64–128 and the stable periodic-loop onset near token 478. Prefer logits or state hashes; do not claim internal divergence from decoded text.
5. **Reviewed physical gate.** Only after a host candidate is committed and reviewed, request phone priority for a distinct bounded run. Preserve every failed attempt and cleanup proof.

## First milestone

[`results/long-collapse-baseline/result.json`](results/long-collapse-baseline/result.json) records:

- all five QNN long outputs are byte-identical and retokenize to the profiled 2,048 tokens;
- the first 128-token window with four-gram unique ratio at or below 0.25 begins at generated token 84;
- an exact nine-token periodic suffix starts at generated token 479 and covers the final 1,570 tokens (174 full cycles plus four tokens);
- the dominant phrase pattern occurs 215 times;
- accepted LiteRT GPU and CPU outputs both EOS-stop at 756 tokens, have no repeated periodic suffix, and pass sanity;
- QNN and LiteRT differ at the first common output word, while LiteRT GPU and CPU emitted-token trajectories differ at token 6 despite both staying coherent. Therefore text alone cannot localize a numerical logit/state divergence;
- collapse starts around absolute context position 2,012 and stable periodic looping around 2,407, while generation ends at 3,977. Crossing the 4,096 boundary is not the trigger.

## Candidate order

1. **Request-level hybrid:** HTP for short/medium, LiteRT GPU for long. Existing accepted medians predict no short/medium regression and a 59.1% lower long completion time, while replacing the repetitive 2,048-token output with a sensible 756-token EOS response. The cost is a second explicit route setup and memory footprint.
2. **HTP-only global-value FP16:** change only `past_value_{4,9,14}` cache I/O to identical FP16 across AR1/AR128. Storage width remains 16 bits and conversion removal could avoid a speed penalty, but this is a hypothesis requiring measurement.
3. **HTP-only all-value FP16:** broaden to all 15 value caches if necessary.
4. **Normalization/fusion variant:** investigate the expanded float normalization components and value conversion path if cache precision alone does not fix the trajectory.

No phone access or model conversion occurred in the first milestone.
