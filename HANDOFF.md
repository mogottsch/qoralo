# Cross-device handoff

This file is the durable resume point for the Android TTS investigation. Detailed evidence lives in the linked experiments and the generated benchmark registry; Messenger history is not required to continue.

## Current product direction

Moritz's current favorite is the Supertonic 3 official-FP32, stable-Softplus, all-HTP route from experiment 0011. Its exact legacy-v1 sample was accepted and sounds somewhat more natural to him than Pocket. Measured warm RTF was `0.170316`, setup was `22.8147 s`, and process VmHWM was `1,407,393,792 B` (~1.31 GiB). This route remains the leading product candidate, but it still needs a canonical-v2 all-HTP benchmark and production-style precompiled-context startup test.

The current standard input is canonical transcript v2 in [`protocols/android-tts-benchmark/transcript.txt`](protocols/android-tts-benchmark/transcript.txt): 226 bytes, no trailing newline, SHA-256 `424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67`. Follow [the project benchmark skill](.agents/skills/android-tts-benchmark/SKILL.md): setup, one first generation, at least five same-session warm generations with full state reset, actual emitted-duration RTF, memory/thermal/runtime provenance, a hashed WAV, and an exact Moritz listening verdict.

## Authoritative completed state

### Pocket TTS — canonical v2 complete

- Experiment: [`0014`](experiments/0014-pocket-fp-onnx-qnn-htp/)
- Final experiment commit: `751ad6c05b71c9657457845a2984fdf43bd3a234`
- Dashboard ingest: `d8d8b8b6e6f56fbde2b2e5ba26326cf8b8bb0c9f`
- Android CPU: setup `2.597 s`, first RTF `0.412321`, five-warm median RTF `0.414234`, VmHWM `1,446,170,624 B`; accepted WAV SHA `2e9021b972d69e05e5cd301973e2dc17cb8143f2a029bc027ef619a3460c34bd` (“good”).
- Physical fallback-disabled HTP: setup `62.2327 s`, first RTF `0.191013`, five-warm median RTF `0.181643`, VmHWM `2,463,559,680 B`; accepted WAV SHA `601cd622dd0598c23dd7275074763aa37ae79b18a9d777ad946b1eaebd2c58e5` (“good”).
- Separate physical proof: `344` QNN / `0` CPU neural events and exactly `344` RPC, accelerator, cycle, and HVX records. Profiled proof latency is separate from the warm headline.
- The route is fixed-Alba text64/cache512, not voice cloning. The public no-voice-cloning checkpoint's Mimi encoder tensors are zero; old Bria-conditioned evidence exercised an invalid voice contract.

### Supertonic — canonical CPU and historical refresh complete

- Historical exact refresh: [`0020`](experiments/0020-historic-android-benchmark-refresh/), evidence commit `b717b74`, verdict commit `5d70b77`.
  - It preserves legacy transcript v1 and the old three-warm-run harness.
  - Refreshed warm median RTF `0.393086`; exact sample SHA `1cf003d55c81e49983cbe385fdb98868ccdf4b1a6b1482e21bab020c7567ee6e`, accepted “good.”
  - It is a nested dated refresh of route 0008, not a second visible route.
- Canonical-v2 Android CPU: [`0021`](experiments/0021-supertonic-canonical-v2-android-cpu/), evidence commit `b406692`, verdict commit `76b63c7`.
  - Setup `0.853867 s`, first RTF `0.395521`, five-warm median RTF `0.395615`, 15.794172-second output, peak sampled PSS `480,366,592 B`, VmHWM `548,986,880 B`.
  - Exact sample SHA `201f8e79d39e2fbb9db8a64a9f139641db9e27fabb828bcc039286a49c8987df`, accepted “good.”
- Dashboard verdict ingest: `accbde2`.
- The preferred all-HTP FP32 route is still experiment [`0011`](experiments/0011-supertonic-official-fp32-phone-comparison/) and uses legacy-v1 text. Do not present it as canonical-v2.

### MOSS-TTS-Nano — host-valid, physical Android blocked

