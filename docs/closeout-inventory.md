# Remaining loose material at the offline closeout

Inventory taken against `120d64c9` during the October 17 offline closeout. This is a list of existing work, not a new feature backlog. No files were deleted, reset or bulk-staged. App finishing work and the short visual article are separate owned changes.

## App and article

- The previously dirty round-three prompt/runtime changes and prompt bench are now committed in `33fbfb4d`. Read `podcast-app/promptlab/README.md` and its linked evidence for the two saved runs. Writing approval remains Moritz's decision.
- `podcast-app/docs/current-closeout.md` records the final build candidate, active tests, historical-scope failures and device-evidence limits. The first frozen candidate is retained even if a later lint repair produces another.
- Luke owns the replacement visual article. `docs/qoralo-linkedin-draft.md` is being superseded, not treated as text approved for publication.
- The presentation and reconstruction are already tracked. Their earlier untracked status is historical, not a current backup gap.

## Existing material still outside commits

Counts below are the inventory snapshot, not a continuously refreshed dashboard.

| Area | Snapshot | Treatment |
| --- | --- | --- |
| `docs/explainers/` | One modified tracked index and 28 untracked files, approximately 5.3 MB | Existing Gemma and Supertonic teaching explorers, fixtures, source and tests. Preserve as authored educational material; not official-weight inference or a device result. Needs its own reviewed commit rather than incidental inclusion in an app commit. |
| `docs/wiki/` | Ten modified tracked files and 15 untracked files, approximately 1.7 MB | Existing hardware/model notes, links and assets. Includes a third-party hardware illustration; inspect attribution/sharing terms before using it in the public article. A private backup is not a redistribution license. |
| `notebooks/` | Three untracked files, approximately 55 KB | README, ignore rules and a DSP-versus-HTP teaching notebook. No current app-build dependency. |
| `output/` | 116 untracked files, approximately 7.3 MB | Prior UI concepts, screenshots, reports and logs. Generated examples are not evidence of the final installed UI. Review selectively; do not stage the directory wholesale with an application change. |
| `.agents/skills/impeccable/` | 56 untracked files, approximately 2.1 MB | A local skill installation, including license and notice files. Decide dependency-versus-vendoring separately from app delivery. |
| `.impeccable/surfaces/docs-explainers-gemma-4-e2b-html.md` | One untracked design brief | Associated with the existing educational explorer, not the new article. |
| `experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/tools/compare_embedding_boundary.py` | One untracked file | Explicitly untested and never executed. Jere's investigation was stopped. Do not execute it or include it as a validated tool; the committed handoff records its status. |

The tracked wiki/explainer diffs pass `git diff --check`. This inventory did not rerun their browser or numerical tests, inspect every generated log, or certify the loose files for public release. Untracked files are **not backed up by pushing main**; the list makes that remaining gap explicit.

## What is actually required to finish

1. Complete the owned host-build/lint work and freeze its exact output; install/test when the phone returns.
2. Run one final real episode through the UI, listen to its exact output and capture the demonstration.
3. Finish and review the short visual article. Public posting is Moritz's action.
4. Make an explicit backup/retention decision for the loose educational and generated material above. This does not require reopening the parked research or holding the app rollout.
