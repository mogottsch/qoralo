# Phone-return handoff

**No further phone work is authorized by this handoff.** Explicit load-only and one canonical TTS slots completed; another device action needs Pi's new slot. Frozen candidates remain unchanged. Git push/external publication is held for coordinated historical privacy cleanup.

## 1. Coherent UI candidate — FINAL host + synthetic UI approved

Frozen pair: `.local/integration-ready/fb16b90-02/`; source `fb16b90`, effective `app/src` tree `314010f949ba5e33fe7845230c3c3b2b875d7c97`. It combines accepted05 layouts/gallery, owned form acknowledgements and the calibrated readability tests.

- Host: **113 JVM +15 Python**, lint/release/debug/test assembly passed; exact source/input/native-payload preflight independently accepted.
- Nik's **FINAL approval** covers **56/56 actual combined Android tests**, **38/38 fresh final gallery pairs**, all **8 actual-keyboard cells**, **10 matched-pair observations** and **2 PasteIME geometry records**. Exact identities and cleanup passed; emulator stopped, no owned process and canonical lock free. Host113/15 execution was corroborated from logs/XML, not a new Nik rebuild.
- App SHA: `1cfe1419d974ac4e88d3039806a1a6bc849b602ec3036a474cd877f068ed8e7d`.
- Test SHA: `b03d8fe7f87325d3db3bf1d6a349b87fad8955b7e41da905655167aae80af76d`.
- Candidate SHA: `2b3c1ed1c8fe8683f3a87dc1f6491efbd989775218cc8786f4fd4f33457379e7`.

Final report/new-app evidence: [`../evidence/coherent-ui-integration-result/`](../evidence/coherent-ui-integration-result/). Frozen readiness/source/native proofs remain in [`../evidence/coherent-ui-integration/`](../evidence/coherent-ui-integration/). Approval is limited to host/source and synthetic emulator UI, not physical Galaxy/TalkBack/playback/export, native generation, model quality or product E2E. No05 image/test result is substituted for this candidate's new evidence.

## 2. Duration load/close — manifest variant succeeded, zero inference

The tested manifest-only derivative is `.local/duration-native-library-ready/cc473f8/`, candidate `ac4d325f7f5b66ca5ff144590b991775d616c18bfb9ac56065f3c66c6af89fb2`, app `78488901d63032b87d2d575c6bec5b7f578b3a7ee38c92e3c633ed943dcb96ab`, with the unchanged baseline test below. It is **not** the approved coherent UI binary.

Baseline run `duration-20260910t16001789056033z` failed on V73 stub resolution of public `libcdsprpc.so` in the app namespace. A manifest-only declaration was separately reviewed. Its first slot stopped before install on an existing test-package PID; Pi's separate scoped maintenance and a fresh explicit slot followed. New run **`duration-fastrpc-20260910t162500z` created and closed one duration session successfully, with zero Run/Gemma/other-context/TTS/capacity calls**. QNN device creation/status0 and session initialization were logged; cleanup/settings/actual-name PID absence passed and the lock was released. See [`../evidence/qnn-duration-load-result/duration-fastrpc-20260910t162500z/`](../evidence/qnn-duration-load-result/duration-fastrpc-20260910t162500z/).

The embedded baseline contract remains intact, but its no-new-library namespace description is explicitly overridden by the reviewed optional public `libcdsprpc.so` declaration. All other code/native/context/options remain unchanged. The **baseline** identities below are retained for comparison, not as the installed manifest variant:

- Source: `3fd75c06481bcc709d45da5c4933347f348e9079`.
- Candidate SHA: `806c9b6db0766eb3a7455cc2bd23a68c61153d257f4b0f0b7bb98ced6972238d`.
- App SHA: `08cc825128533cab6d1103680b98025171ef7fd014495b0afc04655bcc417290`.
- Test SHA: `120420d6925283ccf44478b58aef29a12e4575bbf6f1027df9a3d98e83cf2c8c`.

