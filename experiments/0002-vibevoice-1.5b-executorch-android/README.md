# Experiment 0002 — VibeVoice 1.5B with ExecuTorch on Android

## Objective

Export VibeVoice components to ExecuTorch, validate them against experiment 0001 fixtures, and progress toward the same approximately 15-second output on the Galaxy S23 Ultra.

## Status

Blocked on experiment 0001.

## Component order

1. Acoustic decoder
2. Diffusion-head step
3. Language-backbone forward pass
4. KV-cache update
5. Speaker conditioning
6. Short end-to-end generation
7. Fixed reference transcript
