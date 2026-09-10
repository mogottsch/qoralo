# Physical duration-load-only result: loader dependency unavailable

**Collection completed; the single duration session constructor failed. No neural inference occurred.** This is a diagnostic result, not QNN readiness, speech/capacity, fallback execution, benchmark or product-E2E approval.

## Exact attempt

- Opaque run ID: `duration-20260910t16001789056033z`.
- Frozen APK source: `3fd75c06481bcc709d45da5c4933347f348e9079`.
- Approved original candidate SHA: `806c9b6db0766eb3a7455cc2bd23a68c61153d257f4b0f0b7bb98ced6972238d` (`approved-candidate-original.json`). The controller's separately serialized run copy remains unchanged under `host/`.
- Installed app SHA: `08cc825128533cab6d1103680b98025171ef7fd014495b0afc04655bcc417290`; test SHA: `120420d6925283ccf44478b58aef29a12e4575bbf6f1027df9a3d98e83cf2c8c`.
- Reviewed host source: `9e2c41d240ac6f104ee96a3e37be19bc69597b3d`; closure: `3ad4c644a7733d1f1feeb7bbbe83532cc0be0f727f32f59dda00c951dd6e202d`.
- Exact S23 identity, PID absence and coherent read-only eligible DB state passed under the uninterrupted canonical lock before both installs and instrumentation. Existing pack verification passed in the service.
- One constructor BEGIN, **zero Run/Gemma/other-context/TTS/capacity calls and zero retries**. The driver recorded `duration_load_failed` at `duration-load`, with2227ms total driver collection time—not an isolated constructor latency measurement.

## Earliest decisive error and downstream chain

All passages below are from original [`device/native-stderr.txt`](device/native-stderr.txt), SHA-256 **`f0559f76c5c2e2e529053b65bc45ed1c005d3610d06014d04d22b582ab9f5180`**:

1. **Line154:** `Failed in loading stub: dlopen failed: library "libcdsprpc.so" not found: needed by …/libQnnHtpV73Stub.so in namespace clns-9`.
2. **Lines156–166:** `loadRemoteSymbols failed with err 4000`, failed transport creation, then `Transport layer setup failed: 14001`.
3. **Line176:** `QnnDevice_create done. status 0x36b1`.
4. **Line195:** `QNN SetupBackend failed Failed to create device. Error: QNN_DEVICE_ERROR_INVALID_CONFIG: Invalid config values`.
5. **Line233:** ORT finally rejects graph nodes assigned to its default CPU EP because fallback is explicitly disabled.

Thus the original INVALID_CONFIG failure is **still present**, now with a concrete preceding loader/transport error. The last CPU-assignment message is downstream, not evidence of unsupported model operators or successful CPU fallback. Logger/backend initialization messages earlier in the trace do not establish successful device/session creation.

[`device/environment.json`](device/environment.json) records `libcdsprpc.so` in this device's `/vendor/etc/public.libraries.txt`. A filesystem-readable file alone would not prove namespace access; here the explicit dlopen error establishes that the V73 stub could not resolve that dependency in the app namespace. The frozen main manifest requests optional `libOpenCL.so`/`libvndksupport.so`, but not `libcdsprpc.so`.

SoC43, ORT1.27.1, QAIRT build `v2.49.0.260730134355`, context bytes, APK-only ADSP, inherited unset LD and disabled CPU fallback were preserved. Line144 says the supplied SOC config is ignored on the real target; it does not justify changing the SoC value. The sole ORT profile contains a Session `model_loading_uri` event, no executed Node/kernel evidence.

## Cleanup and retention

`host/cleanup.json` records no cleanup/settings errors and verified app/generation/test PID absence. Guard before/after settings match. The controller released the lock after cleanup and exited normally. Normal instrumentation completion means a terminal diagnostic record was collected, not that QNN loaded successfully. No follow-on device action was started.

`retained-manifest.json` binds283 public original files/extracted diagnostic members (1,832,416 bytes). The original app-owned diagnostic archive is retained and its members are extracted under `device/`. **Six private DB snapshots and unfiltered logcat/std-error remain local-only**, represented solely by hashes/sizes/exclusion reasons. No database row or device database was cleared, repaired or changed to satisfy eligibility. Old wiring, UI candidates and prior failures remain unchanged.

## Minimal next proposal — separately controlled, not executed

Pi has authorized source/build preparation only for a manifest-only variant of this frozen diagnostic:

```xml
<uses-native-library android:name="libcdsprpc.so" android:required="false" />
```

`required="false"` makes the library optional for **installation**, matching the existing vendor-library declaration style. It does not make QNN optional at execution and does not enable CPU fallback: load must still fail if the required runtime dependency cannot be resolved. The target S23 advertises this library in its saved public list. Final declaration/packaging semantics require focused review.

Keep app code, DEX/resources and all native payloads—including the bridge—unchanged; no ADSP/LD/namespace bypass, SoC/version/context modification or model recompilation. The declaration asks the platform to expose an advertised public native library; it is not an unsupported loader workaround. Bind new source/manifest/app/test/candidate/host identities and inspect the packaged manifest before any separately authorized one-constructor repeat. Success would only close a load diagnostic, not prove inference or whole-chapter capacity. No new APK or phone call has been made by this result packaging.
