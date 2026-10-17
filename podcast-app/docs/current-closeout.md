# Current closeout and delivery runbook

**2026-10-17 · offline weekend closeout.** Moritz is away with the phone. No
ADB, device action or model inference belongs to this closeout. This page
supersedes old handoffs' **current/installed** nominations, not their historical
results. Normal future delivery still includes install/launch without a
separate permission question, once device work is authorized again.

## Candidate and last actual device evidence

**Frozen source:** `1a089581a3a0e8e11c92ebb6f5d56ca07b1ef330`, `app/src` tree
`e0fb66126fb16bad6f4f1ae22741fa01ef93130d`. It retains Thomas's verified round3
candidate from combined commit `33fbfb4d` and adds only the debug export-cursor
lifecycle fix and eight focused host tests. No production policy/UI change.

**Immutable local bundle:**
`.local/closeout/20261017T075644Z-1a089581a3a0/` (read-only; `SHA256SUMS` verified).
It includes APKs, a 295-file source binding plus source archive, effective local
configuration/toolchain/pack hashes, generated BuildConfig, JUnit XML, lint,
signature/package/native proofs and command logs. No payload was added to Git.

| Frozen file | SHA-256 |
| --- | --- |
| `app.apk` (131,740,380 B) | `cc1f6436969eb1b27499e6d7e09bbb34feba4983369dff7a00aa79cfda65dd44` |
| `test.apk` (3,423,901 B) | `9c40d9187668f73d2687b12823f816b5751fe7de11b970c70fc9c41925324fbf` |
| `manifest.json` | `3ea8814210bbb932baae3351e3813f18d6055e2ebcd64bede45aed189ce05465` |

**Result: active Gradle build/lint green; historical Python scope suite red.**
The serialized final Gradle invocation exited **0**: both APKs assembled,
androidTest compiled, release Kotlin checked and lint passed without a suppression
or baseline. JVM: **301 discovered / 288 executed / 13 skipped / 0 failures or
errors**, including all **8/8** new cursor tests. Provider Python **15/15**,
promptlab **5/5**, eight promptlab checksums, signatures, package/target identities
and trusted packaged runtime-byte verification passed. The native-policy target
was **UP-TO-DATE**, not a new native-test execution. Eleven skips are
`ProviderAudioPlanTest` local-pack-gated cases; the other two are the private
frontend-reference and long-pack reconstruction tests. Exact names are retained
in `manifest.json`; skipped cases are not passes.

The first freeze remains unchanged at
`.local/closeout/20261017T074832Z-33fbfb4d7346/`, manifest SHA
`e5e95013014bc1f02d0ccf4873edecc4fc2e95974f214b68b5de016964b3ad8e`.
Its Gradle run failed only at lint **Recycle**, `ShortProductDiagnostics.kt:56`.
Pi authorized the follow-up fix: query validation now owns the nullable cursor in
an explicit `try/finally { cursor?.close() }`. URI/authority/document-ID/name/empty
checks and receipt-after-validation ordering are unchanged. Thomas's read-only
review found no blocking issue; focused Robolectric tests verify query arguments,
success, null/empty/wrong-name/unknown-size/nonzero/negative-size rejection and
close-once behavior after a metadata-read exception. The simple finally form does
not preserve `use()`'s suppressed-exception behavior if both reading and closing
throw; that rare dual-failure case is not covered or claimed equivalent.

**The final app has changed from phone-proven `677f8d6f…`; neither APK in this
final pairing was installed or device-tested during closeout.** The test APK is
byte-identical to the first offline freeze; the app is not. Rebuilding need not
yield identical ZIP/signature bytes: use these frozen hashes as the identity,
not a promise of bit-for-bit reproducible builds.

