# Disk-backed scratch and AR1 reuse — exercised in attempt 06

## Diagnosed attempt-05 failure

AR1 conversion completed, but sequential AR128 failed with `OSError: [Errno 28] No space left on device` while writing `/tmp/tmprema7d8c/model.data`. `/tmp` is a roughly 16 GiB tmpfs. This is a host storage failure, not a numerical or model failure.

Only that traceback-bound, UID-owned scratch directory was removed, after retaining its inventory and partial data hash: 8,263,168,000 bytes, SHA-256 `5d0b944e1df62d1c9e0fa3995bfe8591c88ac293f00e3489bdb9c47b255760ae`. The completed AR1 DLC and all source/candidate ONNX files remain untouched. Other `/tmp` directories were not cleaned.

## Source-bound fix

The installed QAIRT utility `lib/python/qti/aisw/converters/onnx/util.py`, function `unload_external_data`, chooses its parent directory from `QAIRT_TMP_DIR`, otherwise Python's default temporary directory. It then creates a unique child directory there. Inspected file SHA-256:

`d118b2b14bc57340fedfe3e7f950a38806d1f4d917b51a2a2620de579aae54b2`

For a new separately approved attempt, set only:

```text
QAIRT_TMP_DIR=<fresh attempt directory under this track/.local>/qairt-tmp
```

Keep the accepted SDK, `.local/host-libs`, model bytes, patch and quantization settings unchanged. This is not a model or precision correction. Following Pi's source-only efficiency direction, the next distinct attempt may convert **AR128 only**, reusing the verified attempt-05 AR1 DLC byte-for-byte instead of repeating its successful conversion.

## Verified AR1 reuse

`convert_global_value_fp16.py --run-dir <fresh-run> --reuse-ar1-dlc <retained-ar1.dlc>` now verifies, before importing QAIRT:

- accepted provenance commit `d5e6b94`, run `global-value-fp16-20260910T090755Z-attempt-05`;
- committed result SHA-256 `b298cab9c895955069b8b671835d4ac29d66b58aaac37ec8398bdc9f6621dcac` and its passed actual AR1 interface gate;
- AR1 DLC size **2,356,848,948 bytes** and SHA-256 `4e67d80ea342088f5235a9238dc209739d8961083b08895fa066d6857687a6cc`.

A missing file, wrong size, same-size wrong hash, or changed provenance is rejected. The successful file is referenced in place, never rewritten or relabeled as a new conversion. The new run writes `ar1-reuse.json` and records only newly converted AR128 in `converted-models.json`; `candidate-models.json` explicitly distinguishes reused and new origins. Reuse-only receipts also prevent an in-place restart after an early failure.

The precision patch is unchanged; a regression test compares its AST to the successful attempt-05 snapshot. Tests use tiny files or synthetic metadata, not real model execution. `validate_global_value_patch.py` accepts an AR128-only patch receipt only with explicit AR1 reuse provenance.

Before compilation, inspect actual AR128 interfaces against its baseline and feed both actual CSV comparisons through `inspect_global_value_dlc.require_cache_pair`. Missing/failed AR128 evidence or any four-way datatype/encoding mismatch is rejected. Even a passed pair gate does not prove HTP delegation or fidelity. No compilation is invoked by the conversion tool.

The source-only preparation was accepted in `bbd1eec`. It was subsequently exercised after a separate release in `global-value-fp16-20260910T095945Z-attempt-06`: real AR1 reuse verification passed, only AR128 was converted, and both actual CSVs passed the paired-cache gate. This does not authorize or establish context compilation or fidelity.

## Readiness checks and future launch gate

A lightweight check on 2026-09-10 found this track's `.local` on writable **ext4**, mounted from `/dev/mapper/cryptoroot`, with **687,656,939,520 bytes available**. `/tmp` is a separate tmpfs. Free space is a snapshot, not a reservation.

Before any future launch:

1. Obtain explicit Pi approval and the heavy slot; app work remains highest priority.
2. Create a new run directory exclusively through `run_host_guarded.py`. Never reuse attempts 01–05.
3. Inside that fresh run, create `qairt-tmp` with mode `0700` before starting Python. Verify the resolved path remains under the new run and is not a symlink.
4. Recheck that the scratch filesystem is writable and disk-backed (not tmpfs/ramfs), with at least **32 GiB free**. This is an operational reserve for external-data dumps, not a claim about model memory.
5. Record `QAIRT_TMP_DIR`, filesystem/free-space observations, SDK and host-library identities, and the command in the new attempt. Keep the low-priority pressure guard and swap policy.
6. Retain failure evidence and ownership-bound scratch inventory. Clean only that attempt's scratch, never shared `/tmp`, worktrees, completed DLCs, or model sources.

Attempt 06 verified an owned `0700` ext4 scratch directory with 686,253,473,792 bytes free, successfully completed AR128 conversion, and removed its empty scratch root after the SDK had cleaned all temporary files. Exact preflight, reuse, process and cleanup receipts are in `results/global-value-fp16-attempt-06/`. Actual AR128 input/output FP16 signatures and all 30 four-way AR1/AR128 cache contracts passed. Context compilation, fidelity execution and phone access still require separate approval; none occurred in attempt 06.
