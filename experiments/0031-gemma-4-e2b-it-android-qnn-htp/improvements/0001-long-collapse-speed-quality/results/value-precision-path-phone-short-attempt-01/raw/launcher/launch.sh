#!/bin/bash
set -u
umask 077
printf "%s\n" "$$" > /home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/value-precision-phone-launches/value-short-20260911T124722Z-01/launcher.pid
nice -n 15 timeout --signal=TERM --kill-after=450s 3600s python3 -B /home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/tools/phone_value_precision_short.py --execute --reviewed-stage-digest 206ca960a69f915f81cb5c61dde5684259f8fbee8a37e14ef8b8bbf9fcafc78b --pi-slot pi-gemma-value-short-20260911-a --run-id value-short-20260911T124722Z-01 > /home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/value-precision-phone-launches/value-short-20260911T124722Z-01/controller.stdout 2> /home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/value-precision-phone-launches/value-short-20260911T124722Z-01/controller.stderr
rc=$?
printf "%s\n" "$rc" > /home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/value-precision-phone-launches/value-short-20260911T124722Z-01/controller-exit-code.txt
printf "GEMMA_VALUE_SHORT_CONTROLLER_FINISHED exit=%s\n" "$rc"
exit "$rc"
