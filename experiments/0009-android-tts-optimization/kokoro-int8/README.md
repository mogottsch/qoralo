# Exact Kokoro v1.0 mixed-INT8 host quality package

**Gate status: `passed_user_listening` for relative INT8-vs-FP32 degradation.** Automated host checks passed, and Moritz finalized all six blind votes: four ties, one INT8 preference, and one FP32 preference. Both directional votes had confidence 2/5. The ballot detected no systematic INT8 degradation, so the candidate may proceed to a later Android benchmark. The retained machine status does not claim perceptual equivalence, INT8 superiority, or absolute usability/quality acceptance for either variant.

This subtree is deliberately host-only. It contains no phone benchmark, Android RTF/PSS result, proprietary accelerator flow, or change to experiment 0008's measured decision.

## Selected candidate

| Item | Value |
|---|---|
| Source | exact `kokoro-multi-lang-v1_0` already pinned and extracted by experiment 0008 |
| Voice | SID 3, proven as `af_heart` by pinned v1.0 metadata |
| Source model | 325,630,829 bytes, SHA-256 `c436dc6a842b62aba06af67e40bafcfb9c60ac3af895358f1974ad9a7f7c026b` |
| Method | ONNX Runtime 1.22.1 static PTQ, QDQ, symmetric S8 activations and S8 weights, per-channel weights, MinMax calibration |
| Quantized scope | eligible Conv/MatMul/Gemm outside `/decoder/generator/` |
| Effective boundary | 163 eligible nodes have weight QDQ; 102 eligible generator nodes retain their original FLOAT weight inputs |
| Candidate | 175,678,702 bytes, SHA-256 `c37d76d0ada7414d18841ed454e8c7f00c8b1f631e97e1fd019c3ba01a0fbd92` |
| Size change | 149,952,127 bytes smaller (46.05%) |
| Host compatibility | CPU session construction and inference passed; sherpa-onnx 1.13.5 CPU synthesis passed |
| Structural limitation | The exact source passes ONNX checker 1.18.0; the quantized graph does not, because the quantizer moves an outer-scope `SplitToSequence` producer after its consuming `Loop` |

This is mixed precision, not a claim that every model weight or operator is INT8. Excluded generator operators and weights remain FP32, but they can consume activations affected by upstream quantization. `reports/quantization-report.json` contains the effective graph audit. `reports/reproduction-rebuild.json` and the retained rebuild model independently match the selected candidate bit-for-bit.

The checker diagnostic is not hidden or attributed to the source: `reports/checker-limitation.json` proves the source passes and the candidate fails structural checking. Both pinned host runtimes nevertheless construct sessions and synthesize structurally valid audio. This package therefore treats executable CPU inference as the host compatibility gate and carries the checker result as a deployment limitation. Any later deployment must reassess deterministic structural normalization rather than assuming the diagnostic is harmless on a new runtime.

## Why this recipe

`reports/candidate-selection.json` retains all candidate choices:

- Default dynamic QInt8 produced a 114,705,762-byte model but ONNX Runtime CPU could not implement its `ConvInteger(10)` node. It is rejected and retained.
- Static S8S8 QDQ over every eligible Conv/MatMul/Gemm produced a 126,457,536-byte CPU-loadable model. All six matched pairs exceeded the documented 0.20 spectral-centroid relative-difference screen (about 0.41–0.63 in the retained canonical run), so it was not sent to listening. This is an automated screening result, not a subjective quality claim.
- A MatMul/Gemm-only candidate passed the supporting screen but reduced size by only about 11%.
- Excluding eligible waveform-generator nodes retained a 46.05% reduction and passed all six integrity and supporting acoustic screens, so this is the candidate in the blind package.

The model contains unseeded random operators. The ONNX candidate is deterministically reproducible, but synthesis WAVs are not expected to be bit-identical across reruns. Every retained WAV is therefore hash-addressed, and a full rerun creates a new internally matched evidence set and blind-package hash. Raw sample MSE is neither computed nor used.

## Current evidence

