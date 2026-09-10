# Candidate persistent-state encoding alignment — hypotheses only

**Not implemented, not calibrated, not compiled, not approved for execution.** Keep the accepted artifacts and physical baseline unchanged. The purpose is to identify bounded candidates for later review, not to conclude that convolution behavior explains all logit drift.

## What is worth testing later

1. **Prioritize the eight interfaces with observed p0 next-input incompatibility**, rather than changing all48 at once:
   - K layers3,7,11 / states3,7,11;
   - V layers3,7 / states27,31;
   - convolution layers0,2,10 / states24,26,34.
   These priorities come from actual saved returned values and their destination input domains. Their relative counts are not importance scores or logit-attribution percentages. The large K/V overhang examples deserve attention alongside the original conv anchor.
2. **Shared persistent-interface calibration/encoding** is one candidate. Jointly observe the values read and written across a particular state interface, then use a compatible shared domain while preserving W4A16 precision, model weights, state ABI and tensor-compute delegation. This could remove scalar re-clipping of representable carried values. It may change rounding/resolution elsewhere, and native behavior has not been established for a changed encoding.
3. **Input-only coverage expansion** is another candidate to compare offline. Merely copying the output scale/zero point can shrink coverage on the opposite side; require the revised input range to cover the relevant current input range as well as transported outputs. A range union at fixed16-bit codes changes the quantization step, may reduce resolution and may still round endpoints outside the intended coverage. Any concrete scale/zero-point pair requires its own code-grid and saved-value checks; none is prescribed here.

## Limits that prevent an unjustified fix

- Identical boundaries are sufficient for scalar code-grid idempotence only under the explicitly checked QDQ arithmetic; **interval containment alone is not byte identity**. Grid counts are not probabilities.
- The twelve K/V outputs are new-token slices inserted at positions/axes3 or2, not full-cache replacements. Align the transported value domain without changing cache ownership, insertion order, mask, RoPE or attention layout.
- Input direct quantizers, DQ consumers and immediate output-producer domains are explicit here, but internal consumers or native finalized/fused graph behavior can impose additional constraints. Do not silently rewrite every quantizer reachable from a state name or infer native encoding metadata from the QDQ map.
- Eight recurrent interfaces have theoretical clipping exposure but no such values in these p0/p1 samples. That neither justifies a blanket recurrent change nor proves long-sequence safety. Rounding and non-state operators remain separate possible contributors.
- QNN's frozen-PTE sweep did **not** match a universal output-only path and showed in-range/half-step differences. Removing an offline QDQ clipping opportunity is not evidence that an SDK issue or model fidelity problem is fixed.

## A possible future validation sequence, requiring new approval

- First compare candidate domains with existing domains by saved-value/code-grid arithmetic, explicitly measuring coverage gained/lost and changed rounding on both state reads and writes. Keep baseline copies and separate candidate names.
- Review per-consumer propagation and Q/DQ placement in source before creating a new graph. Do not create float/FP16 islands, CPU casts or tensor fallback to obtain delegation.
- Only after a separately released compilation/execution plan, use bounded weight-free controls and later same-position/same-input model diagnostics. Retain raw outputs and exact source/encoding/PTE identities. A new PTE introduces a compiler confound; do not present it as inputs-only reuse of the frozen sweep artifact.
- Any eventual model evaluation must separate FP32 fidelity, own-QDQ agreement, state-feedback effects, native runtime behavior, physical execution and the canonical campaign. Neither a better synthetic range match nor a handful of p0/p1 values is a campaign or root-cause result.

**Current next action is review of this audit, not any step above. No model/native/phone call is authorized.**
