# Worker handoff: Android thread sweep

## Completion

- Campaign `20260813T150053Z-e6053419a29b` is complete: **9/9 configurations succeeded**.
- **36/36 WAVs** and **9/9 telemetry files** passed independent retained-artifact validation.
- Best observed warm-median RTF thread counts were Pocket `2`, Kokoro `4`, and Supertonic 3 `2`. These are observations, not tuning recommendations.
- Machine report: `results/measured-thread-sweep.json`
- Human report: `results/measured-thread-sweep.md`
- Campaign receipt: `results/campaign-receipt.json`

## Required interpretation

**Differences below 5–10% are inconclusive.** Even changes at or above 10% are directional here: there is only one rotated campaign, and the gate changed after sequence 6. Sequences 1–6 required Android thermal status NONE. Following Moritz's explicit authorization, sequences 7–9 accepted NONE and LIGHT, waited only at MODERATE or higher, and had no fixed passive sleeps.

The interrupted sequence-7 attempt never began synthesis. Its raw pre-state and empty allocated run directory are preserved in the receipt. Resume verification hash-checked the ledger, all six completed runs (24 WAVs and six telemetry streams), the installed APK, 401 staged files, and nine descriptors before executing only sequences 7–9 in the registered order under the public phone lock. No phone setting was changed.

## Revalidation

```bash
python3 experiments/0009-android-tts-optimization/thread-sweep/tools/generate_descriptors.py --check
python3 -m unittest discover -s experiments/0009-android-tts-optimization/thread-sweep/tests -p 'test_*.py' -v
python3 experiments/0009-android-tts-optimization/thread-sweep/tools/build_report.py --check
```

Raw artifacts remain ignored under `artifacts/0009/thread-sweep/campaigns/20260813T150053Z-e6053419a29b` and are hash-addressed by the receipt/report. No commit or push was made.
