# Saved-QDQ replay helper readiness

**Source and synthetic tests only. No model archive was loaded, no real prompt replay was run, and no phone was accessed.** This prepares a safer replacement for the unused replay prototype; it does not extend the numerical evidence in `e528f41`.

`tools/replay_saved_qdq.py` derives all output IDs and logits from the graph's actual tensors. It has no physical-output placeholder or hard-coded expected model answer. Its default artifact manifest binds the accepted HistogramObserver diagnostic PT2 archive and parameter file by SHA-256 and size before loading.

## Contract protected by the helper

- Exactly 174 little-endian int32 IDs with the canonical short token hash. Same-length substitutions, wrong endian, truncation, extension, and insufficient prompt-plus-2048 context are rejected before graph loading.
- Each invocation starts from zero recurrent, convolution, and full-attention KV state. It feeds the original prompt IDs in order, positions 0–173, and masks only prior occupied KV slots plus the current-token slot as visible.
- Recurrent/convolution outputs are cloned for the next step; full-attention key/value slices are inserted at the actual input position. Extra hidden/component diagnostic outputs are ignored, never used as state.
- Every returned raw logit tensor is saved to a new `--logits.steps/position-NNN.pt` checkpoint before summary or state-output validation. Each journal entry binds its tensor path/hash, input token, position, actual argmax, top logits, and finiteness observations.
- Evaluated-token and completed-state-update counts are separate. Model-load errors, graph exceptions, malformed state outputs, nonfinite/empty logits, and TERM/INT leave an explicit error/interruption result and preserve prior evidence; they do not become a successful completion.
- Empty/nonfinite logits do not inherit a previous step's summary or publish a fabricated argmax. Nonfinite raw tensors are retained with a null argmax.
- The final `--logits` tensor and `final_logits` summary are populated only after all steps and state updates succeed. Before then the reserved final tensor path is empty; partial tensors are in the checkpoint directory, not at that final path.
- Output/result, journal, final tensor, and checkpoint directory are exclusively created. Existing files/directories, dangling symlinks, input/output aliases, and prior partial attempts cannot be overwritten. Atomic checkpoint replacement uses file and directory fsync. A forced SIGKILL or power loss may leave `started_not_complete`; this is never interpreted as completion or resumable KV state.

The helper does not retry, resume, or schedule jobs. Host-slot approval and the outer resource guard remain required. No optional RSS/timing counter is used as an inference-success gate.

## Synthetic validation

`tests/test_replay_saved_qdq.py` covers successful 174-input state/mask transport with a two-layer tiny graph, different computed argmax outcomes, tie handling, artifact/input identity errors, real SIGTERM handler dispatch/restoration, partial/error raw retention, invalid state geometry, alias protection, failed atomic writes, and final-save failure.

The tests replace `torch.export.load` with a failure trap: any actual model-deserialization attempt would fail the suite. Test inputs are only the pinned 696-byte token-ID file, tiny fake artifact files, and small synthetic tensors. `test-process.json` records the lightweight process bound; its RSS/time are test-process observations, not LLM measurements.

Run after source review:

```bash
E=experiments/0032-qwen-3.5-2b-android-qnn-htp
python -m py_compile "$E/tools/replay_saved_qdq.py" "$E/tests/test_replay_saved_qdq.py"
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  artifacts/venv-executorch-1.2/bin/python "$E/tests/test_replay_saved_qdq.py" -v
```

An initial test-launch command could not find `/usr/bin/time`; no test/model execution occurred in that launch. Its stderr is retained. The successful launcher used Python's standard-library timer/resource accounting instead. No dependency installation was needed.

## Future real replay command — not executed

Only after Pi reviews this helper and releases a heavy-host slot, use a **new** output directory under the existing resource supervisor:

```bash
E="$PWD/experiments/0032-qwen-3.5-2b-android-qnn-htp"
export PYTHONPATH="$E/.local/executorch:$PWD"
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
# Pick a fresh attempt root; do not reuse interrupted outputs.
D="$E/.local/diagnosis/<fresh-replay-attempt>"
nice -n 15 ionice -c 2 -n 7 artifacts/venv-executorch-1.2/bin/python \
  "$E/tools/replay_saved_qdq.py" \
  --params "$E/.local/executorch/examples/models/qwen3_5/config/2b_config.json" \
  --token-ids "$E/protocol/token-ids/short.int32le" \
  --qdq-file "$E/.local/diagnosis/restart-20260910T083327Z/01-hidden-compile/diagnostic-w4a16-qdq.pt2" \
  --artifact-manifest "$E/results/host-histogram-precision-20260910/artifact-manifest.json" \
  --output "$D/result.json" --logits "$D/final-logits.pt" \
  --progress "$D/progress.jsonl" --context 4096
```

This supersedes the older unused local replay wrapper, which lacks the required `--progress` argument. Do not execute this command without the separate resource guard/release. A successful future replay would still be host QDQ evidence, not QNN-x86 execution, physical HTP, sensible autoregressive text, or campaign readiness.
