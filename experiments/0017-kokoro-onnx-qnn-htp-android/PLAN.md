# Experiment 0017 plan — exact-source Kokoro ONNX on QNN HTP

## Current checkpoint

The canonical-v2 route is frozen for a fresh complete host gate, but no QNN relaunch occurs until the scoped operator-stop/shared-lock follow-up commit is reviewed. The first canonical host QNN attempt remains externally interrupted after stages 1–15 passed; stage 16 reached graph sequencing at 12% without finalizing, and stages 17–18 were not attempted.

A native-host reconstruction recovered every model/input/runner hash. Two clean Ubuntu 22 CPU stage runs were bit-exact to each other and to a fresh complete compatibility-graph run, producing structurally valid audio SHA `56ce6a24498d8db270c0a34eb1fe0a87b762a0fb8121616790f03391c132aa3c`. The historical WSL CPU evidence remains unchanged at `fb8895f6bb9c2ee94dd18f8b9bfdc6f1b36f99e01c40f5806bdd71076acd6d36`; cross-environment bit reproducibility is unproven because the historical ignored payload is unavailable. The prospective comparison policy is [`protocol-canonical-v2-reconstruction-baseline.json`](protocol-canonical-v2-reconstruction-baseline.json), backed by [`results/canonical-v2-cpu-reconstruction-baseline.json`](results/canonical-v2-cpu-reconstruction-baseline.json).

One crossed-message launch was stopped before Docker creation because host `/usr/bin/time` was absent. No QNN session, compiler, stage, or phone access began; [`results/canonical-v2-rerun-operator-cancelled-pre-gate.json`](results/canonical-v2-rerun-operator-cancelled-pre-gate.json) preserves that operator-cancelled boundary.

The later approved `canonical-v2-native-rerun-1` completed stages 1–12 with clean provider/output evidence. Experiment-0023 QNN work overlapped stages 7–10, so their timing/resource observations are not isolated. The run was then operator-stopped during unfinalized stage 13 under an overbroad concurrency-policy interpretation. The corrected boundary and exact evidence are [`results/canonical-v2-native-rerun-1-operator-stopped.json`](results/canonical-v2-native-rerun-1-operator-stopped.json). This is not a QNN correctness failure, but the incomplete run cannot be resumed. After review, `canonical-v2-native-rerun-2` must restart from stage 1 and hold `artifacts/locks/heavy-ram.lock` for its full lifetime. Clean-machine reconstruction and restart instructions are in [`REPRODUCING.md`](REPRODUCING.md).

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

## Remaining gates

1. **Fresh complete host QNN gate**
   - regenerate/verify every ignored asset using [`REPRODUCING.md`](REPRODUCING.md);
   - require the exact committed reconstruction policy/baseline hashes and a complete CPU checkpoint whose 18 per-stage outputs match the frozen current-environment `56ce6a…` baseline;
   - preserve `fb8895…` as historical WSL evidence and make no cross-environment bit-exact claim;
   - acquire nonblocking `artifacts/locks/heavy-ram.lock` before QNN preflight and hold it for the full script lifetime; this infrastructure lock prevents peer overlap but is not a model eligibility field;
   - start fresh ID `canonical-v2-native-rerun-2` from stage 1 with [`host/run_canonical_v2_staged_host_qnn.sh`](host/run_canonical_v2_staged_host_qnn.sh);
   - run one stage process at a time so compiler memory is released;
   - require all 18 sessions to finalize and execute their real upstream tensors;
   - require one QNN provider event per stage and zero CPU provider events;
   - preserve per-stage exit, wall, session, inference, `ru_maxrss`, output, ORT profile, QNN CSV/log, and numerical comparison evidence;
   - inspect final duration and audio. EOS/numerical divergence is descriptive, but invalid/non-finite/clipped audio blocks phone access.
2. **Host fidelity and structure**
   - record actual duration tensor/sum and emitted sample count;
   - require finite non-silent, unclipped float audio within the frozen structural bounds;
   - compare to the controlled eager and patched-ORT CPU references using the named phase-tolerant policy;
   - report waveform metrics descriptively and never turn them into a listening verdict.
3. **Phone run, only if every host gate passes**
   - acquire Messenger and `artifacts/locks/phone.lock` locks;
   - verify exact serial/model/SoC/ABI and sole-device state;
   - use scoped internal staging and cleanup;
   - create sessions once, record setup, one first and at least five warm complete generations with full model/cache/random-state reset before each generation;
   - compute every RTF from the actual emitted duration;
   - retain per-stage provider proof plus physical RPC, accelerator-time, accelerator-cycle, and HVX evidence;
   - retain thermal context and process-lifetime memory high-water semantics;
   - create a valid canonical-v2 WAV and a blind comparison package.
4. **Listening**
   - record the exact WAV SHA;
   - listening status remains `not_reviewed` until Moritz explicitly accepts or rejects that exact sample;
   - do not transfer the accepted historical experiment-0013 CPU verdict to this route.

## Stop rules

- Do not relaunch until the operator-stop/shared-lock follow-up is reviewed and the policy/baseline/current CPU checkpoint/shared-lock gates pass.
- Do not resume either interrupted attempt or operator-stopped `canonical-v2-native-rerun-1`; produce a fresh complete 18-stage record from stage 1.
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
