# Phone-return handoff

**No phone work is authorized by this handoff.** Wait for Moritz's return and Pi's explicit physical-device slot. Do not start another build or change any frozen APK.

## 1. Coherent UI candidate — FINAL host + synthetic UI approved

Frozen pair: `.local/integration-ready/fb16b90-02/`; source `fb16b90`, effective `app/src` tree `314010f949ba5e33fe7845230c3c3b2b875d7c97`. It combines accepted05 layouts/gallery, owned form acknowledgements and the calibrated readability tests.

- Host: **113 JVM +15 Python**, lint/release/debug/test assembly passed; exact source/input/native-payload preflight independently accepted.
- Nik's **FINAL approval** covers **56/56 actual combined Android tests**, **38/38 fresh final gallery pairs**, all **8 actual-keyboard cells**, **10 matched-pair observations** and **2 PasteIME geometry records**. Exact identities and cleanup passed; emulator stopped, no owned process and canonical lock free. Host113/15 execution was corroborated from logs/XML, not a new Nik rebuild.
- App SHA: `1cfe1419d974ac4e88d3039806a1a6bc849b602ec3036a474cd877f068ed8e7d`.
- Test SHA: `b03d8fe7f87325d3db3bf1d6a349b87fad8955b7e41da905655167aae80af76d`.
- Candidate SHA: `2b3c1ed1c8fe8683f3a87dc1f6491efbd989775218cc8786f4fd4f33457379e7`.

Final report/new-app evidence: [`../evidence/coherent-ui-integration-result/`](../evidence/coherent-ui-integration-result/). Frozen readiness/source/native proofs remain in [`../evidence/coherent-ui-integration/`](../evidence/coherent-ui-integration/). Approval is limited to host/source and synthetic emulator UI, not physical Galaxy/TalkBack/playback/export, native generation, model quality or product E2E. No05 image/test result is substituted for this candidate's new evidence.

## 2. Next native diagnostic — approved scope, never executed

Use the separate frozen **duration-load-only** pair `.local/duration-ready/3fd75c0/`, not the UI APK or test-only text-layout diagnostic.

- Source: `3fd75c06481bcc709d45da5c4933347f348e9079`.
- Candidate SHA: `806c9b6db0766eb3a7455cc2bd23a68c61153d257f4b0f0b7bb98ced6972238d`.
- App SHA: `08cc825128533cab6d1103680b98025171ef7fd014495b0afc04655bcc417290`.
- Test SHA: `120420d6925283ccf44478b58aef29a12e4575bbf6f1027df9a3d98e83cf2c8c`.

**One duration constructor; zero `Session::Run`, Gemma, other-context, TTS or capacity calls; zero retries.** Keep SoC43, ORT1.27.1/QAIRT2.49.0.260730, context bytes, APK-only ADSP path, inherited LD/namespace and disabled CPU fallback unchanged. Only logging is varied. Existing verified Supertonic pack must already be present; this diagnostic stages no models.

Bounds: verification60s, load/close45s, service120s, driver135s, instrumentation150s. A completed collection is not proof of successful QNN initialization; a successful constructor would still not prove accelerator execution.

Procedure and claim limits: [`qnn-duration-load-only.md`](qnn-duration-load-only.md). The controller remains plan-only without `--execute`. Pi must authorize the exact candidate hash, matching S23 identity (`R5CW81PR8SY`), exclusive canonical lock and idle jobs before any physical action. Retain raw failures/cleanup; stop and report rather than retrying or changing paths/configuration.

## 3. What remains unresolved

- **QNN startup:** original real wiring failed during device creation with `QNN_DEVICE_ERROR_INVALID_CONFIG`. No TTS graph, WAV or capacity call was reached. Successful Gemma requests must not be repeated merely to diagnose this failure.
- **Whole-chapter capacity:** pinned T239/L238 contexts allow230 normalized text codepoints before tags and roughly16.58s, not the intended1–2minute chapters. These are known pack limits, not a completed physical whole-chapter experiment. No splitting/stitching, fallback, graph replacement or automatic recovery is approved.
- **Product/hardware:** physical accessibility/media/export, native lifecycle and complete generation remain separate gates. UI success does not close them.

Pi must choose the next physical lane explicitly: UI inspection or the unchanged duration-load diagnostic. They share the application ID; installing one does not preserve the other's installed binary identity. Never mix their app/test pairs. **Normal Gradle output APKs were deliberately restored to old c893 binaries; use only the nominated frozen paths above.**
