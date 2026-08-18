# Experiment 0010 execution plan

## Goal

Select and validate a text-to-speech model that can become the local voice of a future NotebookLM-like Android experience. It should sound pleasant and natural over sustained listening, with podcast-like delivery rather than merely intelligible speech.

A convincing two-speaker conversation is desirable but not required. A strong narrator or persistent voices generated turn by turn can also meet the goal if the deployment remains practical on a modern phone.

The current model is Supertonic 3, selected from the completed listening and Android experiments. The current runtime question is whether Qualcomm HTP acceleration improves the working CPU deployment enough to justify its extra complexity.

## Phase map

These phases belong to experiment [`0010: Supertonic QNN/HTP feasibility`](README.md). The completed result is summarized in the experiment [`README`](README.md), final [`HANDOFF`](HANDOFF.md), and canonical [`E2E checkpoint`](results/e2e-hybrid-cpu-checkpoint.json).

| Phase | Status | Purpose |
|---|---|---|
| Phase 1: vocoder HTP feasibility | **Complete — numerically rejected, perceptually promising** | Physical HTP execution succeeded and failed the frozen full-tensor gate; a later informal blind A/B found no audible difference for the single frozen utterance. |
| Phase 2: vector-estimator value | **Complete — full HTP blocked; paired one-run diagnostic complete** | Fail-closed assignment remains blocked. In one matched cold step-00 pair, mixed QNN+CPU was 9.23% faster than CPU-only inference, but session creation was 118.4× longer and peak RSS 4.68× higher; no recursive-chain evidence exists. |
| Phase 3: complete accelerated synthesis | **Complete — faster hybrid, numerical rejection, perceptual match** | Hybrid warm latency was 37.22% lower. The prospective waveform gate failed, while Moritz later reported the randomized CPU/hybrid samples sounded exactly the same. |
| Phase 4: deployment decision | **Complete — retain CPU; bound hybrid as research** | CPU remains the supported reference. The fixed-shape mixed route is perceptually promising but carries very high setup/memory costs and is not numerically accepted or production-ready. |

## Current position

| State | Work item | Result or gate |
|---|---|---|
| **Done** | Tiny physical-HTP control | A six-node QDQ graph executed on the S23 Ultra's HTP v73 with CPU fallback disabled. This proves the device path only. |
| **Done** | Patched host runtime | ONNX Runtime 1.27.1 with the Pad-selector backport was rebuilt against QAIRT 2.49 and reproduced the retained library hash. |
| **Done** | Models and fixtures | Official Supertonic INT8 models, deterministic fixtures, and the fixed and folded vocoder derivatives were restored and hash-verified. |
| **Done** | Folded-vocoder negative gate | The folded vocoder exposes 338 supported nodes and eight unsupported `Erf` nodes. Session creation is rejected with fallback disabled; no inference runs. |
| **Done** | Explicit GELU derivative | Eight verified standard GELU decompositions were replaced by explicit `com.microsoft.Gelu`; the full 731,136-element CPU output is bit-identical to the folded/fixed reference. |
| **Done** | Explicit GELU host gate | With CPU fallback disabled, patched host ORT assigns the complete optimized graph to one QNN partition (304/304 nodes) and initializes successfully. This is host capability evidence only. |
| **Done** | Android runtime build | Patched arm64-v8a/API 27 ONNX Runtime + QNN was rebuilt, validated, and reused for the scoped physical explicit-GELU vocoder probe. |
| **Done** | Scoped physical HTP execution | The exact authorized S23 Ultra executed three vocoder iterations with fallback disabled. Detailed profiles contain RPC, QNN accelerator, accelerator-cycle, and four-HVX-thread evidence. |
| **Failed** | Frozen physical numerical gate | All 731,136 finite samples were compared, but cosine `0.865454`, SNR `5.716 dB`, max error `0.595960`, mean error `0.012167`, and RMSE `0.029311` fail the predeclared limits. The result remains numerically rejected. |
| **Observed** | Post-hoc blind A/B | Moritz reported that the CPU reference and physical-HTP WAV sounded exactly the same for this one frozen utterance. This single-listener observation is encouraging product evidence, but it does not retroactively pass the numerical policy or establish broad perceptual equivalence. |
| **Done** | Cleanup and stop gate | The unique scoped device directory was removed and the phone lock was released. No vector-estimator work began during the completed vocoder campaign. |
| **Done** | Layer-level numerical bisection | The first material observable boundary is the composite embed `Pad → QDQ` transition. An exact-real-input QDQ microprobe is non-material, while exposing raw embed `Conv` breaks full delegation; the evidence is fusion/context dependent and does not establish an operator defect. |
| **Blocked** | Released vector estimator host gate | Concrete shapes remove the released graph's dynamic-I/O rejection, but patched ORT/QNN supports only 921 of 1,057 optimized nodes across 21 partitions. The remaining 136 nodes prevent fail-closed session creation. |
| **Observed** | One step-00 CPU-fallback diagnostic | Mixed execution is physically proven: 21 QNN partition events and 136 CPU node events. The full tensor passed its prospective gate in `1.054 s`; this is not full HTP. |
| **Observed** | Matched step-00 CPU-only diagnostic | All 823 profile node events ran on CPU. Its `1.161 s` inference makes the single mixed observation 9.23% faster, while CPU session creation and peak RSS were dramatically lower. |
| **Done** | Fixed-transcript end-to-end CPU and hybrid generation | Both routes executed duration, text encoding, five recursive estimator calls, vocoding, trimming, and WAV output. Hybrid physically used HTP for estimator partitions and the fully delegated vocoder. |
| **Observed** | End-to-end latency | Hybrid warm median was `3.809 s` versus CPU `6.067 s`, a 37.22% reduction. Hybrid session creation was `26.965 s` versus `0.611 s`, and peak RSS was `1,154,172 KiB` versus `459,432 KiB`. |
| **Failed** | Prospective end-to-end numerical audio gate | Both WAVs are structurally valid and non-silent, but hybrid-vs-CPU cosine `0.405`, SNR `-0.593 dB`, and normalized RMSE `1.071` fail the frozen gate. |
| **Observed** | Post-run randomized A/B | Moritz reported that the CPU and hybrid E2E samples sounded exactly the same. This is one-listener/one-utterance informal evidence and does not override the failed waveform gate. |
| **Decided** | Bounded deployment conclusion | Preserve CPU as the supported reference and the fixed-shape hybrid as a research baseline only. No production adoption or full-HTP success is claimed. |

