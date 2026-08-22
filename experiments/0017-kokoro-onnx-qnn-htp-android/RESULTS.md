# Experiment 0017 results — exact-source Kokoro ONNX on QNN HTP

## Current bounded conclusion

The original 116-byte experiment-0013-derived route and the newer canonical-v2 route are separate evidence tracks.

- The historical monolithic compatibility graph was blocked before execution by kernel OOM. An authorized later decomposition did execute all 18 historical stages on host QNN, but duration changed from 304 to 305 and its final float audio was structurally invalid. It remains noncanonical feasibility/debug evidence only.
- The canonical-v2 route has complete frontend/export/CPU/stage-recomposition proof. Its first fallback-disabled host QNN attempt completed stages 1–15, then a WSL shutdown/restart externally interrupted stage 16 during graph sequencing at 12%. Stage 16 did not finalize or execute, stages 17–18 were not attempted, no final canonical QNN audio exists, and the phone remains forbidden.
- Native-host reconstruction reproduced every source/model/input/runner hash but not the historical WSL CPU audio hash. Two clean current-environment staged CPU runs and a complete-graph run are mutually bit-exact at audio SHA `56ce6a24498d8db270c0a34eb1fe0a87b762a0fb8121616790f03391c132aa3c`. The historical WSL `fb8895…` record is preserved, and cross-environment bit reproducibility is explicitly unproven.

Neither track proves physical phone HTP execution. The canonical interrupted attempt is not a technical stage-16 failure or OOM; the next attempt must restart from stage 1. See [`REPRODUCING.md`](REPRODUCING.md).

Historical machine-readable evidence is [`results/host-gate-checkpoint.json`](results/host-gate-checkpoint.json) and [`results/staged-host-qnn-feasibility.json`](results/staged-host-qnn-feasibility.json). Canonical-v2 machine evidence begins with [`protocol-canonical-v2-stage-decomposition.json`](protocol-canonical-v2-stage-decomposition.json) and [`results/canonical-v2-host-qnn-interrupted-checkpoint.json`](results/canonical-v2-host-qnn-interrupted-checkpoint.json). The prospective current-environment comparison contract is [`protocol-canonical-v2-reconstruction-baseline.json`](protocol-canonical-v2-reconstruction-baseline.json), with evidence in [`results/canonical-v2-cpu-reconstruction-baseline.json`](results/canonical-v2-cpu-reconstruction-baseline.json). Large models, fixtures, profiles, compiler logs, tensors, local binaries, and audio remain ignored under `work/` and `.local/`; their hashes and regeneration commands are committed.

## Historical verified source and contract

The route starts from experiment 0013 commit `b6fd6e8c123cbf5170f1b1ee1367bb08eef6f5c0` and preserves its claim boundary:

- official model: `hexgrad/Kokoro-82M@f3ff3571791e39611d31c381e3a41a3af07b4987`;
- model SHA-256: `496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4`;
- voice `af_heart` SHA-256: `0ab5709b8ffab19bfd849cd11d98f75b60af7733253ad0d67b12382a102cb4ff`;
- exact-source-derived FP32 controlled ONNX SHA-256: `d11a0dd7c4eb768e1f0ef03090c69b6761f55e37b9f196749349591c40be232b`;
- fixed input: tokens `[1,125]`, style row 123 `[1,256]`, speed `1.0`, seed `20260818`;
- fixed output oracle: duration `[125]`, sum `304`; audio `[182400]` at 24 kHz;
- no quantization, calibration, substitute model, custom QNN operator, or neural intermediate fixture.

The controlled ONNX remains only a fixed-contract exact-source-derived representation. It is not waveform-identical official eager, arbitrary-text deployment, or the rejected sherpa `disable_complex=True` graph. Experiment 0013's preliminary `.999/.01` waveform-screen failure remains unchanged.

## Host compatibility map

All QNN gates used the experiment-0010 patched ORT 1.27.1 build, QAIRT/QNN `2.49.0.260730`, `session.disable_cpu_ep_fallback=1`, `offload_graph_io_quantization=0`, HTP SoC model 43, and one thread.

### Exact controlled graph

The unmodified controlled graph did not pass:

| Capability pass | Partitions | QNN nodes | Total nodes |
|---|---:|---:|---:|
| first | 18 | 990 | 1768 |
| second | 18 | 982 | 1759 |

