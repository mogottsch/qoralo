#!/bin/bash
set -u
umask 077
printf "%s\n" "$$" > /home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/phone-return-launches/trace-long-20260911T150027Z-01/launcher.pid
nice -n 15 timeout --signal=TERM --kill-after=450s 3600s python3 -B /home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/tools/phone_selected_id_appguard.py --execute --reviewed-stage-digest 07e5b1b5f1e75c20022e6f9356262fe969eadbead6f91b8017f01429c20fc2f2 --pi-slot pi-gemma-selected-id-long-20260911-a --run-id trace-long-20260911T150027Z-01 > /home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/phone-return-launches/trace-long-20260911T150027Z-01/controller.stdout 2> /home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/phone-return-launches/trace-long-20260911T150027Z-01/controller.stderr
rc=$?
printf "%s\n" "$rc" > /home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/phone-return-launches/trace-long-20260911T150027Z-01/controller-exit-code.txt
printf "GEMMA_SELECTED_ID_CONTROLLER_FINISHED exit=%s\n" "$rc"
exit "$rc"