The current boundary is therefore clear: **the fixed-transcript hybrid pipeline works end to end and is materially faster once initialized, with physical HTP proof for 20 mixed vector-estimator calls and four fully delegated vocoder calls. It is not full HTP, requires 44.1× longer session creation and 2.51× peak `ru_maxrss`, and fails the prospective numerical comparison even though Moritz heard no difference in the randomized A/B. CPU remains the supported reference; hybrid remains a bounded research baseline.**

When a phase finishes, its detailed result stays in experiment `0010`, its condensed outcome moves to [`docs/history.md`](../../docs/history.md) and the [history HTML](../../docs/history.html), and it is removed from this plan.

## Phase 1: establish vocoder HTP feasibility

The former blocker was eight `Erf` nodes inside standard decomposed GELU patterns. A narrow, source-hash-locked rewrite replaced only those verified patterns with explicit `com.microsoft.Gelu`; it passed bit-identical CPU equivalence and complete fail-closed host QNN assignment. The subsequent physical run proved accelerator execution but failed numerical correctness, producing the bounded negative result for this route.

Completed preparation:

- rebuilt and validated the patched host runtime;
- restored the official models, fixtures, and fixed-shape derivatives;
- reproduced the fail-closed support report;
- rebuilt the patched Android arm64 runtime and runner;
- re-established authorized ADB transport without accessing phone data.

Completed derivative and host gates:

- created a separately labeled derivative that replaces only the eight verified `Div → Erf → Add → Mul → Mul` patterns with explicit `com.microsoft.Gelu` nodes;
- recorded all replacements, exact float32 constants, source/output hashes, fixed shapes, and consumer-safety checks;
- produced a bit-identical full-tensor result against the folded/fixed vocoder using the same patched ORT 1.27.1 CPU runtime;
- initialized the host QNN session with CPU fallback disabled, one complete QNN partition, and no unsupported operators.

Physical result:

- exact authorized device identity passed and all staging remained inside one unique `/data/local/tmp` directory;
- patched ORT/QNN created the session in `4.82669 s` and completed three runs with CPU fallback disabled;
- first inference was `0.313119 s`; the two-run warm mean was `0.198222 s`;
- detailed profiles recorded QNN accelerator execution of `297517`, `186278`, and `185925` µs, corresponding RPC execution, accelerator cycles, and four HVX threads on every run;
- the physical tensor was finite and had the expected `[1,731136]` shape, but failed every non-finite-independent frozen metric: cosine `0.865454 < 0.995`, SNR `5.716 < 20 dB`, max absolute error `0.595960 > 0.05`, mean absolute error `0.012167 > 0.002`, and RMSE `0.029311 > 0.005`;
- the scoped device directory was removed and the repository phone lock was released.