The second pass left 777 nodes unsupported and session preparation terminated with:

```text
qnn_model.cc:73 ParseGraphInputOrOutput Dynamic shape is not supported yet, for output: /shared/Transpose_output_0
```

### Metadata-only fixed-shape pass

ORT basic optimization was serialized, every observed tensor shape was added as value metadata, and the graph outputs were fixed to `[182400]` and `[125]`. Node bodies, attributes, and retained initializer payloads were unchanged. The metadata-only derivative was bit-identical to its unshaped source on CPU.

This improved but did not complete assignment:

| Capability pass | Partitions | QNN nodes | Total nodes |
|---|---:|---:|---:|
| first | 27 | 1720 | 1768 |
| second | 28 | 1862 | 1910 |

The first pass retained 48 unsupported nodes: 12 `IsNaN`, 12 `Shape`, 7 `Expand`, 5 `ConstantOfShape`, 3 `Range`, two each of `If`, `Slice`, and `SplitToSequence`, plus one `Loop`, one `SequenceEmpty`, and one `ConcatFromSequence`.

### Bounded QNN compatibility derivative

The only semantic rewrite was fixed to those observed blockers:

1. bypass 12 `IsNaN → Where` attention sanitizers after the exact fixed input proved their softmax values finite;
2. lower duration-driven `repeat_interleave`/sequence/loop/scatter alignment to a fixed `[1,125,304]` comparison mask still computed from the runtime `pred_dur` tensor;
3. replace fixed-contract shape-derived zero/index tensors with equivalent constants;
4. lower two fixed-shape squeeze `If` nodes to `Reshape`;
5. prune only now-dead exporter control/shape constants.

Derivative facts:

- SHA-256: `7278ed2f0dbe8307a42904434b81116f252dd996bb6a2c064f81ad44269f21cb`;
- 1,685 nodes and 809 initializers;
- zero quantized operators;
- zero retained-initializer payload changes;
- patched ORT 1.27.1 CPU output and duration were bit-identical to the same-runtime source (`182400`-sample audio SHA-256 `56464612c786a6fcc9034e51a24d7e26d17910147a72e5e5672220c45f15045f`; duration SHA-256 `7977e82d5304abba333a0b1caa0f0ef39b265b11205ff217c5979255cc44b80e`).

QNN capability reported complete assignment:

| Capability pass | Partitions | QNN nodes | Total nodes |
|---|---:|---:|---:|
| first | 1 | 1685 | 1685 |
| second | 1 | 1821 | 1821 |

These counts prove only that the provider accepted the nodes for one partition. They do **not** prove that a session finalized, an inference ran, or physical HTP executed.

## Final fallback-disabled host run

The final run used the complete derivative and the real fixed tokens/style/speed inputs. It had a prospective 10,800-second cap but failed earlier:

- start: `2026-08-19T16:12:46+01:00`;
- end: `2026-08-19T16:40:48+01:00`;
- measured wall time: `28:01.52`;
- exit code: `137` (`SIGKILL`);
- `Graph Preparation Initializing`: `0.005045 s`, completed;
- `Graph Optimizations`: `767.039310 s`, completed;
- `Post Graph Optimization`: `20.270704 s`, completed;
- `Graph Sequencing for Target`: reached 64%, did not complete.

The kernel recorded the exact cause:

```text
Out of memory: Killed process 354695 (kokoro-ort-host)
total-vm:8983428kB, anon-rss:5334340kB, file-rss:384kB
```

The ignored kernel excerpt is SHA-256 `1b2aa690b45008ef6c66ed1fe429e26a6378ee6059036a2b55021ad3f7946c49`.

Consequences:

- QNN session finalization: **not completed**;
- complete fixed-input host inference: **not executed**;
- ORT profile: empty, because the session never became runnable;
- audio output: absent;
- duration output: absent;
- host execution proof: absent;
- physical RPC/accelerator/cycle/HVX proof: absent;
- phone eligibility: **failed**;
- phone lock/ADB/staging: never used;
- QNN listening verdict: not applicable because no QNN audio exists.

## Historical decision

Keep experiment 0013's ONNX Runtime CPU route as the proven Kokoro Android **technical** reference; Moritz accepted its exact retained WAV as “Good.” That verdict remains bound to the CPU sample and does not imply anything about another route.

