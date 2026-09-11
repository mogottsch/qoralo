#!/bin/bash
set -u
umask 077
printf "%s\n" "$$" > /home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/phone-return-launches/value-long-20260911T130755Z-01/launcher.pid
nice -n 15 timeout --signal=TERM --kill-after=450s 3600s python3 -B /home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/tools/phone_value_precision_long_health.py --execute --reviewed-stage-digest 373ca1b67b3ce65920127eede27df84b2832a783aee14d934d328835bc9f0996 --pi-slot pi-gemma-value-long-20260911-a --run-id value-long-20260911T130755Z-01 > /home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/phone-return-launches/value-long-20260911T130755Z-01/controller.stdout 2> /home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/phone-return-launches/value-long-20260911T130755Z-01/controller.stderr
rc=$?
printf "%s\n" "$rc" > /home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/phone-return-launches/value-long-20260911T130755Z-01/controller-exit-code.txt
printf "GEMMA_VALUE_LONG_CONTROLLER_FINISHED exit=%s\n" "$rc"
exit "$rc"
