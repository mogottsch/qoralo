---
title: Mobile Podcast Inference Wiki
aliases:
  - VibeVoice Android
  - Project wiki
kind: home
project: vibevoice-android-spike
---

# Mobile Podcast Inference Wiki

> A human-readable map of the models, concepts, experiments, and decisions behind this repository's local LLM and TTS work.

The project validates two local inference components for offline-first mobile podcast generation: an LLM, eventually used to generate transcripts, and TTS used to render speech. This vault explains project terminology before asking the reader to understand benchmark details. It is a maintained interpretation layer over the committed experiment evidence, not a replacement for that evidence.

## Start here

- [Wiki index](index.md) — every maintained page and its purpose.
- [VibeVoice 1.5B](models/vibevoice-1.5b.md) — the original large-model Android export and its terminal feasibility result.
- [VibeVoice Realtime 0.5B](models/vibevoice-realtime-0.5b.md) — the smaller streaming model's feasibility-only status.
- [Supertonic 3](models/supertonic-3.md) — CPU, hybrid, full-neural-HTP, and precompiled-context routes.
- [Pocket TTS](models/pocket-tts.md) — archive, source-derived, fixed-Alba, and QNN routes.
- [Kokoro-82M](models/kokoro-82m.md) — completed CPU routes and the terminal host-QNN boundary.
- [MOSS-TTS-Nano](models/moss-tts-nano.md) — completed CPU execution and blocked physical-phone QNN work.
- [Fixed Alba](concepts/fixed-alba.md) — why some Pocket routes use one pinned voice rather than voice cloning.
- [text64](concepts/text64.md) — why the canonical Pocket transcript is described as a 64-token route.
- [cache512](concepts/cache512.md) — what the 512-position static cache is and why QNN needs it.
- [Evidence boundaries](methods/evidence-boundaries.md) — how technical execution, audio validity, numerical comparison, and listening review differ.
- [Wiki log](log.md) — chronological maintenance history.

## How this fits the project

The repository has two deliberately separate layers:

1. **Evidence:** experiment directories, component-specific protocols, result JSON, retained outputs, and the separate normalized Android LLM and TTS benchmark registries.
2. **Explanation:** this vault, which connects that evidence into concept and overview pages.

When the two disagree, the committed owning evidence wins. Wiki pages should be corrected and their source references updated.

## Current scope

The vault has a baseline note for every TTS model label represented in the Android TTS benchmark registry: VibeVoice 1.5B, VibeVoice Realtime 0.5B, Supertonic 3, Pocket TTS, Kokoro, and MOSS-TTS-Nano. The first concept set explains the terminology behind Pocket's “fixed-Alba text64/cache512” route. The generic Android LLM protocol and registry now establish a separate performance-focused evidence path; LLM model notes can be added after committed experiments exist. Experiment narratives and decision pages can be integrated incrementally without replacing their owning evidence.
