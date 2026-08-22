#!/usr/bin/env bash
# Reconstruct the exact experiment-0011 T239/L238 graph identities from official FP32 source.
set -euo pipefail
if [[ $# -ne 3 ]]; then
  echo "usage: $0 PYTHON OFFICIAL_ONNX_DIR OUTPUT_DIR" >&2
  exit 2
fi
PYTHON=$1
SOURCE=$2
OUTPUT=$3
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
SPECIALIZE="$ROOT/experiments/0011-supertonic-official-fp32-phone-comparison/tools/specialize_onnx_io_shapes.py"
REWRITE="$ROOT/experiments/0011-supertonic-official-fp32-phone-comparison/tools/rewrite_vector_softplus.py"
mkdir -p "$OUTPUT"

"$PYTHON" "$SPECIALIZE" \
  --input "$SOURCE/duration_predictor.onnx" \
  --output "$OUTPUT/duration_predictor.onnx" \
  --provenance "$OUTPUT/duration_predictor.json" \
  --input-shape text_ids=1,239 --input-shape style_dp=1,8,16 \
  --input-shape text_mask=1,1,239 --output-shape duration=1 >/dev/null
"$PYTHON" "$SPECIALIZE" \
  --input "$SOURCE/text_encoder.onnx" \
  --output "$OUTPUT/text_encoder.onnx" \
  --provenance "$OUTPUT/text_encoder.json" \
  --input-shape text_ids=1,239 --input-shape style_ttl=1,50,256 \
  --input-shape text_mask=1,1,239 --output-shape text_emb=1,256,239 >/dev/null
"$PYTHON" "$SPECIALIZE" \
  --input "$SOURCE/vector_estimator.onnx" \
  --output "$OUTPUT/vector_estimator.onnx" \
  --provenance "$OUTPUT/vector_estimator.json" \
  --input-shape noisy_latent=1,144,238 --input-shape text_emb=1,256,239 \
  --input-shape style_ttl=1,50,256 --input-shape latent_mask=1,1,238 \
  --input-shape text_mask=1,1,239 --input-shape current_step=1 \
  --input-shape total_step=1 --output-shape denoised_latent=1,144,238 >/dev/null
"$PYTHON" "$SPECIALIZE" \
  --input "$SOURCE/vocoder.onnx" \
  --output "$OUTPUT/vocoder.onnx" \
  --provenance "$OUTPUT/vocoder.json" \
  --input-shape latent=1,144,238 --output-shape wav_tts=1,731136 >/dev/null
"$PYTHON" "$REWRITE" \
  --input "$OUTPUT/vector_estimator.onnx" \
  --output "$OUTPUT/vector_estimator-stable-softplus.onnx" \
  --provenance "$OUTPUT/vector_estimator-stable-softplus.json" >/dev/null

cd "$OUTPUT"
printf '%s  %s\n' \
  8a1875ef0f6960ca16fc06814509b1c3258e8f50b04a5d590d3ab6db8c775016 duration_predictor.onnx \
  769fd1d257674e8624bdea941f7a903d9460051f9845b604cd2c2980f281a8c3 text_encoder.onnx \
  723316adfcff378c8ac72ee9db34cadf3b890e4167fa9a76f07398e0d4ff5b92 vector_estimator.onnx \
  f2318c54726a034dcc89aa9818a91f1c3db0e3067b9932c7c2dae65957897c7b vector_estimator-stable-softplus.onnx \
  35b90eeae4a01d06f82dccc903a63d23c95eb2d9095ffa0d62f2cf151817c7c7 vocoder.onnx \
  | sha256sum --check --strict
