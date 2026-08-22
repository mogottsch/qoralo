# Experiment 0023 plan

## Current state

All four exact experiment-0011 graph identities passed host QNN HTP external-context generation and independent source-unavailable reload. The preliminary functional wave overlapped experiment 0017, so its timing/resource values remain excluded. After explicit Pi clearance, a separate clean ten-process setup campaign completed under the full-lifetime heavy-RAM lock with five fresh containers per arm and no QNN overlap. Median exact four-session readiness was 24.731559668001864 seconds from source ONNX versus 0.2008688030000485 seconds from external context. A bounded matched Android runner, stage and native-Linux adb transport contract are prepared without phone access. Execution remains paused pending preparation review and device availability.

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

## Prepared Android campaign

- [`phone/supertonic_qnn_context_runner.cc`](phone/supertonic_qnn_context_runner.cc) supports matched `source`/`context` arms and separate `setup`/`e2e`/`proof` actions.
- [`tools/build_phone_runner.sh`](tools/build_phone_runner.sh) cross-compiles Android API 28 AArch64 with warnings as errors.
- [`tools/prepare_phone_stage.py`](tools/prepare_phone_stage.py) verifies every graph/context/runtime hash and produces the ignored stage plus remote manifest.
- [`protocol/phone-transport-contract.json`](protocol/phone-transport-contract.json) documents native Linux `/usr/bin/adb` as the platform adaptation; the historical Windows path is absent.
- [`device/run_phone_campaign.sh`](device/run_phone_campaign.sh) holds `phone.lock`, performs identity/space/hash gates, runs the bounded campaign, samples memory, pulls evidence and verifies scoped cleanup.
- [`tools/validate_phone_campaign.py`](tools/validate_phone_campaign.py) separates setup, E2E and profiled proof evidence; numerical differences are descriptive.

The current retained Android ORT 1.27.1 library hash is `643c6f6fd3d2b375ca8f2407a1695acaf55320b8e947adc4284665640fdc3ae9`. The historical 0011 library hash is not locally retained. Both 0023 arms therefore use the current rebuild identically; this is a documented pragmatic runtime adaptation, not a claim of exact 0011 binary reuse.

## Next execution sequence after preparation review

1. Wait for actual device availability; do not expand the bounded campaign.
2. Acquire `artifacts/locks/phone.lock`; use native Linux `/usr/bin/adb`; verify exactly serial `R5CW81PR8SY`, manufacturer `samsung`, model `SM-S918B`, device `dm3q`, SoC `SM8550`, ABI `arm64-v8a`, Android 16/API 36, boot complete, verified boot green, flash locked and authorized state.
3. Use unique scoped staging, minimum-free-space and remote hash gates, no personal settings/data, evidence pull, cleanup verification and lock release.
4. Collect exactly three clean fresh-process phone setup runs per arm. Record process-entry-to-ready and each session construction time; compare distributions without a minimum-speedup gate.
5. Run one separate six-generation E2E process per arm: one first plus five same-session warm generations with full deterministic state reset. Record actual WAV duration and RTF.
6. Delete source models and verify absence before every context-arm process.
7. Run one separate profiled context generation and require QNN-only ORT nodes plus RPC/accelerator/cycle/four-HVX-thread evidence. Exclude it from setup/E2E timing.
8. Validate WAV RIFF/PCM structure, sample rate, channel count, samples, duration and SHA-256. Record numerical differences descriptively. Transfer historical listening only for an exact accepted WAV hash; otherwise mark `not_reviewed`.
9. Commit only 0023 evidence and notify Pi. Alex owns dashboard ingestion.

## Validation

```bash
python3 -m unittest discover \
  -s experiments/0023-supertonic-qnn-precompiled-context-startup/tests \
  -p 'test_*.py' -v \
&& git diff --check
```
