#!/usr/bin/env bash
set -euo pipefail
[[ ${QNN_HOST_ACCESS_CONFIRMED:-} == yes ]] || {
  echo 'set QNN_HOST_ACCESS_CONFIRMED=yes only after Jens/Jere/Pi clearance' >&2
  exit 2
}
ROOT=$(git rev-parse --show-toplevel)
EXP="$ROOT/experiments/0024-pocket-tts-qnn-precompiled-context-startup"
GRAPHS="$EXP/.local/graphs"
CONTEXTS="$EXP/.local/contexts-host"
ISOLATED="$EXP/.local/context-reload-isolated"
RUNTIME="$ROOT/experiments/0010-supertonic-qnn-htp-feasibility/.local/ort-v1.27.1-qnn-2.49.0-host-patched-a08e17/Release"
SDK=${QAIRT_SDK_ROOT:-/home/moritz/opt/qairt/2.49.0.260730}
IMAGE=${QAIRT_HOST_IMAGE:-vibevoice-experiment-0010-qairt:2.49.0.260730-ubuntu22.04}
TARGET=${1:-all}
mkdir -p "$ROOT/artifacts/locks" "$CONTEXTS" "$ISOLATED"
exec 8>>"$ROOT/artifacts/locks/heavy-ram.lock"
flock -n 8 || { echo heavy_ram_lock_busy >&2; exit 3; }
[[ -d $RUNTIME && -f $SDK/lib/x86_64-linux-clang/libQnnHtp.so ]] || {
  echo missing_host_runtime_or_qairt >&2
  exit 4
}

declare -A MODELS=(
  [text]=text_conditioner.onnx
  [prefill]=flow_prefill_text64.onnx
  [bos]=flow_ar_bos1.onnx
  [latent]=flow_ar_latent1.onnx
  [flow]=flow.onnx
  [decoder12]=mimi_decoder12.onnx
  [decoder6]=mimi_decoder6.onnx
  [decoder1]=mimi_decoder1.onnx
)
ORDER=(text prefill bos latent flow decoder12 decoder6 decoder1)
run_container() {
  docker run --rm --user 1000:1000 -e HOME=/tmp \
    -v "$ROOT:/repo" -v "$RUNTIME:/build:ro" -v "$SDK:/opt/qairt:ro" \
    -w /repo "$IMAGE" bash -lc \
    "export PYTHONPATH=/build LD_LIBRARY_PATH=/build:/build/onnxruntime/capi:/opt/qairt/lib/x86_64-linux-clang; $*"
}
run_isolated() {
  local isolated_dir=$1; shift
  docker run --rm --user 1000:1000 -e HOME=/tmp \
    -v "$isolated_dir:/smoke" -v "$RUNTIME:/build:ro" -v "$SDK:/opt/qairt:ro" \
    -w /smoke "$IMAGE" bash -lc \
    "export PYTHONPATH=/build LD_LIBRARY_PATH=/build:/build/onnxruntime/capi:/opt/qairt/lib/x86_64-linux-clang; $*"
}
for component in "${ORDER[@]}"; do
  [[ $TARGET == all || $TARGET == "$component" || ($TARGET == remaining && $component != text) || ($TARGET == decoder-tail && ($component == decoder6 || $component == decoder1)) ]] || continue
  model="$GRAPHS/${MODELS[$component]}"
  [[ -f $model ]] || { echo "missing $model" >&2; exit 5; }
  out="$CONTEXTS/$component"
  isolated="$ISOLATED/$component"
  [[ ! -e $out && ! -e $isolated ]] || {
    echo "refusing to replace existing evidence for $component" >&2
    exit 6
  }
  mkdir -p "$out/profiles" "$isolated/profiles"
  descriptor="$out/${MODELS[$component]}"
  token_arg=''
  if [[ $component == text ]]; then
    token_arg="--token-fixture /repo/experiments/0024-pocket-tts-qnn-precompiled-context-startup/.local/assets/canonical-token-ids-64.i64"
  fi
  set +e
  run_container \
    "python3 /repo/experiments/0024-pocket-tts-qnn-precompiled-context-startup/tools/qnn_context_component.py generate" \
    "--component $component --model /repo/${model#$ROOT/}" \
    "--descriptor /repo/${descriptor#$ROOT/}" \
    "--backend /opt/qairt/lib/x86_64-linux-clang/libQnnHtp.so" \
    "--profile-prefix /repo/${out#$ROOT/}/profiles/generate" \
    "--result /repo/${out#$ROOT/}/generate-result.json $token_arg" \
    >"$out/generate.stdout.json" 2>"$out/generate.stderr.log"
  rc=$?
  set -e
  printf '%s\n' "$rc" >"$out/generate.exit"
  [[ $rc == 0 ]] || exit "$rc"

  cp "$descriptor" "$out/${MODELS[$component]%.*}_qnn.bin" "$isolated/"
  cp "$EXP/tools/qnn_context_component.py" "$isolated/"
  reload_token_arg=''
  if [[ $component == text ]]; then
    cp "$EXP/.local/assets/canonical-token-ids-64.i64" "$isolated/"
    reload_token_arg="--token-fixture /smoke/canonical-token-ids-64.i64"
  fi
  set +e
  run_isolated "$isolated" \
    "python3 /smoke/qnn_context_component.py reload" \
    "--component $component --model /smoke/${MODELS[$component]}" \
    "--descriptor /smoke/${MODELS[$component]}" \
    "--backend /opt/qairt/lib/x86_64-linux-clang/libQnnHtp.so" \
    "--profile-prefix /smoke/profiles/reload" \
    "--result /smoke/reload-result.json --require-source-absent" \
    "--isolation-root /smoke $reload_token_arg" \
    >"$isolated/reload.stdout.json" 2>"$isolated/reload.stderr.log"
  rc=$?
  set -e
  printf '%s\n' "$rc" >"$isolated/reload.exit"
  [[ $rc == 0 ]] || exit "$rc"
  python3 - "$out/generate-result.json" "$isolated/reload-result.json" <<'PY'
import json,sys
generate=json.load(open(sys.argv[1])); reload=json.load(open(sys.argv[2]))
assert generate['qnn_only_provider_proof'] and reload['qnn_only_provider_proof']
assert reload['source_onnx_absent_from_isolation_root']
assert [x['sha256'] for x in generate['outputs']] == [x['sha256'] for x in reload['outputs']]
PY
  echo "passed generate+isolated reload: $component"
done
