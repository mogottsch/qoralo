# Worker handoff — task-14

## Status

**Package complete; quality gate: `awaiting_user_listening`.** Automated host checks passed. No subjective equivalence is claimed, and no Android performance conclusion was made.

## Completed

- Revalidated the exact experiment 0008 `kokoro-multi-lang-v1_0` archive and all 377 extracted deployment files; SID 3 is provenance-backed as `af_heart`.
- Rebuilt the selected mixed S8S8 QDQ model twice. Both retained outputs are 175,678,702 bytes with SHA-256 `c37d76d0ada7414d18841ed454e8c7f00c8b1f631e97e1fd019c3ba01a0fbd92`.
- Added an effective graph audit: 163 eligible Conv/MatMul/Gemm nodes have weight QDQ; 102 eligible `/decoder/generator/` nodes retain original FLOAT weight inputs.
- Reproduced and retained the rejected dynamic-QInt8 CPU failure, the 126,457,536-byte all-eligible static candidate (six of six spectral screens failed), and the non-selected linear-only candidate (six screens passed, only about 11% smaller).
- Revalidated the prior six matched FP32/INT8 pairs by full hash/format decode and recomputation of the supporting acoustic comparisons. All six pass; no raw sample MSE is used.
- Reran pinned Whisper small: FP32 WER 0.031, INT8 WER 0.031, normalized hypothesis-to-hypothesis WER 0.000.
- Rebuilt and verified the deterministic blind ZIP. The answer key and seed remain outside it.
- Added canonical reports, candidate-selection/failure records, source/tool hashes, a complete ignored-artifact manifest, strict verifier, full reproduction entrypoint, focused tests, and local documentation.

## Tests and verification

- `kokoro-int8/.venv/bin/python -m pytest -q kokoro-int8/tests` — **13 passed**.
- `scripts/verify_package.py --source-root <exact-0008-root> --runtime-smoke --require-manifest` — **passed**; this rehashed all 377 source files, wheelhouse, models, 12 final WAVs, blind ZIP/key assignments, and the complete package inventory, then ran a host-only sherpa CPU smoke.
- `bash -n scripts/reproduce_host_gate.sh` — passed.
- Python compilation, every JSON parse, and blind ZIP CRC test — passed.

## Evidence

- Overall gate: `reports/quality-gate.json` and `QUALITY_GATE.md`
- Selected build/audit: `reports/quantization-report.json`
- Bit-exact rebuild: `reports/reproduction-rebuild.json`
- Matched audio: `reports/synthesis-fp32.json`, `reports/synthesis-int8.json`, `reports/audio-analysis.json`
- ASR support: `reports/asr-report.json`
- Candidate choice and failures: `reports/candidate-selection.json`, `reports/failures.json`, `reports/checker-limitation.json`
- Blind artifact: `generated/blind/kokoro-int8-listening.zip` — 3,356,161 bytes, SHA-256 `d41d97ed0acf38320a4daacbc1a00c2ef5a805bff35c27340eb165b7b35b6c04`
- Complete paths/sizes/hashes for every current ignored model, WAV, ZIP, key, log, and historical artifact: `package-manifest.json`

## Limitations

- The exact FP32 source passes ONNX checker 1.18.0; the quantized candidate does not. ONNX Runtime quantization moves an outer-scope `SplitToSequence` producer after its consuming `Loop`. Pinned ONNX Runtime CPU and sherpa-onnx runtimes still load and infer successfully. This structural limitation must be reassessed before later deployment.
- Kokoro contains unseeded random operators. The selected model rebuild is bit-exact; regenerated WAVs are a new hash-addressed evidence set rather than bit-identical audio.
- Automated integrity, ASR, pitch, and spectral checks support triage only. They do not replace listening.
- No calibrated voice-specific speaker verifier was available, so no speaker-similarity score is reported.
- The supporting ASR environment is hash-pinned to the installed host and checkpoint but is not bootstrapped from the CPython 3.11 wheel lock.
- Historical `generated/trial-*` files from interrupted workers are retained and hash-pinned, but canonical screening reports supersede stale historical references.
- No phone was accessed; Android deployment, RTF, and PSS are explicitly deferred. No shared docs or thread-sweep files were touched.

## Exact user listening next step

1. Copy or unzip `generated/blind/kokoro-int8-listening.zip`.
2. **Do not open** `generated/blind/answer-key.json` or `generated/blind/seed.hex` first.
3. Open `listening-guide.html`, use headphones at fixed volume, and listen to A and B for all six pairs.
4. Fill in `ballot.csv` with `A`, `B`, or `tie`, confidence 1–5, and notes on intelligibility, voice identity, artifacts, prosody, and pacing.
5. Return the completed `ballot.csv`; only then reveal the answer key and record the listening verdict.