**Completed with split evidence:** physical HTP execution is proven and numerical equivalence remains rejected under the unchanged policy. After completion, Moritz listened through a randomized CPU/HTP A/B page and reported that both versions sounded exactly the same. That observation is recorded rather than used to rewrite the frozen gate: it covers one utterance, one listener, and PCM16 renderings, and it does not prove broad perceptual equivalence or speedup. It justified the separately frozen end-to-end audio-quality gate recorded later in this plan.

### Layer-level localization

A scoped coarse-to-fine diagnostic campaign used the unchanged latent fixture, patched runtime, fail-closed QNN sessions, and predeclared intermediate rules. These rules classify localization evidence only; they do not replace final-waveform policy SHA `7116c522…`, which remains failed.

Facts:

- Full-output cross-correlation finds a best lag of exactly zero within ±4,096 samples, so a simple alignment shift does not explain the rejected waveform.
- Error is temporally concentrated and grows with reference amplitude, but neither fact identifies an operator.
- The fully delegated coarse wave first crosses the material rule between the predecoder affine output and the embed Conv output after QDQ.
- The fully delegated fine boundaries are non-material through embed `Pad`, then first become material after embed input QDQ: normalized RMSE rises from `0.000294` at `Pad` to `0.010376` after QDQ; post-QDQ cosine remains `0.999946`.
- Exposing the raw embed Conv output changes QNN fusion/assignment. The fail-closed session rejects that tap before inference, so it supplies no numerical evidence and cannot isolate Conv-before-QDQ.
- An exact-input two-node `QuantizeLinear → DequantizeLinear` microprobe uses the actual CPU embed-Pad tensor, scale `0.007331503`, and zero point `102`. It fully executes on physical HTP but is non-material: normalized RMSE `0.005996`, cosine `0.999982`, SNR `44.442 dB`, and max error `0.004008`.

Bounded conclusion: **the narrowest observable composite interval is embed `Pad → QDQ`, but isolated QDQ does not reproduce the material prefix result. The leading evidence is fusion/context-dependent quantization behavior or amplification of a small upstream perturbation, not a confirmed QDQ, Conv, GELU, or general QNN implementation defect.** Physical profiles do not expose definitive intermediate HTP precision, so reduced-precision accumulation remains possible but unconfirmed.

All diagnostic phone stages were unique experiment-0010 paths, all cleanup attempts succeeded, and the phone lock was released. No vector-estimator work began.

## Phase 2: test vector-estimator value

This phase completed as a bounded host blocker. The exact official `vector_estimator.int8.onnx` is SHA-256 `20cd86fa…`. Its seven float32 inputs and one float32 output retain symbolic batch, latent-length, and text-length dimensions. All frozen files for the five real estimator steps were revalidated against fixture-manifest SHA-256 `59acefd…`; every output of CPU step 0–3 is the exact noisy-latent input of the following step.

The released graph first fails before capability analysis because QNN does not support its dynamic graph-I/O shapes. A deterministic derivative then fixed only batch `1`, latent length `238`, and text length `239`. The derivative is SHA-256 `e154e60f…`; all 1,222 ordered nodes and all 682 initializer names and bytes remain identical to the official source, ONNX full-check passes, and a deterministic rerun is byte-identical.

That shape-only derivative still fails the mandatory no-fallback host gate. The final optimized capability pass reports:

- 21 QNN partitions;
- 921 of 1,057 nodes supported;
- 136 unsupported nodes: 80 standalone per-channel `DequantizeLinear`, 34 `MatMulInteger`, 21 `DynamicQuantizeLinear`, and one `Softplus`;
- session creation rejected because CPU fallback is explicitly disabled.

The canonical exact node enumeration is in [`results/vector-estimator-checkpoint.json`](results/vector-estimator-checkpoint.json). This is not a narrow operator mismatch like the vocoder GELU case: reaching complete HTP assignment would require a broad static-quantization/export conversion. No such conversion or re-quantization was attempted. During this bounded host-gate phase, no Android runner, phone command, correctness policy, HTP output, recursive estimator chain, or other component test occurred; the later authorized mixed and end-to-end diagnostics are recorded below.

