# 0024 — Pocket TTS QNN precompiled-context startup

## Status

**Complete: external QNN contexts cut median physical-phone setup from 27.0767 seconds to 1.01122 seconds while preserving structurally valid canonical-v2 E2E execution. Moritz subsequently reviewed and accepted both distinct retained phone WAVs by exact hash.**

This experiment compares source-ONNX QNN session creation with external precompiled QNN EPContext reload for a newly reconstructed derivative of experiment 0014’s accepted canonical-v2 fixed-Alba/cache512 Pocket route.

It is **not** the exact 0014 graph set. The ignored historical graph/work files were cleaned. Reconstruction from the same public pinned weights, tokenizer, Alba state, code, and exporter first diverges at controlled ONNX serialization, before any 0024 context transformation:

- the four used controlled ONNX files reproduce the committed 0012 byte sizes exactly;
- their SHA-256 values differ;
- all eight 0014 derivative hashes consequently differ.

The unavailable historical Python/protobuf package state is not treated as an indefinite blocker. Experiment 0024 names and fingerprints its deterministic derivative honestly, requires fresh fallback-disabled QNN assignment for every graph, and requires fresh E2E/audio validation. See [`results/reconstruction.json`](results/reconstruction.json) for the full boundary, source/base hashes, operator counts, initializer-payload fingerprints, and I/O names.

## Final physical-phone result

Three independent fresh processes per arm each created all eight sessions, then ran one first and five warm complete generations with full state reset before every generation.

| Measurement | Source ONNX | External QNN context |
|---|---:|---:|
| Fresh setup runs | 27.0767, 23.8668, 28.6125 s | 0.729463, 1.26412, 1.01122 s |
| **Median setup** | **27.0767 s** | **1.01122 s** |
| Median first RTF | 0.172432 | 0.167330 |
| Pooled 15-warm median RTF | 0.168605 | 0.164032 |
| Warm RTF range | 0.164660–0.177048 | 0.163039–0.165763 |
| Maximum process VmHWM | 2,568,248 kB | 201,616 kB |
| Representative WAV | `028f8a1e…4241` | `7c3fc41d…6d81` |
| Listening status | `accepted` (`028f8a1e…4241`) | `accepted` (`7c3fc41d…6d81`) |

Observed median setup delta is **26.06548 seconds**, a **96.26535% reduction** or **26.7763×** source/context ratio. There was no minimum speedup gate. Every completed output had reference EOS 160, 163 frames, 312,960 samples, and 13.04 seconds of finite, non-silent, unclipped 24 kHz mono PCM16 audio. RTF uses each run’s actual emitted duration.

The campaign spans two authorized phone windows because of an external disconnect. Source runs occurred first; context run 1 followed on the same window, while context runs 2–3 and both proofs ran after reconnect two days later. AP start/end temperatures ranged 34.9→51.0, 36.2→51.1, and 50.8→59.0 °C for source; 44.5→53.6, 32.1→41.4, and 37.5→48.0 °C for context. The phone was USB powered. These order/date/thermal differences are disclosed confounders, not laboratory control. VmHWM is cumulative process high-water, not isolated model memory.

The WAVs are byte-distinct and numerically divergent (correlation `0.4530`, source-over-difference SNR `-0.356 dB`). This remains descriptive rather than an execution or quality verdict. Moritz later reviewed both distinct retained phone WAVs and accepted each exact hash as “good”; neither verdict transfers to other outputs. Exact retained samples: [`results/phone-campaign/source.wav`](results/phone-campaign/source.wav) and [`results/phone-campaign/context.wav`](results/phone-campaign/context.wav). The hash-bound review record is [`results/listening-review-2026-08-25.json`](results/listening-review-2026-08-25.json).

Separate profiled processes, excluded from the unprofiled setup/RTF distributions, proved both arms physical and fallback-free:

- source: 344 QNN / 0 CPU events, exactly 344 RPC/accelerator/cycle/HVX records, 3,989,277,125 cycles;
- context: 344 QNN / 0 CPU events, exactly 344 RPC/accelerator/cycle/HVX records, 3,998,683,560 cycles;
- each HVX thread sum was 1,376.

Full machine result: [`results/result.json`](results/result.json). Hash-bound phone package: [`results/phone-campaign/evidence-manifest.json`](results/phone-campaign/evidence-manifest.json).

## CPU gate

The pinned exporter’s CPU verification passed its `rtol=2e-5`, `atol=2e-5` component checks for text, Mimi audio/state, FlowLM conditioning/EOS/state, and flow output.

The reconstructed fixed-Alba/text64/cache512 route then completed end to end on ORT CPU:

