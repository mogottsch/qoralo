# Layer-0 convolution-history encoding audit

**Source metadata and scalar arithmetic only. No model/PTE load, graph execution, weight/constant tensor read, new compile, or phone access.**

The audit explains the QDQ endpoint observed in `6a5dc5b`: common history input **23.7218952179** becomes QDQ output **22.1315498352**, whereas QNN outputs **23.7218971252**. It does not establish the actual optimized QNN path or a model-wide cause.

## Exact metadata binding

The previously bound PT2 archive has SHA-256 `30799090d14a42c92ea804a2763df55ff231ba232653d96484324ad40c492364`. This audit did not rehash/read its 13.65 GB of payloads. It read exactly one ZIP member:

```text
diagnostic-w4a16-qdq/models/model.json
32,499,235 bytes
SHA-256 2d879235c4d4a47643378e3ec3739bd587d4b0a68b23097b8ba64092ce20ad86
```

The complete metadata member is retained losslessly compressed, with verified raw recovery. No `data/weights`, `data/constants`, or sample-input member was read. All required scales/zero points were inline JSON literals.

The graph has 51 user inputs and 73 outputs. User input **27**, `states_24`, is the layer-0 convolution state; output **25**, `dequantize_per_tensor_221`, is the new convolution-history state. Selected exact nodes/arguments and tensor metadata are retained in `qdq-metadata-trace.json`.

## Clipping and requantization trace

The history path is:

```text
states_24
 → quantize_per_tensor_25 → dequantize_per_tensor_148
 → cat(history, projected-current-token), dim=-1
 → quantize_per_tensor_67 → dequantize_per_tensor_220
 → slice(dim=3, start=-4)
 → quantize_per_tensor_68 → dequantize_per_tensor_221
```

All stages use codes 0–65535. Serialized scalar type 4 is **INT32**, used as the container for these 16-bit activation codes; it is not 4-bit storage. The PyTorch scalar-type schema and Qualcomm visitor's INT32→UINT16 packing comment are retained as source evidence.

| Stage | Scale | Zero point | Representable upper bound | Output for this scalar |
|---|---:|---:|---:|---:|
| State input Q/DQ25/148 | 0.0007933978922665119 | 37640 | **22.1318340302** | **22.1318340302** |
| Concat Q/DQ67/220 | 0.0009200899512507021 | 32457 | 30.4347362518 | 22.1318435669 |
| History output Q/DQ68/221 | 0.0008176580304279923 | 36523 | **23.7218952179** | **22.1315498352** |

At the input stage the unbounded integer code is **67539**, so it clamps to **65535**. Subsequent concat and output quantization produce codes 56511 and 63590 without clipping. FP32 scalar arithmetic, following the retained PyTorch `round(input * inv_scale) + zero_point`, clamp and dequantization source, reproduces the recorded QDQ value **exactly**.

Therefore **22.131550 is not the final output encoding ceiling**. It is input-range saturation followed by two requantization rounds. The final encoding permits values up to 23.721895.

## What is—and is not—known about QNN

Applying only the final output encoding to the original common value yields 23.7218952179, within one FP32 ULP of the observed QNN value. This is an **output-only arithmetic hypothesis**, not a recovered backend execution trace.

The original compiler log explicitly creates `input_2_states_24@0` and a **Quantize** node using it. Its exact log excerpt and source hash are retained. Thus a simple claim that the frontend omitted input quantization is not supported.

The public lowering source shows:

- `AnnotateQuantAttrs` transfers Q/DQ attributes and records mismatches;
- `FoldQDQ` erases explicit Q/DQ nodes;
- `InsertRequantize` creates conversion nodes for recorded encoding changes;
- `InsertIOQDQ` rebuilds boundary quantization/dequantization;
- the tensor visitor selects base or per-consumer requantization attributes;
- the concat builder supplies its input/output tensor wrappers to QNN.

These explain where to capture metadata in a future probe. They do **not** prove which tensor encodings or fused path the accepted binary finally uses. The retained exact compile has no separate readable finalized tensor-encoding/optimized-graph dump. No opaque PTE/backend model load was attempted to obtain one.

## Verification and limits

`tools/audit_conv_history_metadata.py` imports only standard-library modules, validates the node lineage, and reads only the bounded metadata member. Pure metadata/scalar tests exercise the exact trace, paired encodings, output-ceiling distinction, rounding and forbidden payload reads.

The finding is limited to this QDQ history endpoint. It does not prove a QNN compiler/backend defect, explain the full hidden/logit discrepancy, choose which route is closer to FP32, or establish fidelity/performance/campaign readiness. Original model/PTE/input/output/reference artifacts remain unchanged.

See [`SYNTHETIC_PROBE_PROPOSAL.md`](SYNTHETIC_PROBE_PROPOSAL.md) for the separately proposed tiny lowering/control probe. It has not been compiled or run.
