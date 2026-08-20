# Experiment 0020 — historical Android benchmark refresh

This experiment audits the visible full end-to-end registry without editing frozen historical result records. It is the owner of any future exact rerun evidence and curated media.

## Current status

The exact Supertonic 3 INT8 ONNX/sherpa CPU route has now been rerun on the authorized S23 Ultra. Moritz explicitly accepted the exact representative legacy-v1 WAV SHA-256 `1cf003d5…ee6e` on 2026-08-20 with verdict “good”; that verdict applies only to this route/sample hash. Earlier zero-device observations are preserved as timestamped evidence of the wrong native-Linux ADB transport; the successful run used the exact Windows `adb.exe` through the scoped audited shim. Android 16 rejected two shell/app-external staging approaches, so the final 0020-only APK changed only the verified input root to app-internal `getFilesDir()` while leaving benchmark/runtime/timing/output behavior unchanged. Frozen experiment 0008 remains untouched.

The complete audit is [`results/registry-audit.json`](results/registry-audit.json). It covers every `scope: full_e2e` registry row, records missing fields, and keeps old values beside exact refresh values. The canonical result is [`results/supertonic-3-int8-cpu-refresh.json`](results/supertonic-3-int8-cpu-refresh.json): old warm median RTF `0.370303`, new `0.393086` (`+6.15%`, inside the 10% RTF margin); old cold RTF `0.385468`, new `0.415874` (`+7.89%`). Setup changed from `0.7651` to `1.0033` seconds (`+31.13%`) and is explicitly flagged beyond the margin. Audio duration/protocol/provider/thread count matched. The refresh deliberately reproduced frozen 0008's legacy-v1 transcript (`350c8d3d…`) and one-first-plus-three-warm contract. Canonical v2 (`424b3807…`, 226-byte comma transcript) superseded v1 after this completed run. The refresh therefore does **not** satisfy the current v2/five-warm contract and must remain labeled as a legacy-v1 historical old/new comparison.

## Evidence rules

- Frozen experiment result files are read-only inputs; this experiment never rewrites them.
- A rerun must pin the exact archive/file hashes, runtime/build, transcript, voice/SID, seed/settings, device, thread count, timing boundary, and memory semantics before comparison.
- New output is copied only after independent SHA-256, WAV-header, PCM16, channel, rate, duration, finite/non-silent/clipped checks.
- New audio starts `not_reviewed` in the dashboard until Moritz explicitly reviews that exact sample.
- Old and new values remain side-by-side. A relative RTF change over 10%, or any material protocol/output-duration difference, is flagged beyond the sensible comparison margin rather than silently replacing history.
- The rerun uses `artifacts/locks/phone.lock`, the exact S23 Ultra identity gate, closed lock FDs in ADB children, unique staging, cleanup verification, and lock release. It serializes with active phone work and stops for any new terms, gates, licenses, consents, or attestations.

## Files

- [`protocol/refresh-policy.json`](protocol/refresh-policy.json) — frozen refresh contract and comparison rules.
- [`results/device-readiness.json`](results/device-readiness.json) — exact blocked readiness evidence.
- [`results/rerun-supertonic-3-int8.json`](results/rerun-supertonic-3-int8.json) — preserved initial blocked attempt.
- [`results/supertonic-bootstrap-attempt.json`](results/supertonic-bootstrap-attempt.json) — preserved app-external staging blocker.
- [`results/supertonic-3-int8-cpu-refresh.json`](results/supertonic-3-int8-cpu-refresh.json) — canonical completed old/new comparison, provenance, structural audio, and cleanup.
- [`results/registry-audit.json`](results/registry-audit.json) — all visible full-E2E rows and missing-field audit.
- [`tools/audit_registry.py`](tools/audit_registry.py) — deterministic audit generator.

Run the audit from the repository root:

```bash
python3 experiments/0020-historic-android-benchmark-refresh/tools/audit_registry.py
```
