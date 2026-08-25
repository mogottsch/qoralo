---
title: cache512
aliases:
  - cache512
  - 512-position cache
  - fixed cache512
kind: concept
project: vibevoice-android-spike
status: reviewed
last_verified: 2026-08-25
evidence_commits:
  - 751ad6c
  - b59601e
---

# cache512

> Pocket's recurrent FlowLM graphs use a fixed attention-cache capacity of 512 sequence positions so their shapes can be compiled for QNN/HTP.

## Why the cache is fixed

A dynamic recurrent cache can grow as generation proceeds. Accelerator compilation is easier and more predictable when tensor shapes are known in advance, so this route exports fixed-size key/value tensors and a fixed validity mask.

“512” counts sequence positions. It is not 512 bytes, 512 generated audio frames, or a generic device cache size.

## How the positions are used

The canonical route reserves:

| Content | Positions |
|---|---:|
| [Fixed Alba](fixed-alba.md) voice state | 126 |
| [text64](text64.md) token positions | 64 |
| Maximum generated positions | 292 |
| **Total required** | **482** |
| Spare capacity | 30 |

Because `126 + 64 + 292 = 482`, the complete bounded route fits inside 512 positions without rolling away the voice or text context at the configured generation cap.

The protocol represents this as twelve right-aligned `[1, 16, 512, 64]` key/value tensors plus a `[1, 1, 1, 512]` finite additive validity mask.

## What it does not mean

- It is not the model's total memory usage.
- It does not guarantee arbitrary text or generation lengths will fit.
- It does not describe the offline QNN context binary size.
- It does not make graphs with different serialized hashes identical.

## Evidence sources

- `experiments/0014-pocket-fp-onnx-qnn-htp/canonical-benchmark-protocol.json` at commit `751ad6c`
- `experiments/0014-pocket-fp-onnx-qnn-htp/README.md` at commit `751ad6c`
- `experiments/0024-pocket-tts-qnn-precompiled-context-startup/protocol/experiment-contract.json` at commit `b59601e`
