# Plan — MOSS-TTS-Nano fail-closed QNN/HTP attempt

## Scope

Determine whether the complete official MOSS-TTS-Nano neural pipeline can execute through QNN/HTP without CPU fallback on the authorized S23 Ultra. Preserve exact official model assets and derivative provenance. Use canonical-v2 benchmark text for final comparable work. Never call mixed fallback full HTP.

## Procedure

1. Hash-lock the official source, ONNX files, external weights, voice, sampling settings, and canonical-v2 direct SentencePiece output.
2. Host-gate prefill, autoregressive decode, local fixed-frame sampling, and full codec decode with CPU fallback disabled.
3. Apply only provenance-locked rewrites, with frozen CPU equivalence before QNN or phone use.
4. Replace the dynamic KV ABI with a single reusable 600-position decode input and 601-position output/state contract. Prove the first, middle, penultimate, final, all-375-call, and final-state boundaries.
5. Generate/reload QNN contexts serially after CPU equivalence and preserve resource evidence.
6. On phone, require exact identity/lock/hash/thermal/cleanup gates and fail closed during all four session creations. Only after complete assignment may inference begin.
7. For a successful route, run one unprofiled first generation plus at least five same-session warm generations with full state reset, then a separate profile process. Require QNN-only provider events and physical RPC/accelerator/cycle/HVX proof before claiming full HTP.
8. If the platform blocks before assignment, retain null benchmark/listening fields with exact reasons rather than fabricating or substituting a mixed route.

## Outcome

The final attention-insertion fixed-capacity graph passed canonical-v2 recursive CPU equivalence for all 375 calls and the final 601-position state. Fixed-capacity codec equivalence passed at both the observed 161-frame stop and full 375-frame capacity. All four graphs compiled into host QNN contexts, and every context reloaded as one fail-closed QNN partition.

Physical execution remained blocked. Under the exact carrier/app UID on the authorized Samsung, QNN loads its HTP backend interface but fails `CreateDevice` with `QNN_DEVICE_ERROR_INVALID_CONFIG` before the first session assignment. The result persists with:

- public `libcdsprpc.so` declared and exposed;
- exact Package-Manager-labeled runner/ORT/QNN native hashes;
- a unique hash-verified V73 DSP skel and standard vendor RFSA paths;
- source ONNX and EPContext modes;
- runtime SoC auto-detection;
- no burst or other optional device configuration;
- CPU fallback disabled.

Experiment 0019 therefore stops without inference, WAV, RTF, physical HTP proof, or listening verdict. The conclusion is bounded to this recorded app-UID carrier/device/runtime path.
