# Offline-first mobile podcast inference on Android

This repository builds and validates the local inference components needed for an offline-first, NotebookLM-like listening experience on Android.

The technical scope has two component layers:

1. **Local language-model inference** — run candidate LLMs on a modern phone and measure model setup, prompt processing, token generation, memory, and operational behavior. Transcript generation is the eventual use, but the first comparable experiments are performance and execution benchmarks rather than script-quality evaluations.
2. **Local text-to-speech** — select, deploy, and measure speech models that can render long-form material naturally and practically on a phone.

A convincing two-speaker result is useful but not required. A strong single narrator or persistent voices generated turn by turn can also work. Source acquisition, retrieval infrastructure, application UI, script editing, episode assembly, export, and episode management are outside this repository's current component-inference scope.

Historical TTS experiments remain unchanged. New LLM experiments use the same numbered, evidence-first workflow without reusing TTS-specific transcript, WAV, RTF, or listening fields.

## Repository structure

- [`docs/history.md`](docs/history.md) and its [HTML mirror](docs/history.html): completed experiments, results, and decisions carried forward.
- [`docs/plan.md`](docs/plan.md) and its [HTML mirror](docs/plan.html): the current goal and unfinished work.
- [`docs/wiki/`](docs/wiki/): repository-backed explanatory wiki; open this directory as its own Obsidian vault if desired.
- [`docs/devices/`](docs/devices/): target-device baselines and constraints.
- [`docs/architectures/index.html`](docs/architectures/index.html): preserved interactive architecture reference for the compared TTS families.
- [`docs/android-benchmarks/`](docs/android-benchmarks/): normalized Android TTS registry and dashboard.
- [`docs/android-llm-benchmarks/`](docs/android-llm-benchmarks/): separate normalized Android LLM registry and dashboard.
- [`protocols/android-tts-benchmark/`](protocols/android-tts-benchmark/) and [`protocols/android-llm-benchmark/`](protocols/android-llm-benchmark/): component-specific comparable benchmark contracts.
- [`experiments/`](experiments/): numbered, reproducible investigations and their canonical evidence.
- [`scripts/`](scripts/): shared inventory, validation, reporting, and benchmark helpers.
- `artifacts/` and experiment-local `.local/` or `work/` directories: ignored storage for models, generated media, builds, profiles, logs, and other large or restricted material.

The published TTS results dashboard is at <https://preview.moket-home.de/vibevoice-android/>. The LLM dashboard starts empty and will publish only committed normalized evidence.

## Way of working

### Experiments record the past; plans describe the future

Numbered experiment directories preserve what was actually attempted and measured. Their results remain historical evidence even when the preferred model or technical direction changes. Future work is described as gated work in the plan rather than as if its outcome were already known.

Every phase links to the experiment that owns its detailed evidence. When a phase finishes, the experiment keeps the full record, the condensed outcome moves to the history, and completed work leaves the current plan.

### Evidence before claims

Each result records exact model, artifact, tokenizer, runtime, input, configuration, device, timing, memory, output-hash, and limitation provenance as applicable. Host tests, physical-phone runs, component probes, and complete routes remain distinct.

For LLM work, successful execution, output sanity, measured performance, and later quality evaluation are separate claims. `looks_sensible` is only a superficial corruption/gibberish smoke check on one exact output hash; it is not correctness, grounding, quality, or acceptance.

For TTS work, technical execution, structural audio validity, objective comparison, and exact-hash listening review remain separate. Plausible output never overrides a failed numerical, reproducibility, or provider gate.

### Small gated steps

Work starts with the smallest test that can answer the next uncertainty. A phase proceeds only when its entry conditions are met and its evidence justifies additional complexity. Negative and blocked results are retained when reproducible.

For accelerator work, CPU fallback is disabled whenever full delegation is part of the claim. Thresholds are frozen before inspecting corresponding accelerated output.

### Reproducible source, local artifacts

Scripts, prompts, manifests, schemas, hashes, bounded measurements, raw text outputs, and conclusions belong in Git. Model weights, generated audio, converted models, SDK binaries, APKs, tensors, raw profiles, and large build trees remain ignored and local.

Proprietary terms, account logins, export attestations, paid services, privileged changes, and personal-device access require explicit human approval.

### Two records, multiple benchmark views

[`docs/history.md`](docs/history.md) is the source for completed work. [`docs/plan.md`](docs/plan.md) is the source for unfinished work. Detailed plans remain with their experiments. Adjacent HTML files provide human-readable views.

TTS and LLM metrics remain in separate registries because their performance and output-evidence contracts are not interchangeable. A future landing page may link TTS, LLM, and end-to-end integration views; that integration view would combine the two component layers rather than add a third charter layer.

Regenerate the plan and history mirrors with:

```bash
python3 scripts/build_docs_html.py
```

Keep shared documents concise. Detailed commands, measurements, failures, and resume instructions belong in the relevant experiment.
