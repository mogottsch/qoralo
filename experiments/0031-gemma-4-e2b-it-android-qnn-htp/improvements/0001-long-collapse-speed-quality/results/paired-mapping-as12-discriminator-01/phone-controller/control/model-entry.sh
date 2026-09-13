#!/system/bin/sh
set -eu
. /data/local/tmp/vibevoice-0031-mapping-as12-mapping-as12-20260913T104909Z-01/control.sh

# Both identity records must be written successfully BEFORE exec; same PID/starttime.
record_self model
cd "$REMOTE"
export LD_LIBRARY_PATH="$REMOTE/lib" ADSP_LIBRARY_PATH="$REMOTE/lib" QNN_LOG_LEVEL=verbose
export GEMMA_PREFILL_CAPTURE_DIR="$REMOTE/evidence/prefill-capture"
mkdir -m 700 "$GEMMA_PREFILL_CAPTURE_DIR" || exit 71
ulimit -v 12582912 || exit 72
exec "$REMOTE/bin/genie-app" -s exact-long.script