- canonical transcript: 226 bytes, SHA-256 `424b3807…b67`;
- 64 tokenizer IDs;
- EOS step **160**;
- **163** latent frames;
- **312,960** samples / **13.04 s** at 24 kHz mono;
- structurally valid, finite, non-silent, unclipped PCM16 WAV;
- WAV: [`results/host-cpu-derivative.wav`](results/host-cpu-derivative.wav), SHA-256 `7979459f95752064b3aa025644a102d85d555e9684ff6f204d348025e394cb1d`;
- listening status: **`not_reviewed`**. Structural agreement does not transfer Moritz’s verdict for a different exact WAV.

This CPU run is a reconstruction/effectiveness gate, not an Android benchmark or QNN/HTP proof.

## Host external-context result

Every neural session—text, text prefill, BOS AR, latent AR, flow, and decoder-12/6/1—generated a non-embedded external context with CPU fallback disabled, then reloaded successfully in a separate fresh Docker process that mounted only its descriptor, `<stem>_qnn.bin`, smoke tool/input fixture, ORT runtime, and QNN backend. Source ONNX was unavailable in every reload.

| Component | Source generation setup | Isolated reload setup | External binary |
|---|---:|---:|---:|
| Text | 0.115842 s | 0.034384 s | 8,245,976 B |
| Text prefill | 5.757081 s | 0.111627 s | 133,112,008 B |
| BOS AR | 3.571449 s | 0.116972 s | 145,429,536 B |
| Latent AR | 3.703581 s | 0.130259 s | 151,717,872 B |
| Flow | 0.425223 s | 0.049611 s | 19,967,696 B |
| Decoder-12 | 7.037149 s | 0.049825 s | 22,515,448 B |
| Decoder-6 | 2.051637 s | 0.048777 s | 21,757,688 B |
| Decoder-1 | 1.233648 s | 0.044665 s | 21,384,952 B |
| **Sum** | **23.895610 s** | **0.586121 s** | **524,131,176 B** |

Generation and reload each recorded exactly eight `QNNExecutionProvider` events and zero CPU-provider events. Per component, all output tensor hashes were identical between generation and reload. Decoder zero-element inputs retain their declared shapes and have exactly zero elements/bytes.

These are one-process-per-component functional host smokes, not a three-run cold distribution or physical-phone timing. Setup is measured only around `InferenceSession` construction. Host HTP-emulator first execution—up to roughly 44 seconds for decoder-12—is separately recorded and deliberately excluded from setup. Full evidence: [`results/host-context-smoke.json`](results/host-context-smoke.json), with the hash-bound ORT JSON, QNN CSV, and QNN logs under [`results/host-context-profiles/`](results/host-context-profiles/).

## Frozen comparison

Both measured phone arms used the same eight 0024 graph derivatives, ABI, runtime/provider options, canonical inputs, runner, and phone:

1. **Source arm:** create eight QNN sessions from source ONNX; compilation is inside measured setup.
2. **Context arm:** create the same sessions from non-embedded EPContext ONNX descriptors plus external `<stem>_qnn.bin` files; offline context generation is reported separately and excluded from reload setup.

Sessions are text conditioner, text prefill, BOS AR, latent AR, flow, and Mimi decoder 12/6/1. CPU fallback remains disabled. Context reload must pass in a fresh isolated Docker process where only the descriptor, binary, smoke tool, required input fixture, ORT runtime, and QNN backend are mounted—source ONNX is unavailable.

Each arm completed three fresh cold phone processes. Every benchmark process created sessions once, ran one first complete generation plus five warm generations, and fully reset model/cache/decoder/noise state before every generation. CPU-reference EOS 160 / 163 frames remained descriptive: the runner reports `behavior_matches_reference` and fails only for real execution, decode, or structural invalidity.

## Prepared Android packages

Both ignored phone-stage packages are prepared and hash-bound without accessing the device:

- source arm: 19 files / 1,179,649,223 bytes, manifest `b724cb17…85fe`;
- context arm: 27 files / 654,600,434 bytes, manifest `d26e6a1c…fa0b`;
- matched runner: 162,352-byte Android-27 AArch64 PIE, SHA-256 `dce2aa98…c859`, linked to the staged ORT and libc++ libraries;
- context model directory: exactly eight small EPContext descriptors and eight external binaries; no source graph is packaged;
- all source graphs match the documented 0024 derivative inventory, and all context files match the host functional evidence.

See [`results/android-stage-provenance.json`](results/android-stage-provenance.json). This proves package construction, not device portability or execution. No `phone.lock`, ADB, or device access occurred.

## Interrupted phone checkpoint

The authorized campaign completed three source benchmark processes and one context benchmark process before the device disconnected during context run 2:

