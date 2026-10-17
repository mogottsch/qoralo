# Current closeout and delivery runbook

**2026-10-17 · offline weekend closeout.** Moritz is away with the phone. No
ADB, device action or model inference belongs to this closeout. This page
supersedes old handoffs' **current/installed** nominations, not their historical
results. Normal future delivery still includes install/launch without a
separate permission question, once device work is authorized again.

## Candidate and last actual device evidence

Final offline APK identity and host results will be recorded here after the
single serialized build of Thomas's committed round3 candidate. Shared Gradle
output is not an immutable artifact or evidence binding.

| Evidence | What it establishes | Boundary |
| --- | --- | --- |
| Last retained phone app `677f8d6fbe25d4ed8b438af1f55f198c0cf7cd135dceaf2a66fbe40151eec46d` | Installed renamed app/UI; real Gemma outline + chapter and provider HTP segment smoke. Thomas also reports this exact pulled app after round3b. | Built while prompt edits were dirty: do **not** identify its effective source solely as commit `ffa7cf3c`. No fresh phone observation in this closeout. |
| Retained test `21293c4c80e237fdae7491b48b099ee6a081adf0b41930163f46a4679f207f4b` | On-disk pre-closeout test APK, includes the prompt bench. | Not a per-run round3/3b test-APK hash receipt. Janek also installed later smoke/export test builds; no current phone test identity is newly verified. |
| [Rename/route evidence](rebrand-qoralo.md) | Real GPU outline/chapter; real HTP segment reproduced byte-identically across two builds. | Not a fresh full script→audio→player E2E. Device histories in that page are chronological, not all simultaneously current. |
| Owned `RenamedExportSmokeTest` | Complete owned WAV exported byte-for-byte (8,864 B); filename cases; partial episode rejected. | Does not drive Android's system file picker. |
| Round3 / repeat | Saved application-specific script runs, reviewed/committed by Thomas. | Not the canonical fixed-input Android LLM performance campaign or a listening/grounding acceptance. |

Pre-closeout outputs were copied **before** Gradle could overwrite them to
`.local/closeout-audit/prior-device-candidate/{app.apk,test.apk,manifest.json}`.
The retained app's packaged bridge is `2d9ece14775d86528cd658995ad09a770ddc3b083f2db7c0b91c19521d3b414a`,
not the earlier accepted `44a41cd4…`. Keep that native-byte difference explicit;
source-built or successful smoke does not mean identical old bridge bytes.

## Offline build / freeze checklist

- [ ] Thomas's round3 runtime, JVM tests and prompt-bench source committed; no
  further runtime/config edits or concurrent Gradle/native builds during freeze.
- [ ] Java 17; SDK 35; NDK `28.1.13356709`; CMake `3.22.1`; Gradle cache and
  authorized runtime inputs present. No network/model acquisition implied.
- [ ] Normal provider selectors, **not** legacy application ID or short plumbing.
- [ ] Run the host command below once, retaining exit codes, logs and XML; record
  tests **discovered/executed/skipped**, never call skipped cases passed.
- [ ] Copy matching APKs immediately into a new `.local/closeout/<stamp>-<commit>/`
  directory. Retain source-file/config/toolchain/native-library hashes,
  effective generated `BuildConfig`, source commit/tree and build/test logs.
- [ ] Verify APK signatures, package/target IDs and trusted native runtime bytes;
  re-hash frozen files, make the completed bundle read-only. No APK/model/vendor
  payload goes to Git. Commit only docs/tests owned by this closeout.
- [ ] Mark device verification **pending**. Installation is a real blocker while
  the phone is away; host success never silently inherits an older device pass.

```bash
cd podcast-app
./gradlew --offline -Ppodcast.legacyApplicationId=false -Ppodcast.shortProductE2e=false \
  :app:testDebugUnitTest :app:assembleDebug :app:assembleDebugAndroidTest \
  :app:compileReleaseKotlin :app:lintDebug :app:testNativePolicies
python3 -m unittest discover -s tools/tests -v
python3 -m unittest discover -s tools/provider_pipeline -p test_pipeline.py -v
python3 tools/verify_apk_runtime.py --apk "$FROZEN/app.apk" \
  --output "$FROZEN/runtime-proof.json"
```

The general Python command is expected to return **nonzero**, not be ignored:
[the exact audit](host-scope-test-baseline.md) records eight historical scope
failures (106 discovered, 98 passed), no errors. Before repair it was ten red
names, including three invalid historical paths. Two active behavioral guards
were fixed rather than weakened; no historical hash/source baseline was re-pinned.
The provider Python suite independently passes 15 tests.

## Provisioning: prerequisites, not repository payloads

1. Acquire authorized Gemma model/tokenizer, accepted context artifacts, ORT
   headers and QAIRT/ORT libraries outside Git. Their reviewed authorities are
   `config/trusted-local-runtime.json` and `config/trusted-supertonic-provider.json`.
   A clean clone without them cannot reproduce neural deployment; do not hide
   that behind a stub/CPU route or a successful non-neural compile.
2. On a fresh authorized host, `python3 tools/prepare_local_runtime.py` verifies
   the base experiment inputs, prepares Gemma and **legacy** Supertonic packs,
   injects the six vendor libraries and writes ignored `local.properties`.
   It rewrites those local base-pack directories: do not rerun it gratuitously
   during an already-provisioned freeze. It does not run inference or provision
   the normal provider pack.
