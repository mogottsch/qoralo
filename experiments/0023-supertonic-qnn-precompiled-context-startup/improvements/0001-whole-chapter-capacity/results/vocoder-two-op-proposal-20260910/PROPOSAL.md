# Two-op vocoder lowering proposal — synthetic/source proof only

## Recommendation and hard boundary

Propose **two explicit batch1 parity branches around each of only the two failing depthwise Conv operators**. Keep the existing `Pad(mode=edge)` before splitting, share the original weight/bias initializers byte-for-byte, replace dilation2 with dilation1/kernel7 in each branch, and interleave feature-time outputs back to the original tensor. No real graph was mutated, no new derivative/context was produced, and no model/phone runtime was called for this proposal.

This is a candidate for a separately reviewed structural/tiny-algebra gate, not proven QNN support or a compile release. It preserves the whole T2048/L2048 graph, one logical vocoder call and one WAV. It is **not text/audio chunking**.

## Exact source/failed-backend mapping

Only these original ONNX nodes are candidates:

- `/decoder/convnext.1/dwconv/net/Conv`
- `/decoder/convnext.4/dwconv/net/Conv`

Both are FLOAT source depthwise cross-correlations: kernel `[7]`, dilation `[2]`, stride `[1]`, group512, Conv pads `[0,0]`; weight `[512,1,7]`, bias `[512]`. Both consume their already existing **causal edge-mode Pad:12 feature samples on the left,0 on the right**. The retained pad-builder `Constant_1` is `[12,0]`, expanded to ONNX pads `[0,0,12,0,0,0]`. Preserve that node and every producer/consumer outside these two operator sites.

The accepted materialization delta pins these serialized initializer bytes unchanged:

| Initializer | SHA256 |
|---|---|
| block1 weight |`5eb2bb5498d6f6cc2ef7e1c2e78d7fb4ff86f04a416197fd838411cabe91884c`|
| block1 bias |`c4e8daef9d00b4e897ab0cbe4555920502f2567cb6d0e6a018121ad72544bb7b`|
| block4 weight |`76d95a9819397b93880e53f83d4f424ad49806de4c501a560d96b0fa4043d704`|
| block4 bias |`9fce35a71b71df666cc6f38f40fe22d541a2ad47490b51fe4fa1e6444ed2f6cf`|

Original source/delta evidence: `../host-preparation-20260910/raw/inspect-vocoder-01/data/metadata.json` and `../materialization-20260910/raw/vocoder/data/structural-delta.json`.

Verbose composition metadata maps the same operators to QNN `DepthWiseConv2d`, FP32 input `[1,1,12300,512]`, weight `[1,7,1,512]`, bias `[512]`, output `[1,1,12288,512]`. SDK output63→`[95,0]`/`0x5f` and output165→`[221,0]`/`0xdd` tie the sites to the tiler warnings. This is failed-graph composition metadata, **not a returned ORT-session I/O receipt**.

SDK diagnostics report32 generated dilated-conv errors,16 per site: minimum tile12,920,320B, required TCM12,605,440B versus8,388,608B VTCM; missing time split at12288 → migration failure/Optimize17/finalize1002. These are compiler reports, not standalone source tensor sizes or summed measured live storage. Host-cgroup peak427,532,288B/events0 excludes a recorded8GiB limit hit in that attempt. Target3.75GB session VA is a different constraint, not the observed TCM failure.

## Algebra: preserve the existing Pad first

Let `z` be the **already edge-padded** input `[1,512,12300]`; weights `w[c,k]`, bias `b[c]`, `k=0..6`. Output time T=12288:

```text
y[c,t] = b[c] + sum(k=0..6, w[c,k] * z[c,t+2*k])
z_p[c,j] = z[c,2*j+p], p in {0,1}
u_p[c,j] = b[c] + sum(k=0..6, w[c,k] * z_p[c,j+k])
y[c,2*j+p] = u_p[c,j]
```

Each branch input is `[1,512,6150]`; each nondilated valid Conv produces `[1,512,6144]`. Bias is applied once per output. Kernel tap order/channel grouping are unchanged. Interleave by stacking the parity outputs on a new final axis `[1,512,6144,2]` and reshaping to `[1,512,12288]`; **do not concatenate whole even then odd sequences**.