- source setup: 27.0767, 23.8668, 28.6125 seconds; all three WAVs SHA-256 `028f8a1e…4241`;
- context run 1 setup: 0.729463 seconds; WAV SHA-256 `7c3fc41d…6d81`;
- every completed process ran one first plus five warm generations, matched reference EOS/frame behavior, passed structural/stage/identity gates, and verified cleanup;
- both new WAV hashes were `not_reviewed` at this checkpoint; Moritz's later exact-hash acceptances are recorded separately in `results/listening-review-2026-08-25.json`.

Interrupted context run `phone-context-20260823T085809Z-225310` passed exact identity, context source-absence, full stage push, and local/remote manifest equality. The runner ADB command then returned 255 after the external disconnect; no result or WAV was pulled. It is excluded from measurements and is not a QNN/model failure. The preserved historical `cleanup-proof.txt=cleanup_ok` is invalid because the former two-state test conflated ADB failure with absence. On the authorized reconnect, the exact pending root was removed and tri-state verified absent under `phone.lock` before any new staging. The campaign resumed with fresh context IDs; the interrupted run remained excluded.

Machine interruption history: [`results/phone-campaign-checkpoint/checkpoint.json`](results/phone-campaign-checkpoint/checkpoint.json). Cleanup closure: [`results/phone-campaign/cleanup-resume/cleanup-resume.json`](results/phone-campaign/cleanup-resume/cleanup-resume.json).

## Claim boundary

Completed claims are bounded to this deterministic 0024 reconstruction derivative, fixed Alba, canonical-v2 text, exact fixtures, ORT 1.27.1, QAIRT 2.49.0, and the authorized SM-S918B. Host context generation is offline cost and not charged to phone reload setup. Physical proof establishes the observed calls, not arbitrary graphs or production readiness.

Human review is now complete for the two retained phone WAVs. Moritz independently accepted source SHA-256 `028f8a1e…4241` and context SHA-256 `7c3fc41d…6d81` as “good.” These are new exact-hash verdicts recorded in [`results/listening-review-2026-08-25.json`](results/listening-review-2026-08-25.json); neither is inherited from experiment 0014, and neither transfers to any other hash or to the Pocket TTS family.

## Reproduction

The normative contract is [`protocol/experiment-contract.json`](protocol/experiment-contract.json). Public source pins are:

- Kyutai code `d108410d23eef7e01db282f9442891162dbc3db6`;
- exporter `b25d4a7da07c5a96d1429102fcd9116f25d7ab5d`;
- weights `be9c6b48…bb0a`;
- tokenizer `d461765a…c3f6`;
- fixed Alba state `e4a323e8…17b1c`.

The local reconstruction environment used Python 3.11.13, Torch 2.10.0+cpu, ONNX 1.17.0, and ORT CPU 1.22.1. After placing the pinned exporter/config/assets under ignored `.local`, run under the shared nonblocking heavy-RAM lock:

```bash
ALLOW_DOCUMENTED_DERIVATIVE=yes \
  experiments/0024-pocket-tts-qnn-precompiled-context-startup/tools/reconstruct_graphs.sh

experiments/0024-pocket-tts-qnn-precompiled-context-startup/.local/export-venv/bin/python \
  experiments/0024-pocket-tts-qnn-precompiled-context-startup/tools/generate_host_e2e.py \
  --graphs experiments/0024-pocket-tts-qnn-precompiled-context-startup/.local/graphs \
  --assets experiments/0024-pocket-tts-qnn-precompiled-context-startup/.local/assets \
  --output experiments/0024-pocket-tts-qnn-precompiled-context-startup/.local/host-e2e
```

Context generation reproduction remains serialized: [`tools/generate_contexts.sh`](tools/generate_contexts.sh) requires `QNN_HOST_ACCESS_CONFIRMED=yes`, takes `artifacts/locks/heavy-ram.lock` nonblockingly, and is permitted only after explicit clearance. Aggregate it with [`tools/finalize_host_context_smoke.py`](tools/finalize_host_context_smoke.py). Phone tooling additionally requires both standing authorization and fresh coordination clearance, the real `artifacts/locks/phone.lock`, and the exact native transport/device contract in [`protocol/phone-transport-contract.json`](protocol/phone-transport-contract.json): regular non-symlink `/usr/bin/adb` at the pinned hash/version, `ADB_LIBUSB` unset, sole authorized serial plus manufacturer/model/device/SoC/ABI/boot/verified-boot/flash-lock gates, scoped staging, evidence pull, and verified cleanup. The first cleared attempt stopped before ADB because the historical Windows executable was absent; [`results/pre-adb-transport-attempt.json`](results/pre-adb-transport-attempt.json) binds that non-measurement.

## Validation

```bash
python3 -m unittest discover \
  -s experiments/0024-pocket-tts-qnn-precompiled-context-startup/tests \
  -p 'test_*.py' -v

git diff --check -- \
  experiments/0024-pocket-tts-qnn-precompiled-context-startup
```
