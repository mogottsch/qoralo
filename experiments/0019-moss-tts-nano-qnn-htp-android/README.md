# Experiment 0019 — MOSS-TTS-Nano QNN/HTP feasibility

## Result

**Stopped before phone.** The official Android architecture needs one autoregressive decode session whose KV-cache dimension grows on every frame. QNN HTP cannot fully delegate that reusable dynamic-shape graph with CPU fallback disabled.

Localized, audited rewrites make every fixed call shape observed in experiment 0018 individually delegable, but they do not create a complete deployable all-HTP route. No mixed fallback was run, no physical HTP claim is made, and latency, memory, first-audio, or audio comparisons were not eligible.

## Locked source contract

Experiment 0019 reuses experiment 0018 commit `f38c8aa` and its exact assets:

- OpenMOSS source revision `cc7bdf19c7639c0870dab22045a33b442760f6be`
- TTS ONNX revision `f52645cb467506d8e18e746ddd59482685b74e58`
- audio-tokenizer ONNX revision `ceff0d0749bfb3fa2d61149794ec6feef0d1e1ae`
- transcript SHA-256 `350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f`
- 51 exact text tokens, Junhao voice, seed `20260818`, prefill sequence 226
- CPU-observed generation: 209 frames, decode `past_seq` 226 through 434, codec output 802560 samples

[`results/source-lock.json`](results/source-lock.json) records and re-verifies the exact model and external-weight hashes. Experiment 0018 was not modified.

## Original fail-closed capability map

The host gate used patched ONNX Runtime 1.27.1, QNN 2.49.0 HTP backend, `session.disable_cpu_ep_fallback=1`, `offload_graph_io_quantization=0`, burst mode, and `soc_model=43`.

| Fixed call | Result | Final optimized assignment | Unsupported nodes |
|---|---|---:|---|
| Prefill `[1,226,17]` | rejected | 1014 / 1027, 2 partitions | root `Slice`; 12 rotary `Einsum` nodes with `bs,d->bsd` |
| Decode, past 226 | rejected | 965 / 966, 2 partitions | rotary `Einsum` |
| Decode, past 330 | rejected | 965 / 966, 2 partitions | rotary `Einsum` |
| Decode, past 434 | rejected | 965 / 966, 2 partitions | rotary `Einsum` |
| Local fixed-frame decoder | passed | 1565 / 1565, 1 partition | none |
| Full codec decode, 209 frames | rejected | 863 / 864, 2 partitions | root boolean `Xor` |

Complete node names and both capability passes are retained in [`results/host-gate-details.json`](results/host-gate-details.json).

## Audited fixed-shape derivatives

Only the observed blockers were changed:

- `Einsum("bs,d->bsd")` → `Unsqueeze(axis=2)` + broadcast `Mul`;
- the prefill `Slice` → `Identity`, after proving that fixed `[1,226]` attention makes `[-226:INT64_MAX:1]` the whole tensor;
- boolean `Xor(a,b)` → the canonical `Or(And(a,Not(b)), And(Not(a),b))` expansion.

All other original nodes and original initializers remain ordered and byte-identical. Shape specialization changes graph I/O metadata only. Deterministic ONNX Runtime 1.20.0 CPU comparisons passed the frozen policy with **zero error and cosine 1.0** for:

- the exact 226-row prefill request;
- decode past lengths 226, 330, and 434;
- the local fixed-frame graph;
- 209-frame full codec decode.

See [`results/derivative-provenance.json`](results/derivative-provenance.json), [`protocol/rewrite-equivalence-policy.json`](protocol/rewrite-equivalence-policy.json), and [`results/rewrite-cpu-equivalence.json`](results/rewrite-cpu-equivalence.json).

After the rewrites:

| Fixed call | Final optimized assignment |
|---|---:|
| Prefill | 1038 / 1038, 1 partition |
| Decode representatives | 967 / 967, 1 partition |
| Local fixed-frame decoder | 1565 / 1565, 1 partition |
| Full codec decode | 867 / 867, 1 partition |

All **209** decode shapes observed in the CPU reference, past lengths 226–434, independently created fail-closed QNN sessions. [`results/decode-static-gate-matrix.json`](results/decode-static-gate-matrix.json) retains every shape, model hash, structural check, rewrite check, log hash, and exit code.

## Decisive deployment blocker

The official Android code creates `moss_tts_decode_step.onnx` once and reuses it while `past_seq` grows. Even after the exact `Einsum` rewrite, that dynamic graph produced:

- 13 QNN partitions;
- 52 / 1091 optimized nodes assigned to QNN;
- 1039 unsupported nodes;
- fail-closed session rejection.

The exact 1039-node list is retained in `results/host-gate-details.json`.

Using one static model per observed CPU step is not equivalent to a reusable route:

1. it requires 209 distinct decode sessions or session compilations for this one output;
2. those host session creations totaled 1052.77 seconds, with a 5.39-second median, before any inference;
3. HTP numerical differences can alter the stop frame, while the contract permits up to 375 frames;
4. full codec decode would also need the actual HTP-produced final length.

A single fixed-capacity KV-cache graph would require a substantial state/topology redesign—fixed cache update, fixed outputs, and valid-length masking—not another localized unsupported-operator substitution. That work was not justified inside this bounded attempt.

## Claim boundaries

- Host QNN HTP capability and graph finalization are not physical phone execution.
- No phone lock was acquired and nothing was staged to the phone.
- No quantization, calibration, context optimization, hybrid fallback, or CPU fallback was used.
- No complete all-HTP route, retained HTP WAV, or matched performance/memory comparison exists.
- [`results/host-checkpoint.json`](results/host-checkpoint.json) is the canonical conclusion.