| Evidence | What it establishes | Boundary |
| --- | --- | --- |
| Last retained phone app `677f8d6fbe25d4ed8b438af1f55f198c0cf7cd135dceaf2a66fbe40151eec46d` | Installed renamed app/UI; real Gemma outline + chapter and provider HTP segment smoke. Thomas also reports this exact pulled app after round3b. | Built while prompt edits were dirty: do **not** identify its effective source solely as commit `ffa7cf3c`. No fresh phone observation in this closeout. |
| Retained test `21293c4c80e237fdae7491b48b099ee6a081adf0b41930163f46a4679f207f4b` | On-disk pre-closeout test APK, includes the prompt bench. | Not a per-run round3/3b test-APK hash receipt. Janek also installed later smoke/export test builds; no current phone test identity is newly verified. |
| [Rename/route evidence](rebrand-qoralo.md) | Real GPU outline/chapter; real HTP segment reproduced byte-identically across two builds. | Not a fresh full script→audio→player E2E. Device histories in that page are chronological, not all simultaneously current. |
| Owned `RenamedExportSmokeTest` | Complete owned WAV exported byte-for-byte (8,864 B); filename cases; partial episode rejected. | Does not drive Android's system file picker. |
| Round3 / repeat | Saved application-specific script runs, reviewed/committed by Thomas. | Not the canonical fixed-input Android LLM performance campaign or a listening/grounding acceptance. |

Pre-closeout outputs were copied **before** Gradle could overwrite them to
`.local/closeout-audit/prior-device-candidate/{app.apk,test.apk,manifest.json}`.
Both the retained and frozen app's packaged bridge is
`2d9ece14775d86528cd658995ad09a770ddc3b083f2db7c0b91c19521d3b414a`, not the
earlier accepted `44a41cd4…`. CMake configure/build ran with pinned NDK28.1 and
existing local inputs; the packaged bridge did **not** change. The six injected
vendor libraries and Maven LiteRT JNI matched their reviewed authorities. This
is deliberate incremental reuse, not a fresh independent bridge compilation or
proof of numerical equivalence to `44a41cd4…`.

## Offline build / freeze checklist

- [x] Thomas's round3 runtime, JVM tests and prompt-bench source committed; no
  further runtime/config edits or concurrent Gradle/native builds during freeze.
- [x] Java 17; SDK 35; NDK `28.1.13356709`; CMake `3.22.1`; Gradle cache and
  authorized runtime inputs present. No network/model acquisition implied.
- [x] Normal provider selectors, **not** legacy application ID or short plumbing.
- [x] Run the host command below for each frozen source revision, retaining exit codes, logs and XML; record
  tests **discovered/executed/skipped**, never call skipped cases passed.
- [x] Copy matching APKs immediately into a new `.local/closeout/<stamp>-<commit>/`
  directory. Retain source-file/config/toolchain/native-library hashes,
  effective generated `BuildConfig`, source commit/tree and build/test logs.
- [x] Verify APK signatures, package/target IDs and trusted native runtime bytes;
  re-hash frozen files, make the completed bundle read-only. No APK/model/vendor
  payload goes to Git. Commit only docs/tests owned by this closeout.
- [x] Mark device verification **pending**. Installation is a real blocker while
  the phone is away; host success never silently inherits an older device pass.

```bash
cd podcast-app
./gradlew --offline --no-daemon --max-workers=2 \
  -Ppodcast.legacyApplicationId=false -Ppodcast.shortProductE2e=false \
  :app:testDebugUnitTest --rerun :app:assembleDebug :app:assembleDebugAndroidTest \
  :app:compileReleaseKotlin :app:lintDebug :app:testNativePolicies
python3 -m unittest discover -s tools/tests -v
python3 -m unittest discover -s tools/provider_pipeline -p test_pipeline.py -v
mkdir -p .local/closeout-audit
python3 tools/verify_apk_runtime.py --apk "$FROZEN/app.apk" \
  --output .local/closeout-audit/runtime-proof-recheck.json  # never rewrite the frozen bundle
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

- Active Gradle/lint checks now pass, but 13 JVM cases skipped, including all
  11 pack-gated provider-plan cases; historical Python scope failures remain.
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
