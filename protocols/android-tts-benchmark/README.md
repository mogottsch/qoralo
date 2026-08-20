# Android TTS benchmark contract

This directory is the canonical input and minimum evidence contract for comparable full end-to-end Android TTS benchmarks in this repository.

## Canonical transcript

Use `transcript.txt` as exact bytes. Canonical transcript v2 is 226 bytes, has no trailing newline, and has SHA-256:

```text
424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67
```

It uses commas after “studio” and “meaning”; it contains no three-period or Unicode ellipsis pauses. Record the effective text and tokenizer output because a frontend may transform the input. Transcript v1 (`350c8d3d…13471f`) is retained only as legacy provenance and is not canonical v2. If a model cannot accept this contract, preserve that route as noncanonical and state the exact reason; never silently substitute another sentence.

## Comparable timing

Create sessions once, report setup separately, time one first complete generation, then time at least five additional warm generations in the same sessions. Reset all model-owned recurrent, cache, decoder, RNG/noise, and orchestration state before every generation. Confirm that each iteration emits the intended complete utterance.

Normalize every RTF by that iteration's actual emitted audio duration:

```text
RTF = end-to-end generation seconds / emitted audio seconds
```

The headline warm RTF is the median of the per-iteration warm RTF values. Preserve every raw latency, duration, and RTF. Never relabel a proof/profile run or a single post-setup run as warm.

See `contract.json` for the machine-readable minimum and the project skill at `.agents/skills/android-tts-benchmark/SKILL.md` for the full workflow.
