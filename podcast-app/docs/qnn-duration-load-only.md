# QNN duration-session load-only diagnostic — baseline, host-only

## Accepted failure being investigated

The immutable collection in `evidence/runtime-wiring/wiring-20260910t085908z/` reached the first duration-context session constructor, then reported **QNN_DEVICE_ERROR_INVALID_CONFIG during device creation**. CPU fallback was disabled and the session failed. No neural graph ran, no four-session readiness was established, and no TTS or capacity result exists. The successful Gemma requests must not be repeated to diagnose this failure.

## Source comparison (no phone queries used)

| Item | Accepted experiment 0023 phone runner | Failed app wiring |
|---|---|---|
| Process | Native executable started by ADB shell | APK native bridge in `:generation`; recorded UID/GID 10755, Seccomp 2 |
| Loader | Shell environment with `LD_LIBRARY_PATH=<stage>/lib` | Android app classloader namespace; retained logcat reports bridge load in `clns-9` |
| `ADSP_LIBRARY_PATH` | `<stage>/lib;/vendor/lib/rfsa/adsp;/vendor/dsp/cdsp;/system/lib/rfsa/adsp;/vendor/dsp` | APK native-library directory only |
| FastRPC | Accepted v73 stub has `DT_NEEDED libcdsprpc.so` | Same stub bytes; app manifest does not declare that vendor library. No explicit loader denial was retained in the failed run |
| `soc_model` | `43` | `43` |
| HTP mode / graph I/O quantization | `burst` / `0` | `burst` / `0` |
| CPU fallback | Disabled | Disabled |
| ORT / QAIRT payload | Pinned ORT 1.27.1 and QAIRT 2.49.0.260730 | Same pinned injected bytes; no version change proposed |

Sources inspected:

- `experiments/0023-supertonic-qnn-precompiled-context-startup/device/run_phone_campaign.sh`, `run_native` environment.
- `experiments/0023-supertonic-qnn-precompiled-context-startup/phone/supertonic_qnn_context_runner.cc`, `Options` provider/session settings.
- Pinned QAIRT `include/QNN/QnnTypes.h`: `QNN_SOC_MODEL_SM8550 = 43`.
- Pinned ORT source `onnxruntime/core/providers/qnn/builder/qnn_backend_manager.cc`:
  - `LoadBackend` honors an existing ADSP path and prints a generic warning.
  - `InitializeQnnLog` maps ORT VERBOSE to QNN VERBOSE; `QnnLogging` forwards callbacks only when the default logger enables VERBOSE.
  - `SetupBackend` queries/logs backend build identity, initializes logging/backend, then calls `CreateDevice` **before** profiling/context setup.
  - `CreateDevice` adds the supplied SoC custom config; ARCH is added only when requested. The app does not request ARCH.
- Host `readelf -d` on the exact pinned v73 stub confirms `libcdsprpc.so` dependency and SONAME.

These establish concrete differences and a logging gap, not causation. A generic ADSP warning does not prove the vendor suffix omission caused the error; `soc_model=43` is not an established wrong-chip setting.

## Diagnostic candidate (not run)

Debug-only non-exported `DurationLoadService` runs in `:generation`, driven solely by opt-in `DurationLoadOnlyTest`. It verifies the unchanged full Supertonic data pack and exact duration descriptor, then calls one dedicated native function:

1. Record UID/GID/PID, actual ORT runtime version, loaded ORT path, APK library paths/hashes, inherited LD/ADSP environment, SELinux context, and readable linker/public-library configuration. Inaccessible files are explicitly recorded as unavailable.
2. Set ADSP to **the same APK-only directory as the failed baseline**, inherit LD unchanged, and retain `soc_model=43`, burst, graph I/O quantization=0, and disabled CPU fallback. No new vendor library declaration, extra dlopen probe, or other namespace/path adjustment is made.
3. Construct **one** duration `Ort::Session` with the same external descriptor/binary and detailed profiling setting. Only diagnostic log verbosity changes: ORT environment/session VERBOSE (with a native stderr callback) enables the existing ORT→QNN log bridge. ORT logs the queried backend SDK build ID and device setup path. Recorded provider option values are real options supplied to ORT; the source-derived low-level device-config expectation is labeled as such, not misrepresented as a direct struct interception.
4. If construction returns, record counts, end profiling, and close the session. There is **no `Session::Run`, tensor submission, Gemma load, text/vector/vocoder session, audio output, or capacity call**. A constructor failure is retained verbatim, not retried or relabeled as a successful backend.

