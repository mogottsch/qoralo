#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT="$1"
AR="$2"
MODE="$3"
EXP=/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp
TRACK="$EXP/improvements/0001-long-collapse-speed-quality"
export QAIRT_TMP_DIR="$ROOT/scratch"
export TMPDIR="$QAIRT_TMP_DIR"
mkdir -m 700 "$QAIRT_TMP_DIR"
python3 - "$ROOT" <<'PY'
import json,os,shutil,subprocess,sys
from pathlib import Path
r=Path(sys.argv[1]);s=r/'scratch'
fstype=subprocess.check_output(['findmnt','-n','-o','FSTYPE','-T',str(s)],text=True).strip()
assert fstype not in ('tmpfs','ramfs'), fstype
free=shutil.disk_usage(s).free
assert free>=8*1024**3
mem={l.split(':')[0]:int(l.split()[1]) for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')}
assert mem['MemAvailable']>=4*1024**2, mem
(r/'preflight.json').write_text(json.dumps({'filesystem':fstype,'disk_free_bytes':free,'mem_available_kib':mem['MemAvailable'],'scratch':str(s)},indent=2)+'\n')
PY
set +u
source /home/moritz/opt/qairt/2.49.40.260810/bin/envsetup.sh
set -u
export LD_LIBRARY_PATH="$EXP/.local/host-libs:${LD_LIBRARY_PATH:-}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export TF_NUM_INTEROP_THREADS=1 TF_NUM_INTRAOP_THREADS=1 CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
ulimit -f 2097152
ARGS=()
if [[ "$MODE" == candidate ]]; then ARGS+=(--candidate); fi
exec "$EXP/.local/qairt-2.49.40-venv/bin/python" -B "$TRACK/tools/probe_value_precision_path.py" --run-dir "$ROOT/fixture" --ar "$AR" "${ARGS[@]}"
