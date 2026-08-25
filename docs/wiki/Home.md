---
title: VibeVoice Android Wiki
aliases:
  - VibeVoice Android
  - Project wiki
kind: home
project: vibevoice-android-spike
---

# VibeVoice Android Wiki

> A human-readable map of the models, concepts, experiments, and decisions in this repository.

This vault explains project terminology before asking the reader to understand benchmark details. It is a maintained interpretation layer over the committed experiment evidence, not a replacement for that evidence.

## Start here

- [Wiki index](index.md) — every maintained page and its purpose.
- [Fixed Alba](concepts/fixed-alba.md) — why some Pocket routes use one pinned voice rather than voice cloning.
- [text64](concepts/text64.md) — why the canonical Pocket transcript is described as a 64-token route.
- [cache512](concepts/cache512.md) — what the 512-position static cache is and why QNN needs it.
- [Evidence boundaries](methods/evidence-boundaries.md) — how technical execution, audio validity, numerical comparison, and listening review differ.
- [Wiki log](log.md) — chronological maintenance history.

## How this fits the project

The repository has two deliberately separate layers:

1. **Evidence:** experiment directories, protocols, result JSON, retained samples, and the normalized Android benchmark registry.
2. **Explanation:** this vault, which connects that evidence into concept and overview pages.

When the two disagree, the committed owning evidence wins. Wiki pages should be corrected and their source references updated.

## Current scope

The initial vault is intentionally small. It starts with the terminology behind Pocket's “fixed-Alba text64/cache512” route because that phrase is difficult to understand without context. More concepts, model pages, experiment narratives, and decisions can be added incrementally as they become useful.
