# Android benchmark registry

This directory is the durable cross-experiment index for Android model and deployment routes. It is deliberately separate from the detailed experiment records: the experiment remains the source of truth, while this registry makes the comparable Android evidence discoverable in one place.

- [`index.html`](index.html) (also [`dashboard.html`](dashboard.html)) — static dashboard for browsing routes and verified audio.
- [`registry.json`](registry.json) — normalized machine-readable registry.
- [`schema.json`](schema.json) — JSON Schema for the registry contract.
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

The registry includes deferred and blocked routes as well as successful phone runs. A route with `android_attempted: false` has `device: null`; a route stopped before session creation has null measurements. Null never means zero and never licenses a host-only inference. The detailed reason for each intentionally unavailable field is in `missing-fields.md`.

## Metric boundaries

`warm_median_rtf` is the owning result's synthesis wall time divided by generated audio duration. It is not a quality score. `peak_pss_bytes` and `peak_vm_hwm_bytes` retain the source semantics; in particular, VmHWM/ru_maxrss is a cumulative process high-water mark, not isolated model memory. Component probes, fixed-transcript diagnostics, and full text-to-WAV runs are separate routes and are not silently merged.

The canonical device is Samsung Galaxy S23 Ultra `SM-S918B`, Snapdragon `SM8550`, `arm64-v8a`, serial `R5CW81PR8SY`. The registry records only committed evidence paths; ignored raw benchmark files may be referenced by their owning result but are not copied here unless the local WAV is available and independently verified.
