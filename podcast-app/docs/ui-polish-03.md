# Gallery ownership correction only

The production layout and the7+3+1 UI regressions remain exactly as accepted at `a603f52`. Nik independently passed all22 Android executions across default and320dp/font2. The entire narrow Paste Add button ended at1161px and label at1119px, both above actual IME top1209px, with a successful submit callback. These PNG/geometry/results and the partial Library smoke are retained without alteration in `evidence/ui-polish-03/before/` with a hash manifest.

The remaining `polish-02` smoke failed because requested `LayoutParams.title` was **not** the observed accessibility title (`VibeVoice`). The retained PNG shows a real Library frame. No full gallery matrix followed the failure, and it was not classified as an app-rendering failure.

This correction reads actual platform accessibility IDs from `View.createAccessibilityNodeInfo().windowId` on attached, shown decor views in the private gallery process, including dialog windows. No marker nodes or titles are injected. The continuously refreshed private acknowledgement binds frame/run token, process, initially acknowledged PID and observed window IDs. The driver checks snapshot age≤1500ms and correlates those IDs with live UiAutomation window AND root IDs, expected package, visibility and stable identity. IME focus does not require the matching app root itself to remain focused. Observed titles remain evidence, not authorization. Root ownership is checked again before interaction/tree extraction.

Twelve deterministic policy tests include requested-versus-observed title mismatch, unauthorized same-package windows, stale/future snapshots, wrong PID/token/frame/window IDs, keyboard focus and partial-evidence retention. Screenshot/metadata-before-tree behavior and fail-overall/continue-distinct-frames behavior remain intact. External budgets remain480s all-frame /90s single-frame. [Capture contract](ui-polish-gallery.md).

## Candidate isolation

Async Agent/Paste form-acknowledgement work is **not included**. Only Janek's three owned WIP files were backed up with hashes, excluded/restored to the committed production snapshot for the driver build, then restored byte-for-byte. Both new form helper source files are excluded from this candidate. The candidate's `app/src/main` tree matches `a603f52`; the working-tree form follow-up remains separate and uncommitted. Earlier APK/candidate directories remain immutable.

## Next gate

Nik alone: verify the new exact APKs/source and run a single base smoke, followed by a dialog/IME smoke if the new ownership correlation works. Inspect the owner-process observed IDs against selected UiAutomation/root IDs and the actual PNG/tree. Then perform the requested full gallery matrix only if smoke succeeds. Do not repeat an unchanged failing run. No physical/default ADB, model packs, inference or native preparation is authorized. Host checks do not prove the new device-side ID correlation until this smoke runs.
