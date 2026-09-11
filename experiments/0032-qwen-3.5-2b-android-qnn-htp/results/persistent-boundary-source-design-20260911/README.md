# Qwen persistent-state boundary: K layer3 plus a same-layout control

**Source investigation complete; no execution release.** This follows the closed48-state audit `f873355`, not a replay of that audit or the tiny Conv sweep. The next decision is whether to prepare the single weight-free K-cache consumer probe in [NEXT_PROBE.md](NEXT_PROBE.md). No full-model, SDK, phone or app operation was performed.

## Selected boundary and control

Both are Histogram-route K updates, not recurrent matrices or convolution history. An output `[1,2,256,1]` is copied into the existing `[1,2,256,4095]` cache at axis3/source position. It is **not** a whole-cache replacement or a rolling shift. Logical indices below belong to the full model, not native delegate-port indices.

| | Affected: state3, layer3 | Control: state15, layer15 |
|---|---|---|
|Logical input → output index|6 →4|18 →16|
|Source placeholder|`states_3`|`states_15`|
|Input Q/DQ|`quantize_per_tensor_4` /`dequantize_per_tensor_127`|`quantize_per_tensor_16` /`dequantize_per_tensor_139`|
|Input scale / zero point|0.00029122494743205607 /42000|0.00027434100047685206 /32369|
|Next consumer|`cat_7`, last axis|`cat_34`, last axis|
|Returned-key AND concatenated-key scale / zero point|0.00034575574682094157 /35376|0.0003006155020557344 /35268|
|Saved QDQp0 return range|−10.3685236…10.0289907|−3.6173062…4.0129166|
|Previous audit's next-input would-clip count|1 of512|0 of512|

All domains use codes0…65535. Exact node records and FP32 scale bits are in `selected-states.json`; the newly traced immediate Cat paths are in `selected-cat-paths.json`.

**New path detail:** the current-key branch and Cat output share the returned-key encoding in both selected layers. The incoming persistent cache has a different, narrower input encoding. For state3, the saved QDQp0 value10.028990745544434 at `[0,1,24,0]` would become6.853979110717773 under the next-input scalar QDQ, while it fits the later Cat domain. The corresponding saved QNNp0 return10.194262504577637 also fits that later domain. These are saved return values plus previously computed hypothetical next-input arithmetic, **not observed clipping when QNN consumes the next cache**.

State15 is a same-shape/same-transport control with no clipping in the cited saved samples. Its two domains are unequal and have theoretical negative-side exposure; it is not an aligned-domain control or a universal no-clipping guarantee. Neither the selected values nor the previous counts establish importance for logits.

## Where the binding lives

`source-evidence.json` gives exact files, hashes and line-numbered passages. Source paths below are relative to the pinned ExecuTorch Qualcomm backend unless stated otherwise.

1. **Caller transport is float data movement.** Retained `advance_state` source copies `next_a[...,0]` into `a[...,position]`. There is no quantization or encoding negotiation in this handoff. The model concatenates that cache with the new key before attention. This is a source statement, not a new capture of historical runtime buffers.
2. **Annotation and folding preserve proposed domains as metadata.** `AnnotateQuantAttrs` puts Q/DQ parameters on source nodes and records differing consumer domains. Preprocess runs `FoldQDQ → InsertRequantize → InsertIOQDQ → LayoutTransform` (plus cast/transpose cleanup). `compile_exact_qnn.py:528–563` disables `TagQuantIO` for this route. For a float placeholder with quantization attributes, `InsertIOQDQ:78–90,124–151` moves those attributes to an inserted Q node; output DQ nodes restore float public outputs.
3. **QNN-facing dtype/offset are explicit frontend declarations.** `builders/utils.py:146–161` maps nonnegative0…65535 to UINT16; `node_visitor.py` maps that quantized carrier to `QNN_DATATYPE_UFIXED_POINT_16`. It emits scale-offset with **offset=−zero_point**, consistent with `float=(code+offset)*scale` in the public QNN header. Thus proposed input offsets are−42000 and−32369; proposed returned-key/Cat offsets are−35376 and−35268. FLOAT32 public I/O has undefined quantization after attribute movement. The serialized QDQ INT32 carrier is not a native32-bit activation declaration.
4. **Operators, not host buffer casts.** The quantize/dequantize visitors submit QNN `Quantize`/`Dequantize`. Differing quantized domains can produce `Convert`; the `_to_copy` visitor does not imply CPU fallback. At runtime `QnnExecuTorchBackend.cpp:139–186` registers memory or binds existing client pointers, clones tensor structs and calls `Execute`; `TensorWrapper::FillDataBuffer` binds/copies bytes, without a numeric quantization loop. This does not show which conversions the SDK finally executes.

## Finalization authority: a concrete limit of the available bindings

**Reading a wrapper after `Compile` does not turn it into an internal finalized-encoding query.**

- `QnnGraph::EnsureTensorInQnnGraph` submits a cloned tensor to `qnn_tensor_create_graph_tensor` and calls `UpdateQnnTensorMeta`.
- Despite that method's broad name/comment, `TensorWrapper.cpp:150–152` updates **only the tensor id**. It does not refresh dtype, scale or offset.
- `QnnManager::Compile:589–648` creates tensors, adds nodes, and calls `GraphFinalize`; it does not query optimized internal tensor encodings afterward.
- `GetGraphInputs/Outputs` return stored manager vectors. In the fresh AOT path those vectors may be empty unless populated; empty getters must not cause an invented success or an automatic extra load.
- When a context is restored, `QnnBackendCache` calls the QNN System binary-info API and copies **public graph input/output descriptors**; `AllocateTensor` constructs wrappers from them. This is a stronger source for a context's public I/O declaration, not a listing of arbitrary internal Quantize/Convert/fused tensors. It is an SDK call and was not invoked here.
- A tensor-dump build would turn internal tensors into public reads and can affect optimization. It cannot silently replace an unchanged-artifact observation.

The exact selected full-model native node names, internal finalized scales/conversion placement and actual consumed integer codes remain **null/unobserved**. Frontend declarations, public context I/O and internal numerical behavior are separate evidence layers. No source-proven backend defect or encoding fix was identified.

## Provenance and work bounds

The historical Histogram compile shell explicitly selects QAIRT**2.49.0.260730**, not an assumed2.49.40 substitution. Selected installed Python source pins agree with the retained native-readiness request; the inspected C++ files agree between the two local ExecuTorch checkouts. That equality is **not** a reconstruction of exact loaded-binary provenance or disassembly of the proprietary backend.

Only the existing758,313-byte graph-metadata zstd was recovered:32,499,235-byte JSON, SHA `2d879235c4d4a47643378e3ec3739bd587d4b0a68b23097b8ba64092ce20ad86`. No PT2/PTE/checkpoint member, tensor bundle or learned payload was opened. The bounded source collector used stdlib plus one zstd subprocess:1GiB address-space limit, CPUs0–3, low priority, owned disk scratch,30s guard/20s cleanup grace. Collection0.356s; supervisor0.602s; PID93431 reaped/group absent/scratch empty. Source snapshots are excerpts, not full proprietary SDK source. No Torch/ExecuTorch/ORT/model/SDK import or call, no compilation, no app/APK/pack/user-data edit, no agents, no push/history rewrite.

The old physical baseline and completed source/Conv evidence remain unchanged. Own-QDQ agreement, FP32 fidelity, state-feedback causality and the Android campaign remain separate unresolved questions. Pi and Kate receive this handoff; Nik is exclusively Janek's reviewer.
