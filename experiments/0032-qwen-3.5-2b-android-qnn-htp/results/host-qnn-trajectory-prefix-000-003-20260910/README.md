# QNN-x86 own-state trajectory: positions 0–3

**The authorized four-position host segment completed, but numerical drift remains.** Position-1 logit cosine drops to **0.679220** and the first argmax divergence occurs at **position 2**. This is accumulated own-state trajectory drift, not same-state causal localization or full-model fidelity.

## Exact bounded outcome

The exact HistogramObserver/W4A16 73-output PTE (`7f30be3d…ff3fea`) ran positions 0–3 of the canonical short input from zero state. Its first 49 outputs comprise logits and **48 state tensors**; 24 additional hidden tensors were retained, never fed back as state. QNN carried its own state after every call; the completed `30799090…c492364` QDQ trajectory supplied comparison targets only.

| Position | Input ID | Cosine | Max absolute error | Mean absolute error | QDQ argmax | QNN argmax |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 248045 | 0.947168 | 2.895951 | 0.483211 | 198 | 198 |
| 1 | 8678 | **0.679220** | 7.649495 | 1.416106 | 198 | 198 |
| 2 | 198 | 0.784361 | 7.648499 | 1.292108 | **248045** | **71093** |
| 3 | 2523 | 0.890331 | 6.707253 | 1.101813 | 2224 | 513 |

Four forwards, four state updates, and four comparisons completed. Independent saved-data inspection verified all 73 tensors were finite at every position and each 48-state checkpoint exactly matched the declared state-output insertion/replacement semantics. One-thread recomputation matches the original four-thread comparison values within `1e-6`; raw original values are retained in the journal.

The supervisor exited 0 after **526.831 seconds** (worker 525.999 seconds), below the **900-second** limit. This wall time includes preflight, runtime load, raw/checkpoint writes and comparison; it is not Android latency or a campaign rate. Host logs show four contexts loaded/retrieved and 16 successful QNN graph executions. `kHtpBackend` here is a **QNN-x86 host backend/simulation observation**, not physical HTP proof.

## Checkpoints and cleanup

The final checkpoint is after position 3, with **next position 4**:

- metadata SHA-256: `029e2c3735442e6604bf3efd94e88669bff1ded328f654da77d4620baf74b07b`;
- state-file SHA-256: `f2591ab3810126ef996f3cf5f3c9e751ebebaf33f0fc10f2eb02a9f450aefe3c`;
- consumed-prefix SHA-256: `41f2cf826f7fa46fbbc1d834ee96eb9582847af2ad575471ee0ab2629e9b5e0a`.

Every checkpoint binds the exact PTE, QDQ/reference manifest, parameters, input IDs, context, driver/state-transport source, prefix, and own-QNN-state origin. No checkpoint was resumed. No automatic follow-on, full174 run, autoregressive generation, or phone operation occurred. Worker 1683122 was reaped, its process group was absent, and disk-backed scratch was empty. No outputs or reference tensors were cleaned.

## Complete retention and verification

Git contains lossless copies of all **four complete 73-output bundles**, all **four complete 48-state checkpoints**, the four paired QDQ logit tensors, checkpoint headers, journal, logs, telemetry and exact command/source bindings. Thirteen raw recoveries were checked. Compressed payloads total about 65 MB; each file is below 11 MB. `compression-manifest.json` contains every raw/compressed path, size and SHA-256.

Raw originals and local compressed backups remain protected at:

```text
experiments/0032-qwen-3.5-2b-android-qnn-htp/.local/diagnosis/qnn-prefix-20260910T104805Z/
```

Unlike the earlier full174 QDQ tensor archive, this four-position result's payloads **can be recovered from Git**. The earlier 174-position LOCAL-ONLY retention/migration requirement is unchanged and those directories must not be cleaned. Restoring a checkpoint at a different filesystem path requires an explicitly reviewed metadata relocation/new header digest; do not edit the original reviewed header or auto-resume it.

Byte/hash/prefix verification (streaming decompression, no model load):

```bash
E=experiments/0032-qwen-3.5-2b-android-qnn-htp
python "$E/tools/verify_qnn_prefix_evidence.py" "$E/results/host-qnn-trajectory-prefix-000-003-20260910"
```

Numerical comparison and checkpoint-materialization verification on saved tensors only (one thread, **no PTE/PT2/model load or execution**):

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  artifacts/venv-executorch-1.2/bin/python "$E/tools/verify_qnn_prefix_evidence.py" \
  "$E/results/host-qnn-trajectory-prefix-000-003-20260910" --tensor-values
```

## Source-only next control

[`SAME_STATE_PLAN.md`](SAME_STATE_PLAN.md) proposes one **position-1** call using reconstructed saved QDQ-after-position-0 state, with existing QDQ position-1 logits as the reference. Inventory confirms the saved QDQ position-0 outputs come from the exact accepted PT2/input/reset configuration and their logits are bit-identical to the full replay's position 0. The full replay did not save state checkpoints: logit identity alone does not prove missing state-byte identity, so the deterministic-source lineage still needs review.

The proposed controlled call could distinguish current-call numerical difference from prior-state feedback effects. It has **not run**. Do not misuse the own-state resume path by relabeling QDQ-origin state as QNN-owned. No additional QDQ replay is needed merely to inventory/materialize the saved position-0 outputs, and none occurred here.

There is no full174 QNN fidelity, current-call causal attribution, FP32/accuracy, generated-text, physical HTP, benchmark reuse, or campaign claim. Physical PTE `23ac8abd…d2c506` and its preflight remain unchanged.
