# PAUSED: weight-only ablation source, not an executed model comparison

Moritz explicitly paused Ben through Pi on2026-09-11. **No request was prepared, no attempt directory was created, and no ablation model load/forward, native build/compile or phone run started.** The code is a tested partial implementation, not a validated full-model worker. It must not run until Moritz resumes this track and a new heavy-host window is coordinated.

## Accumulated work

The preceding FP32 comparison (`06d8332`) found same-input logit cosines of0.50597369 for saved QDQ and0.49293107 for saved QNN versus FP32. Own-QDQ agreement was therefore not FP32 fidelity. Both routes share argmax198, which does not resolve the numerical gap.

Source inspection confirms that the existing W4A16 recipe already uses per-channel Linear/Conv weights. The installed quantizer exposes per-block W4, and upstream Qwen recipes use16/32-sized groups. Some upstream recipes also introduce W8 exceptions: those have **not** been copied or authorized as a silent route change.

The proposed next discriminator is two CPU weight-only calls on the same frozen QDQ-origin p1 pack:

1. Reconstruct Linear/Conv W4 per-output-channel weights, with FP32 activations.
2. Reconstruct Linear W4 in32-input-channel groups with source-derived LPBQ scale expansion; depthwise Conv remains per-channel. Activations, embedding, norm and other parameters remain FP32.

Neither case is a deployed W4A16 candidate. The point is to distinguish bulk weight-quantization loss from activation/state-boundary quantization before paying for another complete native compile. Every case restores original checkpoint values into one private CPU model; originals are never modified.

## Source-derived LPBQ limit

`builders/node_visitor.py::make_qnn_per_block_config` takes the maximum original block scale per output channel, divides it by16, then rounds/clamps each block's scale multiplier to1…16. The source's weight-data path says parameters have already been quantized by the framework. The proposed CPU reconstruction therefore preserves those original framework codes and multiplies by the submitted expanded scale. This is **not an observation of finalized native weights or internal SDK behavior**.

Six small CPU tests passed: exact per-channel parity with framework Q/DQ; framework per-block codes plus independent channel-loop scale expansion; depthwise preservation; rejection of non-divisible groups without padding; no embedding/norm mutation; and a counterexample showing compressed scale expansion can worsen error. The last test prevents assuming group quantization always improves fidelity.

Two optional TorchAO CUDA-library import warnings are retained verbatim. They did not prevent the CPU tests. No fix, rerun or model call was made because of them.

## Restart location and limits

- Partial tools: `../../tools/weight_only_ablation.py` and `../../tools/run_weight_only_ablation.py`.
- Small tests: `../../tests/test_weight_only_ablation.py`.
- Tested source snapshots and original stdout/stderr are retained here.
- Intended fresh path: `.local/weight-only-ablation-20260911/attempt-01/` **does not yet exist**.
- Intended worker envelope:18GiB address space,4CPU low priority,180s wall plus20s TERM grace, two calls, no retry. This envelope and full-model code remain unexecuted.
- Future preparation would bind the completed FP32 request/reference and unchanged checkpoint/input pack. Review the partial controller before preparing; do not treat small math tests as a successful end-to-end run.

No owned process remained at pause. Only an empty test-owned `torchinductor_moritz` directory was removed, with its original presence retained in`cleanup.json`; scratch is now empty. The earlier FP32 worker1475364 was already reaped with its group absent, and the phone lock had already been released after`696f42d`. No other agent's job or app data was touched. Ben's request for the next heavy-host slot is withdrawn.
