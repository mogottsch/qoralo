# Native-QAT CPU checkpoint: bounded timeout, no logits

**The one authorized forward attempt was consumed.** Strict loaded text/head validation passed, but the forward did not return before the guard stopped work at580 seconds inside its600-second envelope. There is **no last-position logit vector, numerical-fidelity result or generation-quality result**. No replay followed.

## What actually ran

- Pinned Transformers source `323f24345ed92f88e68a14aeef7db78ee2b52475` (reports5.16.0.dev0), torch2.10.0+cpu, and private dependency overlays. The working QAIRT environment was not modified.
- Native QAT checkpoint `efab4290…76a9a4`, native quantization config `cf6d7dc2…0424`, unchanged native Gemma quantization implementation `9bf6d109…cc17`.
- **1,371 loaded text/head tensors** checked against source values at their native dtype, including packed weights, scale values, shapes and CPU placement. Quantized module classes/bit widths matched the native inventory. The230 source keys unused by the pinned native model/quantizer were explicitly accounted for, not silently dropped by custom logic.
- Exact frozen1929 single-BOS IDs `3b5c04fe…52b64`, positions0–1928, all-one input attention mask, CPU/eager attention, BF16 native computation, `use_cache=False`, `logits_to_keep=1`. No tokenizer/BOS addition and no `generate()` call.
- The pinned native SRQ/mixed-bit path was selected; no dequantized-weight-only substitute or dtype fallback was made. However, complete module/SRQ execution counters were only written after return, and were not reached before termination. **Complete observed execution coverage is therefore unavailable**, rather than claimed from configuration alone.

## Preserved preparation and load history

1. Metadata-only validation initially rejected PLE scales `[262144,35]` against a constructor placeholder `[262144,1]`. Inspection showed that the exact native quantized loader accepts checkpoint-shaped parameters, and native embedding dequantization already supports35 blocks of256 columns. Only the validator was corrected for that exact source-defined shape; no model/scale arithmetic was patched. Regression tests reject other shapes.
2. An unsupported systemd `MemoryOOMGroup` property was rejected before a process or lock was started. The supported group-kill OOM policy was then used.
3. Load attempt1 read2550 tensors but failed during generation-config initialization because the old local directory held only safetensors. Exact same-revision generation metadata (`fb53f4c6…1050e`) was supplied explicitly; it is unused by the direct forward. This attempt made **zero forwards**.
4. Guard attempt2 found a transient host-lock conflict and launched no child. The later kernel query showed no matching holder; the record does not identify or blame another agent.
5. Guard attempt3 passed actual loaded validation and attempted **one forward**. At580.402s the guard terminated its owned child with SIGTERM; actual child exit−15. The child was reaped and resources released. No raw logits had been written.

Limits were MemoryHigh10GiB/MemoryMax12GiB/MemorySwapMax2GiB,2CPU,nice15, idle I/O,600s process envelope with cleanup margin and live headroom floors. The journal records754.181s CPU over580.464s wall time and5.8GiB peak memory. A live snapshot retained6,247,862,272 peak bytes. No OOM or headroom-floor trigger occurred. Minimum observed host available memory was19,420,823,552 bytes.

The historical run acquired `heavy-ram.lock` under the then-current coordination instruction and released its descriptor during normal cleanup. Moritz removed that admission requirement while the run was active. **Future launches must not require a memory lock**; actual resource/headroom safeguards remain mandatory, and `phone.lock` remains mandatory for device work. No phone was accessed here.

## Offline cost assessment

Saved validated matrix shapes and the pinned eager implementation imply approximately:

-7.188 trillion nominal FLOPs in276 quantized linear calls;
-0.053 trillion in the ordinary PLE projection;
-1.280 trillion in eager QK/AV attention products;
-**8.522 trillion combined**, before unpacking, SRQ, normalization, softmax, allocation and memory traffic.

The native linears dequantize2.266 billion weight values. Their SRQ input/output tensors cover3.155 billion elements across the nominal forward. These are static workload descriptors, **not measured throughput or a completion-time prediction**.

A concrete source cost deserves observation: `Gemma4Model.forward` obtains the pad row through `embed_tokens.weight[pad_token_id,:]`. For the native quantized embedding, `.weight` materializes the complete262144×1536 table before indexing. Its BF16 result alone is805MB and its repeated FP32 scale tensor is1.61GB. We did not replace this with a cheaper lookup or remove the operation.

The host is Ryzen7 5800H: AVX2 is present; AVX512/BF16 ISA flags are absent. The actually selected BF16 GEMM kernel was not captured, so this does not prove the sole bottleneck. The saved guard recorded capacity, not per-process I/O counters. There are no per-module timings or partial operation markers beyond forward start. We cannot retrospectively locate the unfinished operation or claim zero I/O wait.

## One proposed next observation-only checkpoint

Recommend **one newly authorized, identically configured checkpoint with streamed operation timings**, retaining the same1929 IDs, BF16/native SRQ/mixed bits, eager attention, `logits_to_keep=1`, and12GiB/2GiB-swap/2CPU/600s envelope. No deadline bump, changed dtype/computation, shortened input or alternate arm is proposed.

Before each native call, flush an operation-start record; after return, record wall/process-CPU duration, shapes/dtypes and completion. Cover:

- token and PLE embedding dequantization, including the full-table `.weight` property;
- every quantized linear's weight dequantization and SRQ calls;
- native `F.linear` calls and decoder-layer boundaries;
- owned-child CPU and read/write counters, with bounded optional oneDNN/MKL verbosity to identify actual CPU kernels.

The observation-only `native_qat_cost_trace.py` helper is prepared and tested for unchanged argument/result/exception behavior and pre-call flushing. It imports or runs no model. Installation/restoration of wrappers must retain the original native callables and avoid inspecting a quantized embedding's `.weight` merely to label a trace, which would itself add expensive work.

**The realistic success criterion of that bounded retry is durable cost evidence**, including the last unfinished operation if it times out again. Full logits remain a conditional outcome, not promised within the unchanged budget. This would provide evidence for any later resource decision instead of a blind timeout increase. The old grant is consumed; this proposal has not been executed.
