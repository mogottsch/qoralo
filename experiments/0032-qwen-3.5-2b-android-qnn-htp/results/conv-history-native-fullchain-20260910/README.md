# First native full-chain boundary probe: finite, localized mismatch

**One authorized weight-free QNN-x86 case completed and stopped.** No retry, other native control, full-model load or phone work occurred. This is host HTP simulation targeting SM8550/v73, not physical HTP or Android performance evidence.

## Execution and retention

The approved `fullchain` request was SHA-256 `f9ef7075427df9a4cf8c4e565f9c261c4065380384ec35a7a1dbba9865b8548e`, using the reviewed adapter from `d687756`. Four Q/DQ pairs use three encoding domains; there are no weights.

| Phase | Observed guard wall time | Bound |
|---|---:|---:|
| One high-level compile | 10.611 s | 120 s |
| One runtime load + one forward | 4.205 s | 60 s |
| Complete case | 14.819 s | 240 s active |

Both phases exited 0 and were reaped. Low priority, four math threads, EXT4 scratch and external STOP/PSI/deadline guards were used. These durations include imports, metadata capture and evidence handling; they are not model inference-performance measurements.

The early delegation report records one subgraph, two delegated tensor operations (Concat and Slice), and only nondelegated `getitem` plumbing. The final emitted plan has **one QnnBackend delegate call and zero KernelCalls**. This proves no ExecuTorch tensor-compute fallback for the tiny route, not absence of CPU work inside the host simulator.

The compiler observer saw one Python manager construction and one native Compile callback. Logs separately show one backend-create sequence per phase, one compile-time graph finalization, and one runtime graph-execute completion with status `0x0`. These different counts are retained separately rather than equated.

All raw inputs/output, 64 metadata taps, complete compiler/runtime logs, release, commands, resources and emitted-plan proof are in `raw/`. The 230,736-byte context and 232,144-byte PTE remain **LOCAL-ONLY**, hash-bound in `local-native-artifacts.json`; copy their bytes during migration. The controller and both phase process groups are absent, and scratch is empty.

## Independent output check

The raw output is **98,304 bytes / 24,576 FP32 values, all finite**, SHA-256:

```text
06465f73b3ecf72d1d27d5908a679ee7f3d68666007a769997e998fb389a9845
```

`analyze_saved.py` uses only stdlib and saved bytes. It independently reconstructs the entire full-chain scalar oracle from the submitted inputs and compares the QNN output with all three previously accepted CPU/oracle arrays. No extra CPU model or native case is run. Original arrays remain unchanged. All **36 saved-data contract tests** passed, including full analysis recomputation; the previously accepted 177-test adapter suite was not rerun for this evidence/docs-only change.

| Saved reference | Selected `[0,6053,0,2]` | Selected absolute difference | Maximum difference outside selected slot |
|---|---:|---:|---:|
| Full-chain | 22.131549835205078 | 1.5903472900390625 | 5.96046448e-8 (**≤1 ULP**) |
| Output-only | 23.721895217895508 | 1.90734863e-6 (**1 ULP**) | 0.000817656517 |
| Aligned | 23.721895217895508 | 1.90734863e-6 (**1 ULP**) | 0.000817656517 |

QNN's selected value is **23.72189712524414**, reproducing the earlier selected full-model convolution-history endpoint observation. That is not a full-model fidelity or causality verdict.

The whole array does **not** follow output-only/aligned behavior. All **6,144 slot-0 values** are QNN `0.49958908557891846`, within one ULP of full-chain `0.49958905577659607`, but about one final quantization step away from output-only/aligned `0.5004067420959473`. All other nonselected values also agree with full-chain within one ULP. The substantial discrepancy is localized to the single history input beyond its encoding range in this fixture; it is not evidence that every intermediate quantizer was globally bypassed.

Call/collection status is complete, but numerical equivalence is **false**. No numerical acceptance tolerance or model-quality pass is claimed.

## Saved encoding trace through Compile entry

Every one of the **50 graph snapshots** preserves the four boundary declarations. Twelve per-consumer configuration taps and the actual native wrapper getters carry the corresponding encodings. Five returned operator wrappers contain eleven tensor getter rows, with no missing tensor rows.

| Boundary | Exact FP32 scale | QNN offset | Native fixed-point dtype |
|---|---:|---:|---|
| History | 0.0007933978922665119 | -37640 | UFIXED_POINT_16, code 1046 |
| Projection | 0.0008176580304279923 | -36523 | UFIXED_POINT_16, code 1046 |
| Concat | 0.0009200899512507021 | -32457 | UFIXED_POINT_16, code 1046 |
| Slice/output | 0.0008176580304279923 | -36523 | UFIXED_POINT_16, code 1046 |

Observed representation changes, not semantic domain changes:

1. `0024`: AnnotateQuantAttrs copies unchanged Q/DQ arguments to producer metadata.
2. `0026`: FoldQDQ removes explicit pairs; all four boundary encodings remain as metadata.
3. `0046`: InsertRequantize leaves the five-node graph and its domain attributes unchanged.
4. `0048`: InsertIOQDQ makes both input Quantize nodes and the output Dequantize explicit again, preserving domains.
5. `0063`: native fixed-point tensors use UFIXED16 rather than the graph's INT32 quantized carrier. Exact scale bytes and negated zero points are preserved.

**Both input Quantize wrappers are present before Compile.** No first semantic scale/offset change is observed through this boundary; frontend omission is not supported. Graph INT32 carriers, native datatype code 1046, and quantization bitwidth are different concepts.

Complete native encoding-kind/bitwidth and the SDK's internal finalized/fused graph remain unknown. Post-Compile manager getters returned a graph name with empty IO arrays; this is not evidence that logical IO is absent and supplies no additional encoding proof. Raw observations remain intact.

The remaining question is the treatment of the out-of-range history value inside this host-QNN route. Neither the endpoint nor pre-Compile wrappers establish an SDK defect or actual internal optimized path. See `SWEEP_PROPOSAL.md` for a **source-only, unapproved** next-control proposal. The first-case release is consumed; no native follow-on is authorized.
