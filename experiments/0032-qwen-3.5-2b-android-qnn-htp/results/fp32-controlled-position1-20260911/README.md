# Same-input full-model FP32 reference at position1

Status: one FP32 call completed after Jere's AR1 converter released; the worker and its resource reservation are released. **Both retained W4A16 routes differ substantially from this reference despite agreeing with each other and sharing argmax198.** The Android campaign and overall Qwen fidelity objective remain active; work continues into a weight-quantization discriminator, not another phase-approval stop.

## First outcome

| Same-input position1 metric | Saved QDQ versus FP32 | Saved QNN versus FP32 |
|---|---:|---:|
|Logit cosine (FP64 arithmetic)|0.5059736899955564|0.4929310695067458|
|Logit L2 error|1272.0424897720638|1264.0653165041974|
|Logit mean absolute error|2.026125978061764|2.0114968970456184|
|Layer0 hidden cosine|0.94045|0.94031|
|Layer23 hidden cosine|0.29911|0.32335|
|Argmax (FP32 also198)|198|198|

The lower QNN cosine but slightly lower QNN L2/MAE gives no blanket route winner. More importantly, the earlier~0.888 QDQ/QNN cosine was not FP32 fidelity. This does not isolate weight quantization from activations, state boundaries or other current-call quantization effects.

All73 outputs are finite, submitted inputs are unchanged, and every requested postpin passed. Raw outputs21,878,472B SHA`e172f90c8102e9a28fcf4ad5e6a4aca33f7745320785d5cee045d8f546a73b55` were retained before comparisons and are fully recoverable from the19,844,904B zstd copy. Originals remain local.

The model constructed/loaded in10.014843s and executed once in1.948122s; guard total19.421157s. These are CPU diagnostic intervals, not Android performance. Process RSS high-water13,378,484KiB includes loading/mapped source and analysis lifecycle, not isolated model memory. The loaded checkpoint had285 BF16 and36 FP32 tensors;9,561,537,792 allocated FP32 Parameter bytes include the duplicated tied-weight allocation. PID1475364 was reaped, its group absent, scratch empty; Jere was immediately told that his next heavy slot was available.

The next source check confirms W4 per-channel Linear/Conv quantization is **already enabled**. A separate CPU weight-only per-channel-versus-group32/LPBQ ablation, explicitly leaving activations FP32, will test whether bulk weight quantization dominates before a costly new W4A16 compile. Supported group-quantization declarations are not a model-fidelity fix or evidence that a full candidate already compiles. No upstream W8 exceptions will be copied silently.

## Why this call is different

The completed physical K-cache fixture (`696f42d`) reproduces the host output on v73. Its overrange K3 value is closer to plain float concatenation than to the narrow fullchain QDQ clamp. That does not determine which **full-model** route is closer to an unquantized reference.

This worker evaluates the unchanged converted checkpoint (`a2640184…c70e86`) in the unchanged adapter (`67ac8061…94a4ed`) with FP32 parameters and arithmetic. It submits the exact51-input position1 pack (`bfe14bca…98ebe0d`) already consumed by both retained QDQ and QNN controls. The pack's history comes from QDQ position0, not an FP32-origin trajectory. No QDQ or QNN model is run again. No PTE, quantization, calibration, tokenizer, prompt or production model source is changed.

The existing model forward emits49 public outputs. Read-only hooks save the post-layer hidden state for each of24 layers, matching the diagnostic compiler's append order, without replacing layer outputs. The worker saves all73 tensors before numerical classification/comparison. It compares every tensor to the retained paired QDQ and QNN arrays using FP64 differences and cosine arithmetic. Nonfinite observations remain retained; zero-norm cosine is null, not an artificial failed-forward gate.

## Reference and resource limits

- This is FP32 computation on the published/converted checkpoint's existing values, not recovery of unknown higher-precision training weights. The original checkpoint dtype inventory is recorded on load.
- It is the unquantized **same-adapter** reference, not a new independent Hugging Face implementation validation. Prior eager equivalence/source evidence remains separate.
- Common external inputs do not make later internal layer inputs equal, and do not identify a causal operator. This one call cannot establish full-trajectory fidelity, generated-text sanity or Android performance.
- The compared full-model QNN outputs are the retained x86 HtpProvider controls. The small Cat fixture's target equivalence does not turn those full-model arrays into physical outputs.
- Copying `load_state_dict` preserves the existing Parameter objects and the recurrence's plain A_log/dt_bias references. Meta/assign loading is deliberately avoided; a small regression test verifies the alias rule.
- One model only:18GiB address-space cap,4CPU low priority,600s wall plus20s TERM grace, owned disk scratch, STOP/pressure supervision and group reap. No overlap with Jere's heavy conversion/paired compile; no phone access.
- The sum of allocated Parameter elements/bytes includes separately allocated tied-weight modules and is a memory/accounting fact, not a new authoritative model-parameter count.

Seven small tests passed. Request `26733511cb62b56047e652e27323ff91dc4b207dbd3992d98259d674ac53e438` binds the worker/controller/source, checkpoint, exact pack, saved references and selected runtime files. Native/model payloads remain local-only and migration-required; all older evidence and physical baselines stay unchanged.
