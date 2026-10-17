# Host scope-test audit — 2026-10-17

This supersedes the 2026-09-20 baseline note, not the historical gate receipts.
Run from the **Git checkout with its history available**, not a bare `git archive`
extraction: three tests intentionally read old source through `git show`.

```bash
cd podcast-app
python3 -m unittest discover -s tools/tests -v
python3 -m unittest discover -s tools/provider_pipeline -p test_pipeline.py -v
```

## Result and narrowly justified repairs

Before this audit: **105 tests, 95 passed, 7 failures, 3 errors** — the same ten
names listed in [the historical finding](finding-frozen-gate-scope-tests.md).
After: **106 tests, 98 passed, 8 failures, 0 errors**. The provider pipeline's
separate **15 tests pass**. The general tools suite is **not green**.

Two of the ten were stale implementations of useful behavioral assertions:

- `test_gallery_scope.GalleryScopeTests.test_gallery_is_nonexported_and_in_nonproduction_process`
  split the main-process guard at its first closing brace. The nested deletion
  reaper loop made that stop before the watchdog/dispatcher. Read the balanced
  block instead; retain the exported/process/task/privacy checks. A new test
  proves nested blocks are included but startup **outside** the guard is not.
- `test_short_product_scope.ShortProductScopeTests.test_observer_seams_do_not_override_normal_limits_or_profiles`
  required the old synchronous call spelling, before production response-format
  forwarding, and looked for player setup in the screen rather than the
  persistent `EpisodePlayerSession`. It now checks the synchronous call still
  forwards `responseFormat`, and still checks muting/configuration **before**
  `prepare()`, export observation before opening a stream, no async/model
  substitution/profile override, and the controller's three checkpoints.

Three historical-source lookups used today's `dev/qoralo` path at commits that
only contained `dev/vibevoice`. Correcting the **lookup path**, without changing
any baseline commit or expected source, turns misleading Git errors into honest
scope-drift failures. They remain red; package text is not normalized away.

## Exact remaining failures

These eight assertions deliberately retain their old expected values. None was
skipped, disabled, re-pinned or converted into an expected failure.

| Module / class | Exact test name | What currently fails |
| --- | --- | --- |
| `test_normal_integration_scope.NormalIntegrationScopeTests` | `test_normal_source_pin_uses_existing_distinct_data_namespace` | Expects the T2048/L2048 experimental pack `116fda95…`; normal config now selects `supertonic-3-provider`, `423429c6…`. Later UI/source checks in this method are masked by that first mismatch. |
| same | `test_coordinator_changes_only_model_directory_and_id_selection` | Whole-file comparison against `cc7e772c` plus one selector edit; coordinator has since gained provider plans, deletion leases, retained drafts and chapter request changes. |
| same | `test_target_prompt_binding_only_no_limits_parser_sampler_or_global_minimum` | Whole-file `NativeEngines.kt` comparison against `7980d11` plus the historical single-chapter edits; constrained decoding, diagnostics and newer chapter plumbing exceed that frozen scope. |
| same | `test_native_and_legacy_runtime_pack_authorities_stay_unchanged` | Native source is no longer byte-identical to `cc7e772c`: provider registration and renamed JNI paths were added. The first mismatch masks later authority/preparation-file comparisons; this is not a fresh native-byte or numerical-fidelity proof. |
| `test_short_product_scope.ShortProductScopeTests` | `test_contract_short_selector_and_long_source_pin_unchanged` | Contract checks pass, then the normal-pack file differs from `70a6ac6` (old long pack versus provider). Later Gradle-selector assertions are masked. |
| same | `test_library_fix_only_names_the_real_action_and_selector_uses_it` | Whole library source differs from `3957b8d` plus the one accessibility-label fix, due to subsequent UI/features/rename. Later driver-selector assertions are masked. |
| `test_tts_long_scope.TtsLongScopeTests` | `test_reviewed_guard_privacy_and_three_prelaunch_checkpoints_remain` | Frozen host identity `5ca6be91…` differs from current `f47130ff…`. Privacy-source equality passes first; subsequent historical override/checkpoint assertions are not reached. |
| `test_tts_only_scope.TtsOnlyScopeTests` | `test_controller_pins_new_scope_before_dispatch_and_reuses_guard` | Same old host-identity pin; the preceding controller/scope/checkpoint/no-push assertions pass. |

The full current host-identity SHA-256 is
`f47130ff72572b7590050a3a2a08863d3f37393e3ecea1f9555867d5bcda2b2a`.
The old expected one remains
`5ca6be91be151acd2937b5e65871a40361f9bae99ae444880eae0e29b6f2c425`.
Schema path, controller and guard evolution changed this composite identity;
replacing the old value would not revalidate any historical physical gate.

## Interpretation

The eight red tests assert **historical equality/scope**, not observed runtime
misbehavior. That does not establish every assertion after their first failure,
or prove the current application correct. Current Kotlin, native-policy,
provider-tool and runtime-byte checks are reported separately in
[current-closeout.md](current-closeout.md). A future owner may separate active
behavioral tests from archived historical-scope checks; this audit does not
silently retire the latter or rewrite their receipts.

The earlier guard-fixture `KeyError` was already fixed in `808f1b06`, including a
recorded-only fingerprint regression test. It is not an open closeout defect.
Private full logs remain under `.local/closeout-audit/` and the final candidate's
`logs/`; no phone, ADB or inference was used for this audit.
