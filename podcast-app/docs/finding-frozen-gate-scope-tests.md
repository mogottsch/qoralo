# Finding: frozen gate scope tests fail independently of the Qoralo rename

**This is a separate pre-existing finding. It is not rename damage, and it was not fixed inside the rename work.**

Ten tests under `podcast-app/tools/tests` fail on `main` before any rebrand commit. Measured by extracting each commit and running `python3 -m unittest discover -s tools/tests`:

| Commit | Failing | Note |
| --- | --- | --- |
| `cc7e772c` (2026-09-10) | 0 | last clean point measured |
| `70a6ac6b` (2026-09-10) | 3 | first measured non-zero |
| `c34cf107` (2026-09-11) | 7 | |
| `7b06a3fe` | 9 | |
| `b375d66c` | 10 | on the episode-management branch |
| `0ef9e0e4` | 10 | the count entered `main` with this integration |
| `7cceadff` | 10 | immediately before the first rebrand commit |
| `fab2f552` | 10 | brand rename only, no package change |
| `2f9af40e` | 10 | package and application ID rename |

The failing set is identical on `0ef9e0e4` and after the rename:

- `test_contract_short_selector_and_long_source_pin_unchanged`
- `test_coordinator_changes_only_model_directory_and_id_selection`
- `test_library_fix_only_names_the_real_action_and_selector_uses_it`
- `test_native_and_legacy_runtime_pack_authorities_stay_unchanged`
- `test_target_prompt_binding_only_no_limits_parser_sampler_or_global_minimum`
- `test_controller_pins_new_scope_before_dispatch_and_reuses_guard`
- `test_gallery_is_nonexported_and_in_nonproduction_process`
- `test_normal_source_pin_uses_existing_distinct_data_namespace`
- `test_observer_seams_do_not_override_normal_limits_or_profiles`
- `test_reviewed_guard_privacy_and_three_prelaunch_checkpoints_remain`

## What they actually assert

These are scope guards for completed gates. They compare current application source against frozen copies, or assert pinned SHA-256 values for gate controllers, so that a finished experiment's blast radius stays provable. They therefore fail by construction whenever the application legitimately evolves — for example when the deletion/diagnostics work changed `PodcastApplication`, or when the native bridge gained `RegisterProviderNatives`.

They are not runtime regressions. The application's own suites pass: 265 JVM tests with 1 pre-existing skip on the renamed tree.

## Why the rename did not change the count

Two pins inside gate controllers hash sibling controllers, so renaming the package inside them moved those hashes. Both were re-pinned mechanically and recorded in [the rebrand notes](rebrand-qoralo.md); the superseded values stay in the historical receipts. With those re-pins, the failing set after the rename is exactly the set on `0ef9e0e4` — no test was added to it and none was silenced.

## Not done here

No frozen scope guard was re-pinned to make an old gate look current, and no failing assertion was deleted or weakened. Deciding whether these historical gates should be re-pinned, retired, or left failing as an honest marker of drift belongs to whoever owns that gate history, not to a rename.
