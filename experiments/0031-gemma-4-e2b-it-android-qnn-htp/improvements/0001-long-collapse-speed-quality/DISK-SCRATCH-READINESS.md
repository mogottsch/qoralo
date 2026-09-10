# Disk-backed scratch readiness — no restart authorized

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

Keep the accepted SDK, `.local/host-libs`, model bytes, patch, quantization settings, and sequential AR1→AR128 recipe unchanged. This is not a model or precision correction.

## Readiness checks and future launch gate

A lightweight check on 2026-09-10 found this track's `.local` on writable **ext4**, mounted from `/dev/mapper/cryptoroot`, with **687,656,939,520 bytes available**. `/tmp` is a separate tmpfs. Free space is a snapshot, not a reservation.

Before any future launch:

1. Obtain explicit Pi approval and the heavy slot; app work remains highest priority.
2. Create a new run directory exclusively through `run_host_guarded.py`. Never reuse attempts 01–05.
3. Inside that fresh run, create `qairt-tmp` with mode `0700` before starting Python. Verify the resolved path remains under the new run and is not a symlink.
4. Recheck that the scratch filesystem is writable and disk-backed (not tmpfs/ramfs), with at least **32 GiB free**. This is an operational reserve for external-data dumps, not a claim about model memory.
5. Record `QAIRT_TMP_DIR`, filesystem/free-space observations, SDK and host-library identities, and the command in the new attempt. Keep the low-priority pressure guard and swap policy.
6. Retain failure evidence and ownership-bound scratch inventory. Clean only that attempt's scratch, never shared `/tmp`, worktrees, completed DLCs, or model sources.

No directory has been staged for a new conversion and no next attempt has been launched. The proposal does not grant compilation, fidelity execution, or phone access. Actual AR128 input/output FP16 signatures and the four-way AR1/AR128 cache contract must pass before any separately approved compilation step.