**Completed as a bounded negative host result:** the released vector-estimator route is not eligible for physical HTP testing under the fail-closed policy. Resume full-HTP work only under a separately authorized broad export/static-quantization plan.

### One mixed QNN+CPU fallback diagnostic

Moritz subsequently authorized exactly one real step-00 fallback run to measure the fragmented path rather than treat it as full-HTP evidence. Policy SHA-256 `20c0c8a…` was frozen before output. The same shape-only model and all seven frozen step-00 inputs were staged under a unique experiment-0010 phone directory; all 19 staged hashes matched, and cleanup succeeded.

The physical profile proves mixed execution rather than an ambiguous session success:

- ORT recorded 21 `QNNExecutionProvider` node events and 136 `CPUExecutionProvider` node events;
- the CPU events are exactly the host-gate remainder: 80 `DequantizeLinear`, 34 `MatMulInteger`, 21 `DynamicQuantizeLinear`, and one `Softplus`;
- all 21 QNN partitions recorded RPC execution, accelerator execution time and cycles, and four HVX threads;
- aggregate ORT node durations were `985,883 µs` for QNN partitions and `62,856 µs` for CPU nodes; aggregate QNN accelerator execution was `893,050 µs`;
- session creation took `21.7742 s`, the single inference took `1.05424 s`, and process peak RSS was `762,464 KiB` (`744.6 MiB`).

The full 34,272-element output passed the predeclared step-00 gate against the frozen CPU reference: cosine `0.999942`, SNR `39.327 dB`, normalized RMSE `0.010806`, RMSE `0.008685`, mean absolute error `0.005406`, and max absolute error `0.077937`. This is accepted only for that fixture-fed diagnostic. No output was fed to step 1.

**Bounded interpretation:** 21 accelerator dispatches interleaved with 136 CPU nodes are real, but the retained profile does not separately measure every transfer or synchronization cost. This does not change the fail-closed blocker, validate the recursive five-step estimator, or authorize other components.

### One matched CPU-only comparison

Moritz then authorized exactly one CPU-only step-00 run. It used the same device, shape-only model, seven inputs, runner, patched runtime, one-thread settings, graph optimization, and one-run count. Policy SHA-256 `5e7d6de4…` was frozen before output and timing. All 823 ORT node events report `CPUExecutionProvider`; none report QNN. The full tensor passed with cosine `0.99999985`, SNR `65.357 dB`, normalized RMSE `0.000540`, and max error `0.002547`.

The matched single observations are:

| Measurement | CPU only | Mixed QNN+CPU | Mixed / CPU implication |
|---|---:|---:|---|
| Session creation | `0.1839 s` | `21.7742 s` | mixed `118.4×` longer |
| First and only inference | `1.1615 s` | `1.0542 s` | mixed `9.23%` faster |
| Peak process RSS | `162,848 KiB` | `762,464 KiB` | mixed `4.68×` higher |

This answers the narrow question: fallback did not catastrophically lose this single inference; it was modestly faster despite fragmentation. The cost was very large session setup and memory. The pair was cold, single-sample, sequential rather than randomized, and the mixed run occurred first. It therefore remains descriptive rather than a stable speedup claim, and it must not be multiplied into a five-step or end-to-end estimate.

## Phase 3: run complete accelerated Android synthesis

Moritz authorized a matched fixed-transcript end-to-end probe. A new Android runner starts from the exact experiment `0008` transcript and packaged Unicode indexer/voice assets, selects SID 5 / M1, executes duration prediction and text encoding, creates deterministic seeded noise, recursively executes all five estimator steps, vocodes, trims, and writes PCM16 WAV. No intermediate fixture tensor is substituted.

The deployment remains transcript-specific: QNN requires concrete shapes, so both routes use the previously proven text length `239`, latent length `238`, and trimmed length `729,746`. Duration prediction still executes and reports `16.9202 s`, but it does not dynamically rebuild the fixed QNN graphs. This is not arbitrary-text support.

Provider routes:

- CPU: all four ONNX components on `CPUExecutionProvider`;
- hybrid: duration and text encoder on CPU; each vector call split into 21 QNN partitions plus 136 CPU nodes; explicit-GELU vocoder fully on QNN with fallback disabled.

Physical evidence across four complete generations is unambiguous:

