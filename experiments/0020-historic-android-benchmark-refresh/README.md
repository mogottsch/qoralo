# Experiment 0020 — historical Android benchmark refresh

This experiment audits the visible full end-to-end registry without editing frozen historical result records. It is the owner of any future exact rerun evidence and curated media.

## Current status

The first authorized refresh attempt is **blocked before rerun**: the repository-safe readiness gate observed zero Android devices (`expected exactly one device, observed 0`). No model archive was downloaded, no APK was staged, no lock-protected phone execution occurred, and no historical result was replaced.

The complete audit is [`results/registry-audit.json`](results/registry-audit.json). It covers every `scope: full_e2e` registry row, records missing WAV/metrics/provenance fields, and keeps old values separate from any future refresh values. The Supertonic 3 INT8 ONNX/sherpa route is the first rerun priority but has no new value yet.

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
- [`results/rerun-supertonic-3-int8.json`](results/rerun-supertonic-3-int8.json) — priority route attempt, blocked before phone execution.
- [`results/registry-audit.json`](results/registry-audit.json) — all visible full-E2E rows and missing-field audit.
- [`tools/audit_registry.py`](tools/audit_registry.py) — deterministic audit generator.

Run the audit from the repository root:

```bash
python3 experiments/0020-historic-android-benchmark-refresh/tools/audit_registry.py
```
