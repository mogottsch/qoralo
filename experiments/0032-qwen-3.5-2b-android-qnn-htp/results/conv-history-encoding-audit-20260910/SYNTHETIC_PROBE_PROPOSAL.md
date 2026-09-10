# Proposed minimal lowering/control probe — not executed

## Question

Does the accepted ExecuTorch/QNN lowering stack preserve the three explicit history encodings, or alter their effective range before/inside QNN optimization?

The scalar audit proves QDQ input clipping plus requantization. The current QNN endpoint is consistent with a wider effective path but does not prove one. A tiny probe can distinguish these without loading or recompiling the 24-layer model.

## Minimal graph

Use weight-free history and current-projection inputs, retaining the real boundary geometry:

- history `[1, 6144, 1, 4]` (98,304 bytes in float32);
- current projection `[1, 6144, 1, 1]` (24,576 bytes);
- set one retained-history value at channel 6053/slot 3 to `23.721895217895508`; keep other inputs zero or bounded small controls;
- apply the three fixed Q/DQ encodings from `qdq-metadata-trace.json`, concat and `slice[-4:]`;
- return the history result, with optional tiny intermediate taps.

No model weights or private calibration are needed. This is a **synthetic boundary probe**, never an exact-model benchmark.

## Planned variants

1. Full explicit input→concat→output encoding chain; scalar/PyTorch reference should produce 22.1315498352 at the retained slot.
2. Output-only encoding baseline; expected about 23.7218952179.
3. Aligned-encoding control, using the same fixed encoding at all three boundaries, to test whether the discrepancy depends on range transitions.

Keep these variants separate and retain every result/failure. Do not change the model's calibration recipe or promote a synthetic result to model fidelity.

## Evidence needed before attribution

After a separate compile/runtime release, lower only the tiny graphs through the same SM8550/v73 stack and require zero nondelegated tensor compute. Capture the pre-lowering QDQ metadata, post-pass tensor attributes and actual QNN tensor encodings **before finalization**, plus any available finalized metadata and output hashes.

- If the narrow encoding is already altered before SDK finalization, localize the frontend pass/wrapper transition.
- If encodings remain exact into QNN but runtime output changes, investigate SDK optimization/quantization semantics rather than asserting frontend omission.
- A direct tiny QNN graph may be a subsequent control if the frontend comparison remains ambiguous; it is not authorized here.

The existing log shows that an input Quantize node was constructed. The probe must account for that fact, not assume the node was absent.

## Gate

This file is a proposal only. No new compile, QNN/model runtime call, or phone access has occurred. Review source/variant/encoding-capture details and a small host budget before execution. The exact model, repaired physical baseline, controlled input pack and all protected evidence remain unchanged.
