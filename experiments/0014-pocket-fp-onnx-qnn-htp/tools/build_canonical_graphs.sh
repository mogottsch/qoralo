#!/usr/bin/env bash
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel);EXP="$ROOT/experiments/0014-pocket-fp-onnx-qnn-htp";E12="$ROOT/experiments/0012-pocket-onnx-vs-executorch-android";PY="$E12/.local/source-venv/bin/python";CANON="$EXP/.local/canonical-benchmark";mkdir -p "$CANON/text" "$CANON/qnn-flow" "$EXP/work/canonical-benchmark"
"$PY" "$EXP/tools/prepare_text_conditioner_variant.py" --source "$E12/.local/onnx-controlled/text_conditioner.onnx" --tokens 64 --output "$CANON/text/text_conditioner-text64.onnx" --report "$CANON/text/report.json" >"$EXP/work/canonical-benchmark/text-export.stdout.json"
PYTHONPATH="$E12/.local/onnx-export" "$PY" "$EXP/tools/export_flow_qnn_static.py" --config "$E12/.local/onnx-export-local.yaml" --exporter-root "$E12/.local/onnx-export" --output "$CANON/qnn-flow" --capacity 512 --voice-steps 126 --text-steps 64 --skip-voice >"$EXP/work/canonical-benchmark/flow-export.stdout.json" 2>"$EXP/work/canonical-benchmark/flow-export.stderr.log"
python3 - "$CANON" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]);files=[root/'text/text_conditioner-text64.onnx',root/'qnn-flow/flow_lm_prefill_text64.onnx',root/'qnn-flow/flow_lm_ar_bos1.onnx',root/'qnn-flow/flow_lm_ar_latent1.onnx'];out={'schema_version':1,'route':'pocket-fixed-alba-text64-cache512-canonical-v2','generated':[{"path":str(p),"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]};(root/'graph-inventory.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
PY
