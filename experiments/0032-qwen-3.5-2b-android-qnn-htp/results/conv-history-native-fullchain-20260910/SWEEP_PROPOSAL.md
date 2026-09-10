# Next control proposal — source only, not execution approval

## Question

Does the large discrepancy begin when the history quantizer must clip, rather than at an ordinary in-range requantization boundary? The first fixture has only one out-of-range input. Its other 24,575 output values match the full-chain reference within one ULP, while output-only/aligned references disagree at all 6,144 slot-0 values. A range sweep is more discriminating than labeling the selected endpoint as an output-only path.

## Keep fixed

Retain the full-chain graph, history/projection geometry, all four Q/DQ pairs and three exact encoding domains, pinned SDK/backend configuration and zero tensor-fallback/emitted-kernel gates. Do not change precision or bypass a quantizer. Preserve the existing firstcase and all original inputs/oracles unchanged.

Use distinct channels' retained history slot3 (output slot2) for the new sweep, leaving the other slots/projection at the accepted pattern and retaining the original selected outlier as an anchor. Pair repeated values in two disjoint channel ranges to expose any position dependence rather than assuming it away.

## Planned values

The history decoded range is approximately **[-29.8634967804, 22.1318340302]**, while the final output range is approximately **[-29.8633251190, 23.7218952179]**.

- In-range anchors: zero, +0.5, -0.75, +1, a value well below the history upper endpoint, and several ordinary half-step rounding boundaries.
- Float32 neighbors immediately below/at/above the history upper decoded endpoint.
- Float32 neighbors around **upper endpoint + half a history scale**. The decoded endpoint is not the same as the ties-to-even quantizer's first out-of-range integer code; the CPU oracle must retain unbounded rounded code, clipped code and final value for every sample.
- Upper endpoint plus one and two history steps, additional points across the gap, and neighbors below/at the final output ceiling. Keep these upper-side values inside the final output range to isolate intermediate history clipping from final-output clipping.
- Lower-limit controls: neighbors and half/full-step offsets around the history minimum, plus values above the final-output minimum. **Below-history-minimum values are also below the final-output minimum in this encoding set**, so these controls are not clean lower-side isolation; report final-output clipping separately instead of inferring its cause.

Exact FP32 values and their bytes are not materialized by this proposal. Source preparation should construct a compact deterministic list, record the scalar stages and sign/rounding conventions, then retain a new input pack and full CPU/scalar references before execution is considered.

## Required preparation and approval

The current adapter deliberately loads the frozen old inputs. The consumed request `f9ef7075…548e` cannot authorize different values. A new source-reviewed materialization/input binding and request SHA are required; do not edit old helpers or overwrite accepted artifacts to substitute inputs.

Propose at most one new high-level compile (120s) and one runtime load/forward (60s), 240s active total, external STOP/PSI/TERM/grace20/KILL/reap, four threads and low priority. These are planning limits, not permission. A separately reviewed compatible-context reuse route could avoid recompilation, but is neither implemented nor authorized here.

No native execution, output-only/aligned follow-on, retry, model load or phone access is released by this document. First commit and review the current evidence; request the next explicit scope afterward. Even a clipping-correlated result would still not alone identify an internal finalized SDK path, establish an SDK defect, or prove physical/full-model fidelity.