3. The provider assembly is separately `python3 tools/provider_pipeline/prepare_pack.py`.
   It requires the four accepted local context exports named in that script,
   including the corrected duration/text exports and experiment0037 vector/vocoder.
   It refuses an existing destination and writes the provider authority file;
   verify its generated bytes against the committed authority, never accept a
   changed pin merely because preparation produced one. Missing accepted context
   exports are a provisioning blocker, not permission to recompile/infer this weekend.
4. For the existing prepared host, retain rather than regenerate:
   `.local/model-packs/gemma-4-e2b/current/manifest.json` SHA
   `9fb627ef9a4eb0ed49056c32bc16f2846e6edf68dc8d854b02af90e24e4e96cd`,
   and `.local/model-packs/supertonic-3-provider/current/manifest.json` SHA
   `423429c6642da131ac62511e3b233f1a121b97975aa5b6e9aa755bb13a927670`.
   Verify each listed asset's size/hash too; a manifest hash alone is not a full
   pack check. All model/context assets are data-only, never executable libraries.
5. Effective `local.properties` needs `gemma.manifest.sha256`,
   `native.runtime.enabled=true`, `onnxruntime.include.dir` and `sdk.dir`.
   The normal voice pin comes from `config/normal-supertonic-pack.properties`,
   **not** the legacy `supertonic.manifest.sha256` property. `app/runtime-libs/arm64-v8a/`
   contains vendor inputs; CMake builds the renamed app bridge from source.

Script = Gemma / LiteRT-LM0.16.1 **GPU** (`Backend.GPU`, not QNN).
Voice = Supertonic provider / ORT1.27.1 + QAIRT2.49.0.260730 **HTP**, four
T320/L512 contexts, eight steps, speed1.05. No CPU neural fallback; admission
failure must remain an actionable failure, not an unreported route change.

## Install on personal user 0 when the phone returns

Do not execute this section during the offline closeout. Use the frozen pair,
not whatever another build last left in `app/build/outputs`.

```bash
# From repository root, with FROZEN pointing to the nominated immutable bundle.
ADB=/home/moritz/Android/Sdk/platform-tools/adb
SERIAL=R5CW81PR8SY
APP=dev.qoralo.podcast.internal
exec 9>artifacts/locks/phone.lock
flock -n 9 || exit 75
# Confirm identity and no live user generation before stopping leftovers.
# Do not stop a running user job. No DB snapshot/inventory ceremony required.
"$ADB" -s "$SERIAL" install -r -t --user 0 "$FROZEN/app.apk" 9>&-
"$ADB" -s "$SERIAL" install -r -t --user 0 "$FROZEN/test.apk" 9>&-
"$ADB" -s "$SERIAL" shell am start --user 0 -n "$APP/dev.qoralo.podcast.MainActivity" 9>&-
# Verify installed APK hashes against manifest, focused/resumed app, no fresh crash.
# Release after any needed pack provisioning/launch checks, not between operations.
flock -u 9
```

Every command is serial-pinned: if the phone disappears, an emulator must never
become the implicit target. **Both installs require `--user 0`**; never use the
work profile, default/all-user install, `pm clear` or legacy app identity.
Readiness checks belong before launch of generation, not after killing it.

For a first personal-user install, stage only the verified **Gemma and provider**
pack directories under an owned `/data/local/tmp` path, readable for `run-as`;
copy data through `run-as dev.qoralo.podcast.internal` to
`no_backup/model-packs/gemma-4-e2b/current` and
`no_backup/model-packs/supertonic-3-provider/current`. Use a new absent destination
or reuse a matching manifest; do not nest `current/current` or replace an active
pack. Verify remote manifest hashes and let full production verification check
listed assets before inference; remove only the owned temporary staging path.
`tools/install_local_debug.sh` is **not provider-complete**: it installs only the
app and stages legacy `supertonic-3`, despite the normal build selecting provider.
Use the explicit frozen-pair/provider procedure above; do not claim the helper
alone provisions the current app.

## Genuine remaining gaps

- No final-candidate device install, instrumentation, playback, system-picker
  export, accessibility or neural replay in this offline window.
- Historical device counter coverage is incomplete: both recorded failed SCRIPT
  jobs had null SDK prefill/decode tokens/rates, runtime init/TTFT; KV availability
  on a separate edit probe does not fill these fields. Wall time is not TTFT or
  decode throughput. `reachedOutputLimit` can be null; do not infer truncation or
  convert unavailable SDK counters to zero. [Counter limits](chapter-json-failure-notes.md).
- Strict legacy vector numerical gate remains failed/non-bit-exact. Old accepted
  WAV listening does not transfer to this candidate or a newly generated episode.
  Profiling-off runs have no measured per-graph HTP RPC/cycle counters by design.
- Provider admission and saved-input coverage are not universal model-capacity,
  sentence-duration, grounding or repetition-quality guarantees. Prompt round3
  is an experimental application candidate, not a canonical benchmark win.
- Eight frozen host-scope assertions remain red, with some later assertions
  masked by first mismatches; their exact names/reasons are in the audit.
- Fresh-host replication needs separately authorized local artifacts/cache;
  the repository deliberately cannot provision restricted payloads by itself.