**One duration constructor; zero `Session::Run`, Gemma, other-context, TTS or capacity calls; zero retries.** Keep SoC43, ORT1.27.1/QAIRT2.49.0.260730, context bytes, APK-only ADSP path, inherited LD/namespace and disabled CPU fallback unchanged. Only logging is varied. Existing verified Supertonic pack must already be present; this diagnostic stages no models.

Bounds: verification60s, load/close45s, service120s, driver135s, instrumentation150s. A completed collection is not proof of successful QNN initialization; a successful constructor would still not prove accelerator execution.

Historical scope: [`qnn-duration-load-only.md`](qnn-duration-load-only.md); the separately reviewed host guard is described in [`duration-phone-guard.md`](duration-phone-guard.md), source `9e2c41d`, closure `3ad4c644a7733d1f1feeb7bbbe83532cc0be0f727f32f59dda00c951dd6e202d`. The controller remains plan-only without `--execute` and requires both candidate and host-guard approval. Any new physical action needs Pi's slot, exact identity, continuous lock and eligible durable state. Private DB snapshots remain local-only.

The separately reviewed TTS-only harness then proceeded directly to one four-context canonical request (section3), without an intermediate four-load-only phone gate. It used no Gemma, splitting/stitching, retries or deliberate capacity probe. That completed slot authorizes no further execution.

## 3. First canonical TTS WAV — produced, listening not reviewed

Run `tts-only-20260910t171039z` used candidate `3cf46e271a515ed30125c09ac6f9891c808218e6871ef39adee7767b0e4c6fed` (app `024f5cd58761f5816163b907293e51867a5c0f3962b37c7aa6416c18ad47228d`, test `7066cbee3abdeff69dbaa5bd0f1ff6031614061f444237488b407aa44bc3263d`). The separately approved TTS controller is `a62d204c380a5b2d0c8f7c5bd94729b6f823e18200feed2ebe24fa73962bec3c`, with unchanged3ad guard. This debug-engineering app, not the coherent UI candidate, is currently the last app installed by Janek.

One complete226-byte request produced **15.640612s mono44.1kHz PCM16**: four-context load669.641ms, profiled render6441.160ms, first-request RTF0.411823. WAV SHA **`bcc277bce02cdb3042a853c91172abc6c99c325657cdce4829b2eabfc79c163a`**. [Safe retained result/WAV](../evidence/tts-only-result/tts-only-20260910t171039z/). Nik verified real QNN Node1/1/5/1 and matching RPC/cycle execution records; final full saved-evidence audit is pending. Cleanup/settings/PID absence passed and the lock was released. No replay or maintenance kill was needed.

**Listening remains not_reviewed; Moritz alone decides the exact sample.** This is one first profiled engineering request, not a warm campaign, long chapter or product E2E. Full DB/battery/thermal/logcat originals stay private; public conditions are explicitly labelled core extracts.

## 4. What remains unresolved

- **Product/native workflow:** canonical four-context TTS execution now produced one WAV, but the complete production generation/job/lifecycle flow and its integration with the approved UI have not been accepted. No further Gemma or TTS run is implied.
- **Whole-chapter capacity:** pinned T239/L238 contexts allow230 normalized text codepoints before tags and roughly16.58s, not the intended1–2minute chapters. These are known pack limits, not a completed physical whole-chapter experiment. No splitting/stitching, fallback, graph replacement or automatic recovery is approved.
- **Product/hardware:** physical accessibility/media/export, native lifecycle and complete generation remain separate gates. UI success does not close them.

Pi must choose and approve the exact next physical candidate/scope explicitly; no unchanged retry is implied. The UI and diagnostic share the application ID; installing one does not preserve the other's installed binary identity. Never mix their app/test pairs. **Normal Gradle output APKs were deliberately restored to old c893 binaries; use only the nominated frozen paths above.**
