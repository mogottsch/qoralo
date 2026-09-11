#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT="$1"
AR1="$2"
AR128="$3"
RAM="$4"
SWAP="$5"
EXP=/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp
TRACK="$EXP/improvements/0001-long-collapse-speed-quality"
export QAIRT_TMP_DIR="$ROOT/scratch" TMPDIR="$ROOT/scratch"
mkdir -m 700 "$QAIRT_TMP_DIR"
FSTYPE="$(findmnt -n -o FSTYPE -T "$QAIRT_TMP_DIR")"
[[ "$FSTYPE" != tmpfs && "$FSTYPE" != ramfs ]]
printf '%s\n' "$FSTYPE" > "$ROOT/scratch-filesystem.txt"
set +u
source /home/moritz/opt/qairt/2.49.40.260810/bin/envsetup.sh
set -u
export LD_LIBRARY_PATH="$EXP/.local/host-libs:${LD_LIBRARY_PATH:-}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2
export TF_NUM_INTEROP_THREADS=1 TF_NUM_INTRAOP_THREADS=2 CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
ulimit -f 33554432
exec /usr/bin/python3 -B "$TRACK/tools/run_value_precision_guard.py" --root "$ROOT" --ram-bytes "$RAM" --swap-bytes "$SWAP" --seconds 1770 -- "$EXP/.local/qairt-2.49.40-venv/bin/python" -B "$TRACK/tools/compile_value_precision_context.py" --ar1-validation "$AR1" --ar128-validation "$AR128" --run-dir "$ROOT/work"