- Six FP32/INT8 pairs used the same sherpa-onnx frontend, exact source assets, corpus order, SID 3, speed 1.0, CPU provider, and one host thread. Each corpus entry was passed whole; no text splitting was used.
- All 12 WAVs are structurally valid: they fully decode as 24 kHz mono PCM16, are finite and non-silent, and have no PCM clipping. This does not by itself establish usable speech.
- All six pairs passed the documented duration, voiced-fraction, pitch, spectral-centroid, and normalized band-power supporting screens.
- Pinned Whisper small produced corpus WER 0.031 for FP32 and 0.031 for INT8; normalized hypothesis-to-hypothesis WER was 0.000. ASR is only an intelligibility signal.
- No calibrated, voice-specific speaker verifier was available. No uncalibrated speaker-similarity number was invented.
- Laptop load/generation timings are retained only as context, not as a controlled performance benchmark.

Canonical reports live in `reports/`. Ignored models, WAVs, logs, the blind ZIP, answer key, and interrupted-worker historical files are all listed by path, byte count, role, and SHA-256 in `package-manifest.json`. Historical `generated/trial-*` reports are retained for provenance but are not used as canonical evidence; interrupted runs referenced FP32 WAVs later replaced by the final run. Canonical screening chains under `reports/screening-*` and `generated/screening/` supersede them.

## Verify the current package

From the repository root:

```bash
ROOT=experiments/0009-android-tts-optimization/kokoro-int8
SOURCE=experiments/0008-sherpa-onnx-android-tts-benchmark/artifacts/extracted/kokoro/kokoro-multi-lang-v1_0

"$ROOT/.venv/bin/python" "$ROOT/scripts/verify_package.py" \
  --source-root "$SOURCE" --runtime-smoke --require-manifest
"$ROOT/.venv/bin/python" -m pytest -q "$ROOT/tests"
```

The strict verifier checks the experiment 0008 archive and all 377 deployed source files, the exact wheelhouse and installed versions, candidate and rebuild hashes, effective QDQ boundary, all final WAV pins and recomputed metrics, blind ZIP CRC/metadata/payload assignments, failure retention (including the candidate-only checker diagnostic), and the finalized user-ballot status. Its runtime smoke uses only the host CPU.

## Rebuild from exact inputs

The build/runtime wheel lock targets Linux x86_64 and CPython 3.11.13. The wheelhouse is ignored, but every filename, URL, size, and SHA-256 is in `toolchain.lock.json` and `requirements.lock`.

```bash
cd experiments/0009-android-tts-optimization/kokoro-int8
python scripts/fetch_tools.py
uv python install 3.11.13
uv venv --python 3.11.13 .venv
.venv/bin/python -m pip install --require-hashes --no-index \
  --find-links=.cache/wheels -r requirements.lock

SOURCE_ROOT="$PWD/../../../experiments/0008-sherpa-onnx-android-tts-benchmark/artifacts/extracted/kokoro/kokoro-multi-lang-v1_0" \
  bash scripts/reproduce_host_gate.sh
```

The first command downloads only the hash-locked Python wheels, not another Kokoro checkpoint. `quantize.py` refuses a source directory with the wrong root name, any symlink, a missing/unexpected file, or any size/hash mismatch against experiment 0008's pinned 377-file deployed inventory.

The supporting ASR rerun uses the separately pinned local `/usr/bin/python3.14` environment and Whisper checkpoint recorded in `toolchain.lock.json`; it fails closed if executable, package RECORD, ffmpeg, or checkpoint hashes drift. This environment is retained as a limitation rather than silently re-created from an unpinned dependency solve.

## Final blind-listening result

The exact downloaded ballot is retained at `reports/user-listening-ballot.csv`; its validated reveal and interpretation are in `reports/user-listening-verdict.json`.

- Ties: 4/6
- INT8 preferred: 1/6, confidence 2/5
- FP32 preferred: 1/6, confidence 2/5

The relative degradation gate passes because the finalized ballot found no systematic INT8 degradation. It did not ask whether either exact variant was usable in absolute terms. Android deployment and device RTF/PSS remain unmeasured and are the next candidate-specific step.
