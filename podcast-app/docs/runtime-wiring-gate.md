# Debug runtime wiring gate (not executed)

This is a **host-reviewed candidate**, not phone permission or product E2E evidence. Start no ADB until Pi assigns the phone and the exact candidate passes review. Model/trust authorities and fallback policy are unchanged.

## What actually runs

`RealRuntimeWiringTest` (explicit opt-in only) starts the non-exported, debug-only `RuntimeWiringService` in the application's real `:generation` process. The driver stays in the UI process and checks the recorded process name/PID. There is no alternate engine, fake output, downloaded code, generated substitute input, or inference retry.

The service calls the existing `GemmaLiteRtGpuEngine` and `SupertonicQnnHtpEngine` directly, after the same pinned full-pack verifier used by production. It refuses to run alongside queued/running product jobs. It does not create a product episode or call its final-publication APIs.

1. One loaded Gemma GPU engine, one outline request constrained to a one-chapter outline, then **one complete chapter request** against that actual outline. Each request gets a fresh Conversation. An invalid outline fails the gate; it is not replaced with a fixture. Streamed raw response fragments are flushed before JSON validation, including error/timeout output.
2. Unload Gemma. Load the four persistent external QNN/HTP sessions with fallback disabled. Render the exact canonical TTS short input once; validate the resulting PCM16 mono 44.1-kHz WAV independently.
3. Send the separately pinned realistic complete chapter once to that same loaded TTS adapter. Success means observing the **specific native text-capacity rejection**, not just any exception, and an empty capacity-output directory. No waveform from that rejected chapter is published. Then close all four sessions and flush ORT/QNN profiles.

The retained T239/L238 pack has capacity for only 230 normalized code points / approximately 16.58 seconds. The larger chapter is intentionally rejected. **Passing this wiring gate does not make the podcast app's complete-chapter product path feasible.** No chunking, stitching, fallback, new graph capacity, or workaround is authorized here.

## Pinned bounds

Inputs, hashes, request counts, ceilings and deadlines live in `app/src/debug/assets/wiring/contract.json`. Its exact SHA-256 is compiled into both the debug policy and host tooling. Input mutations fail before inference.

| Stage | Deadline | Requests/output ceiling |
|---|---:|---|
| Full data-pack verification | 120 s | No inference |
| Gemma GPU load | 180 s | One engine |
| Outline | 180 s | Exactly one request; 256 output tokens maximum |
| Complete chapter | 300 s | Exactly one request; 768 output tokens maximum |
| Gemma close | 60 s | No subsequent LLM load |
| Four QNN session load | 120 s | One set of four sessions |
| Canonical short render | 90 s | Exactly one complete render; 5 vector steps |
| Realistic chapter rejection | 30 s | Exactly one call; zero published audio |
| QNN close/profiles | 30 s | No further requests |

Total service deadline: 1,200 s. Driver acknowledgement: 30 s. Driver total: 1,230 s. Host instrumentation timeout: 1,260 s. Serialized API request plus system-instruction cap: 4,096 UTF-8 bytes, checked before native submission (a conservative byte guard, not a measured input-token count). Raw response cap: 65,536 bytes (the crossing fragment is retained). Evidence cap: 256 MiB, monitored once per second. All token ceilings are ceilings, not actual token counts. The service has an independent scheduled process-kill watchdog because coroutine cancellation cannot reliably interrupt JNI. A timeout marker is written before killing **only its own verified `:generation` PID**. The host also bounds and reaps its ADB children and force-stops only the test app on failure.

Staging is separate from those runtime deadlines: each APK install ≤180 s; each missing-pack push and copy ≤600 s; ordinary ADB command ≤30 s; evidence pull ≤120 s. Existing mismatching model packs are never overwritten. Missing packs are copied into a private `.incoming-<run>` directory before activation; an interrupted copy stays there for diagnosis instead of masquerading as an installed pack. No background power, performance, or charging settings are tuned.

## Evidence and proof boundaries

