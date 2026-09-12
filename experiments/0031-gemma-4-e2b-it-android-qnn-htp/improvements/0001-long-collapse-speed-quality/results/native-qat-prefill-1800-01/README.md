# Full native-QAT last-position checkpoint

**One direct CPU prefill completed and returned all 262,144 last-position logits.** This is a numerical reference checkpoint, not a generation-quality result or proof that the QNN route is defective.

## Authorization and unchanged computation

The earlier 600-second attempts remain immutable: `b376a318` timed out without logits; `4f4d60a4` retained a useful partial cost trace. That trace projected roughly 635 seconds for attention AV alone. Pi then explicitly authorized **one new 1,800-second total envelope**, including cleanup, with the same 12 GiB RAM / 2 GiB swap / 2 CPU limits and fresh/live headroom. The guard reserved 30 seconds for cleanup and allowed 1,770 seconds of work. No memory-lock admission was used.

Only the missing `Gemma4TextDecoderLayer` observation selector was fixed (`5310954e`), with exactly-once/pass-through/restoration tests. The native computation was not optimized or replaced:

- Pinned Transformers source `323f24345ed92f88e68a14aeef7db78ee2b52475`; existing PyTorch `2.10.0+cpu` and isolated dependency overlay.
- Original native mixed INT2/4/8 weights, SRQ8, BF16 CPU tensors, eager attention, eval/inference mode, two compute threads and one interop thread.
- Exact single-BOS **1,929 input IDs**, positions 0–1928, all-one attention mask, `use_cache=False`, `logits_to_keep=1` and `return_dict=True`.
- No `generate()`, sampling, device access, head replacement, dtype/kernel/scale change, pad-row optimization or automatic replay.

The loaded native path again passed all 1,371 text/head tensor checks: key, shape, dtype, CPU placement and exact checkpoint values. The pinned loader's 230 declared-unused checkpoint keys and native cache-scale omissions remain disclosed, not custom-applied.

## Complete output and execution coverage

The forward took **948.119 seconds**; guard elapsed **958.471 seconds**. Native child and guard both exited 0, naturally, with no timeout or delivered stop signal. The child was reaped.

| Saved private artifact | Bytes | SHA-256 |
|---|---:|---|
| Original BF16 bits, `[1,1,262144]` | 524,288 | `021585a71f18f3e9a071455864bde306762ff052afabc190b28f0527a535b28c` |
| F32 serialization of those logits | 1,048,576 | `f2c76d883ed7c67554357d8aa9958803e288adf1e83eb6557b9c3a21d0b253ec` |

Independent saved-byte analysis verified the shape/length and both hashes, checked every BF16-to-F32 bit expansion, and found **all values finite**. The unique argmax is **token ID 8291**. Full vectors and numerical top-logit analysis remain private; this package contains their bindings and verification metadata, not the tensor contents.

Coverage is complete for this single forward:

- All **278** loaded native text/head quantized modules were called exactly once; names independently match the loaded inventory and completed trace.
- **552 native SRQ calls**, all 8-bit; **550 calibrated** calls, matching the native observation receipt.
- All **35 decoder-layer forward boundaries** completed once after the observation-selector fix.
- **1,496 starts and 1,496 completions** in 2,992 flushed JSONL events: no open frames, malformed lines, logging error, cap indication or nesting-accounting mismatch.
- The full token-embedding table was still materialized once by the native pad-row property. No lookup substitution occurred.

## Observed CPU cost

Completed **exclusive wall intervals** avoid summing parents and nested children twice. Observation overhead is included.

| Operation group | Calls | Exclusive wall time |
|---|---:|---:|
| Attention AV, D256 | 28 | 425.097 s |
| Attention AV, D512 | 7 | 201.501 s |
| `F.linear` | 277 | 273.948 s |
| Attention QK, both dimensions | 35 | 33.675 s |
| Native SRQ | 552 | 4.018 s |
| Linear weight dequantization | 276 | 2.618 s |
| Full token-embedding-table dequantization | 1 | 1.367 s |
| Other exclusive work / observation overhead | — | 5.890 s |

AV accounted for **626.598 seconds** of the completed forward. Its process CPU time was approximately wall time, about one busy-core equivalent; QK and linear CPU time were approximately twice wall time. This does not identify the underlying AV kernel or prove a particular thread count.

Bounded MKL/oneDNN verbosity and owned-process CPU/I/O samples were retained. Neither stream was truncated. Missing verbose records do not identify or rule out a kernel. Forward-sampled disk-read delta was 1,011,712 bytes between sampled endpoints—not exact whole-forward I/O or RAM traffic.

Final cgroup counters show **no OOM/high/max events**, memory peak **4,901,928,960 bytes**, and swap peak **0**. Sampled process VmHWM reached **7,154,876,416 bytes**; process residency and cgroup charging are different accounting measures. Minimum sampled host MemAvailable was **19,611,336,704 bytes**. These are host diagnostic observations, not Android benchmark metrics.

## What this establishes—and what it does not

This establishes a strictly loaded, complete **native-QAT CPU last-position logit reference** on the frozen input. It does not establish bitwise equality to the earlier uninstrumented attempt, which returned no logits.

The native argmax 8291 differs from the recorded QNN selected ID 818 and aligned GPU callback ID 2094. That is only a descriptive first-position comparison: native mixed-bit/SRQ8/BF16, the exported QNN w4a16 route, and the LiteRT artifact are not matched numerical implementations. Selected IDs alone cannot localize an exporter or execution defect.

No tokens were autoregressively generated and no EOS or long-output reliability conclusion follows. The QNN repetition-collapse root cause remains unresolved. The canonical Android campaign and earlier negative diagnostics were not refreshed or replaced. Any next comparison requires source/semantics and saved-logit inspection first; this grant is consumed and permits no further replay.
