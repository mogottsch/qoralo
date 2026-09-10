#!/system/bin/sh
set -eu
. /data/local/tmp/vibevoice-0031-fp16-fp16-long-20260910T171555Z-01/control.sh

# Both identity records must be written successfully BEFORE exec; same PID/starttime.
record_self model
cd "$REMOTE"
export LD_LIBRARY_PATH="$REMOTE/lib" ADSP_LIBRARY_PATH="$REMOTE/lib" QNN_LOG_LEVEL=verbose
exec "$REMOTE/bin/genie-app" -s exact-long.script
