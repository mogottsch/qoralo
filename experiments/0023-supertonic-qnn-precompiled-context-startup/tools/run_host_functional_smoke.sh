#!/usr/bin/env bash
# Reproduce the four-component host QNN external-context functional smoke.
set -euo pipefail
if [[ $# -ne 4 ]]; then
  echo "usage: $0 PYTHON OFFICIAL_SUPERTONIC_SNAPSHOT ORT_RELEASE QAIRT_ROOT" >&2
  exit 2
fi
if [[ ${SERIALIZED_QNN_CLEARANCE:-no} != yes ]]; then
  echo "Set SERIALIZED_QNN_CLEARANCE=yes only after Pi/Jens explicitly clears concurrent QNN work." >&2
  exit 3
fi
PYTHON=$(realpath "$1")
SNAPSHOT=$(realpath "$2")
ORT_RELEASE=$(realpath "$3")
QAIRT=$(realpath "$4")
ROOT=$(git rev-parse --show-toplevel)
EXP="$ROOT/experiments/0023-supertonic-qnn-precompiled-context-startup"
IMAGE=vibevoice-experiment-0010-qairt:2.49.0.260730-ubuntu22.04
GRAPHS="$EXP/.local/graphs-all"
INPUTS="$EXP/.local/inputs"
GENERATION="$EXP/.local/contexts-host"
RELOAD="$EXP/.local/reloads-host-isolated"
BACKEND=/opt/qairt/lib/x86_64-linux-clang/libQnnHtp.so

exec 9>"$ROOT/artifacts/locks/heavy-ram.lock"
flock -n 9 || { echo "heavy RAM/QNN lock busy" >&2; exit 4; }

rm -rf "$GRAPHS" "$INPUTS" "$GENERATION" "$RELOAD"
mkdir -p "$GRAPHS" "$INPUTS" "$GENERATION" "$RELOAD"
"$ROOT/experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/tools/reconstruct_frozen_graphs.sh" \
  "$PYTHON" "$SNAPSHOT/onnx" "$GRAPHS"
"$PYTHON" "$ROOT/experiments/0011-supertonic-official-fp32-phone-comparison/tools/prepare_component_inputs.py" \
  --assets "$SNAPSHOT" --transcript "$EXP/protocol/transcript.txt" --output "$INPUTS" \
  >"$INPUTS/generation.stdout.json"

for spec in \
  'duration:duration_predictor.onnx' \
  'text:text_encoder.onnx' \
  'vector:vector_estimator-stable-softplus.onnx' \
  'vocoder:vocoder.onnx'; do
  component=${spec%%:*}
  model=${spec#*:}
  output="$GENERATION/$component"
  mkdir -p "$output/profiles"
  timeout --signal=TERM --kill-after=60 1800 docker run --rm --user 1000:1000 -e HOME=/tmp \
    -v "$ROOT:/repo" -v "$ORT_RELEASE:/build:ro" -v "$QAIRT:/opt/qairt:ro" \
    -w /repo "$IMAGE" \
    env PYTHONPATH=/build LD_LIBRARY_PATH=/build:/build/onnxruntime/capi:/opt/qairt/lib/x86_64-linux-clang \
    python3 "/repo/experiments/0023-supertonic-qnn-precompiled-context-startup/tools/qnn_context_component.py" generate \
      --component "$component" \
      --model "/repo/experiments/0023-supertonic-qnn-precompiled-context-startup/.local/graphs-all/$model" \
      --inputs /repo/experiments/0023-supertonic-qnn-precompiled-context-startup/.local/inputs \
      --descriptor "/repo/experiments/0023-supertonic-qnn-precompiled-context-startup/.local/contexts-host/$component/$component-context.onnx" \
      --backend "$BACKEND" \
      --profile-prefix "/repo/experiments/0023-supertonic-qnn-precompiled-context-startup/.local/contexts-host/$component/profiles/generate" \
      --result "/repo/experiments/0023-supertonic-qnn-precompiled-context-startup/.local/contexts-host/$component/generate-result.json" \
      >"$output/generate.stdout.json" 2>"$output/generate.stderr.log"
done

for component in duration text vector vocoder; do
  source="$GENERATION/$component"
  isolated="$RELOAD/$component"
  mkdir -p "$isolated/profiles"
  cp "$source/$component-context.onnx" "$source/$component-context_qnn.bin" "$isolated/"
  cp "$EXP/tools/qnn_context_component.py" "$isolated/"
  case "$component" in
    duration) files='text_ids.raw style_dp.raw text_mask.raw' ;;
    text) files='text_ids.raw style_ttl.raw text_mask.raw' ;;
    vector) files='step0_noisy_latent.raw text_emb.raw style_ttl.raw latent_mask.raw text_mask.raw current_step.raw total_step.raw' ;;
    vocoder) files='final_latent.raw' ;;
  esac
  for file in $files; do cp "$INPUTS/$file" "$isolated/"; done
  timeout --signal=TERM --kill-after=60 1800 docker run --rm --user 1000:1000 -e HOME=/tmp \
    -v "$isolated:/smoke" -v "$ORT_RELEASE:/build:ro" -v "$QAIRT:/opt/qairt:ro" \
    -w /smoke "$IMAGE" \
    env PYTHONPATH=/build LD_LIBRARY_PATH=/build:/build/onnxruntime/capi:/opt/qairt/lib/x86_64-linux-clang \
    python3 /smoke/qnn_context_component.py reload \
      --component "$component" --model "/smoke/$component-context.onnx" --inputs /smoke \
      --descriptor "/smoke/$component-context.onnx" --backend "$BACKEND" \
      --profile-prefix /smoke/profiles/reload --result /smoke/reload-result.json \
      --require-source-absent --isolation-root /smoke \
      >"$isolated/reload.stdout.json" 2>"$isolated/reload.stderr.log"
done

python3 "$EXP/tools/finalize_host_context_smoke.py" \
  --generation "$GENERATION" --reload "$RELOAD" --graphs "$GRAPHS" \
  --transcript "$EXP/protocol/transcript.txt" --output "$EXP/results/host-context-smoke"
