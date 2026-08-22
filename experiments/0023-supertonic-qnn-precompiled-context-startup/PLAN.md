# Experiment 0023 plan

## Current state

All four exact experiment-0011 graph identities passed host QNN HTP external-context generation and independent source-unavailable reload. The preliminary functional wave overlapped experiment 0017, so its timing/resource values remain excluded. After explicit Pi clearance, a separate clean ten-process setup campaign completed under the full-lifetime heavy-RAM lock with five fresh containers per arm and no QNN overlap. Median exact four-session readiness was 24.731559668001864 seconds from source ONNX versus 0.2008688030000485 seconds from external context. Phone work remains paused pending review.

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
8. Ran a clean balanced `S-C-C-S-C-S-S-C-S-C` campaign under one exclusive `heavy-ram.lock` interval.
9. Recorded five fresh-process/fresh-container session-readiness values per arm, exact component setup intervals, artifact identities and timing boundaries.
10. Observed source/context medians of 24.731559668001864/0.2008688030000485 seconds: a 24.530690865001816-second delta and 99.1878037386379% reduction for the exact host setup boundary.

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

## Clean host timing command

[`tools/run_clean_setup_campaign.sh`](tools/run_clean_setup_campaign.sh) requires explicit clearance, acquires `artifacts/locks/heavy-ram.lock` nonblocking for the full campaign, rejects an active QNN/compiler process, stages source-only and context-only packages, and launches each measurement in a fresh Docker container. [`tools/qnn_setup_timing_process.py`](tools/qnn_setup_timing_process.py) records script-entry, exact four-constructor sequence, per-component intervals and ready memory before post-ready hashing. [`tools/finalize_clean_setup_campaign.py`](tools/finalize_clean_setup_campaign.py) freezes all ten raw records and distributions.

## Next execution sequence after review

1. Implement one matched E2E runner with source/context modes and exact per-session/process-ready boundaries.
2. Verify context mode with source ONNX unavailable.
3. Acquire `artifacts/locks/phone.lock`; use Windows `adb.exe` with `ADB_LIBUSB=1`; verify exactly serial `R5CW81PR8SY`, model `SM-S918B`, device `dm3q`, boot complete and authorized state.
4. Use unique scoped staging, hash verification, no personal settings/data, evidence pull, cleanup verification and lock release.
5. Prove QNN provider and physical RPC/accelerator/cycle/HVX evidence separately if profiling perturbs timing.
6. Collect at least three clean fresh-process phone setup runs for each arm. Record process-to-ready and each session construction time; compare distributions without a minimum-speedup gate.
7. In measured processes run one first and five same-session warm complete generations with full deterministic state reset. Record actual WAV duration and RTF.
8. Validate WAV RIFF/PCM structure, sample rate, channel count, samples, duration and SHA-256. Record numerical differences descriptively.
9. Commit only 0023 evidence and notify Pi. Alex owns dashboard ingestion.

## Validation

```bash
python3 -m unittest discover \
  -s experiments/0023-supertonic-qnn-precompiled-context-startup/tests \
  -p 'test_*.py' -v \
&& git diff --check
```
