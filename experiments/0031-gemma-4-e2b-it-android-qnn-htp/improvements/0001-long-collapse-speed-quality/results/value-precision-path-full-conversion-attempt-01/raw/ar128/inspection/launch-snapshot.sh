#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT="$1"
DLC="$2"
SHA="$3"
EXP=/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp
export QAIRT_TMP_DIR="$ROOT/scratch" TMPDIR="$ROOT/scratch"
mkdir -m 700 "$QAIRT_TMP_DIR"
[[ "$(findmnt -n -o FSTYPE -T "$QAIRT_TMP_DIR")" != tmpfs ]]
printf '%s  %s\n' "$SHA" "$DLC" | sha256sum -c - > "$ROOT/dlc-identity.txt"
set +u
source /home/moritz/opt/qairt/2.49.40.260810/bin/envsetup.sh
set -u
export LD_LIBRARY_PATH="$EXP/.local/host-libs:${LD_LIBRARY_PATH:-}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
exec "$EXP/.local/qairt-2.49.40-venv/bin/python" -B /home/moritz/opt/qairt/2.49.40.260810/bin/x86_64-linux-clang/qairt-dlc-info -i "$DLC" --save "$ROOT/model.csv"
