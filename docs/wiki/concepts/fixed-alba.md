---
title: Fixed Alba
aliases:
  - fixed Alba
  - fixed-Alba
  - fixed Alba state
kind: concept
project: vibevoice-android-spike
status: reviewed
last_verified: 2026-08-25
evidence_commits:
  - ced16de
  - 751ad6c
  - b59601e
---

# Fixed Alba

> Pocket TTS uses one pinned, precomputed speaker state for its Alba voice instead of deriving a new voice from reference audio.

## Why the project uses it

The selected public Pocket checkpoint is the `without-voice-cloning` checkpoint. Earlier experiments accidentally exercised an invalid Bria cloning path: the checkpoint's relevant Mimi encoder tensors were all zero, so matching source and ONNX behavior did not establish a valid cloned voice.

The recovered route supplies the official Alba state directly. This creates a controlled fixed-voice path that can be reproduced across host, Android CPU, and QNN/HTP runs.

## What “fixed” means

Every run in the route receives the same hash-pinned Alba state and packed recurrent cache. The speaker condition is therefore part of the frozen benchmark input, alongside the transcript, token IDs, random seed, temperature, model graphs, and runtime configuration.

In the canonical route, the state consumes 126 sequence positions before the text and generated positions. See [cache512](cache512.md) for the complete layout.

## What it does not mean

- It is **not voice cloning**.
- It does not establish behavior for arbitrary speakers or reference recordings.
- It does not mean every Pocket graph or output is equivalent.
- A listening verdict applies only to the exact reviewed WAV hash; it does not automatically transfer to a reconstructed route or different output.

See [Evidence boundaries](../methods/evidence-boundaries.md) for how the project handles these distinctions.

## Related pages

- [Pocket TTS](../models/pocket-tts.md)
- [text64](text64.md)
- [cache512](cache512.md)

## Evidence sources

- `experiments/0014-pocket-fp-onnx-qnn-htp/results/zero-voice-encoder-root-cause.json` at commit `ced16de`
- `experiments/0014-pocket-fp-onnx-qnn-htp/README.md` at commit `751ad6c`
- `experiments/0014-pocket-fp-onnx-qnn-htp/canonical-benchmark-protocol.json` at commit `751ad6c`
- `experiments/0024-pocket-tts-qnn-precompiled-context-startup/protocol/experiment-contract.json` at commit `b59601e`
