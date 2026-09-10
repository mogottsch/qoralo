# Source-only position-1 identical-state control

**Plan and existing-artifact inventory only. No new QDQ replay, model/PTE load, QNN call, or phone access occurred for this plan.**

## What is already retained

`same-state-inventory.json` binds the available artifacts:

- QDQ position-0 outputs: 73 saved tensors at `.local/diagnosis/restart-20260910T083327Z/qdq-outputs.pt`, SHA-256 `a471368c8b319013c6b0827afb172fd69aabbc11f12bf7de90556af79a7c8bf2`, from the exact `30799090…c492364` PT2 artifact. This additional LOCAL-ONLY state source must be preserved and copied in migrations/handovers, not cleaned as disposable compile scratch.
- The originating QDQ command uses canonical token 248045, input position 0, zero state, and the mask exposing only the current-token slot. Its driver, params, input IDs, and artifact hashes are bound by accepted `e528f41` evidence.
- Independent saved-tensor inspection found the position-0 logits **bit-identical** to position 0 of the completed `cc6c49c` QDQ replay (max absolute difference 0).
- Those 48 QDQ state outputs can materialize the state *before position 1* without a model call: allocate zero state templates, replace recurrent/convolution state, and insert the six full-attention KV updates at slot 0 using the pinned transport helper.
- QNN state before position 1 is the retained position-000 checkpoint; QNN state before position 2 is position-001. QDQ state before position 2 was not retained by the full replay. This makes position 1 the cheapest controlled comparison.
- Existing QDQ and own-state QNN logits at position 1 are both already retained and hash-bound in this prefix result.

The full-short replay saved logits, not QDQ state checkpoints. Thus state-pack lineage rests on the separately retained position-0 outputs from the same graph/input/reset configuration; the direct cross-run equality check covers logits, not unavailable full-replay state bytes. Review that deterministic-source assumption before treating the old position-1 logits as an identical-state reference. Logit equality alone is not a proof of state equality.

No derived QDQ full-state input pack has been executed by QNN. Materializing one later from the saved outputs is data preparation, not a new QDQ model replay; hash every tensor/pack and its source chain before use.

## Proposed controlled call — not executed or authorized

Use the same exact 73-output PTE. Execute **one input position only**:

- position: **1**;
- input token: **8678**, from the canonical IDs;
- state: the reconstructed **QDQ-after-position-0** state as a source-lineage candidate; it is **not byte-verified against missing full-replay state**. For exact same-state attribution, first validate one QDQ position-1 call on this exact input pack and use that output as the paired reference;
- mask: `-65504` except occupied prior KV slot 0 and the final current-token slot, both zero;
- save all raw outputs, input-pack/checkpoint hashes, command, phase/error records and cleanup;
- use a fresh, separately reviewed bounded host run and independent resource/deadline supervisor. A 300-second single-position budget is a planning example, not authorization or a runtime promise.

Do not call the own-state trajectory driver's normal resume path with a fabricated QNN-origin checkpoint. This is a distinct controlled input experiment whose state origin must say **QDQ reference**, not QNN-owned continuation. Do not execute QNN position 0 first or automatically follow the control with further positions.

## What the comparison could distinguish

Let `S_D` be QDQ's state before position 1 and `S_Q` QNN's state before position 1. Existing outputs are historical `D(S_D_old)` and `Q(S_Q)`. If a separately approved one-call QDQ validation supplies `D(S_D)` on the materialized pack, a later paired QNN call supplies `Q(S_D)`. Without that validation, identifying `S_D` with the unretained `S_D_old` remains an assumption:

- current-call route difference at identical state: `Q(S_D) - D(S_D)`;
- previous-state effect through QNN: `Q(S_Q) - Q(S_D)`;
- their vector sum equals `Q(S_Q) - D(S_D)`;
- to relate it to the original historical difference, preserve a third vector `D(S_D) - D(S_D_old)`. The three vectors sum to `Q(S_Q) - D(S_D_old)` without assuming the historical reference used byte-identical state.

Cosines and error norms are not additive; preserve raw vectors rather than pretending scalar metrics form an additive decomposition. Any attribution is conditional on the controlled artifact/input/state bindings and the explicit-state model. It would localize a numerical difference, not establish full trajectory fidelity, identify a specific bad operator by itself, prove useful text, or authorize a campaign.

## Review gate

Review the inventory, derived-input-pack recipe, exact same-state binding, dedicated single-call driver/tests, and budget before any model/QNN execution. The physical baseline and all protected 174-position QDQ archives remain unchanged.
