---
title: text64
aliases:
  - text64
  - 64-token text
kind: concept
project: vibevoice-android-spike
status: reviewed
last_verified: 2026-08-25
evidence_commits:
  - 751ad6c
  - b59601e
---

# text64

> The repository's canonical-v2 benchmark paragraph becomes exactly 64 token IDs when processed by the pinned Pocket tokenizer.

## Why it has a name

Pocket's accelerator-compatible ONNX graphs use fixed input shapes. Changing the number of text tokens changes graph inputs and recurrent-cache placement, so a 64-token graph is a distinct deployment route rather than a cosmetic relabeling of an older graph.

The canonical transcript is 226 UTF-8 bytes with no trailing newline. With the pinned tokenizer it produces 64 IDs, whose little-endian `int64` fixture has SHA-256 `56d50c958627be19a7f2c86dde68a537a80f3f6d9087c16f55fde58c4d117c82`.

## What it changes

The text-conditioner and FlowLM prefill graphs are specialized for 64 text positions. In the static recurrent layout, those positions follow 126 positions occupied by the [fixed Alba](fixed-alba.md) voice state.

Together with the maximum generated sequence, this determines why the route uses [cache512](cache512.md).

## What it does not mean

- It is not a general maximum text length for Pocket TTS.
- It does not mean the original paragraph contains 64 words or characters.
- Metrics and listening verdicts from older `text26/cache256` graphs do not automatically apply.
- A newly reconstructed `text64` graph with a different hash remains a distinct artifact requiring fresh validation.

## Evidence sources

- `protocols/android-tts-benchmark/transcript.txt`
- `experiments/0014-pocket-fp-onnx-qnn-htp/canonical-benchmark-protocol.json` at commit `751ad6c`
- `experiments/0024-pocket-tts-qnn-precompiled-context-startup/protocol/experiment-contract.json` at commit `b59601e`
