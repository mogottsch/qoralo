# QNN-x86 trajectory helper: source-only readiness

**No real PTE/model/QNN execution occurred.** This is helper, checkpoint, supervisor, and synthetic-test readiness following the accepted full-short QDQ result `cc6c49c`. It does not extend that result's numerical claims.

## Comparison question

Use the exact HistogramObserver diagnostic PTE `7f30be3d…ff3fea` against the positional QDQ tensors from `cc6c49c`, with the same canonical 174 input IDs and context 4096. Both trajectories start at zero state. After each input, **QNN carries its own recurrent/convolution/KV outputs**; the QDQ reference is used only for logit comparison.

This measures accumulated **own-state trajectory drift**, not same-state operator error. Feeding QDQ states back to QNN would ask a different question and is not implemented here.

The PTE has **73 outputs: one logit tensor, 48 state outputs, and 24 hidden diagnostic tensors**. Its first 49 outputs are standard; they are not 49 state tensors. The helper saves all 73 raw outputs but advances only the 48 state tensors. Hidden tensors are retained for later localization, not silently treated as state. Only logit reference tensors exist at all 174 positions in the accepted QDQ archive; this helper does not claim a full hidden-state reference comparison.

## Source contracts and retained evidence

- PTE, parameters, and input IDs must match the accepted artifact manifest before the runtime is loaded. The reference must be the completed 174-position QDQ route with matching QDQ/parameter/input bindings.
- Requested reference positions are hash-checked before QNN load. Missing/corrupt LOCAL-ONLY tensors fail preflight without an expensive forward call.
- The runtime's 51 inputs/73 outputs and input tensor geometry/dtypes are checked. Positions/masks use the actual consumed prefix; recurrent/convolution states are copied and full-attention KV slices inserted at the actual position. No silent state dtype conversion.
- All raw QNN output tensors are saved before shape/finiteness checks. After a valid state advance, a durable state checkpoint and `state_committed` journal event precede comparison. A reference/comparison error therefore preserves expensive model work; it does not invent a completed comparison.
- `graph_calls_returned`, `state_updates_completed`, and `comparisons_completed` are separate. A bounded segment is never relabeled a full 174-position request.
- Each output directory and frame/checkpoint path is exclusive. No automatic retry or overwrite of previous attempts.
- TERM/INT, cooperative timeout, graph errors, output ABI errors, and comparison failures retain partial metadata/raw/checkpoints and exit unsuccessfully. Forced KILL can leave `started_not_complete`; recover only the last valid checkpoint, not a claimed completion.

`compare_qnn_trajectory.py` lazily imports/loads the real QNN runtime only inside its production loader. The synthetic suite replaces that loader with a failure trap and injects a tiny fake 24-layer backend; `torch.export.load` is also prohibited. No official weights, PTE, PT2 graph, or QNN backend is loaded by the tests.

## Explicit checkpoint continuation

A new invocation may receive `--resume-checkpoint` plus its exact reviewed `--resume-sha256`. The header binds the PTE, parameters, QDQ reference/manifest, canonical token sequence, context, driver/state-transport source hashes, next position, consumed-prefix hash, own-QNN-state origin, and state-file size/hash. Restoration checks all 48 tensor shapes and dtypes. A changed binding, missing digest, corrupt bytes, wrong prefix, or wrong state geometry is rejected.

Synthetic tests show that two explicit segments reproduce an uninterrupted fake backend's final logits and state exactly. This is **not proof of real QNN restart equivalence**. Before real continuation, keep and audit the native runtime/library stack as well as the pinned PTE, and review the prior segment's evidence. Recreating the runtime between segments is explicitly diagnostic and must not be presented as loaded-route campaign reuse. Each continuation needs a new release and fresh output directory; nothing launches automatically.

## Runtime and resource plan — not executed

The helper requires both `--max-positions` (steps in this invocation, including after explicit continuation) and `--timeout-seconds` (finite, at most 7200). Requested segments cannot overrun the 174-input sequence by silent truncation.

Historical QNN-x86 simulation needed approximately **one hour for 30 inputs**. The planning estimate is 60 seconds preparation plus 120 seconds per input:

- 4 positions: about 540 seconds; suggested first reviewed budget **900 seconds**.
- 30 positions: about 3660 seconds.
- 174 positions: about **20,940 seconds (5.8 hours)**, well beyond a 7200-second invocation.

These are cost estimates, not measured predictions for this new helper. An estimate exceeding the budget is recorded, not misclassified as an inference failure. The actual limits still stop execution and preserve partial evidence.

The normal CLI always launches its internal worker through `qwen_host_guard.py`. The supervisor enforces the wall deadline independently of blocked native calls: TERM, at most 20 seconds checkpoint grace, then group KILL and reap. It also handles `STOP`, sustained near-OOM/memory or I/O pressure, and launch failures. Source tests exercise deadline termination, a TERM-ignoring tiny child, STOP, exclusive supervisor logs, and reaping. No model runs in these tests.

The CLI sets low CPU/I/O priority and four math threads, creates owned disk-backed scratch, and rejects tmpfs/ramfs. App/emulator work keeps priority. A future run saves `supervisor.json`, command, stdout/stderr, resources, and `trajectory/` evidence. State checkpoints may be around 120 MB per position for the real model; all 73 raw outputs add more disk usage. Keep this material local and explicitly migrate it. Do not use or clean the protected QDQ-reference directories as scratch.

## Review-only command example

Only after explicit review/release; **not run during readiness work**:

```bash
E="$PWD/experiments/0032-qwen-3.5-2b-android-qnn-htp"
export QNN_SDK_ROOT=/home/moritz/opt/qairt/2.49.0.260730
export PYTHONPATH="$QNN_SDK_ROOT/lib/python:$E/.local/executorch:$PWD"
export LD_LIBRARY_PATH="$QNN_SDK_ROOT/lib/x86_64-linux-clang:$PWD/artifacts/venv-executorch-1.2/lib/python3.11/site-packages/executorch/backends/qualcomm/sdk/libcxx-14.0.0:$PWD/artifacts/venv-executorch-1.2/lib/python3.11/site-packages/executorch/extension/pybindings"
artifacts/venv-executorch-1.2/bin/python "$E/tools/compare_qnn_trajectory.py" \
  --pte "$E/.local/diagnosis/restart-20260910T083327Z/01-hidden-compile/diagnostic-w4a16-qnn.pte" \
  --params "$E/.local/executorch/examples/models/qwen3_5/config/2b_config.json" \
  --token-ids "$E/protocol/token-ids/short.int32le" \
  --artifact-manifest "$E/results/host-histogram-precision-20260910/artifact-manifest.json" \
  --reference-directory "$E/results/host-histogram-full-short-20260910" \
  --reference-root "$E" --context 4096 \
  --max-positions 4 --timeout-seconds 900 \
  --output-dir "$E/.local/diagnosis/<fresh-reviewed-qnn-segment>"
```

This command cannot prove a full 174-position trajectory or authorize a later segment. No phone, physical provider, generated-text, fidelity, performance, reset/reuse, or campaign claim follows from source readiness.
