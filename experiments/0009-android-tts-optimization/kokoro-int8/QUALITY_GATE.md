# Kokoro INT8 host quality gate

## Status: `awaiting_user_listening`

The mixed S8S8 QDQ candidate passed the automated host integrity and supporting-signal checks. That is **not** a claim of subjective equivalence. The gate remains `awaiting_user_listening` until Moritz returns the blind ballot.

- Exact source: `kokoro-multi-lang-v1_0`, SID 3 (`af_heart`), source SHA-256 `c436dc6a842b62aba06af67e40bafcfb9c60ac3af895358f1974ad9a7f7c026b`.
- Selected candidate: QDQ S8S8 Conv/MatMul/Gemm outside `/decoder/generator/`; 163 nodes have weight QDQ and 102 excluded eligible generator nodes retain their source FP32 weight inputs.
- Candidate SHA-256: `c37d76d0ada7414d18841ed454e8c7f00c8b1f631e97e1fd019c3ba01a0fbd92`; an independent rebuild matched it bit-for-bit.
- Model size: 325,630,829 bytes FP32 to 175,678,702 bytes candidate (46.0% reduction).
- Blind package: `generated/blind/kokoro-int8-listening.zip` (3,356,161 bytes), SHA-256 `d41d97ed0acf38320a4daacbc1a00c2ef5a805bff35c27340eb165b7b35b6c04`.
- Failure retention includes the CPU-incompatible dynamic attempt and the 126,457,536-byte all-eligible S8S8 candidate, whose documented spectral screen failed on all six pairs.

## Exact listening next step for Moritz

1. Copy or unzip `generated/blind/kokoro-int8-listening.zip` without opening `generated/blind/answer-key.json`.
2. Open `listening-guide.html`, use headphones at fixed volume, and listen to A and B for all six pairs.
3. Fill in `ballot.csv` (`A`, `B`, or `tie`, confidence, and notes) and return that file.
4. Only after the ballot is final should the separate answer key be opened.

Supporting Whisper small corpus WER was 0.031 for FP32 and 0.031 for INT8; hypothesis-to-hypothesis WER was 0.000. These and the aggregate pitch/spectral checks are diagnostics, not listening results. No raw sample error decision is used. No uncalibrated speaker-similarity number is reported.

Known structural limitation: the exact source passes ONNX checker 1.18.0, while the quantized graph triggers a topological-order diagnostic after the quantizer moves an outer-scope producer behind its consuming Loop. Both pinned CPU runtimes load and synthesize the candidate. This remains a later-deployment risk, not a hidden source-model issue.

## Android scope

This track did not deploy the candidate to Android. It makes no Android RTF or PSS conclusion. Both are explicitly deferred until the user quality gate passes and the exact hash-pinned candidate is deployed in a later experiment.

See `README.md` for reproduction and `package-manifest.json` for every retained generated artifact hash.
