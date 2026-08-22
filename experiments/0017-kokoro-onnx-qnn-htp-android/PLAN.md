# Experiment 0017 plan — exact-source Kokoro ONNX on QNN HTP

## Current checkpoint

The canonical-v2 route has reached its terminal experiment-0017 host boundary. Locked run `canonical-v2-native-rerun-2` completed all 18 fallback-disabled stages with one `QNNExecutionProvider` event per stage, zero CPU provider events, and exit code 0. This proves full host QNN assignment/execution for the staged fixed contract.

The output fails the separate structural gate. Duration `[235]` changed from CPU sum 602 to QNN sum 605 at five indices. Audio `[361200]` is finite but has SHA `2992f71911b8af233841af4058e8218e8705c987a51643d1d709d96545b60a08`, peak `87296.0078`, RMS `61982.4965`, and 360,921 samples with `abs >= 1`. It is invalid and not listening material. Phone eligibility is false.

Stage 1 `bert` is the earliest non-bit-exact output versus the frozen current CPU baseline (max absolute error `0.395303`, RMSE `0.0220692`, cosine `0.999870856`). Stage 4 `duration_alignment` is the first discrete/material contract divergence: `pred_dur` differs at five indices/sum 605 versus 602, while its aligned float outputs have cosine `0.854534` and `0.828855`. This localizes observed divergence without establishing a root cause.

The complete terminal record is [`results/canonical-v2-host-qnn-gate.json`](results/canonical-v2-host-qnn-gate.json). Historical WSL and operator-stopped records remain preserved. No rerun, graph/runtime change, fix attempt, WAV, listening package, or phone work is authorized unless Moritz explicitly opens a new experiment/scope.

## Objective

Determine whether the official-source Kokoro v1.0 model can synthesize the exact canonical-v2 Android benchmark transcript with every neural ONNX stage assigned to QNN/HTP and CPU fallback disabled, then—only after host eligibility—measure a physical Android run and produce a fresh WAV for Moritz's exact-sample listening decision.

The comparable route must use the exact committed canonical transcript and the pinned official Kokoro frontend. Historical experiment-0013/0017 fixed-fixture metrics and verdicts remain separate.

## Completed preparation gates

1. **Canonical transcript** — exact 226 bytes, no newline, SHA `424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67`.
2. **Frontend** — the old sherpa lexicon failed closed at OOV `makes`; pinned Kokoro 0.9.4/Misaki 0.9.4 American-English KPipeline produced one chunk, 233 phoneme code points, tokens `[1,235]`, and style row 232.
3. **Controlled CPU oracle** — duration sum 602; audio `[361200]` / 15.05 s, structurally valid.
4. **FP32 ONNX export** — exact official weights, no quantization or random operators; duration bit-exact to eager, structurally valid audio, phase-tolerant acoustic pass, separately retained strict waveform failure.
5. **QNN compatibility derivative** — 1,685 nodes, 809 initializers, no quantization or retained learned-payload changes; bit-exact to its metadata-shaped CPU source.
6. **Stage decomposition** — 18 natural module/residual stages, all 1,685 source nodes covered, fixed interfaces and model hashes frozen.
7. **Historical WSL stage CPU recomposition** — all 18 separate CPU processes reproduced the complete compatibility graph bit-for-bit at audio SHA `fb8895…`; this evidence is preserved in its original environment scope.
8. **Current-environment reconstruction baseline** — two clean 18-stage runs produced identical per-stage tensors and final audio SHA `56ce6a…`; a fresh complete-graph run was bit-exact to the staged output, duration remained exact, and final audio passed the structural policy. The first cross-environment hash divergence is stage 1; value-based historical deltas remain unavailable because the ignored WSL tensor is gone.

## Terminal gate outcome

1. **Host QNN execution/provider gate — passed**
   - 18/18 separate stage processes finalized and executed;
   - provider counts `{QNNExecutionProvider: 18}`;
   - CPU provider node events `0`;
   - shared heavy-RAM lock held for the complete run.
2. **Host structural audio gate — failed**
   - duration sum 605 versus expected 602;
   - audio finite but grossly out of range, with 360,921 clipped/out-of-range samples;
   - no valid WAV or listening material.
3. **Phone/benchmark/listening work — blocked**
   - no ADB, staging, physical HTP proof, setup/RTF runs, thermal measurement, WAV, or listening verdict;
   - future investigation requires explicit new authorization and scope, not an experiment-0017 retry.

## Stop rules

- Do not rerun experiment 0017 or resume any partial attempt.
- Do not alter graphs, runtime/provider options, or introduce a fix inside this completed experiment; a new investigation requires explicit Moritz scope.
- Do not retry the monolithic graph.
- Do not enable CPU provider fallback.
- Do not quantize without Moritz's explicit authorization.
- Do not touch the phone before host eligibility.
- Do not rewrite the historical canonical-v2 WSL `fb8895…` baseline or infer unavailable value-based metrics from its hash.
- Do not merge canonical-v2 metrics or verdicts with the old 116-byte experiment-0013/0017 route.
- Do not touch the benchmark dashboard, experiment 0019, or `docs/architectures/` from this experiment.

## Claim discipline

- QNN capability or a fused provider event is not physical phone HTP proof.
- CPU frontend, orchestration, tensor transport, validation, and WAV encoding are separate from neural accelerator execution.
- `ru_maxrss` and `VmHWM` are process-lifetime high-water marks, not steady PSS or component-isolated memory.
- Technical execution, structurally valid audio, named numerical/acoustic comparisons, benchmark performance, and Moritz listening acceptance are separate claims.
