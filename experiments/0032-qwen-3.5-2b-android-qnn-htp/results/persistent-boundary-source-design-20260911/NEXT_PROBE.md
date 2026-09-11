# Next decision: one paired K-cache consumer probe, not an execution release

**Proposed only. No helper, input pack, export, compiler request, context or execution release has been created for this probe.** Pi decides whether to authorize preparation and the separately bound execution. No reviewer replacement is assigned; Nik is not involved.

## Question and discriminating construction

Does an isolated native K-cache consumer retain the incoming narrow input-QDQ behavior for the saved state3 over-range anchor, or does its effective output instead resemble direct quantization into the wider Cat domain? State15 provides a same-layout clean-input control. This tests an effective conversion path in a new synthetic graph, **not finalized internals or the full model's logits**.

Use two independent branches in one weight-free module:

```
for j in {state3, state15}:
    old = QDQ(cache_j, input_domain_j)
    new = QDQ(new_key_j, returned_key_domain_j)
    joined = cat((old, new), dim=-1)
    output_j = QDQ(joined, cat_domain_j)
```

All three domains per branch come from the retained selected source records. The returned-key and Cat domains are equal for each selected layer. Input caches retain `[1,2,256,4095]`, new keys `[1,2,256,1]`, outputs `[1,2,256,4096]`. No slicing, convolution, attention, RoPE, learned weights, calibration or logits. The Cat is deliberately exposed as a float output; this changes the surrounding full-model graph and may change fusion. It must not be called a capture of the original model's internal tensor.

The one proposed fixed input pack, to be materialized/hash-bound only after approval:

- Four FLOAT32 arrays, otherwise positive zero.
- State3 cache `[0,1,24,0]` = exact saved QDQp0 anchor10.028990745544434; `[0,0,0,0]` =1.0 as an in-range control within the same branch.
- State15 cache `[0,1,24,0]` =1.0; both new-key arrays remain zero.
- This is a synthetic sparse cache, not a reconstructed full historical state or model input. The state3 anchor's provenance is retained; the control values are declared synthetic.
- Inputs total16,777,216bytes, outputs total16,777,216bytes. Full raw arrays, including zeros and actual byte hashes, must be preserved. Do not replace them with seed/text-only identity.

Before any native call, prepare a pure CPU scalar/index reference for the complete graph and a separately labeled **concat-domain-only hypothesis**. No neural-model forward is needed for the scalar reference. The state3 anchor fits the wider Cat interval but not the incoming interval, so these hypotheses should be clearly separated; validate that separation from the exact FP32 prepared values before releasing a native run. The state15 control is not expected to prove domain idempotence: its input/output grids differ.

This is **not a repeat of the completed Conv sweep**: it uses a K-cache read boundary with4095+1 concatenation, different state/domain bindings, no Conv-history shift/slice, no39-label threshold sweep and no reuse/rewrite of the frozen tiny PTE. No second or follow-up case is bundled into this proposal.

## Proposed native bounds and preparation gates

The execution decision, if Pi chooses to proceed, is **at most one high-level host compile, one load of that resulting artifact, and one forward containing both branches**. No compilation/runtime permission is implied by approval of this source investigation.

- Keep the existing ExecuTorch/QNN route, QAIRT2.49.0.260730, SM8550/v73 HTP host simulation, `TagQuantIO=false`, no FP16 island, no tensor CPU fallback, no SDK substitution/install. Activation boundaries remain16-bit; a weight-free probe cannot establish W4-weight fidelity.
- New namespace and exact source, arrays, reference, runtime/library, compiler options, artifact and output bindings. Preserve all historical sources/artifacts/failed data. No source mutation of the existing Conv adapter or model.
- Proposed4GiB enforced address-space/memory ceiling, at most4CPU threads, low CPU/I/O priority, owned disk-backed scratch with all temporary-directory variables pinned, STOP/pressure supervision and TERM/KILL/reap. Compile deadline120s, load+forward60s,20s termination grace per phase, total active ceiling240s. No automatic retry, extra graph, fallback, increased limits or post-failure continuation.
- Fixed graph-artifact ceiling16MiB. If tracing/lowering changes topology, shape, precision, delegated tensor-compute coverage or artifact size beyond the binding, retain the result and stop before runtime. A compiler confound is inherent: this is a fresh synthetic graph, not reuse of the model PTE.
- Count high-level requests separately from internal manager/Compile callbacks. Retain actual callback counts; do not assume a particular compiler orchestration count. Required ABI/route/resource/artifact identity protects validity; optional unavailable timing or profiling fields remain null.

Before the SDK boundary, a fresh readiness packet must provide the actual helper/request/input/reference identities and expected graph/ABI. Its exact execution release must be issued separately or explicitly conditionally authorized by Pi; an old release, this document or an `approved:false` draft cannot authorize it.

## Evidence to retain and interpret

1. Postpass source graph and **pre-finalize** native tensor/operator declarations: names, roles, dtype, full quantization kind, FP32 scale bits and signed offsets. Capture both branches, not just the selected anchor. Do not label these finalized encodings.
2. Final PTE/delegation/ABI and native context identities. AOT manager I/O can be empty by construction; missing optional getters are not grounds for an extra SDK load. If reload public-I/O data is not available through the already-scoped load, leave it null rather than adding a second diagnostic context or native rebuild.
3. Raw input bytes before/after, every returned output byte, dtype/shape, primary status/errors and cleanup **before** optional comparisons. Compare every output element with reference and the alternative hypothesis; retain numerical disagreement rather than turning it into a retry trigger.
4. Distinguish `declared Quantize/Convert nodes`, `observed effective output behavior`, `internal finalized encoding/code: unavailable`, and `physical phone execution: not performed`.

A match to full QDQ would support that behavior for this isolated consumer. A mismatch would narrow a synthetic backend/frontend conversion question, not automatically prove an SDK defect, source-input clipping, a full-model cause or a remedy. Concat-domain-only agreement is also not proof that a particular internal Q node was removed. The earlier Conv results already reject a universal output-only model; do not generalize this new test across states.

No shared-domain alignment, source graph/model change, broad recalibration, full-model rerun or Android campaign follows automatically. The next explicit decision is whether this one bounded K-cache probe is worth preparing/executing given these limits—or to stop the lane. App/APK/packs/user data remain untouched; phone needs an independent coordinated slot and full phone.lock; push/history-rewrite hold remains.