Filesystem readability probes do not prove Android linker namespace visibility. Actual loader/QNN/FastRPC messages and maps must be reviewed. This diagnostic cannot prove accelerator execution because it never requests any.

Pinned contract: `app/src/debug/assets/duration-load/contract.json`.

- Supertonic verification: ≤60 s.
- One native load/profile-close/destruction call: ≤45 s including close.
- Service hard deadline: 120 s; driver: 135 s; host instrumentation: 150 s.
- Evidence budget: 64 MiB on device.
- Native calls: one constructor, zero Run calls, zero retries.
- Packages/private evidence retained; exact app/:generation/test PID absence checked in controller cleanup.

The independent watchdog kills only its own verified generation process if JNI hangs. The driver distinguishes a received failure record from a successful load. An instrumentation `OK` result means collection completed, not that QNN initialized successfully.

## Separate hypotheses — NOT applied

1. **Vendor ADSP suffix parity:** if baseline verbose logs support a DSP search-path failure, propose appending the exact accepted 0023 vendor suffixes. This would be a separately reviewed single-variable candidate, not an automatic retry.
2. **Vendor FastRPC namespace access:** if logs show namespace/linker denial for `libcdsprpc.so`, propose the minimal platform-supported vendor-library declaration or delivery adjustment. Do not infer denial from filesystem accessibility alone, preload alternate libraries, or bypass platform security.
3. Inspect deviceCreate logging/config fields before proposing any config change. Keep SoC43, versions, compiled context/capacity and fallback invariant unchanged during baseline diagnosis. Do not recompile models or replace QAIRT to explore this pre-execution failure.

## Host preparation and later authorization

Preserve nominated `c893963` APK/test bytes and candidate. New diagnostic builds must be frozen under a **new** local path and receive their own exact-byte preflight/approval.

```bash
# Host tests/build only. Do not run on the physical phone.
python3 -m unittest discover -s tools/tests -v
./gradlew --max-workers=2 :app:testDebugUnitTest :app:lintDebug \
  :app:assembleDebug :app:assembleDebugAndroidTest :app:compileReleaseKotlin :app:externalNativeBuildRelease
./tools/prepare_duration_load_gate.py --apk <new-debug-apk> --test-apk <new-test-apk> \
  --output .local/duration-ready/<new-id>
./tools/run_duration_load_gate.py --candidate .local/duration-ready/<new-id>/candidate.json \
  --output .local/duration-phone/<new-id> --run-id duration-<new-id>
```

The controller is plan-only without `--execute`. Physical collection requires a separate Pi slot, canonical `phone.lock`, exact new candidate approval hash, matching S23 identity, idle product jobs, and the already installed unchanged Supertonic pack. It installs no models, changes no settings, starts no Gemma request and performs no inference. Each APK install is bounded by180 s and evidence pull by120 s; all normal commands by30 s. Raw stdout/stderr/logcat/failure records and cleanup are retained. No physical call is authorized by this document.

## Host classifier correction

`profile_observations` now requires actual ORT `cat=Node`, `ph=X`, `*_kernel_time` records with finite positive durations and QNN provider attribution, plus positive finite backend ROOT RPC-execute (`US`) and accelerator-execute (`CYCLES`) rows. Session metadata, Node fences, missing providers, nonfinite/zero values, wrong units and CPU execution records cannot establish its predicate. Synthetic regression tests cover the prior metadata-only false positive. This changes future classification only; neither prior collection/raw archive nor accepted partial-result packaging is rewritten.
