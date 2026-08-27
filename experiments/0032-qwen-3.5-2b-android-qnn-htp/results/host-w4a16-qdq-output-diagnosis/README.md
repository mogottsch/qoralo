# Host W4A16 QDQ output diagnosis

The canonical 174-token short prompt was replayed through the exact PT2E quantization recipe used to create the physical QNN route.

To avoid the earlier 25.5 GB multi-representation footprint, preparation and replay ran in separate processes. The prepare process exported, calibrated, converted, persisted the QDQ graph, and exited. A fresh process then loaded only the persisted QDQ graph and explicit state templates. Preparation peaked at 16,992,556 KiB RSS; replay peaked at 6,094,088 KiB RSS and took 2,467.044 seconds.

## Three-way result

- Pre-PTQ host calibration: token 21365, `Given`.
- Host W4A16 PT2E QDQ: token 760, `The`.
- Physical QNN/HTP attempt: token 0, `!`.

PTQ materially changes the top token, but the host QDQ result does not reproduce token 0. Therefore PTQ alone does not explain the physical mismatch. The first divergence remains to be localized among QNN lowering/runtime behavior, explicit input/state transport, shard boundaries, and final output handling.

The 13.64 GB QDQ checkpoint and pre-PTQ logits remain local-only and are hash-bound in `result.json`. The phase logs are retained here.

## Claim boundary

This is one host diagnostic replay, not Android evidence or benchmark performance. It does not establish a downstream root cause, output fidelity, or campaign readiness. No phone retry or campaign is authorized.
