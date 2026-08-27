# Android runner sharding-boundary fix

The first physical attempt loaded all four QNN/HTP contexts but ExecuTorch rejected the method because the runner lacked three registrations for `llama::fallback.out`.

The revised runner now links ExecuTorch v1.2.0's existing Qualcomm Llama `custom_ops` target. Its archive is passed under `--whole-archive`, ensuring the load-time registration constructor is retained even though no ordinary symbol references it. The stripped Android arm64 binary contains the exact `llama::fallback.out` registration string. The pinned implementation only resizes/verifies the output and copies the input bytes; it is an identity boundary between QNN shards, not arithmetic model computation.

The revised local-only runner is 3,446,144 bytes with SHA-256 `0b5bef7984738d60d2f4b2f4dbae1c13f1f5914b75b8cc00e5ae3e2ed0f81fc5`. The guarded phone script now rejects any runner with a different hash.

## Claim boundary

This is host cross-build/link evidence only. No ADB or phone access occurred during this fix. The revised runner has not run on Android, does not retroactively change attempt 01, and provides no new physical inference, output, sanity, or performance evidence. A new explicit Pi phone-priority handoff is required before one bounded retry.
