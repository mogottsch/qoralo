# Pocket ONNX mixed QNN HTP + CPU results

## Clear outcome

**The hybrid route completed text-to-WAV and physically used HTP, but it failed the acceleration/equivalence objectives and Moritz rejected the exact retained sample in listening.**

The primary warm result was:

> **Hybrid warm median RTF: `1.003`**

The CPU-only baseline was `0.630`. Therefore, normalized by generated audio duration, the hybrid route was **59.1% slower** than CPU-only and ran approximately at real-time speed.

More importantly, hybrid execution changed the model's EOS decision. It generated only `3.84 s` of audio instead of the CPU baseline's `6.24 s`. The hybrid output is structurally valid audio (decodable, finite, non-silent, and unclipped), but it is **not numerically or behaviorally equivalent** to the CPU output. Structural validity is not a claim of usable speech.

This is a mixed route, not full HTP.

## Performance

The timing process had profiling disabled so detailed tracing overhead did not contaminate the benchmark.

| Measurement | CPU-only 0012 | Mixed QNN/CPU 0016 | Result |
|---|---:|---:|---:|
| Model/session load | 1.079 s | 2.830 s | Hybrid 162.2% slower |
| Cold generation | 5.697 s | 4.619 s | Not directly comparable: hybrid emitted less audio |
| Cold audio duration | 6.24 s | 3.84 s | Hybrid output 38.5% shorter |
| **Cold RTF** | **0.913** | **1.203** | Hybrid 31.8% worse |
| Warm median generation | 3.933 s | 3.851 s | Not a speedup: hybrid emitted less audio |
| **Warm median RTF** | **0.630** | **1.003** | **Hybrid 59.1% worse** |
| Warm RTF range | 0.628–0.656 | 0.980–1.050 | Hybrid worse |
| Process VmHWM | 1,586,080 kB | 1,188,084 kB | Hybrid 25.1% lower, with caveats |

RTF is generation time divided by generated audio duration. Lower is better. The hybrid warm median corresponds to about `0.997×` real time, versus `1.586×` real time for CPU-only.

`VmHWM` is cumulative process high-water memory, including mapped models/runtime, QNN provider, recurrent caches, buffers, and output. It is not isolated weight or tensor memory.

## How much ran on HTP?

A separate one-generation instrumented process recorded every ORT provider event. The five profiles map deterministically to the Pocket session-construction order.

| Component | Calls | CPU events | QNN events | Distinct CPU kernel events | Distinct QNN partition events |
|---|---:|---:|---:|---:|---:|
| Flow step | 48 | 9,168 | 144 | 191 | 3 |
| FlowLM main | 51 | 34,629 | 1,326 | 679 | 26 |
| Mimi encoder | 1 | 191 | 5 | 191 | 5 |
| Mimi decoder | 4 | 1,128 | 40 | 282 | 10 |
| Text conditioner | 1 | 1 | 0 | 1 | 0 |
| **Total** |  | **45,117** | **1,515** |  |  |

Only **3.25% of recorded provider kernel events** were QNN partition events. One QNN partition event can contain several ONNX nodes, so this percentage is an event ratio rather than a node or FLOP ratio. It nevertheless shows that orchestration remained overwhelmingly CPU-heavy.

The original dynamic-graph capability screen from experiment 0014 similarly found fragmented partial assignment: FlowLM had 26 QNN partitions, flow had 3, encoder had 5, decoder had 10, and the text conditioner had none.

## Physical HTP proof

The detailed QNN profile contained exactly `1,515` physical executions, matching the `1,515` ORT QNN provider events:

- 1,515 RPC execute events, totaling 4,882,217 µs
- 1,515 QNN accelerator execute events, totaling 4,618,650 µs
- 1,515 accelerator cycle events, totaling 2,635,657,640 cycles
- 1,515 HVX records, each reporting 4 threads

This proves that the reported QNN partitions physically executed on HTP. It does not establish the internal arithmetic precision used by QNN merely because the source graphs contain FP tensors.

## Audio sample and fidelity

Representative hybrid WAV:

```text
/home/moritz/vibevoice-android-spike/experiments/0016-pocket-onnx-qnn-hybrid-android/work/pocket-hybrid-qnn-cpu-android.wav
```

SHA-256:

```text
6cd3a98fb821ad76b0c0ad55a20f910da7be9d3058e511ff807b4a4f694aa45f
```

Validation:

- 24 kHz mono PCM16
- 92,160 samples / 3.84 seconds
- finite and non-silent
- peak PCM16 amplitude 8,518
- RMS PCM16 amplitude 575.70
- unclipped
- the proof output and all six benchmark outputs were byte-identical

However, CPU-only generated 149,760 samples / 6.24 seconds using the same frozen text, voice, seed, temperature, flow steps, graphs, and one-thread contract. Hybrid QNN numerical behavior caused EOS after 48 latent frames instead of 78.

Comparing the shared 92,160-sample prefix:

- correlation: `0.89373`
- SNR: `6.51 dB`
- mean absolute error: `0.00604` in normalized PCM units
- maximum absolute error: `0.16129`

This output does **not** pass as equivalent to CPU-only. It is retained as an experimental hybrid sample, not as a faithful acceleration result.

## Moritz listening verdict

Moritz rejected this exact hybrid sample, SHA-256 `6cd3a98fb821ad76b0c0ad55a20f910da7be9d3058e511ff807b4a4f694aa45f`, describing “takataktaka.” This is an exact route/sample verdict only. It does not reject Pocket TTS as a family. Experiment 0012's separate “takakakakakakakaka” rejection remains specific to its different CPU route/sample SHA `406349…7d22`.

## Implementation boundary

The experiment added a narrowly scoped generic QNN selection path to sherpa-onnx at pinned source commit `3dc7c569…`. It forwards QNN provider options while intentionally retaining CPU fallback. The exact patch is [`tools/sherpa-generic-qnn-hybrid.patch`](tools/sherpa-generic-qnn-hybrid.patch).

The five Pocket ONNX graphs were reused unchanged from experiment 0012 and verified by hash. No quantization, calibration, operator rewrite, or model substitution occurred.

## Conclusion

Enabling CPU fallback made the current graphs runnable with QNN, but it did not produce a useful acceleration:

1. Most provider events remained on CPU.
2. Frequent fragmented QNN partitions incurred transfer and RPC overhead.
3. Warm RTF regressed from `0.630` to `1.003`.
4. Numerical differences changed EOS and materially changed the waveform.
5. Moritz rejected the exact retained hybrid sample as “takataktaka.”

The current hybrid route should not replace the CPU technical baseline. A separately authorized QNN-oriented, equivalence-gated export would be the appropriate technical direction; this result does not create or approve such a follow-up. Experiment 0015 does not exist and must not be cited as a route.

Machine-readable result: [`results/hybrid-phone.json`](results/hybrid-phone.json).
