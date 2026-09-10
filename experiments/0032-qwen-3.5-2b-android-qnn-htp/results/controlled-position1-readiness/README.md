# Controlled position-1 readiness and materialized QDQ-origin inputs

**Source/data work only. No new QDQ, QNN, PTE/model execution or phone operation occurred.** The 51-input pack is materialized from saved tensors; the single-position drivers have only synthetic validation.

## Materialized inputs

The saved 73-output QDQ position-0 bundle (`a471368c…c8bf2`) is bound to the accepted `30799090…c492364` PT2, canonical input token 248045, zero initial state, and current-token-only mask. Its logits match the completed replay's position 0 exactly. The materializer copies its 48 state outputs into zero templates, inserts full-attention KV at slot 0, and adds the actual position-1 call inputs:

- **position 1**, canonical input token **8678**;
- mask exposing prior KV slot 0 and the final current-token slot only;
- 48 QDQ-derived recurrent/convolution/KV state inputs;
- **explicit QDQ origin, not own-QNN resume**.

Independent data inspection checked every copied recurrent/convolution tensor and KV insertion/future-zero region against the saved source outputs. No model call was needed.

| Binding | Value |
|---|---|
| Raw input pack | 121,313,354 bytes |
| Raw pack SHA-256 | `bfe14bca74090778550618c1c6eb485728e15e6e784e936b87606dcb298ebe0d` |
| Logical tensor-values/dtype/shape SHA-256 | `4251bbce8005e37cb9fc4c8da8f0af604e7c4a9884179e2ccd358ef4865c78e4` |
| Pack header SHA-256 | `ec38185783dbd2bc387dbf5387c3f89cd4a4fbb786f2504a82b2b48cd43cd392` |

Git retains the complete pack and copied historical QDQ position-1 logits losslessly compressed, with raw/compressed hashes and verified recovery. The original pack/header remain protected under `.local/diagnosis/controlled-p1-qdq-pack-20260910T114619Z/`. Do not overwrite the header or use it with the trajectory helper's resume interface.

The materialization source snapshot is retained in `reproduction/`; the current helper adds a separate data-only verifier and synthetic tests. Both versions' hashes are recorded.

## The lineage assumption remains

The full 174-position QDQ replay saved logits, not state checkpoints. The pack derives from a **separate saved position-0 call** on the same artifact/input/reset configuration. Matching position-0 logits does not prove the absent full-replay state bytes were identical. No unqualified identity with the old full-replay state is claimed.

A QNN call compared only with the historical position-1 QDQ logits remains a **lineage-assumed comparison**. The driver explicitly reports `exact_same_pack_qdq_reference_used: false` in that mode.

## Actual calls needed after review — none run yet

For an exact same-input-pack QDQ/QNN comparison, use **two separately approved and budgeted single calls**, never an automatic sequence:

1. **Optional ONE QDQ position-1 validation call** on this pack. Proposed host limit: **600 seconds**, allowing the 13.65 GB archive hash/load plus one forward. This is not a 174-token replay. Retain all 73 outputs and the input-values digest before/after the call.
2. **ONE QNN-x86 position-1 call** on the same pack. Proposed host limit: **300 seconds**, based on the earlier roughly 130-second-per-position simulation cost plus load/persistence allowance. Supply the exact reviewed QDQ control result path/hash from step 1.

The second call validates that the QDQ reference was a completed one-call result on the same reviewed header and input-values hash, with the correct QDQ artifact and no input mutation. Only then can it report an exact same-pack reference. Backend choice, output directory and timeout are explicit; there is no resume, position loop, autoregressive generation or auto-follow-on. The existing independent supervisor enforces native-call wall limits, pressure yielding, disk-backed scratch, low priority/four math threads, TERM/grace/KILL and reap. Budgets are planning examples, not execution permission or measured runtime guarantees.

If the QDQ validation is omitted, only **one** new QNN call is needed, but **exact same-state attribution is not established**. The missing reference-state assumption cannot be removed by relabeling metadata.

## Dedicated driver and tests

`tools/controlled_position1.py` has three explicit modes:

- `prepare`: saved-tensor materialization only;
- `verify`: independent saved-data copy/insertion checks only;
- `call --backend qdq|qnn`: exactly one separately authorized supervised model call.

The driver checks the reviewed header digest, source model/parameter/token bindings, all 51 input shapes/dtypes/values, position/mask, input mutation, raw output retention, paired-result identity, and time/error/no-overwrite handling. The test suite injects tiny backends and prohibits real model/PTE/PT2 loaders.

The raw model outputs are saved before post-call validation, including on mutation/nonfinite/budget failure. Original historical vectors are never overwritten. `difference_vectors()` performs a **vector** decomposition without modifying its inputs:

```text
current-call term       = controlled QNN - same-pack QDQ
QNN state-effect term   = original own-state QNN - controlled QNN
reference-shift term    = same-pack QDQ - historical full-replay QDQ
sum                    = original own-state QNN - historical full-replay QDQ
```

The reference-shift term is retained if the new QDQ validation differs from the historical baseline. Scalar cosines and error norms are **not additive** and are never summed. Attribution also assumes the fixed reviewed native runtime/artifact stack; it is not a model accuracy or full-fidelity claim.

## Review-only command shapes

Use the protected original header below or an explicitly reviewed relocation, not a silently rewritten header. No `call` command was executed for this readiness milestone.

```bash
E="$PWD/experiments/0032-qwen-3.5-2b-android-qnn-htp"
export PYTHONPATH="$E/.local/executorch:$PWD"
H="$E/.local/diagnosis/controlled-p1-qdq-pack-20260910T114619Z/pack-header.json"
HASH=ec38185783dbd2bc387dbf5387c3f89cd4a4fbb786f2504a82b2b48cd43cd392
# Data-only verification; no model call:
artifacts/venv-executorch-1.2/bin/python "$E/tools/controlled_position1.py" verify \
  --pack-header "$H" --pack-header-sha256 "$HASH" --artifact-root "$E"
# ONLY after a separate QDQ release:
artifacts/venv-executorch-1.2/bin/python "$E/tools/controlled_position1.py" call \
  --backend qdq --pack-header "$H" --pack-header-sha256 "$HASH" \
  --artifact-root "$E" --timeout-seconds 600 --output-dir "$E/.local/<fresh-qdq-control>"
# ONLY after QDQ result review and a separate QNN release; use reviewed QNN environment:
artifacts/venv-executorch-1.2/bin/python "$E/tools/controlled_position1.py" call \
  --backend qnn --pack-header "$H" --pack-header-sha256 "$HASH" \
  --artifact-root "$E" --timeout-seconds 300 --output-dir "$E/.local/<fresh-qnn-control>" \
  --qdq-control-result <reviewed-qdq-result.json> --qdq-control-sha256 <reviewed-result-digest>
```

Physical baseline/preflight, original prefix vectors/checkpoints, and protected 174-position LOCAL-ONLY references remain unchanged. This readiness neither authorizes a model call nor claims physical execution, generated text, full fidelity or campaign readiness.
