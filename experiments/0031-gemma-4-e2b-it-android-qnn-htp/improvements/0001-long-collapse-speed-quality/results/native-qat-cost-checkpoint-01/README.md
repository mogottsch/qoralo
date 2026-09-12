# Native-QAT CPU cost checkpoint: useful partial trace

**The observation objective succeeded; the forward still timed out.** This separately authorized run retained959 operation starts and954 completions before the unchanged guard limit. No final logits or generation-quality result was produced. The earlier `b376a318` attempt remains consumed and unchanged.

## Same computation, bounded observations

The model, native mixed-bit/SRQ implementation, BF16 dtype, eager CPU attention, exact1929 IDs, positions, scales and `logits_to_keep=1` were unchanged. Every wrapper called the original callable once and returned its original object/result or exception. Pass-through tests also verified that installing the embedding-property wrapper did not itself evaluate `.weight`.

Operator starts were flushed before calls. Parent IDs/thread IDs correlate nesting; completed **exclusive** intervals are totaled, not parents plus children. Tensor metadata contains only shape/dtype/device, never contents. Native final logits would have stayed private if returned. Stdout/stderr had16MiB caps but used only473/324 bytes; nothing was discarded.

The guard used12GiB memory/2GiB swap/2CPU and the same600s envelope with cleanup reserve, live headroom and owned cleanup. It used **no memory-lock admission**. No phone, optimization or automatic replay occurred.

## Measured cost

The model was stopped inside zero-based layer21's MLP up-projection. The innermost open call was native `F.linear` with BF16 input `[1,1929,1536]` and weight `[12288,1536]`. The five open frames are nested ancestors, not five independent waits.

| Completed operation group | Calls | Exclusive wall time |
|---|---:|---:|
| Attention AV, head dimension256 |18|273.446s|
| Attention AV, head dimension512 |4|119.684s|
| `F.linear` |181|145.816s|
| Attention QK, both dimensions |22|21.056s|
| Native SRQ |361|2.254s|
| Linear weight dequantization |181|1.170s|
| Full token-embedding-table dequantization |1|1.806s|

For dimension256, QK took median0.849s while AV took15.192s. For dimension512, QK took1.443s while AV took29.910s. AV process CPU time was approximately its wall time—about one busy-core equivalent—whereas QK and linear CPU time were approximately twice wall time. This is a tensor-level cost observation, not identification of the lower-level kernel.

The native pad-row path did materialize the full token-embedding table exactly once, but its measured1.806s was not the dominant sampled cost. It was **not** replaced with an optimized lookup. Native SRQ and weight dequantization also were not the dominant completed costs.

At the observed per-shape medians,28 sliding and7 global AV operations alone project to **634.746s**, before other model work. That is an evidence-based extrapolation, not a guaranteed lower bound or complete runtime prediction. It explains why another unchanged600s completion promise would be unrealistic without additional evidence or an explicitly revised budget.

## CPU/I/O and evidence limits

Forward-sampled process counters observed4,988,928 additional disk-read bytes between the first and last samples after the forward marker. These are not exact whole-forward counters or RAM memory traffic. AV's large measured process-CPU intervals remain the useful cost signal.

Verbose output contained three MKL lines: a library banner and two small RoPE-related SGEMMs. There were no oneDNN verbose records. **Absence of records does not prove which AV kernel ran.** No dtype or kernel implementation was changed.

The trace has no malformed lines, cap indication or nesting-accounting errors. One instrumentation gap is retained: the decoder-layer selector used `Gemma4DecoderLayer`, while this pinned source uses `Gemma4TextDecoderLayer`. Therefore no dedicated per-decoder-layer-forward duration is claimed. Layer-qualified quantized-forward names and nested operator records still locate the partial execution.

## Outcome and cleanup

Actual child exit−15 at the guard's580s work limit; guard elapsed580.454s. The child was reaped. Final cgroup counters show no OOM/high/max events, memory peak5,381,378,048 bytes and swap peak0. Process VmHWM was7,127,773,184 bytes; these accounting measures are different and are not interchangeable. The root forward's open interval at stop was570.853s.

The snapshot is **partial cost evidence**, not QNN root-cause proof, QNNw4a16 numerical equivalence, a full native-QAT logit checkpoint or a quality result. No tensor values were captured by instrumentation. Source/launch/bounds, full metadata trace, bounded verbose streams, owned CPU/I/O samples and cleanup receipts are retained. No replay was performed under this grant.
