# Qwen 0032 shutdown handover — 2026-08-28

## Last accepted milestone

- Commit `8387154` (`Record repaired Qwen physical output`), independently reviewed and pushed by Pi.
- Exact repaired PTE `23ac8abd7e39b596d62bdc6b098a3e61fe0688bf6d1f4d537959e13492d2c506` physically completed 696/696 QNN/HTP-v73 graph calls and produced token 1206 (`To`). This removes the prior token-0 corruption symptom but does not match host W4A16 QDQ token 760 (`The`) or establish campaign readiness.

## Current uncommitted work

Modified owner files, intentionally **not committed** because the diagnostic branch was interrupted and includes rejected prototypes:

- `experiments/0032-qwen-3.5-2b-android-qnn-htp/tools/compile_exact_qnn.py`
  - optional exact diagnostic outputs for every layer and layer-0 subcomponents;
  - MatMul-reduction, float-recurrence, FP16-island, symmetric-activation, and HistogramObserver switches.
- `experiments/0032-qwen-3.5-2b-android-qnn-htp/tools/localize_qnn_first_token.py`
  - understands diagnostic hidden/component outputs.

No other tracked 0032 files are modified. Do not stage other agents' handovers or unrelated untracked files.

## Completed host evidence

All comparisons use the exact pinned Qwen3.5-2B checkpoint/revision, canonical W4A16 weight recipe, same token position 0, same token ID 248045, and zero initial state.

1. Exact MinMax baseline per-layer hidden comparison:
   - `.local/diagnosis/layer-hidden/comparison.json`
   - SHA-256 `6670beb4ee0d18a0668ccd596c2b9406303f689f7357b49a3b738174df4d4476`
   - embedding/norm align; hidden cosine declines smoothly from layer 0 `0.987449` through layer 23 `0.491839`; final-logit cosine `0.433603`.
2. Exact layer-0 component localization:
   - embedding cosine `0.99999994`, attention-normalized `1.0`, attention output `0.992725`, FFN output `0.969934`, layer-0 hidden `0.987449`.
3. Exact layer-0 attention localization:
   - recurrence core cosine `0.999333`;
   - Gated RMSNorm output cosine `0.993601`;
   - this is precision amplification, not a second discrete broadcast/lowering failure.
4. Rejected variants (logs retained under `.local/diagnosis/`):
   - MatMul recurrence reductions worsened the recurrent/Gated RMSNorm comparison and changed QDQ behavior materially.
   - unquantized float recurrence compiled with 214 tensor-compute fallbacks (including 161 mul and 35 add): rejected.
   - explicit FP16 recurrence island made arithmetic supportable but left 143 `dim_order_ops._to_dim_order_copy` nodes outside QNN: rejected under zero-fallback policy.
   - symmetric activations failed QNN preprocessing (`InsertIOQDQ`, per-channel dequantize key error): rejected.
5. Positive fully delegated variant:
   - HistogramObserver activation-range calibration, W4A16 weights unchanged;
   - four QNN subgraphs, 4,210 delegated tensor-compute nodes, zero nondelegated tensor compute;
   - recurrence core cosine improves `0.999333 → 0.999527`;
   - Gated RMSNorm cosine improves `0.993601 → 0.996718`;
   - same-position final-logit cosine improves `0.433603 → 0.947168`;
   - QDQ and QNN-x86 both choose argmax token 198 at position 0.

The last completed owner tests were 20/20 before the final diagnostic switches. The current tools were successfully imported/used for the positive HistogramObserver compile and comparison, but rerun py_compile and the 0032 tests after restart before committing.

## Large ignored artifacts

Positive HistogramObserver route:

- `.local/diagnosis/layer0-attention-histogram/diagnostic-w4a16-qnn.pte`
  - 1,995,775,336 bytes
  - SHA-256 `141c19b03bbbae1e2a4bafd453300876a7940f97403ed1cf95be726c68972b00`
- `.local/diagnosis/layer0-attention-histogram/diagnostic-w4a16-qdq.pt2`
  - 13,645,443,790 bytes
  - SHA-256 `6233c85ede80011c7ce69edd513a4906355b1723c3284be1c801c22d9251a08f`
