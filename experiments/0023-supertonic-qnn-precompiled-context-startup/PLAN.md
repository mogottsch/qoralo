# Experiment 0023 plan

## Current state

All four exact experiment-0011 graph identities passed host QNN HTP external-context generation and independent source-unavailable reload. This is functional evidence only. The wave accidentally overlapped experiment 0017's serialized host QNN campaign before its owner replied; every timing/resource value is excluded from startup comparison. No 0023 QNN session/compiler or phone work may start until explicit Pi/Jens clearance.

## Frozen pragmatic scope

- Input: legacy 230-byte experiment-0011 transcript, SHA-256 `350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f`.
- Effective route: accepted T239/L238/729,746-sample stable-Softplus all-HTP route.
- Arms differ only in fresh source-ONNX QNN session compilation versus external EPContext/context-binary reload.
- CPU fallback is disabled for every neural session.
- Context reload must work in a fresh process without source ONNX.
- Numerical/WAV differences are reported descriptively and do not block execution.
- No minimum speedup is required. Report the observed delta honestly.

## Completed functional smoke

1. Reconstructed all exact frozen graphs and verified their hashes.
2. Generated real component inputs from the complete 0011 legacy CPU chain.
3. Generated one duration external context and reloaded it in an isolated source-absent process.
4. Expanded generation and isolated reload to duration, text, stable-Softplus vector, and vocoder.
5. Preserved normalized raw results plus ORT/QNN profiles.
6. Verified all recorded ORT node events used `QNNExecutionProvider`, fallback was disabled, outputs were finite, and generation/reload output hashes matched.
7. Disclosed the overlapping host-QNN coordination incident and excluded all affected timings/resources.

## Exact component tool contract

Generation:

```bash
python3 tools/qnn_context_component.py generate \
  --component COMPONENT \
  --model SOURCE.onnx \
  --inputs INPUT_DIR \
  --descriptor COMPONENT-context.onnx \
  --backend libQnnHtp.so \
  --profile-prefix profiles/generate \
  --result generate-result.json
```

Reload in a fresh isolated container that mounts only the tool, descriptor, context binary and required raw inputs:

```bash
python3 qnn_context_component.py reload \
  --component COMPONENT \
  --model COMPONENT-context.onnx \
  --inputs . \
  --descriptor COMPONENT-context.onnx \
  --backend libQnnHtp.so \
  --profile-prefix profiles/reload \
  --result reload-result.json \
  --require-source-absent --isolation-root .
```

Both modes set `session.disable_cpu_ep_fallback=1`. Generation additionally sets `ep.context_enable=1` and `ep.context_embed_mode=0`; reload leaves context generation disabled. Both set `ep.context_file_path` and use identical QNN provider options. [`tools/run_host_functional_smoke.sh`](tools/run_host_functional_smoke.sh) preserves the exact Docker mounts, commands, per-component loop, isolation layout, timeout behavior and finalization call; it fails unless explicit serialized-QNN clearance is supplied.

## Next execution sequence after clearance

1. Confirm the shared QNN compiler is clear and acquire `artifacts/locks/heavy-ram.lock` for any heavy host wave.
2. Implement one matched E2E runner with source/context modes and exact per-session/process-ready boundaries.
3. Verify context mode with source ONNX unavailable.
4. Acquire `artifacts/locks/phone.lock`; use Windows `adb.exe` with `ADB_LIBUSB=1`; verify exactly serial `R5CW81PR8SY`, model `SM-S918B`, device `dm3q`, boot complete and authorized state.
5. Use unique scoped staging, hash verification, no personal settings/data, evidence pull, cleanup verification and lock release.
6. Prove QNN provider and physical RPC/accelerator/cycle/HVX evidence separately if profiling perturbs timing.
7. Collect at least three clean fresh-process cold setup runs for each arm. Record process-to-ready and each session construction time; compare distributions without a minimum-speedup gate.
8. In measured processes run one first and five same-session warm complete generations with full deterministic state reset. Record actual WAV duration and RTF.
9. Validate WAV RIFF/PCM structure, sample rate, channel count, samples, duration and SHA-256. Record numerical differences descriptively.
10. Commit only 0023 evidence and notify Pi. Alex owns dashboard ingestion.

## Validation

```bash
python3 -m unittest discover \
  -s experiments/0023-supertonic-qnn-precompiled-context-startup/tests \
  -p 'test_*.py' -v \
&& git diff --check
```
