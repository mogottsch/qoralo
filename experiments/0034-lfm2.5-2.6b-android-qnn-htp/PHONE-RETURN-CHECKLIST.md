# 0034 integrated AR171 → AR1 return-to-phone checklist

This is a **readiness checklist, not authorization**. Wait for a fresh Pi phone-priority handoff. Do not use the older qnn-net-run stages for a corrected position-semantic claim.

## Frozen candidate

- Owner readiness chain: `6b37e37` → `45dbd3e` → `c90d052` → `8ef097a`
- Model revision: `ab00687315bc1298e9d54e9c4b611dde9867ccc2`
- QAIRT/QNN build: `v2.49.40.260810104044`
- Integrated Android stage: `.local/qnn-prefill/integrated-phone-stage/`
- Stage metadata SHA-256: `dbb9d687b34d4476086f59e746907dfb8bef32c5fcf36a0b83331d9b0b02a60f`
- Stage manifest SHA-256: `8fa2c53c79c1ad994ea269266da14fb70c9cf03913d36753220d1379b6e79616`
- Payload: 12 files / 3,400,505,468 bytes
- Android runner SHA-256: `94e76c339107cc3bfae2fb9b296cbcdb76f1970f7aeb8a734bb564029fd6fdb1`
- AR171 context SHA-256: `d5ca624cc71a173c7de969fac777e2ce136db3b502e04c2991651b510dabba5a`
- AR1 context SHA-256: `76ba15e7fd95e5e13e92be0e88e8e6bbd3123f2b993b6986c9dac8800a9bf212`
- Canonical-short token file SHA-256: `eae8e828110f634d5c9954df0372e869f67f67aed846f9f544781faa1d4d29bc`

## Before ADB

- [ ] Pi explicitly assigns the phone slot; no other session owns it.
- [ ] Acquire `artifacts/locks/phone.lock` and hold it through staging, run, evidence pull, cleanup verification, and release.
- [ ] Require serial `R5CW81PR8SY`, Samsung `SM-S918B`, SoC `SM8550`, ABI `arm64-v8a`, completed boot, green verified boot, and locked flash.
- [ ] Require more than 5 GiB free under `/data/local/tmp`.
- [ ] Run local ELF preflight and verify all 12 manifest hashes.
- [ ] Confirm no output path from the new run already exists; the runner uses `O_EXCL` and must not overwrite evidence.

## Position-value and ABI gate

The integrated runner uses direct QNN and must copy native values matching graph descriptors:

- [ ] AR171 `position_ids`: `QNN_DATATYPE_INT_64`, shape `[1,171]`, 1,368 bytes, exact numeric values `0..170`.
- [ ] AR1 `position_ids`: `QNN_DATATYPE_INT_64`, shape `[1,1]`, 8 bytes, then values `171..185` as decode advances.
- [ ] AR171 mask: shape `[1,1,171,4096]`, causal inside the chunk, matching SHA-256 `c96a2d766fadfa77ad687286b727de2e1c554f63a81a704c8a03d6af44465892` before QNN copying.
- [ ] CPU-dequantized 171-row embedding bytes match SHA-256 `ac9fda5637e751b764d4c06f22ab58b1f9e48f9b94541a80cd33a68c4e3df7ed` before QNN copying.
- [ ] Do **not** substitute qnn-net-run raw-file conventions. The old INT32 files were interpreted as FLOAT32 and converted all positions to zero.

## Exact bounded command

After staging under a unique scoped remote root and verifying all remote hashes exactly once:

```sh
./direct_lfm2_qnn_runner "$REMOTE" --integrated "$REMOTE/short.int32le" 16 "$REMOTE/output.int32le"
```

`MAX_NEW=16` means **16 total emitted tokens including the AR171 endpoint**, so at most 15 AR1 graph calls occur. Stop early on EOS `124900`.

## Required lifecycle and evidence

- [ ] Open the raw output exclusively before backend setup.
- [ ] Load AR171 once; construct all 171 embeddings inside the measured request boundary.
- [ ] Request and finite-scan all 38 state and 22 logit outputs before copying.
- [ ] Append and `fsync` the endpoint token immediately.
- [ ] Attempt phase-labelled detailed-profile extraction. If unavailable, retain `optional_telemetry_missing`; do not discard valid output.
- [ ] Free AR171, reset the profile, bridge all 38 states in memory, and load AR1 once.
- [ ] On every AR1 call request and finite-scan all 60 outputs, carry all 38 states in process, append and `fsync` each token immediately, and never reload the context per token.
- [ ] Preserve stdout/stderr, raw token file (including partial output on failure), provider/build ID, hash checks, memory samples, battery/thermal snapshots, and process status before validation or decoding.
- [ ] Remove only the scoped remote root, verify it absent, verify no runner remains, then release `phone.lock`.
- [ ] Report the exact outcome before any retry or follow-on run.

## Timing interpretation

- `process_backend_setup_seconds`: backend/device setup outside the logical request.
- `request_to_first_emitted_token_seconds`: actual request start through endpoint write **and fsync**; excludes later profile work.
- `prefill_compute_phase_sum_seconds`: separately summed context load + CPU prompt preparation + AR171 run/finite-copy + argmax; not delivery time.
- `request_to_final_emitted_token_seconds`: includes the intervening prefill profile dump, AR171 free, profile reset, AR1 load, AR1 calls, and token fsyncs; excludes trailing AR1 profile/free.
- `diagnostic_total_with_profile_and_free_seconds`: includes all profile/free overhead.
- Tokenization is precomputed and excluded from every timing.

## Comparison and claim boundary

Expected CPU reference for the corrected-position route, total cap 16:

```text
[597, 4695, 10966, 622, 310, 1561, 267, 37139,
 9527, 8771, 836, 1703, 2165, 39246, 17354, 342]
```

Compare and retain every mismatch. A pass requires physical direct-QNN HTP execution, bounded finite-scanned output, valid token IDs, coherent partial text, one explicit phase transition, and cleanup. It does **not** require reference equality after the first token and cannot erase the known severe state drift.

Do not claim numerical equivalence, combined/shared-context viability, simultaneous residency, HTP-only execution (CPU embedding/orchestration/argmax/bridge are explicit), complete-answer quality, canonical statistical performance, a campaign, or a registry result.
