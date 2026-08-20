# Android benchmark registry

This directory is the durable cross-experiment index for Android model and deployment routes. It is deliberately separate from the detailed experiment records: the experiment remains the source of truth, while this registry makes the comparable Android evidence discoverable in one place.

- [`index.html`](index.html) (also [`dashboard.html`](dashboard.html)) — static dashboard for browsing routes and verified audio.
- [`registry.json`](registry.json) — normalized machine-readable registry, including the separate model release timeline.
- [`schema.json`](schema.json) — JSON Schema for the registry contract, including explicit `model_identity` source links/revisions, `quantization`, execution/audio evidence, and listening-review fields.
- [`missing-fields.md`](missing-fields.md) — generated unavailable-evidence report.
- [`media/`](media/) — only WAVs present in this checkout whose SHA-256 and WAV headers match their owning committed Android result.
- [`build_registry.py`](build_registry.py) — deterministic generator and media verifier.
- [`validate.py`](validate.py) — fail-closed structural, provenance, and media validation.

## Regenerate and validate

Run from the repository root:

```bash
python3 docs/android-benchmarks/build_registry.py
python3 docs/android-benchmarks/validate.py
```

The registry includes deferred and blocked routes as well as completed phone runs. Status describes execution only: `ran` means that the declared route completed and produced its recorded output. It is not an audio-quality verdict or user acceptance. Only Moritz's recorded listening decision can accept or reject perceived quality; numerical diagnostics stay in the evidence summary. Every row separates the display `model` label from `model_identity` (`name`, canonical source URL, and exact revision when committed) and `quantization`. `registry.json` remains exhaustive and marks component/probe/planning rows as `scope: excluded_non_e2e`; the dashboard table and audio presentation include only `scope: full_e2e` routes. The dashboard links the model label to that source URL without printing revision hashes in cells; archive-backed routes link their exact upstream archive, while HF-backed routes retain the pinned revision in metadata and link targets. A route with `android_attempted: false` has `device: null`; a route stopped before session creation has null measurements. Null never means zero and never licenses a host-only inference. The detailed reason for each intentionally unavailable field is in `missing-fields.md`.

## Metric boundaries

`warm_median_rtf` is populated only when the owning result records a warm distribution/median. `proof_run_rtf` retains a single bounded execution or profiled physical-proof run without relabeling it warm. `first_post_setup_rtf` retains a source explicitly labeled as one first complete generation after setup; it is not a warm median or distribution. Every RTF is synthesis wall time divided by generated audio duration and is not a quality score. The dashboard exposes all three as separate sortable columns. Its **Peak memory** column shows peak PSS when available and otherwise falls back to VmHWM/ru_maxrss, with the measurement type printed beneath the value. `peak_pss_bytes` and `peak_vm_hwm_bytes` retain the source semantics; in particular, VmHWM/ru_maxrss is a cumulative process high-water mark, not isolated model memory. Component probes, fixed-transcript diagnostics, and full text-to-WAV runs are separate routes and are not silently merged.

The dashboard separates technical execution, structural audio validity, objective/descriptive evidence, and `listening_review`. Listening is `not_reviewed` unless Moritz explicitly records an `accepted` or `rejected` verdict; comparative notes such as “sounds identical” never become acceptance. The sortable Listening column and **Needs review** section expose playable full-E2E samples awaiting review. The **Model release timeline** at the bottom of the dashboard is separate from benchmark performance. It records first public family/model release dates, not later quantized archives or Android package dates, with a date basis and authoritative source URL for each row. The canonical device is Samsung Galaxy S23 Ultra `SM-S918B`, Snapdragon `SM8550`, `arm64-v8a`, serial `R5CW81PR8SY`. The registry records only committed evidence paths; ignored raw benchmark files may be referenced by their owning result but are not copied here unless the local WAV is available and independently verified.
