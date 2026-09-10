# Bounded wiring attempt — stopped at QNN device creation

**Outcome:** independently reviewed valid **partial** collection ending in `qnn-load` failure. No retry, no TTS output, no capacity test, no full wiring success or product E2E. Provider acceptance is limited to the core Gemma prefill/decode delegation observations below.

This is the second explicitly authorized collection attempt using the unchanged `c893963` controller and nominated candidate. The earlier transport-only failure is retained separately as `../wiring-20260910t084936z/`.

## Identity

- Reviewed candidate SHA-256: `2797337eaeef41db47d03fbb1354d6330cc6677b282272eb03fee2477b9110f6`
- Installed app APK: `f61aba1664ece228ea3b0e517e574d715a55cc92d75f11b92269d44e1b0da379`
- Installed test APK: `4cd7c1ab251e59b452db92e23a6829834c7eb7fed556f158e3979b0f04d95168`
- Device: `R5CW81PR8SY`, `SM-S918B`, `SM8550`; full build fingerprint is in `driver-identity.json`.
- Instrumentation/UI PID: `14789`; actual `:generation` PID: `14857`.

The installed APK hashes recorded by instrumentation match the nominated artifacts. Both model packs passed the app's pinned verification. The controller's `candidate.json` copy is pretty-printed; the nominated original remains unchanged in `.local/wiring-ready/c893963/`.

## Reached

- APK installation and missing-pack staging succeeded.
- Gemma engine load completed.
- One outline and one whole-chapter request returned parseable output, preserved verbatim with Markdown fences in the two `gemma-*-raw.txt` files.
- The chapter contains **82 words**, below the requested 120–160 range. Logical request completion is not instruction-following or content-quality acceptance. Output-token count and EOS-versus-ceiling stop telemetry were not collected.
- Gemma was closed before QNN initialization.

Nik independently accepted the completed logical requests and **core decode/prefill GPU delegation**: native logs record full `LITERT_CL` replacement of decode (`2068/2068`) and both prefill (`1107/1107`) graphs. CPU embedding work is also explicit: 2 of 8 embedder operations and 1 of 42 per-layer-embedder operations were replaced by XNNPACK. The missing dynamic OpenCL sampler warning selects a statically linked C API; that warning is not proof of CPU sampling or whole-model CPU fallback. Exact sampler placement remains unknown. This is not a blanket “all GPU/no CPU” pipeline claim or per-kernel hardware-counter proof.

## First blocker

App-owned logcat reports, during the first duration-context session constructor:

```text
QNN SetupBackend failed Failed to create device.
Error: QNN_DEVICE_ERROR_INVALID_CONFIG: Invalid config values
```

The subsequent fail-closed error is:

```text
This session contains graph nodes that are assigned to the default CPU EP,
but fallback to CPU EP has been explicitly disabled by the user.
```

The fallback guard prevented an alternate execution route. Four-session readiness was not reached. The only duration ORT profile contains a `Session/model_loading_uri` event, **not a Node execution event**. There is no QNN accelerator execution evidence to accept.

Neither the canonical short render nor the realistic-chapter capacity call ran. No WAV exists, and the expected T239/L238 rejection remains untested on-device. Do not infer it from this different initialization failure.

## Retained evidence

- Exact controller commands, stdout/stderr/exit codes, terminal failure and cleanup records.
- Verbatim raw and parsed Gemma outputs, request/options/input bytes, native stderr, maps/FD/status snapshots, and partial profile in the lossless `private-evidence.tar.gz` copy.
- App-owned logcat lines for generation PID `14857` and driver PID `14789`, copied byte-for-byte to `app-owned-logcat.txt`. The full unfiltered phone logcat remains local; its size/hash and selection rule are recorded in `result.json` to avoid publishing unrelated phone-app logs.
- Stage transitions and all raw callback events in `events.jsonl`.
- Independent cleanup-only identity/PID query evidence in `post-cleanup-verification/`.

No analyzer Boolean was used as accelerator proof. No throughput, warm distribution, listening acceptance, UI/lifecycle acceptance or canonical benchmark result is published.

## Cleanup

The reviewed controller force-stopped the exact app and test packages, pulled private evidence, and removed/verified absence of its scratch root. Those commands returned zero. Wiring did not change the captured animation settings.

Pi separately authorized one cleanup-only identity and exact-process check. Under reacquired `phone.lock`, identity matched and one `pidof` invocation for the app, `:generation`, and test process names returned exit 1 with empty stdout/stderr: all three were absent. No launch, install, inference or settings mutation occurred in that verification. The lock was released; local controller/ADB children were absent. Packages and private evidence remain installed as planned.

## Validation

`SHA256SUMS` binds the committed evidence. The gzip decompresses byte-for-byte to the original pulled archive hash in `result.json`. Inspect the archive without executing its contents. Follow-up work requires a new scoped handback; no automatic phone retry or runtime change is authorized here.
