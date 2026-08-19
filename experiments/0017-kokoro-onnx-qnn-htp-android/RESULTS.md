# Experiment 0017 results — exact-source Kokoro ONNX on QNN HTP

## Bounded conclusion

**Blocked before host execution.** A narrow, fixed-contract compatibility derivative became fully assignable to one QNN partition and was bit-identical to its source under the same patched ONNX Runtime 1.27.1 CPU runtime. However, the required fallback-disabled host session never finalized: Linux killed the QNN HTP preparation process for out-of-memory while `Graph Sequencing for Target` was at 64%. No inference began, no QNN output was produced, and the phone was correctly not accessed.

This is not evidence that Kokoro can never run on QNN HTP. It is also not a full-HTP success. The result is an exact bounded host-finalization/resource blocker in the tested QAIRT/QNN 2.49 setup.

Canonical machine-readable evidence is [`results/host-gate-checkpoint.json`](results/host-gate-checkpoint.json). The metadata pass, rewrite, and same-runtime CPU proof are preserved in [`results/profile-shape-provenance.json`](results/profile-shape-provenance.json), [`results/profile-shape-cpu-equivalence.json`](results/profile-shape-cpu-equivalence.json), [`results/qnn-compat-rewrite-provenance.json`](results/qnn-compat-rewrite-provenance.json), and [`results/qnn-compat-cpu-equivalence.json`](results/qnn-compat-cpu-equivalence.json). Large models, fixtures, profiles, compiler logs, tensors, and local binaries remain ignored under `work/` and `.local/`.

## Verified source and contract

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
- phone lock/ADB/staging: never used.

## Decision

Keep experiment 0013's ONNX Runtime CPU route as the proven Kokoro Android reference. Experiment 0017 establishes a fully assigned and CPU-equivalent fixed-contract graph, but cannot advance beyond that assignment claim because host QNN graph finalization exhausted the tested environment before execution.

A follow-up would require a new decision—for example, a materially larger host preparation environment or semantics-preserving graph segmentation. This experiment does not extend its resource cap, split the model, introduce quantization, or broaden the rewrite.
