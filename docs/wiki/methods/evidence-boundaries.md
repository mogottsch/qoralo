---
title: Evidence boundaries
aliases:
  - evidence classes
  - listening boundary
kind: method
project: vibevoice-android-spike
status: reviewed
last_verified: 2026-08-25
---

# Evidence boundaries

> A model can execute successfully and produce a valid WAV without establishing that the audio sounds good.

The project keeps four evidence classes separate so that a strong result in one class is not silently promoted into a stronger claim.

## Technical execution

This answers whether the route ran under its declared runtime and provider conditions. For QNN/HTP, strong proof includes CPU fallback disabled, QNN provider assignment, and matching physical RPC, accelerator, cycle, and HVX events.

Technical execution alone says nothing about perceptual quality.

## Structural audio validity

This checks whether the output is a complete, decodable audio container with the expected sample rate and channels, finite samples, and no obvious structural failure such as silence or clipping.

A structurally valid WAV may still sound wrong.

## Numerical or acoustic comparison

Correlation, SNR, tensor comparisons, hashes, EOS behavior, and frame counts describe relationships between outputs. These observations are useful for debugging and reproducibility, but numerical similarity or divergence is not itself a listening verdict.

## Listening review

Only Moritz's review of an exact WAV hash can mark that sample `accepted` or `rejected`. A byte-identical artifact may retain its exact-hash verdict. A byte-different output remains `not_reviewed`, even when it is structurally valid or numerically close to an accepted sample.

This is why [Fixed Alba](../concepts/fixed-alba.md) describes a voice/input contract rather than promising that every route using Alba sounds good.

## Evidence sources

- `.agents/skills/android-tts-benchmark/SKILL.md`
- `.agents/skills/experiment-html-pages/SKILL.md`
- `docs/android-benchmarks/registry.json`