- CPU profiles contain only CPU events: duration `1,492`, text `2,632`, vector `16,460`, vocoder `676`;
- hybrid vector profiles contain `420` QNN partition events and `2,720` CPU events across 20 calls;
- hybrid vocoder profiles contain four QNN events and zero CPU events;
- all `420 + 4` QNN executions have detailed RPC, accelerator-time, cycle, and four-HVX-thread evidence.

Matched results:

| Measurement | CPU | Hybrid | Hybrid implication |
|---|---:|---:|---|
| Session creation | `0.611 s` | `26.965 s` | `44.1×` longer |
| First generation | `5.844 s` | `4.331 s` | `25.90%` faster |
| Warm generation median | `6.067 s` | `3.809 s` | `37.22%` faster, `2.258 s` saved |
| Peak process RSS | `459,432 KiB` | `1,154,172 KiB` | `2.51×` higher |
| Warm five-step estimator | about `5.309 s` | about `3.513 s` | primary measured gain |
| Warm vocoder | about `0.669 s` | about `0.200 s` | substantial measured gain |

Both generated files are valid mono 44.1-kHz PCM16 WAVs with `729,746` frames, finite raw samples, no PCM clipping, and non-silent RMS. However, the prospectively frozen hybrid-vs-CPU audio gate failed: cosine `0.405431`, SNR `-0.5926 dB`, normalized RMSE `1.07061`, RMSE `0.05934`, mean absolute error `0.03022`, and max error `0.64116`. The prior vocoder rejection remains immutable; the larger end-to-end divergence may include recursive estimator error accumulation, but no operator defect is claimed.

Afterward, Moritz used the randomized E2E A/B report and reported that the CPU and hybrid samples sounded exactly the same. This is encouraging perceptual evidence for one listener and one utterance. It remains distinct from, and does not override, the failed prospective numerical gate. The ignored convenience report `work/e2e/e2e-report.html` is SHA-256 `ab7d97a7…`; it is not a durable committed dependency.

The startup boundary is session creation rather than phone boot. CPU created all sessions in `0.611 s`; hybrid required `26.965 s`, dominated by vector QNN preparation (`21.985 s`) and vocoder QNN preparation (`4.748 s`). QNN must partition/optimize/compile/finalize graphs, prepare weights and layouts, and establish RPC/shared buffers. This cost is generally one-time only while sessions remain resident. Setup plus first generation was `6.456 s` CPU versus `31.296 s` hybrid; setup plus all four measured generations was `24.649 s` versus `42.590 s`. Dividing the additional setup by the observed warm saving gives an illustrative break-even near 12 retained-process generations, not a controlled claim.

The memory values are process `ru_maxrss` high-water marks: CPU `217,420 KiB` after sessions and `459,432 KiB` after runs; hybrid `1,028,044 KiB` and `1,154,172 KiB`. They are not steady live PSS or complete DSP-private memory. Hybrid retains the ORT CPU graph/fallback route while adding prepared/compiled QNN graph and weight representations, metadata, RPC/shared buffers, profiling state, and transient setup peaks.

Artifacts are retained locally under `work/e2e/`: CPU and hybrid WAVs in `samples/`, component and aggregate latency arrays in `latencies/e2e-latencies.json`, full metrics/provider summaries in `e2e-analysis.json`, and the canonical tracked record in [`results/e2e-hybrid-cpu-checkpoint.json`](results/e2e-hybrid-cpu-checkpoint.json).

**Completed with split evidence:** the transcript-specific hybrid pipeline is physically accelerated, materially faster warm, and perceptually promising for the observed sample. It is not numerically accepted, full-HTP, arbitrary-shape, or deployment-ready.

## Phase 4: make the deployment decision

The bounded decision is complete. The hybrid route demonstrated a meaningful warm latency reduction and sounded identical to Moritz in the one-utterance randomized comparison, but it also failed the prospective waveform gate, consumed much more memory, required expensive session creation, used mixed CPU/HTP vector execution, and supported only the frozen shape.

**Current decision:** preserve Supertonic CPU as the supported reference deployment. Retain the experiment-0010 hybrid as a bounded research baseline because its performance and perceptual evidence are promising, but do not claim production adoption, arbitrary-text readiness, numerical acceptance, or full-HTP success.

Pleasant speech across a broader corpus, sustained generation, same-device latency, memory, storage, thermals, and integration cost still matter before any deployment change. A source-model-first or full-HTP follow-up is only under discussion; no export route or new experiment is approved here.