- Experiment: [`0019`](experiments/0019-moss-tts-nano-qnn-htp-android/)
- Final experiment commit: `de8d22c`
- Cross-device reconstruction handoff: `f2b8df4`, executable-mode follow-up `bcae6b4`
- Hidden exhaustive dashboard ingest: `fa7e96b`
- Corrected fixed-capacity decode and codec pass canonical-v2 CPU equivalence across all 375 calls and final 601-position state.
- Four graphs pass complete host QNN assignment; four generated contexts reload fail-closed as one QNN partition each.
- On the authorized phone, the exact carrier/app-UID direct-QNN path fails at QNN `CreateDevice` with `QNN_DEVICE_ERROR_INVALID_CONFIG` before capability, session assignment, or inference, even after minimal auto-detect configuration and verified RPC/DSP/linker staging.
- Therefore there is no physical HTP result, WAV, RTF, phone-memory metric, or listening verdict. The dashboard record is exhaustive-only and hidden from the compact full-E2E table.
- Resume only from [`experiments/0019-moss-tts-nano-qnn-htp-android/HANDOFF.md`](experiments/0019-moss-tts-nano-qnn-htp-android/HANDOFF.md) and its continuation manifest. It includes clean-machine derivative/context/tool reconstruction. A new device requires fresh authorization; the old phone serial is evidence, not transferable permission.

## Active work to resume

### 0017 — Kokoro canonical-v2 QNN/HTP

Owner at handoff: Jens. Canonical-v2 CPU/export/decomposition state began at `f37a7ad`; the complete cross-device checkpoint is commit `b4a186607c1c859eb828e29948820641dc5d23b2`:

- official Kokoro 0.9.4 American-English KPipeline frontend;
- token shape `[1,235]`, style row 232;
- eager oracle duration sum 602, 361,200 samples / 15.05 s;
- FP32 ONNX CPU output structurally valid and phase-tolerant-policy passing;
- compatibility rewrite bit-exact to its shaped CPU source;
- 18 stages cover all 1,685 nodes and CPU recomposition passes.

The legacy 116-byte staged host batch is feasibility evidence only and produced invalid/clipped divergent audio; do not treat it as the canonical route. The newer canonical 18-stage fallback-disabled host QNN batch was externally interrupted by the requested WSL restart after stages 1–15 completed. Stage 16 reached graph sequencing at 12% but did not finalize or execute; stages 17–18 were not attempted. This is not a stage-16 failure or OOM, and it is not phone-eligible. The durable restart rule is to reconstruct the ignored hash-pinned inputs and rerun all 18 stages from stage 1:

```bash
RUN_ID=device-transfer-rerun experiments/0017-kokoro-onnx-qnn-htp-android/host/run_canonical_v2_staged_host_qnn.sh
```

Read the newest committed [`0017/HANDOFF.md`](experiments/0017-kokoro-onnx-qnn-htp-android/HANDOFF.md), README/RESULTS, and `results/canonical-v2-host-qnn-interrupted-checkpoint.json` before running. No physical canonical Kokoro HTP result or listening verdict exists.

### 0022 — Supertonic precompiled QNN-context startup

Owner at handoff: Sean. Migration checkpoint commit: `a82f710` (the 0022 path is clean and no implementation/context/phone execution has occurred).

Experiment: [`0022-supertonic-canonical-v2-precompiled-qnn-context`](experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/). Goal: compare matched canonical-v2 all-HTP Supertonic arms:

1. source ONNX sessions compiled/finalized by QNN at runtime;
2. precompiled ORT QNN EPContext/context binaries loaded at runtime.

Use the accepted experiment-0011 stable-Softplus all-HTP graph family, exact canonical-v2 text, M1/SID5, fallback disabled, identical runtime/provider/precision, and physical proof. Measure at least three independent cold processes per arm; per-session and total readiness; first + five warm RTF; memory/thermals; source/context/package sizes; host context-generation time; compatibility; output equality; and fresh listening if bytes differ. This experiment exists to test whether the measured `22.8147 s` 0011 cold setup can be materially reduced.

Critical first gate: frozen 0011 graphs require wrapped `T239/L238`, while canonical-v2 naturally wraps to `T235`. Prove that four masked padding positions preserve canonical semantics and exact graph hashes, or report incompatibility; never silently substitute legacy text or re-specialize the route. Resume from [`experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/CONTINUATION.md`](experiments/0022-supertonic-canonical-v2-precompiled-qnn-context/CONTINUATION.md).

## Dashboard

Authoritative files:

- [`docs/android-benchmarks/registry.json`](docs/android-benchmarks/registry.json)
- [`docs/android-benchmarks/index.html`](docs/android-benchmarks/index.html)
- [`docs/android-benchmarks/dashboard.html`](docs/android-benchmarks/dashboard.html)
- [`docs/android-benchmarks/missing-fields.md`](docs/android-benchmarks/missing-fields.md)

At commit `fa7e96b`, validation passed with 43 exhaustive routes, 18 experiments, and 17 verified WAVs. The dashboard-specific cross-device handoff is committed at `eaef377` in [`docs/android-benchmarks/HANDOFF.md`](docs/android-benchmarks/HANDOFF.md). Marius owns dashboard edits. Ingest only committed experiment evidence, preserve proof/first/warm distinctions, and keep listening verdicts bound to exact route and WAV SHA.

## Phone and toolchain constraints

Authorized phone only:

- serial `R5CW81PR8SY`
- model `SM-S918B`
- SoC `SM8550`, ABI `arm64-v8a`, HTP v73

Use Windows ADB, not bare Linux ADB:

```text
ADB_LIBUSB=1
/mnt/c/Users/mgottschling/AppData/Local/Android/platform-tools-pi/platform-tools/adb.exe
```

All phone runs must acquire `artifacts/locks/phone.lock`, recheck exact serial/model/SoC/ABI, use a unique stage, avoid inherited lock FDs in ADB children, verify remote hashes, pull evidence, clean/uninstall, independently verify absence, and release the lock. Android 16 scoped-storage runs may require app-internal `getFilesDir()` staging through a bounded copied APK.

Canonical local environment used by the completed work:

```text
JAVA_HOME=/home/moritz/opt/jdk-17
ANDROID_SDK_ROOT=/home/moritz/opt/android-sdk
ANDROID_HOME=/home/moritz/opt/android-sdk
QAIRT_SDK_ROOT=/home/moritz/opt/qairt/2.49.0.260730
QNN_SDK_ROOT=/home/moritz/opt/qairt/2.49.0.260730
```

The final WSL session used a 29 GiB RAM cap and 8 GiB swap; this was required for the ~22.7 GiB MOSS CPU-equivalence process and allows monitored overlap of smaller jobs. Recheck live headroom rather than assuming the same limits on the next device.

QAIRT version: `2.49.0.260730`. Android patched ORT 1.27.1 `libonnxruntime.so` SHA-256: `40bc591798287525f365e8ded4bbc40e0c4e9440737e876026ec09ba359ac041`. Proprietary SDK binaries, model weights, generated contexts, profiles, and most WAVs are intentionally not tracked; reproduce them from committed scripts/manifests and verify the committed hashes. Do not silently accept licenses, terms, login prompts, model gates, or export attestations on the new device.

## Evidence rules that must survive the move

- Technical execution, structural WAV validity, numerical/acoustic comparison, and human listening are separate claims.
- Only Moritz's explicit route/sample verdict can set accepted or rejected.
- Full HTP means CPU fallback disabled, complete intended neural assignment, every required session invoked, and physical RPC/accelerator/cycle/HVX evidence.
- Host QNN execution is eligibility evidence, not physical phone proof.
- Normalize RTF with actual emitted audio duration and keep setup, first, warm, and profiled-proof measurements distinct.
- Preserve historical records. Add dated/provenance-tracked refreshes rather than rewriting them.
- Missing values remain null with an explicit reason.
- Never commit proprietary Qualcomm binaries, generated models/contexts, raw profiles, serial-bearing logs, or uncurated WAVs.

The standalone interactive model-architecture reference is preserved at [`docs/architectures/index.html`](docs/architectures/index.html), commit `98feb02`.

## Resume checklist on the next device

1. Pull the final pushed `main` and verify this file plus the newest experiment-specific handoffs.
2. Run `git status --short`; do not proceed with an unexplained dirty tree.
3. Install/rebuild local toolchains and ignored artifacts from committed provenance; verify every pinned hash.
4. Verify dashboard determinism with `python3 docs/android-benchmarks/build_registry.py --check` and `python3 docs/android-benchmarks/validate.py` (see its README for exact invocation changes).
5. Check `artifacts/locks/phone.lock` and exact Windows-ADB identity before phone work.
6. Resume 0017 and 0022 only from their newest committed checkpoints. Do not reconstruct state from chat memory.