The later authorized stage decomposition did not erase the monolithic OOM. It separately executed all 18 historical host stages with QNN assignment and zero CPU provider events. The final output nevertheless failed basic structure: duration sum changed from `304` to `305`, float peak was `94848`, and `182236/182400` samples had `abs >= 1`. See [`results/staged-host-qnn-feasibility.json`](results/staged-host-qnn-feasibility.json). No phone attempt or listening sample was justified.

## Canonical-v2 route

### Frontend and fixed contract

The exact canonical transcript is 226 bytes with no newline, SHA `424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67`. The historical sherpa lexicon failed closed on `makes`, so the comparable route uses the pinned official Kokoro 0.9.4 American-English KPipeline:

- one chunk;
- 233 phoneme code points / 323 UTF-8 bytes, SHA `7c7299c2d19943162b5bc85cebe116d16e534f336ac5bcb4fce40fe126a8b3a0`;
- tokens `[1,235]`, SHA `9c565b2a6ee1a811f188f3e3425a3188af58866988ce5a2197eeaacc81dde280`;
- `af_heart` style row 232, SHA `8acaca07623d98a1085f6b182fb997d715dd1d67862e350567e6d9b1bc8ec71b`;
- duration `[235]`, sum `602`, SHA `99494f78e82ad3d8b506d5b0a5c4edde6292c6a52ca54a47b50f109fa534480c`;
- audio `[361200]` at 24 kHz (`15.05 s`).

The controlled-eager CPU oracle was structurally valid: audio SHA `b7cc6d6c719bd0151c35aa6ae4ef8bcec0b3b99acb7a6423e4c6e42e2edee536`, peak `0.457968`, RMS `0.051719`, zero clipped float samples. Its process-lifetime `ru_maxrss` was `1,524,412 KiB`.

### Export and CPU gates

The canonical FP32 ONNX export is SHA `26120b192f2ad7567c6c1215ccbcf374d1946460c4589c1098941ab15e43aa73` with 4,352 nodes, 445 FP32 initializers, and zero quantized/random operators.

On patched ORT 1.27.1 CPU:

- duration was bit-exact to controlled eager;
- audio SHA was `1f7eb49ca903a3eed8cdb36049041a48540bd08027b38b4a6cee52e27cb9f624` and structurally valid;
- the phase-tolerant policy passed: spectral convergence `0.06260`, log-magnitude Pearson `0.99533`, log-mel cosine `0.99923`, mean absolute log-mel error `0.827 dB`, RMS-envelope Pearson `0.99913`;
- the separate strict waveform `.999/.01` screen failed: waveform cosine `0.99515`, NRMSE `0.10372`. It remains explicit and is not a listening verdict.

The metadata-shaped graph is SHA `d81053acc21a9fa42a7ff09bae17abad1ef7499aa2252f70bda27f9ac89194a3`. The bounded QNN compatibility graph is SHA `0c7ce33eac4c6664819a61e48469a9cf43ad403d852b01af5517a13c7ed2a066`, with 1,685 nodes, 809 initializers, no quantization, no retained initializer changes, and bit-exact CPU output versus the shaped graph.

Eighteen fixed stage models cover all 1,685 source nodes. Five named support nodes are recomputed at boundaries, as declared in the stage provenance. The historical WSL separate-process CPU recomposition was bit-exact to its complete compatibility-graph run: audio SHA `fb8895f6bb9c2ee94dd18f8b9bfdc6f1b36f99e01c40f5806bdd71076acd6d36`, duration SHA `99494f78e82ad3d8b506d5b0a5c4edde6292c6a52ca54a47b50f109fa534480c`.

### Current-environment CPU reconstruction baseline

After migration to the native Manjaro host, all source assets, the patched ORT shared library (`bc9df5…`), runner (`938480…`), manifest, 18 models, and fixed inputs matched their committed hashes. The available tracked-shape Ubuntu 22 image has full ID `b170f55a…`; it was locally aliased to the expected tag only after inspect/history/package verification. Tag equality is not identity proof, and the prior QNN toolchain record retained only historical short image ID `2803b0712b5b`.

Two clean containerized staged CPU runs produced identical output hashes at every stage. A fresh complete QNN-compat graph CPU run was bit-exact to both staged runs:

