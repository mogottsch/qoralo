# 0024 — Pocket TTS QNN precompiled-context startup

## Status

**All eight host external-context functional smokes pass; Android E2E and measured cold distributions remain pending because the phone is unavailable.**

This experiment compares source-ONNX QNN session creation with external precompiled QNN EPContext reload for a newly reconstructed derivative of experiment 0014’s accepted canonical-v2 fixed-Alba/cache512 Pocket route.

It is **not** the exact 0014 graph set. The ignored historical graph/work files were cleaned. Reconstruction from the same public pinned weights, tokenizer, Alba state, code, and exporter first diverges at controlled ONNX serialization, before any 0024 context transformation:

- the four used controlled ONNX files reproduce the committed 0012 byte sizes exactly;
- their SHA-256 values differ;
- all eight 0014 derivative hashes consequently differ.

The unavailable historical Python/protobuf package state is not treated as an indefinite blocker. Experiment 0024 names and fingerprints its deterministic derivative honestly, requires fresh fallback-disabled QNN assignment for every graph, and requires fresh E2E/audio validation. See [`results/reconstruction.json`](results/reconstruction.json) for the full boundary, source/base hashes, operator counts, initializer-payload fingerprints, and I/O names.

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

Both eventual phone arms use the same eight 0024 graph derivatives, ABI, runtime/provider options, canonical inputs, runner, and phone:

1. **Source arm:** create eight QNN sessions from source ONNX; compilation is inside measured setup.
2. **Context arm:** create the same sessions from non-embedded EPContext ONNX descriptors plus external `<stem>_qnn.bin` files; offline context generation is reported separately and excluded from reload setup.

Sessions are text conditioner, text prefill, BOS AR, latent AR, flow, and Mimi decoder 12/6/1. CPU fallback remains disabled. Context reload must pass in a fresh isolated Docker process where only the descriptor, binary, smoke tool, required input fixture, ORT runtime, and QNN backend are mounted—source ONNX is unavailable.

After host smoke and complete E2E, each arm requires at least three fresh cold phone processes. Every benchmark process creates sessions once, runs one first complete generation plus five warm generations, and fully resets model/cache/decoder/noise state before every generation. The observed setup delta will be reported without a minimum speedup gate.

## Pending claims

- Host QNN source assignment/context generation/isolated reload: **passed for all eight functional smokes**.
- Android E2E for either arm: **pending / null**.
- Cold setup runs: **0 source, 0 context**.
- Warm RTF: **pending / null**.
- Physical RPC/accelerator/cycle/HVX evidence: **pending / null**.
- New phone WAV/listening verdict: **pending / null**.

No phone access occurred. The device became unavailable before a bounded phone campaign was prepared; no result is inferred from host emulation.

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

Context generation reproduction remains serialized: [`tools/generate_contexts.sh`](tools/generate_contexts.sh) requires `QNN_HOST_ACCESS_CONFIRMED=yes`, takes `artifacts/locks/heavy-ram.lock` nonblockingly, and is permitted only after explicit clearance. Aggregate it with [`tools/finalize_host_context_smoke.py`](tools/finalize_host_context_smoke.py). Phone tooling additionally requires both standing authorization and fresh coordination clearance, the real `artifacts/locks/phone.lock`, exact serial/model/SoC/ABI/boot gates, scoped staging, evidence pull, and verified cleanup.

## Validation

```bash
python3 -m unittest discover \
  -s experiments/0024-pocket-tts-qnn-precompiled-context-startup/tests \
  -p 'test_*.py' -v

git diff --check -- \
  experiments/0024-pocket-tts-qnn-precompiled-context-startup
```
