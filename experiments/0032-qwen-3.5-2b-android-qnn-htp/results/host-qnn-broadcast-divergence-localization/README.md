# Host QNN first-divergence localization

The exact PTE can execute through QNN's x86 backend using the same serialized SM8550/v73 contexts. This provides a host-only way to compare QNN outputs directly against the saved PT2E QDQ graph without another phone run.

At token position zero, with every explicit state input zero, the exact QNN route is already badly divergent. Its logits are finite but 39,209 vocabulary entries share the exact maximum. More importantly, the first layer's causal-convolution state remains closely aligned with QDQ (cosine 0.9999996), while its recurrent state is the first large mismatch (cosine 0.0064 and about 118× the QDQ L2 norm). This rules out cross-token runner state transport and later layers as the first cause.

## Minimal reproduction and fix

A synthetic one-layer W4A16 probe reproduced the recurrent-state failure. The correct QDQ outer product contained 128 nonzero values. QNN wrote only 16 values when lowering the implicit broadcast multiplication `[B,H,K,1] * [B,H,1,V]`, giving cosine 0.353553.

The adapter now explicitly expands both operands to identical `[B,H,K,V]` geometry before multiplication, and does the same for the recurrence's other broadcast multiplies. With this change:

- QDQ semantics are unchanged.
- QNN writes all 128 recurrent-state values.
- Recurrent-state cosine is 1.0 with maximum absolute error `4.13e-7`.
- Final-logit cosine is approximately 1.0 with maximum absolute error `2.96e-5`.

This identifies implicit QNN elementwise broadcasting in the Gated Delta recurrence as the first divergence and demonstrates a bounded fix.

## Claim boundary

All evidence here is host-only QNN x86 simulation. The exact 24-layer model still needs recompilation and host validation with explicit broadcasts. There is no revised physical-output, campaign, or performance claim, and no phone run is authorized.