- current audio SHA: `56ce6a24498d8db270c0a34eb1fe0a87b762a0fb8121616790f03391c132aa3c`;
- duration SHA/sum: `99494f78e82ad3d8b506d5b0a5c4edde6292c6a52ca54a47b50f109fa534480c` / 602;
- complete graph versus staged: max absolute error `0`, RMSE `0`, cosine `1`;
- final audio: 361,200 finite samples, peak `0.4363551`, RMS `0.0497710`, zero samples with `abs >= 1`; structurally valid.

The first known cross-environment divergence is stage 1 (`bert`): historical output SHA `cb5d2d…`, current output SHA `01e4e8…`. The historical stage/final float payloads were intentionally ignored and no surviving copy was found, so the first differing element and historical-to-current max-absolute-error/RMSE/cosine are `null` with an explicit unavailable reason. A hash mismatch proves bit/value divergence but cannot supply numerical distance.

This does not rewrite the historical `fb8895…` result. [`protocol-canonical-v2-reconstruction-baseline.json`](protocol-canonical-v2-reconstruction-baseline.json) prospectively selects the deterministic current `56ce6a…` stage outputs for the next same-environment QNN comparison. Cross-environment bit reproducibility remains unproven.

A crossed-message rerun launch was stopped before Docker creation. Host `/usr/bin/time` was absent, no QNN session/compiler/stage began, and no phone access occurred. [`results/canonical-v2-rerun-operator-cancelled-pre-gate.json`](results/canonical-v2-rerun-operator-cancelled-pre-gate.json) classifies this as operator-cancelled pre-gate, not a QNN failure.

### Interrupted canonical host QNN attempt

The run started `2026-08-20T13:34:52Z` using patched ORT 1.27.1, QAIRT/QNN `2.49.0.260730`, HTP SoC model 43, one thread, graph optimization disabled, and `session.disable_cpu_ep_fallback=1`. Each stage used a separate process.

Stages 1–15 all finalized and executed their complete real inputs:

- provider counts: 15 QNN events, zero CPU events;
- sum of per-process session creation: `3587.162919 s`;
- sum of single inference times: `5385.56082 s`;
- maximum separate process-lifetime `ru_maxrss`: `4,170,140 KiB`;
- detailed host QNN CSVs contain finalize time, HVX-thread count, accelerator cycles, accelerator execution time, and QNN execution time for every completed stage.

These metrics are sums across separate processes, not an end-to-end phone benchmark. The memory value is a process-lifetime high-water maximum, not additive, steady PSS, or component-isolated memory.

A WSL shutdown/restart externally interrupted stage 16 (`generator_1_resblock_5`) after:

- graph preparation: `288 us`;
- graph optimization: `43,520,959 us`;
- post graph optimization: `5,485,532 us`;
- graph sequencing: 12% maximum observed progress.

Stage 16 had no finalized session, inference, output, non-empty provider profile, or exit code. Stages 17–18 were not attempted. The top-level run has no end/exit file. There was no ORT error or kernel OOM. The host-wide monitor captured 1,804 samples; minimum `MemAvailable` was `9,539,000 KiB`, swap consumption did not grow, and no automatic pause occurred. These facts make the boundary an external interruption, not a technical stage failure.

Exact per-stage timing, outputs, numerical comparisons, QNN metrics, log/profile hashes, and resource facts are committed in [`results/canonical-v2-host-qnn-interrupted-checkpoint.json`](results/canonical-v2-host-qnn-interrupted-checkpoint.json).

## Current decision and next gate

No canonical QNN audio exists, so canonical QNN listening is `not_reviewed`/not yet applicable. Phone eligibility is false.

Regenerate and hash-verify ignored artifacts plus the current-environment CPU checkpoint. The host script now fail-closes on the exact committed reconstruction policy/baseline hashes and all 18 frozen current CPU stage-output hashes before any Docker/QNN launch. When reviewed, restart the complete host gate from stage 1; do not resume the partial stage-16 attempt. [`REPRODUCING.md`](REPRODUCING.md) contains the exact commands.

Only a fresh 18/18 fallback-disabled host pass with zero CPU provider events, comparison to the current `56ce6a…` baseline, and **structurally valid final audio** can advance to phone work. Historical `fb8895…` remains separate WSL evidence. Physical phone RPC/accelerator/cycle/HVX proof, setup/first/five-warm RTFs using actual emitted duration, thermal context, memory semantics, a fresh WAV/hash, and Moritz's exact-sample verdict remain outstanding. No quantization is authorized.
