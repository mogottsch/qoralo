#!/usr/bin/env bash
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel);EXP="$ROOT/experiments/0014-pocket-fp-onnx-qnn-htp";CANON="$EXP/.local/canonical-benchmark";OUT=${1:-$EXP/work/canonical-benchmark/host-qnn-gate};mkdir -p "$OUT"
declare -a ITEMS=(
 "text:$CANON/text/text_conditioner-text64.onnx"
 "prefill_text64:$CANON/qnn-flow/flow_lm_prefill_text64.onnx"
 "ar_bos_cache512:$CANON/qnn-flow/flow_lm_ar_bos1.onnx"
 "ar_latent_cache512:$CANON/qnn-flow/flow_lm_ar_latent1.onnx"
 "flow:$EXP/.local/static-optimized/flow_lm_flow-flow1.onnx"
 "decoder12:$EXP/.local/qnn-v2/mimi_decoder-decoder12.onnx"
 "decoder6:$EXP/.local/qnn-v2/mimi_decoder-decoder6.onnx"
 "decoder1:$EXP/.local/qnn-v2/mimi_decoder-decoder1.onnx"
)
for item in "${ITEMS[@]}";do name=${item%%:*};model=${item#*:};[[ -f $model ]]||{ echo "missing $model" >&2;exit 2;};echo "gating $name";HOST_FP16=1 "$EXP/tools/run_host_qnn_gate.sh" "$model" "$OUT/$name";done
python3 - "$OUT" <<'PY'
import hashlib,json,sys
from pathlib import Path
out=Path(sys.argv[1]);rows=[]
for d in sorted(x for x in out.iterdir() if x.is_dir()):
 text='\n'.join((d/f).read_text(errors='replace') for f in ('stdout.log','stderr.log') if (d/f).exists());model=None
 rows.append({'component':d.name,'exit_code':int((d/'exit-code.txt').read_text()),'all_nodes_placed':'All nodes placed on [QNNExecutionProvider]' in text,'cpu_fallback_text_seen':'fallback to CPU' in text,'summary':(d/'summary.txt').read_text().splitlines()})
result={'schema_version':1,'route':'pocket-fixed-alba-text64-cache512-canonical-v2','cpu_fallback_disabled':True,'components':rows,'passed':all(x['exit_code']==0 and x['all_nodes_placed'] and not x['cpu_fallback_text_seen'] for x in rows)};(out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));assert result['passed']
PY
