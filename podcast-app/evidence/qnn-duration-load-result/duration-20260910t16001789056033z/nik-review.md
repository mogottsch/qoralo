# Nik saved-evidence review — first duration-load-only collection

**Accepted as a valid retained failed load-only diagnostic. QNN initialization did not succeed. The earliest decisive failure is now evidenced: the app linker namespace cannot resolve the V73 stub's libcdsprpc.so dependency.** No new device action was performed for this review.

Original collection: `podcast-app/.local/duration-phone/duration-20260910t16001789056033z/`.
Raw archive SHA-256: `067524fb7c9b0308c4b45cc9b7a00e74b6b22577935fd7e5f1fc3bbe39f4611b`.
Native stderr SHA-256: `f0559f76c5c2e2e529053b65bc45ed1c005d3610d06014d04d22b582ab9f5180`.

## Exact identity and bounds

- Frozen3fd75c0 candidate SHA: `806c9b6db0766eb3a7455cc2bd23a68c61153d257f4b0f0b7bb98ced6972238d`.
- Observed installed app: `08cc825128533cab6d1103680b98025171ef7fd014495b0afc04655bcc417290`.
- Observed installed test APK: `120420d6925283ccf44478b58aef29a12e4575bbf6f1027df9a3d98e83cf2c8c`.
- Host guard closure: `3ad4c644a7733d1f1feeb7bbbe83532cc0be0f727f32f59dda00c951dd6e202d`; recorded lock descriptor non-inheritable.
- Driver PID12944; actual `dev.vibevoice.podcast.internal:generation` PID13006, UID/GID10755.
- Contract bytes match SHA `51edc271c52b43e14f901169315136f29298c29f7e8954eb6b99d6fe21954f02`.
- Verified Supertonic manifest matches `dc4ac737924d7d62e57ff5e166707198095c49e51d77cfed04a44d9e9435952d`. Exact reviewed code verifies the descriptor and full pack before this log point.
- All nine on-device packaged-library size/hash records match the exact frozen APK payloads.

One constructor BEGIN record, no constructor RETURNED record. Exact source path contains no Session::Run/Gemma/other-context call; retained command/event/profile history agrees. There is one instrumentation invocation, with no retry. Driver elapsed2227ms; duration-load-begin to failed service record66ms, including surrounding error/evidence handling—not a successful setup/performance metric. No watchdog timeout was reported.

## Earliest causal chain

Line references are within the archived `native-stderr.txt`:

1. **53–59:** HTP and QnnSystem interfaces load. HTP provider `HTP_QTI_AISW`, backend id6; queried backend build `v2.49.0.260730134355`. API interface2.38.0 is not a conflicting QAIRT package version.
2. **113,129–134:** logger/HTP initialization and QnnBackend_create succeed. This is backend setup progress, not a ready session or neural execution.
3. **135–148:** device creation starts. QNN logs `Specified config SOC, ignoring on real target`, then default platform info/unsigned-PD setup. The log does not show SoC43 to be the wrong target.
4. **150–154:** attempts to load the packaged V73 stub by absolute and base name. First decisive failure:
   `Failed in loading stub: dlopen failed: library "libcdsprpc.so" not found: needed by .../libQnnHtpV73Stub.so in namespace clns-9`.
5. **156–176:** remote-symbol/transport failures4000, failed skel setup as a consequence, device/platform failures14001, QnnDevice_create status0x36b1.
6. **195:** ORT reports `QNN_DEVICE_ERROR_INVALID_CONFIG: Invalid config values`.
7. **233–235:** session initialization rejects nodes left on the default CPU EP because CPU fallback was explicitly disabled.

Therefore the previous INVALID_CONFIG failure **repeats**, now localized to an actual FastRPC dependency-resolution failure in the app namespace. It is not evidence of unsupported neural operators, successful CPU fallback, or CPU model inference. ORT's earlier default CPU-EP registration/arena creation and CPU-named graph transformations are setup/optimization observations, not Session::Run evidence.

## Namespace versus DSP path

- Archived environment confirms targetSDK35 and untrusted_app SELinux context.
- `native-stderr.txt:6–7` records successful filesystem readability checks for vendor libcdsprpc.so paths.
- Saved `/vendor/etc/public.libraries.txt` contains the exact `libcdsprpc.so` entry.
- Retained `logcat.txt:5172` configures `clns-9` with `uses_libraries=libOpenCL.so`, omitting libcdsprpc.so.
- The stub's loader error explicitly names that namespace/dependency. Filesystem presence alone did not establish namespace visibility; the loader message now supplies the decisive evidence.

The generic ADSP warning is not the primary failure. `Failed to load skel` follows inability to load the host stub/FastRPC dependency; it does not independently prove an ADSP search-path or skeleton-byte defect. ADSP remains APK-directory-only and LD is unset, as the frozen baseline intended.

## Missing execution evidence stays missing

The only profile is121bytes containing one `Session/model_loading_uri` event. No Node execution/provider, RPC-execute or accelerator-cycle evidence exists. No successful duration session, four-session readiness, Gemma request, TTS/WAV, realistic capacity rejection or product E2E occurred.

`controller-result`/instrumentation completion means diagnostic collection completed. Service outcome remains `duration_load_failed`, and driver explicitly reports backendApproved=false/neuralInferenceRequested=false/GemmaRequested=false.

## Guard, privacy and cleanup audit

- Read-only guard checkpoints precede app install(command030), test install042 and instrumentation054.
- Each checkpoint's two snapshot hash manifests agree; all three checkpoints have the same DB/WAL/SHM hashes. Guard summaries report known-schema input state, zero episodes/generation-history rows. I inspected these summaries/order, not private DB contents.
- Six raw DB archives remain only under local `.private-db`, directory0700/files0600. None is in the diagnostic archive. The original global logcat remains local; public evidence filtering is a separate packaging task.
- PID absence checks before guarded actions and final cleanup use exit1 with empty stdout/stderr; command057 proves exact app/generation/test names absent after force-stop055.
- Settings-before and settings-after maps are identical. Cleanup errors/settingsErrors are empty; no scratch root was created.
- Logcat additionally records generation PID13006 killed/exited at lines6612/6686. Host controller release is reported and no review-time ADB/lock acquisition was used.
- The non-atomic external-launch race remains the previously documented operator restriction; this run is not proof of a general atomic Android freeze mechanism.

## Minimal next candidate hypothesis

The evidence supports ONE separately reviewed manifest declaration for the public vendor `libcdsprpc.so`, with optional/required installation semantics explicitly documented. Keep DEX/resources/native/context/SoC/profiling/fallback/ADSP/LD behavior otherwise unchanged and reuse the frozen test where possible. Verify the new APK's manifest/import and unchanged payload hashes, then seek a separately authorized bounded duration-load-only attempt.

Do not append ADSP paths, alter SoC43, replace SDK/native bytes, recompile models, or repeat Gemma to address this evidenced namespace failure. A later stub/DSP-path problem may still surface after this dependency is resolved; none is assumed fixed now. No manifest variant or follow-on execution is approved by this result review itself.

Janek's retention commit8c08c9f is a separate packaging claim; this review binds the original saved collection and archive hash above.
