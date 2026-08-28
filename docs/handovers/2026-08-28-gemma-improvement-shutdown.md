# Gemma improvement shutdown handover — 2026-08-28

## Exact shutdown status

- **Accepted milestone:** `1c5b7b6`
- **Candidate-2 WIP:** `experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/tools/convert_global_value_fp16.py`
- Candidate was designed but **not executed or validated** due observed memory pressure.
- No model/result artifacts were created.
- No phone or ADB access occurred.
- Owned processes: none.
- `artifacts/locks/phone.lock`: free.

## Candidate scope

The uncommitted WIP prepares a distinct, fallback-free HTP candidate with FP16 value-cache I/O for global-attention layers `{4,9,14}` in both AR1 and AR128. It is intended to leave all transformer execution on HTP, keep the other cache contracts unchanged, and preserve the completed campaign and registry evidence as immutable baselines.

The script has not yet been run, so its ONNX patch, conversion result, tensor signatures, delegation, conversion counts, compilation, context, or fidelity properties are not evidence and must not be claimed.

## Restart gate

Do not restart until Pi explicitly approves and observed available host memory is comfortably above the prior Gemma conversion peak of approximately 26 GB. Continue to coordinate from actual memory pressure; do not reintroduce `heavy-ram.lock`. Do not access the phone until a host candidate is committed and reviewed.

Known environment:

- Repository: `/home/moritz/dev/vibevoice-android-spike`
- QAIRT: `/home/moritz/opt/qairt/2.49.40.260810`
- Python: `experiments/0031-gemma-4-e2b-it-android-qnn-htp/.local/qairt-2.49.40-venv/bin/python`

After approval and a fresh memory check, the intended distinct host launch is:

```bash
cd /home/moritz/dev/vibevoice-android-spike
export QAIRT_ROOT=/home/moritz/opt/qairt/2.49.40.260810
source "$QAIRT_ROOT/bin/envsetup.sh"
EXP=experiments/0031-gemma-4-e2b-it-android-qnn-htp
TRACK="$EXP/improvements/0001-long-collapse-speed-quality"
RUN="$TRACK/.local/global-value-fp16-convert-run"
mkdir -p "$RUN"
set +e
"$EXP/.local/qairt-2.49.40-venv/bin/python" \
  "$TRACK/tools/convert_global_value_fp16.py" \
  >"$RUN/stdout.jsonl" 2>"$RUN/stderr.log"
status=$?
printf '%s\n' "$status" >"$RUN/exit-code.txt"
exit "$status"
```

Preserve the run directory even on failure. Do not retry in place: fix a diagnosed cause and use a new distinct run directory. The first resumed validation must fail closed on exact AR1/AR128 cache identity, FP16 signatures only for the three selected global value caches, unchanged remaining cache signatures, conversion/operator counts, zero unsupported/fallback conversion markers, DLC/context identities and sizes, compiler metadata, and bounded host fidelity evidence.
