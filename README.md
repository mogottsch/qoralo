# Local podcast-style TTS for Android

This repository investigates local text-to-speech for a future NotebookLM-like listening experience on Android: someone explaining source material in a pleasant, natural, engaging voice, ideally with podcast-like delivery.

A convincing two-speaker conversation would be useful, but it is not required for the first result. A strong single narrator or persistent voices generated turn by turn can also work, as long as the speech stays natural over longer material and runs well on a modern phone.

The repository covers selection, deployment, and measurement of the TTS layer. It does not contain the surrounding source ingestion, retrieval, script generation, application UI, or episode-management product.

## Repository structure

- [`HANDOFF.md`](HANDOFF.md): current cross-device resume state, active experiment boundaries, and exact next steps.
- [`docs/history.md`](docs/history.md) and its [HTML mirror](docs/history.html): completed experiments, results, and decisions carried forward.
- [`docs/plan.md`](docs/plan.md) and its [HTML mirror](docs/plan.html): the current goal and unfinished phases.
- [`docs/devices/`](docs/devices/): target-device baselines and constraints.
- [`docs/architectures/index.html`](docs/architectures/index.html): preserved interactive architecture reference for the compared TTS families.
- [`experiments/`](experiments/): numbered, reproducible investigations and their canonical evidence.
- [`scripts/`](scripts/): shared inventory, validation, reporting, and benchmark helpers.
- `artifacts/` and experiment-local `.local/` or `work/` directories: ignored storage for models, generated audio, builds, profiles, logs, and other large or restricted material.

The human-facing results dashboard is published at <https://preview.moket-home.de/vibevoice-android/>.

## Way of working

### Experiments record the past; phases describe the future

Numbered experiment directories preserve what was actually attempted and measured. Their results remain historical evidence even when the preferred model or technical direction changes. Future work is described as gated phases in the plan rather than as if its outcome were already known.

Every phase links to the experiment that owns its detailed evidence. When a phase finishes, the experiment keeps the full record, the condensed outcome moves to the history, and the completed phase leaves the current plan.

### Evidence before claims

Each result records the model and source revisions, runtime and tool versions, inputs, configuration, device identity, timings, memory, output hashes, limitations, and deviations. We keep host tests, emulators, physical-phone controls, component runs, and complete Android synthesis separate.

We do not present a component result as an end-to-end result, or successful execution as a speedup without an equivalent baseline. Audio that sounds plausible does not override a failed numerical or reproducibility gate.

### Small gated steps

Work starts with the smallest test that can answer the next uncertainty. A phase proceeds only when its entry conditions are met and its evidence justifies the additional complexity. Negative and blocked results are retained when they are reproducible.

For accelerator work, CPU fallback is disabled whenever full delegation is part of the claim. Thresholds are frozen before inspecting the corresponding accelerated output.

### Reproducible source, local artifacts

Scripts, manifests, schemas, hashes, bounded measurements, and conclusions belong in Git. Model weights, generated audio, converted models, SDK binaries, APKs, tensors, raw profiles, and large build trees remain ignored and local.

Proprietary terms, account logins, export attestations, paid services, privileged changes, and personal-device access require explicit human approval.

### Two records, two views

[`docs/history.md`](docs/history.md) is the source for completed work. [`docs/plan.md`](docs/plan.md) is the source for unfinished work. Detailed experiment plans remain with their experiments. Adjacent HTML files provide human-readable views.

Regenerate the mirrors with:

```bash
python3 scripts/build_docs_html.py
```

Keep both documents concise. Detailed commands, measurements, failures, and resume instructions belong in the relevant experiment rather than being repeated in the history, plan, or README.
