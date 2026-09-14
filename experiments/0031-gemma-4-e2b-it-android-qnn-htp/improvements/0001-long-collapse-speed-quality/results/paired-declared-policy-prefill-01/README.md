# Completed host prefill, failed numerical comparison

> **INVALID REFERENCE — additive finding:** the original reference treated binary16 static transport words as integers (`0x3c00` became 15360 rather than 1.0), corrupting 15 RMS normalization paths. The original run and comparison below remain preserved, not QNN/model defect evidence. See [the notice](INVALID-REFERENCE.json) and [static audit](../declared-reference-static-audit-01/README.md). Finite final codes did not validate intermediates; overflow/invalid-operation warnings are retained in `host/child.stderr`.

The single authorized host reference `legacy-ref-20260913T131149Z-01` completed with **native, guard, service and controller exits 0** after the phone was released and its complete capture passed strict binding. It used the actual 128 captured inputs and its own 30 caches. No HTP caches were imported.

The reference completed **16 chunks / 1,929 inputs / zero generation calls** in **367.735 seconds**; guard wall time was **375.316 seconds**. The service reported 4.7 GiB peak memory and zero peak swap, under the unchanged 12 GiB RAM / 2 GiB swap / 2 CPU / 1,800-second limits. All 110,288 operator begins have matching ends: 220,576 trace events / 19,914,985 bytes, with no trace error.

## Full vectors were saved before comparison

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| QNN UINT16 row 8 | 524,288 | `7b6c6e2d755a024e59d8ac05fbe4a27e992bfa4774c2286fff85144da26bafe9` |
| Reference UINT16 | 524,288 | `6ec66bc08b0081546bd3863ffa65835f3e2204c7dbe95319f400e305ea26d455` |
| Reference F32 serialization | 1,048,576 | `4baa342a88c0eed83c356977897850f3bd6b379df5aa87d1893ae6e61ae8d5ea` |

The F32 file contains 262,144 finite values and matches expansion of the saved reference raw codes on the declared output grid. All vectors and the complete operation trace remain private; hashes and bounded derived statistics are published.

## The comparison fails badly

- Unique QNN argmax **818**, reference argmax **83634**.
- **0 / 262,144** equal raw codes; top-20 overlap **0**.
- Common-grid mean absolute error **27.3911**, maximum error **46.7555**.
- Cosine **−0.5066**, Pearson correlation **−0.0482**.

These observations do **not** establish a QNN/DSP defect or generation-quality failure. The portable reference's encoding/operator semantics must be audited before treating it as numerical ground truth. The mismatch is much larger than a claim about proprietary half-way rounding can explain without further evidence, but its cause is not established here.

The actual captured inputs matched the prepared host formulas at all 32,768,000 UINT16 elements. That rules out a formula-versus-capture discrepancy in these external inputs; it does not validate static-weight interpretation, all operator semantics, cache evolution or DSP equivalence.

## Boundaries and next work

The one host grant is consumed. There is **no automatic full-model or phone replay**. Preserve this completed result, earlier failures and missing-output attempts unchanged. Pi authorized a bounded **saved/static** contract audit: verify BW4 storage semantics against documented contracts and known mapped float weights, then grids, channel axes, clipping/folds, masks, casts and operator axes/broadcasting. Do not select an interpretation merely because it makes QNN logits look closer.

`analyze_paired_declared_prefill.py` performs saved-only length/hash/F32 checks and comparison. Undefined cosine/Pearson metrics remain nullable; incomplete traces remain evidence. No model or device execution occurs in analysis.
