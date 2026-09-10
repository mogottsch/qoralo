# Controlled QDQ position-1 reference validation

**Exactly one QDQ call completed on the reviewed input pack. No paired QNN call has run.**

The accepted `30799090…c492364` PT2 consumed position **1**, token **8678**, and the 51-tensor QDQ-origin input pack with header SHA-256 `ec381857…43cd392` and logical values digest `4251bbce…c78e4`. The input-mutation check was false. All **73 returned tensors** were finite.

## Output observation

The new logit tensor is **bit-identical to the historical position-1 QDQ logits**:

- argmax **198**;
- maximum absolute error **0**;
- mean absolute error **0**.

The original float32 cosine calculation reported **1.000003695487976**. This is reduction-rounding overshoot on identical nonzero vectors, not above-perfect similarity. It is retained unchanged in the raw result; exact tensor equality and zero absolute error are the decisive observations.

This creates a real QDQ reference evaluated on the known input pack. It does **not** directly prove that unretained full-replay state bytes were identical, and it does not establish QNN same-state fidelity or causal attribution before a paired QNN control is executed.

## Exact reference handoff

The later QNN driver must consume this reviewed result, not a historical-only substitute:

- raw result path: `.local/diagnosis/controlled-p1-qdq-call-20260910T120717Z/run/control/result.json`;
- raw result SHA-256: `7137d83a3c89a73121ad5bd2514c865b7cec97fe8b5c2d117be25fe165f43519`;
- raw 73-output bundle SHA-256: `b5aa794276833f2285935889b4723b57b1c50ce114e2c1b33c429c4632f54cfb`.

The raw result itself is copied byte-for-byte under `raw/result.json`. Complete outputs, historical comparison tensor and telemetry are retained losslessly with raw/compressed sizes and hashes in `compression-manifest.json`; all three recoveries were independently checked. `verification.json` records saved-tensor checks only, with no new model load.

## Runtime and cleanup

Worker wall time was **143.392 s**, supervisor wall time **146.954 s**, below the authorized **600 s** limit. These include preflight hashing, model load and persistence; they are host diagnostic times, not Android or campaign timings.

The independent low-priority/four-thread guard used owned ext4 scratch. Worker 1724347 was reaped, its process group was absent, and scratch was empty. The raw pack, outputs, original vectors and protected reference artifacts remain unchanged. No retry, QNN follow-on, own-state resume, 174-token replay, autoregressive text or phone operation occurred.

## Next gate

Review the new result/hash before releasing **one separately budgeted QNN position-1 call** on the same pack, using `--qdq-control-result` and `--qdq-control-sha256`. No follow-on is authorized by this result. Physical baseline `23ac8abd…d2c506` remains unchanged; there is no physical, accuracy, generated-text, full-fidelity or campaign claim.
