# Publication shutdown handover — 2026-08-28

## Last accepted state

- Latest accepted publication commit: `e5c7942` (`Publish physical LFM resumed decode`).
- Latest registry publication: `e91b3f5` (`Publish Gemma QNN HTP campaign`). The Android LLM registry has **7 rows**, including the first QNN/HTP campaign row.
- Latest completed-page improvement publication: `a1f92e7` (Gemma long-collapse improvement baseline; completed campaign/card unchanged).
- No publication work is in progress and no publication-owned file is uncommitted.

## Completed validation

For `e5c7942`:

- deterministic selected-page regeneration passed;
- global experiment-page `--check` passed;
- shared page/registry tests: 21/21;
- experiment 0034 owner tests: 35/35;
- seven-row Android LLM registry validation passed before/after rebuild;
- 39 local links/assets resolved;
- desktop and 390 px Chrome checks passed: Active, exactly three primary sections, source `17a2712`, no registry card, no overflow or console errors.

## Current working tree and processes

- Current non-publication changes belong to Ben/Jens/Janek/Jere and must remain untouched. They include active files under `experiments/0032-*`, `experiments/0034-*`, `podcast-app/`, and the untracked Gemma improvement converter.
- `output/` is untracked and not publication evidence.
- No page generator, registry builder, Kate HTTP server, or Kate Playwright process remains.
- No publication reservation remains except this handover while it is being committed.

## External and ignored artifacts

- Publication owns no external or ignored binary artifact.
- Registry/page claims point only to committed owner evidence. Do not reconstruct a row from `.local/`, Messenger text, or ignored state.
- Current durable registry source for 0031 is `experiments/0031-gemma-4-e2b-it-android-qnn-htp/results/android-qnn-physical-campaign-attempt-02/result.json`; provider raw SHA-256 is `32f516c5f9775a39bfd003907438ae430bf019d2081e1c76a80bb706377e8baa`, retained losslessly as committed gzip SHA-256 `84bb2a028c45d80efbab48678acd8c95e1be0351b92c49f9907058a211d473fd`.

## Boundaries and risks

- Preserve every attempt chronologically. A corrected campaign rerun is a distinct complete attempt; never selectively rerun or cherry-pick individual requests.
- Registry eligibility requires one complete valid canonical physical campaign. Host, preparation, bounded, partial, or diagnostic evidence stays page-only.
- The 0031 registry row is performance evidence, not quality acceptance: all five long outputs retain `looks_sensible: false` and exact issue `Severe repetition collapse in the exact max-token output.`
- 0031 registry decode throughput remains null because Genie does not define first-token inclusion. Raw Genie rates may be shown as observations but not normalized against explicit exclude-first-token rates.
- Keep thermal escalation and process-only memory/HTP-private-unavailable limits visible.
- For 0034 hybrids, identify the exact CPU/GPU/HTP partition and never label a hybrid as HTP-only. Current physical max-16 resumed-decode evidence lacks serialized per-call states/logits, detailed QNN profiles, and explicit finite scans; severe state drift remains.
- Do not let `podcast-app/` work modify experiment pages or registry files.

## Exact restart step

1. Wait for Pi's reviewed handoff referencing a committed owner SHA.
2. Read the committed README/PLAN/contract/result; reserve only the relevant publication page (and registry/dashboard files only for a complete valid campaign).
3. Update `page.md`, regenerate HTML, and run:

```bash
python3 scripts/generate_experiment_pages.py --check
python3 -m unittest scripts.test_generate_experiment_pages docs.android-llm-benchmarks.tests.test_contract
python3 docs/android-llm-benchmarks/validate.py
python3 docs/android-llm-benchmarks/build_registry.py
python3 docs/android-llm-benchmarks/validate.py
```

4. Run the relevant owner contract test, local-link check, `git diff --check -- docs/`, deterministic hash regeneration, and desktop/390 px Chrome inspection.
5. Commit only reserved publication files; report to Pi and owner; release reservations.

## Phone and lock cleanup

- Kate performed no ADB or phone operation.
- `artifacts/locks/phone.lock` exists as the normal lock file but has **no holder** (`lsof` returned no owning process); lock is free.
- No Kate child process or remote cleanup obligation remains.
