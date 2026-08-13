# Kokoro INT8 host quality gate

## Status: `passed_user_listening`

Moritz finalized all six blind votes: four ties, one INT8 preference, and one FP32 preference. Both directional preferences had confidence 2/5. The retained ballot detected no systematic INT8 degradation, so the user listening gate passed. This does not prove perceptual equivalence or INT8 superiority.

- Exact source: `kokoro-multi-lang-v1_0`, SID 3 (`af_heart`), source SHA-256 `c436dc6a842b62aba06af67e40bafcfb9c60ac3af895358f1974ad9a7f7c026b`.
- Candidate SHA-256: `c37d76d0ada7414d18841ed454e8c7f00c8b1f631e97e1fd019c3ba01a0fbd92`; an independent rebuild matched it bit-for-bit.
- Model size: 325,630,829 bytes FP32 to 175,678,702 bytes candidate (46.0% reduction).
- Selected boundary: QDQ S8S8 Conv/MatMul/Gemm outside `/decoder/generator/`.
- Blind package: `generated/blind/kokoro-int8-listening.zip` (3,356,161 bytes), SHA-256 `d41d97ed0acf38320a4daacbc1a00c2ef5a805bff35c27340eb165b7b35b6c04`.
- Automated Whisper WER was 0.031 for FP32 and 0.031 for INT8.

The exact source passes ONNX checker 1.18.0, while the quantized graph retains a known outer-scope topological-order diagnostic. Pinned CPU runtimes load and synthesize it, but this must be reassessed before Android deployment.

## Android scope

The exact candidate is now eligible for a later Android benchmark, but it has not been deployed. No Android RTF or PSS value is claimed here.
