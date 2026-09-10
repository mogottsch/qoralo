#!/usr/bin/env bash
set -euo pipefail
RUN="$3"
EXP="$4"
export QAIRT_TMP_DIR="$RUN/qairt-tmp"
mkdir -m 700 "$QAIRT_TMP_DIR"
python3 - "$RUN" "$QAIRT_TMP_DIR" <<'PY'
import json, os, shutil, stat, subprocess, sys
from pathlib import Path
run, scratch = map(Path, sys.argv[1:])
if scratch.is_symlink() or scratch.resolve().parent != run.resolve():
    raise RuntimeError('scratch escapes the fresh owned run')
if scratch.stat().st_uid != os.getuid() or stat.S_IMODE(scratch.stat().st_mode) != 0o700:
    raise RuntimeError('scratch owner/mode mismatch')
fstype = subprocess.check_output(['findmnt', '-n', '-o', 'FSTYPE', '-T', str(scratch)], text=True).strip()
if fstype != 'ext4':
    raise RuntimeError(f'expected reviewed disk-backed ext4, got {fstype}')
free = shutil.disk_usage(scratch).free
if free < 32 * 1024**3:
    raise RuntimeError('less than 32 GiB free for scratch')
probe = scratch / 'write-probe'
with probe.open('x') as f:
    f.write('ok\n')
probe.unlink()
(run / 'scratch-preflight.json').write_text(json.dumps({
    'path': str(scratch), 'resolved_path': str(scratch.resolve()),
    'filesystem': fstype, 'uid': os.getuid(), 'mode': '0700',
    'free_bytes': free, 'minimum_free_bytes': 32 * 1024**3,
    'writable_probe_passed': True, 'new_owned_directory': True,
}, indent=2) + '\n')
PY
# SDK envsetup does not support nounset; restore it afterward.
set +u
source /home/moritz/opt/qairt/2.49.40.260810/bin/envsetup.sh
set -u
export LD_LIBRARY_PATH="$EXP/.local/host-libs:${LD_LIBRARY_PATH:-}"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4
exec "$1" "$2" --run-dir "$RUN" --reuse-ar1-dlc "$5"
