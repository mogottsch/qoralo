#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 2 ]]; then
  echo "usage: $0 ORT_RELEASE QAIRT_ROOT" >&2
  exit 2
fi
if [[ ${SERIALIZED_QNN_CLEARANCE:-no} != yes ]]; then
  echo "explicit Pi clearance required: set SERIALIZED_QNN_CLEARANCE=yes" >&2
  exit 3
fi
ROOT=$(git rev-parse --show-toplevel)
EXP="$ROOT/experiments/0023-supertonic-qnn-precompiled-context-startup"
ORT_RELEASE=$(realpath "$1")
QAIRT=$(realpath "$2")
IMAGE=vibevoice-experiment-0010-qairt:2.49.0.260730-ubuntu22.04
CAMPAIGN="$EXP/.local/clean-setup-campaign"
SOURCE_PACKAGE="$CAMPAIGN/source-package"
CONTEXT_PACKAGE="$CAMPAIGN/context-package"
RUNS="$CAMPAIGN/runs"

exec 9>"$ROOT/artifacts/locks/heavy-ram.lock"
flock -n 9 || { echo "heavy-ram.lock unavailable" >&2; exit 4; }

if ps -eo cmd | grep -E '[Q]NNExecutionProvider|[H]tpPrepare|[o]nnxruntime_perf_test|[q]nn_context_component' >/dev/null; then
  echo "another QNN/compiler process is active" >&2
  exit 5
fi

rm -rf "$CAMPAIGN"
mkdir -p "$SOURCE_PACKAGE" "$CONTEXT_PACKAGE" "$RUNS"
cp "$EXP/tools/qnn_setup_timing_process.py" "$SOURCE_PACKAGE/"
cp "$EXP/tools/qnn_setup_timing_process.py" "$CONTEXT_PACKAGE/"
cp "$EXP/.local/graphs-all/duration_predictor.onnx" \
   "$EXP/.local/graphs-all/text_encoder.onnx" \
   "$EXP/.local/graphs-all/vector_estimator-stable-softplus.onnx" \
   "$EXP/.local/graphs-all/vocoder.onnx" "$SOURCE_PACKAGE/"
for component in duration text vector vocoder; do
  cp "$EXP/.local/contexts-host/$component/$component-context.onnx" \
     "$EXP/.local/contexts-host/$component/$component-context_qnn.bin" \
     "$CONTEXT_PACKAGE/"
done

printf 'schedule_position\tmode\trun_index\tstart_utc\tend_utc\texit_code\n' >"$CAMPAIGN/schedule.tsv"
python3 - "$CAMPAIGN/campaign-start.json" "$IMAGE" <<'PY'
import json,platform,subprocess,sys,time
from pathlib import Path
out=Path(sys.argv[1]); image=sys.argv[2]
out.write_text(json.dumps({
  'schema_version':1,
  'start_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
  'host':platform.platform(),
  'docker_image':image,
  'docker_image_id':subprocess.check_output(['docker','image','inspect','--format={{.Id}}',image],text=True).strip(),
  'meminfo_before':Path('/proc/meminfo').read_text(),
  'heavy_ram_lock':'acquired nonblocking and held by the parent shell for the full campaign',
  'prelaunch_process_scan':'no QNNExecutionProvider/HtpPrepare/onnxruntime_perf_test/qnn_context_component process found',
},indent=2,sort_keys=True)+'\n')
PY

# Fixed balanced order prevents all source or all context runs from occupying one time block.
schedule=(source context context source context source source context source context)
source_index=0
context_index=0
position=0
for mode in "${schedule[@]}"; do
  position=$((position + 1))
  if [[ $mode == source ]]; then
    source_index=$((source_index + 1)); run_index=$source_index; package=$SOURCE_PACKAGE
  else
    context_index=$((context_index + 1)); run_index=$context_index; package=$CONTEXT_PACKAGE
  fi
  run_dir="$RUNS/$(printf '%02d' "$position")-$mode-$run_index"
  mkdir -p "$run_dir"
  start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  set +e
  timeout --signal=TERM --kill-after=30 900 docker run --rm --user 1000:1000 -e HOME=/tmp \
    -v "$package:/package:ro" -v "$run_dir:/out" \
    -v "$ORT_RELEASE:/build:ro" -v "$QAIRT:/opt/qairt:ro" \
    -w /package "$IMAGE" \
    env PYTHONPATH=/build LD_LIBRARY_PATH=/build:/build/onnxruntime/capi:/opt/qairt/lib/x86_64-linux-clang \
    python3 /package/qnn_setup_timing_process.py \
      --mode "$mode" --package /package --run-index "$run_index" --schedule-position "$position" \
      --output "/out/result.json" >"$run_dir/stdout.json" 2>"$run_dir/stderr.log"
  code=$?
  set -e
  end=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$position" "$mode" "$run_index" "$start" "$end" "$code" >>"$CAMPAIGN/schedule.tsv"
  if [[ $code -ne 0 ]]; then
    echo "campaign run failed: position=$position mode=$mode run=$run_index exit=$code" >&2
    exit "$code"
  fi
  python3 - "$run_dir/result.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]));print(x['schedule_position'],x['mode'],x['run_index'],x['timing']['session_sequence_seconds'],x['timing']['component_session_create_seconds'])
PY
done

python3 - "$CAMPAIGN/campaign-end.json" <<'PY'
import json,sys,time
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({
  'schema_version':1,
  'end_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
  'meminfo_after':Path('/proc/meminfo').read_text(),
  'completed_runs':10,
  'heavy_ram_lock':'still held at campaign completion',
},indent=2,sort_keys=True)+'\n')
PY