Strided Slice with starts0/1, step2, axis2 is one graph expression. If its backend support is unsuitable, reshape to `[1,512,6150,2]` then unit-step last-axis Slice/Squeeze expresses the same parity selection. Neither variant is implemented or claimed supported here.

Do not split the unpadded feature tensor and then edge-pad each parity branch: the odd branch would replicate `x[1]` at its left edge instead of the original padded `x[0]`. A synthetic counterexample is retained. Splitting the **existing padded tensor** also preserves right-edge behavior exactly.

### Separate batch2 formulation

`z.reshape(1,512,6150,2).transpose(0,3,1,2).reshape(2,512,6150)` packs parity into batch. One dilation1/group512/kernel7 Conv yields `[2,512,6144]`; inverse reshape/transpose/interleave recovers the original output. The same weights/bias are shared. This is algebraically valid but changes internal Conv batch handling and cannot inherit backend support from the batch1 case. Prefer two explicit batch1 branches for the first candidate unless Nik finds a stronger target-support argument.

## Alternatives and why they are not the default

| Candidate | What stays exact | Main unresolved risk |
|---|---|---|
| **Two batch1 parity branches** | Original7 coefficients/bias/Pad; original sum tap order under the synthetic reference | Real-data Slice/reshape lowering, extra intermediates, optimizer may refuse or recognize/re-fuse dilation2; native FP16 kernel rounding/tiling unproven |
| Batch2 parity packing | Same coefficients and algebra; one nondilated Conv | Additional backend batch2 layout/tiling assumptions; possible re-fusion |
| Zero-expand kernel7→13, dilation1 | Finite real-number formula; fewest changed Conv attributes | Expanded initializer bytes differ; k13 depthwise support/tiling unproved; zero*Inf/NaN introduces extra propagation absent from dilation2; reduction order/FP16 behavior may change |
| Seven shifted Slice/Mul terms +ordered Add, then bias | Same sampled indices, no dilated Conv | Much more graph arithmetic/live intermediates; QNN broadcasting/delegation/rounding and optimizer re-fusion unproved |
| Manually halo-tile the original dilation2 Conv | Original weights/operator semantics with12 extra input samples per output tile | Still uses the backend's problematic dilation2 path; no observed guarantee on its smaller tile allocator/splitting rules |

The source already contains dilation1/kernel7/group512 operators, which makes that primitive a better-supported direction than inventing a new kernel13 path. This is still not proof of the new composite graph's support. No blind host RAM increase, global vocoder rewrite or L shrink is recommended.

## Size arithmetic, not a promised memory fix

For source feature time `T=6L`, the two full outputs contain `512*T` FP32 values:

| Capacity | T | Padded time | Full output logical bytes | Each parity input/output time |
|---|---:|---:|---:|---|
| L238 |1428|1440|2,924,544|720 /714|
| L2048 |12288|12300|25,165,824|6150 /6144|

The output grows8.605×; padded-input growth differs because the12-sample halo is fixed. Each new full FP32 parity input is12,595,200B, **not** a VTCM requirement: normal nondilated convolution must still be tiled by the backend. Halving time does not prove its compiler requirement halves or fits8MiB. No whole-graph liveness/workspace conclusion is drawn.

A cheap existing-file ValueInfo-only extraction found many internal dimensions remain symbolic in both old/new ONNX annotations. Its rankings cover only statically recorded values and are **not complete peak-memory bounds**. No extra inference/shape propagation was performed; this optional metadata result is not a prerequisite for the two-op proposal.

## Synthetic tests and next gate

`tests/test_vocoder_lowering_algebra.py` uses generated NumPy arrays only, no learned weights or model runtime. It compares explicit batch1 parity, batch2 packing, zero-expanded and shifted-term formulas for finite tensors including full12288 output time; checks both parity/edge positions, independent channel groups/nonzero bias, existing external constant/reflect/**edge** Pad placement, including the actual causal `(12,0)` case, and the full real-shape index identity. It also exhibits zero-insertion's additional nonfinite propagation and the wrong split-before-edge-pad result.

These are algebra/edge/shape proofs under a specified CPU summation order—not QNN tiling, backend-batch support, native FP16 equivalence, whole-model fidelity or listening acceptance. Await Nik's proposal verdict. Any real two-op derivative must receive a new explicit scope, preserve all original initializer bytes/untouched nodes/ABI, retain exact structural deltas, and later prove that lowering avoids the failed backend operators without CPU fallback or re-fusion. No such derivative or compile is authorized here.
