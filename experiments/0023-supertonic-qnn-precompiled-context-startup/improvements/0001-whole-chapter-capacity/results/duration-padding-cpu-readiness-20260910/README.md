# Exact CPU duration padding pair — preparation, not a result

Pi conditionally authorized one CPU session/two forwards after Nik's exact review. This readiness binds the existing **official dynamic FP32 duration model** SHA `c3eb91414d5ff8a7a239b7fe9e34e7e2bf8a8140d8375ffb14718b1c639325db`. Prior accepted materialization proves its1086 computation nodes/98 initializers identical to phone-source T2048 derivative `394ea3e7…8cbad9`; the fixed2048 model cannot accept the1333 case, so it is not substituted or rewritten here.

## One controlled contrast

One explicitly CPU-only ORT1.23.2 session, automatic provider fallback disabled at constructor entry, graph optimizations ALL/profiling disabled, two calls in order:

1. `text_ids INT64[1,1333]`, `text_mask FLOAT[1,1,1333]`, `style_dp FLOAT[1,8,16]`.
2. Same active prefix/style, with715 extra zero IDs and zero mask entries: shapes `[1,2048]`/`[1,1,2048]`.

Shared input NPZ25,856B SHA `0a3a471421089cf4846e2097fd8a7a44df319b59a81d02db454e7be410bfb0da` remains LOCAL-ONLY, including original M1 style data. `input-binding.json` ties it to committed `adef443` exact raw/normalized/reconstruction receipts, accepted voice/indexer hashes and128FLOAT32 DP values at voice offset51248. Preparation independently regenerates IDs/mask and verifies equality with the saved source-bound reconstruction. **Those are not native-buffer captures.** No model was loaded or run in preparation.

The dynamic model file remains byte-identical. No other model, QNN, phone, graph change, installation or network operation. Existing NumPy1.26.4/CPU ORT1.23.2/Python and selected library/Python-source files are pinned (20 files); this is not an exhaustive OS dependency inventory. The CPU paired contrast is distinct from comparing either output to phone ORT1.27.1/QNN.

## Exact execution boundary

Request: `protocol/duration-padding-cpu.request.NOT_APPROVED.json`

```text
78fc97c0da96b99adcd1e1c37c2b1b6dd65ef7f0ccf4ba46f2f644ac417f9031
```

Worker `083db19f…a2f6ed0c`, launcher `0d05f0bb…07b73f9`, frozen host supervisor `33373e74…3705d`. Fresh owned phase/data/disk scratch. Four-CPU affinity0–3, ORT intra4/inter1 and math threads4. **4GiB RLIMIT_AS;100s worker +20s termination grace ≤120s**, STOP/resource-pressure supervision and group reap. The runtime verifies its actual affinity/limit and selected package/version. No automatic fallback, extra case or retry. Both raw returned arrays are retained before output classification; setup/call times, original dtype/bits, input raw hashes, source/input/runtime postpins and cleanup are recorded. Actual release/phase are absent at readiness.

Five synthetic/fake-runtime tests pass in0.012s; PID2019813 reaped/group absent and scratch empty. Tests created zero real model sessions and imported no ORT runtime. `plan.json` is plan-only with no subprocess/runtime call.

## Interpretation boundary

Measured WAV:1,314,042frames /44100 =29.7968707483s, exact audio duration, versus an unforced~90s prose target. Native DP scalar was **not** captured. Pinned CPP computes `floor(float32(duration)*44100)`, so `[frames/44100,(frames+1)/44100)` is only an ideal real-arithmetic comparison, not an exact scalar bound. Reference outputs retain the analogous FP32 multiply/floor frame conversion.

Two CPU outputs can measure this padding contrast and show whether the FP32 model itself predicts a similarly short duration. They cannot prove a QNN-only cause, recover the failed/phone native buffers, establish spoken coverage, or approve fidelity/listening. Jere owns separate ASR coverage work; no duplicate ASR or whole-TTS rerun belongs here. All old contexts, WAVs, source graphs, failed runs and private originals remain protected. No push.