- `.local/diagnosis/layer0-attention-histogram/comparison.json`
  - SHA-256 `88cf1cddb5bb218df2942c165075089403d371f9a007fbdc5d4bbb55d88068da`
- `.local/diagnosis/layer0-attention-histogram/compile-result.json`
  - SHA-256 `48b3dcc30374e36e8fa4abed5af16f56c6fc855975ce7dd5c136e29d2d03dcf2`

Keep PTE/PT2/checkpoints outside Git. Only bounded JSON/log summaries should become durable evidence.

## Interrupted processes and restart state

Pi's shutdown record is `/tmp/qwen-shutdown-20260828T135031Z.txt`; the owner copy is `.local/diagnosis/shutdown-process-state-20260828.txt`.

Two concurrent processes were terminated with TERM and are absent:

1. PID 2714920: full 174-token HistogramObserver QDQ replay. It reached the logged checkpoint at token 110/174. Partial logs remain at:
   - `.local/diagnosis/layer0-attention-histogram/full-prompt.stdout.log`
   - `.local/diagnosis/layer0-attention-histogram/full-prompt.stderr.log`
   - `full-prompt.json` is only the pre-run placeholder and is not a completed result.
2. PID 2714972: HistogramObserver per-layer-hidden exact compile. It had not produced a PTE/result; partial logs remain at:
   - `.local/diagnosis/layer-hidden-histogram/compile.stdout.log`
   - `.local/diagnosis/layer-hidden-histogram/compile.stderr.log`

Both ran concurrently at roughly 10.3 GB and 8.8 GB RSS, causing actual host memory pressure. **Restart serially, not concurrently.**

## Exact next step

After restart:

1. Confirm no stale process, then run:
   ```bash
   python -m py_compile \
     experiments/0032-qwen-3.5-2b-android-qnn-htp/tools/compile_exact_qnn.py \
     experiments/0032-qwen-3.5-2b-android-qnn-htp/tools/localize_qnn_first_token.py
   python experiments/0032-qwen-3.5-2b-android-qnn-htp/tests/test_contract.py
   ```
2. **Serially** rerun the interrupted per-layer-hidden compile using the normal exact compile environment and these distinguishing arguments:
   ```text
   --context 4096 --shards 4 --diagnostic-hidden-states --histogram-activations
   --qdq-output .local/diagnosis/layer-hidden-histogram/diagnostic-w4a16-qdq.pt2
   --output .local/diagnosis/layer-hidden-histogram/diagnostic-w4a16-qnn.pte
   --result .local/diagnosis/layer-hidden-histogram/compile-result.json
   ```
   Then run `localize_qnn_first_token.py` phases `qdq`, `qnn`, and `compare` with `--diagnostic-hidden-states` to quantify the full layerwise improvement.
3. Only after that process exits and memory is released, restart the full 174-token HistogramObserver QDQ replay using the exact command preserved in `/tmp/qwen-shutdown-20260828T135031Z.txt`. Do not treat the token-110 partial run as a result.
4. If the per-layer and full-prompt evidence remain positive, curate/commit a bounded host-only HistogramObserver precision milestone. Do not replace the physically proven MinMax PTE yet.
5. Chunk-prefill work is next, after this bounded precision decision: start with a small static chunk structural/eager-equivalence probe that proves sequential Gated Delta state updates, causal convolution state, full-attention KV insertion/masking, and zero tensor-compute fallback.

## Blockers, risks, and claim boundaries

- Shutdown interruption is the immediate blocker; the positive position-0 HistogramObserver result itself is complete.
- Full-prompt HistogramObserver QDQ output and per-layer HistogramObserver curve are not complete.
- No HistogramObserver route has run physically; no Android output/performance claim.
- No chunked-prefill graph has compiled yet; no speedup claim.
- Do not infer QNN-x86-to-phone equivalence from position 0.
- Do not weaken exact model identity, W4 weights, or zero tensor-compute fallback.
- No ADB was used in this post-`8387154` work. At shutdown, no Qwen child process remained and `artifacts/locks/phone.lock` was independently verified free. Phone priority is not owned by Ben.