- Per-run private directory: `files/wiring/<new-run-id>/`. Reusing an ID or output name fails rather than overwriting a failure.
- Pinned raw sources/instructions/TTS inputs, contract bytes, installed APK and test-APK hashes, build fingerprint, PID/process name.
- Gemma serialized requests/system prompts/options, streamed raw text, callback events/errors. Actual token IDs/counts and exact EOS-vs-ceiling telemetry are not exposed here and remain unknown; callback count is not a token count.
- Actual process maps/FD/status snapshots after load/inference, native stdout/stderr, host logcat, and four ORT/QNN profile pairs. Native profiling is debug-only; release rejects a nonempty profile directory.
- Canonical WAV format/sample-count/SHA, normalized inputs, exact capacity exception, output-directory contents, stage errors/deadlines, terminal result and file inventory. Host pulling preserves partial evidence after process death even if final inventory is missing.
- Runtime-reported readiness strings are explicitly labeled declarations, **not accelerator proof**. Host analysis requires actual QNN node provider records plus positive RPC execute and accelerator cycle observations per component. GPU maps/driver descriptors are observations for independent review, not an automatic delegation claim. Missing profiles/telemetry leave physical proof incomplete without deleting otherwise valid output.
- This is an application-specific Gemma wiring workload, **not** the fixed generic LLM benchmark or its 1+5+5+5 campaign. The TTS text is canonical, but one profiled render is not a warm campaign or RTF comparison. Nothing is added to either benchmark registry.
- Only Moritz can accept/reject the exact listening WAV. Default: `not_reviewed`.
- Atomic moves retain their previous host evidence; sudden-power-loss durability is not claimed.

## Separate test lanes

| Lane | What it proves | Physical bound |
|---|---|---|
| `RealRuntimeWiringTest` | Real adapter/process wiring and expected capacity rejection, subject to provider evidence review | Limits above |
| `ScreenSemanticsTest` | Synthetic UI fixture semantics only, including the synthetic player WAV; **not model audio** | Seven methods, ≤60 s each; host ≤600 s |
| Existing JVM repository/dispatch/watchdog/gate tests | Deterministic host lifecycle policies, not Android process/service behavior | Host suite only |
| Production `GenerationService` duplicate-intent, timeout and kill/reconciliation scenarios | **Not exercised by this harness**; require separately reviewed physical scenarios after wiring | Future proposed bounds: duplicate/claim 30 s; kill/reconcile 30 s; controlled timeout 30 s. No six-hour wait or native inference during synthetic lifecycle probes |

UI tests still need actual execution plus per-frame screenshots, keyboard/inset/touch-target review and TalkBack. The controller's final screenshot is an observation, not visual approval of all frames. This harness does not silently claim those remaining tests are done.

## Host-only preparation

Reuse unchanged trusted pack/native evidence. Do not re-prepare or hash multi-gigabyte inputs just because the harness changed. With existing authorized native injection:

```bash
cd podcast-app
./gradlew --max-workers=2 :app:testDebugUnitTest :app:lintDebug \
  :app:assembleDebug :app:assembleDebugAndroidTest :app:compileReleaseKotlin :app:testNativePolicies
python3 -m unittest discover -s tools/tests -v
./tools/prepare_wiring_gate.py --output .local/wiring-ready/<new-id>
```

The last command checks new APK/test-APK hashes and packages, exact embedded wiring input bytes, all eight native library identities with the existing APK verifier, and unchanged pack manifest pins. It writes a candidate with `phoneAuthorized:false`. A dirty source candidate cannot execute. Release builds have no service/assets/enable function and retain normal request limits and synchronous output behavior.

## Future physical invocation — NOT authorized by this document

The physical controller defaults to **plan-only**. Even that validates the APK candidate locally, but invokes no ADB. Actual execution additionally requires `--execute`, the separately approved candidate SHA-256, and `PODCAST_PHONE_PRIORITY=approved` after Pi's explicit assignment. A single file lock owns identity/install/stage/execute/capture/restoration/cleanup; children do not inherit it.

```bash
# Plan only:
./tools/run_wiring_gate.py --candidate .local/wiring-ready/<id>/candidate.json \
  --output .local/wiring-phone/<id> --run-id wiring-<id>

# Only in an assigned phone slot, with the phone unlocked by its user:
PODCAST_PHONE_PRIORITY=approved ./tools/run_wiring_gate.py \
  --candidate .local/wiring-ready/<id>/candidate.json \
  --output .local/wiring-phone/<id> --run-id wiring-<id> \
  --approved-candidate-sha256 <reviewed-candidate-sha256> --execute
```

The controller captures the three animation settings before any change. Only the separately selected `--suite ui` changes them, and restoration records each key **before** mutation, handles partial command failure, restores absent settings via deletion, and verifies read-back. Errors are retained in `cleanup.json` and do not count as clean completion. It captures before/after thermal/battery conditions, preserves raw failure files, removes only its newly created scratch root, and reaps child processes before releasing the lock. It retains the app/test packages and private run evidence for review; no user data clearing or uninstall is performed.

Analyze without extracting unsafe archive paths:

```bash
./tools/analyze_wiring_evidence.py --archive .local/wiring-phone/<id>/private-evidence.tar \
  --candidate .local/wiring-ready/<id>/candidate.json --run-id wiring-<id> \
  --output .local/wiring-phone/<id>/analysis.json
```

Every failure remains evidence. Do not automatically rerun it or lower the limits. Report the exact failed phase and missing proof to Pi/Nik before the next physical action.
