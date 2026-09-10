# Full-short HistogramObserver QDQ replay

**Completed all 174 teacher-forced input positions on the host. This is not QNN execution, autoregressive text generation, or a campaign result.**

The accepted saved HistogramObserver/W4A16 QDQ graph processed the exact canonical short token sequence from zero recurrent, convolution, and full-attention KV state. Input positions 0–173 and all 174 state updates completed. Every positional logit tensor was finite. Independent inspection of the saved tensors reproduced every argmax and retained top-logit value; the final tensor matches position 173.

## Bound artifacts and result

- Exact source: `Qwen/Qwen3.5-2B`, revision `15852e8c16360a2fea060d615a32b45270f8a8fc`.
- Converted checkpoint SHA-256: `a2640184f26ce851c3bf305fd77f4dac6af3381025a4ace1d431e7d685c70e86`.
- HistogramObserver QDQ archive: 13,645,661,902 bytes, SHA-256 `30799090d14a42c92ea804a2763df55ff231ba232653d96484324ad40c492364`.
- Exact parameter, 174-token input, QDQ archive, accepted artifact-manifest, helper-source, and verifier-source bindings are retained in `result.json` and `raw/result.json`.
- Final next-token argmax: **2523**, unique maximum **18.541059494018555**.
- Final tensor: 994,857 bytes, SHA-256 `38dc3e1fa499e3b1d96418735fb71cf3db8d7a8403bfa90deb4ec3f9c503ccad`.
- Pinned tokenizer JSON SHA-256: `5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42`. It decodes token 2523 as **`You`**; the exact three UTF-8 bytes are retained in `predicted-token.txt`.

`You` is only a single next-token interpretation. It is not a generated response, a sensible-text result, or an accuracy observation. Argmax differences from prior MinMax/physical runs use differing reference routes and are not accuracy comparisons.

## Host lifecycle and timing

The guarded helper exited 0 after 1,802.923 seconds; the supervising process measured 1,810.322 seconds against its explicitly authorized 7,200-second host limit. The helper duration includes input hashing, graph loading, forward/state steps, and durable per-position tensor/journal/checkpoint writes. Execution-only time was not separately measured. These are **host diagnostic wall times**, not Android prefill, TTFT, decode throughput, or matched benchmark measurements.

The process used four math threads, low CPU/I/O priority, and memory/I/O-pressure guards. Scratch was an owned disk-backed ext4 directory, never the 16 GiB `/tmp` tmpfs. After completion the child was reaped, its process group was absent, and scratch contained zero regular files. No retry, second heavy job, QNN invocation, or phone operation occurred. `resource-summary.json` and compressed raw telemetry preserve operating observations without relabeling host RSS as Android memory.

## Raw retention — migration requirement

Git contains the complete 174-position journal, result, command, logs, compressed final tensor/telemetry, and a per-file manifest with raw/compressed sizes, hashes, and retrieval paths. Every positional raw/compressed tensor pair was recovered and verified before this commit.

**Intermediate tensor bytes are LOCAL-ONLY. They cannot be recreated from Git hashes alone. Do not clean these directories. Include them in every migration or handover:**

```text
experiments/0032-qwen-3.5-2b-android-qnn-htp/.local/diagnosis/full-short-20260910T092627Z/replay/final-logits.pt.steps/
experiments/0032-qwen-3.5-2b-android-qnn-htp/.local/diagnosis/full-short-20260910T092627Z/retained-compressed/positions/
```

The 174 raw tensors total 173,105,118 bytes; their zstd level-3 copies total 148,995,000 bytes. Keeping them local avoids a roughly 150 MB Git addition while preserving all samples. The model/PT2 input artifacts are also local-only and must be retained as bound in the accepted artifact manifest.

Verification from a Git checkout (journal/bindings and two committed compressed artifacts; explicitly does **not** recover intermediate tensors):

```bash
E=experiments/0032-qwen-3.5-2b-android-qnn-htp
python "$E/tools/verify_saved_replay_evidence.py" "$E/results/host-histogram-full-short-20260910"
```

Full verification on a machine containing the required local archive (176 lossless recoveries and 174 small tensor-value checks; **no model archive load or execution**):

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  artifacts/venv-executorch-1.2/bin/python \
  "$E/tools/verify_saved_replay_evidence.py" "$E/results/host-histogram-full-short-20260910" \
  --include-local --tensor-values
```

Both verification reports are retained. A postprocessing path-normalization error was fixed without rerunning the model or changing raw outputs; its local note is `full-short-20260910T092627Z/curation-attempt-01.json`.

## Claim boundary and next source-only plan

The physical PTE `23ac8abd…d2c506` is unchanged. This result does not establish QNN-x86/full-prompt equivalence, FP32 fidelity, physical HTP output, sensible autoregressive text, chunk-prefill performance, loaded-route reset/isolation, or campaign readiness. The earlier same-position paired-QDQ result remains separate evidence.

The next lightweight readiness work should prepare a **same-HistogramObserver-PTE, same-input QNN trajectory comparison**, without launching it:

1. Support the diagnostic PTE's 73 outputs while propagating only the 49 standard outputs; retain hidden/logit diagnostics separately.
2. Start from zero state and feed the same 174 token IDs/masks/positions. Compare each position against its saved QDQ tensor. After position zero, each backend propagates its own state: this measures accumulated trajectory drift, not an identical-state operator comparison.
3. Add exclusive per-position raw/checkpoint/error retention and synthetic tests before a reviewed host run. QNN-x86 simulation previously took about an hour for 30 inputs; request an explicit bounded runtime/resource plan rather than silently assuming all 174 will fit the 7,200-second budget.
4. If segmented diagnostic execution is proposed, first prove lossless state/checkpoint continuation, bind the PTE and consumed prefix, and label process restarts explicitly. It must not be presented as loaded-route benchmark reuse.

No additional model run or phone access is authorized by this result. Chunked-prefill structural/state-equivalence work remains a subsequent host task, not a demonstrated speedup.
