# Current-frame semantics and narrow-layout correction

Status: implementation host-validated; new emulator smoke/visual verification pending. No physical phone, model packs or inference. Async form-acknowledgement WIP is excluded from this candidate.

## What the previous matrix actually established

Nik verified `polish-03` ownership through real gallery-process/window/root IDs, inspected the requested38 PNGs and coherent8 IME cells, and retained an extra base smoke. However, **12/30 base accessibility trees were stale** despite `complete` metadata: Sources/empty Sources reused Library-empty, Review reused Instructions, and script-loading/failure/Player reused Generating, at both sizes. Correct screenshots and correct ownership did not establish current-frame semantic content.

`evidence/ui-polish-04/before/` retains the entire prior matrix, smokes, contact sheets and `semantic-frame-audit.json` byte-for-byte. A separate retained manifest records the correction in interpretation; the old false-complete reports are not edited or relabelled in place. No unchanged run was repeated.

## Capture changes

- Every frame launches a **fresh gallery activity/window** in its own debug task affinity. The instrument checks the merged package manager task affinity and nonexported status before using NEW_TASK|CLEAR_TASK. The main product task and its data are never cleared.
- Previously used window IDs cannot satisfy later-frame readiness. Actual observed gallery IDs, initial PID, token/frame, package, visibility, freshness and root/window-ID checks remain required; keyboard focus does not disqualify a live app root.
- Android34+ SDK-public UiAutomation cache clearing and root refreshing precede traversal. The approved emulator is Android35.
- The merged tree must match **existing production landmarks and state**, including Continue enabled/disabled for source presence and distinct writing/audio/error/Player content. No fake markers or unmerged selectors are injected.
- A10s content deadline is separate from acknowledgement/window readiness. PNG/partial metadata are saved before tree work. Every distinct intermediate tree is retained by SHA-256 with its failed/successful content checks. Wrong content cannot yield complete status even with a fresh owned window.
- External supervisor budgets are now **600s all-frame /100s single-frame or IME**, including the additional content wait. Every frame is launched once; failed readiness is retained, and later distinct requested frames continue while the run fails overall.

Five new deterministic tests cover the six actual stale-tree relationships under valid fresh ownership, source enabled-state distinction, Agent/error distinction, text/description landmarks and rejected window reuse. The17 gallery tests do not replace the next actual emulator smoke.

## Layout changes driven by real PNGs

- **Player ±15:** use intrinsically measured text controls (minimum64dp in the wide row), a balanced separate seek row at narrow/large-font sizes, and slightly wider large-font control space. Labels stay single-line without reducing font size. Seek behavior remains exactly15 seconds.
- **Creating episode / Episode stopped:** an inset-owning, minimum-height bar grows with wrapped title text instead of clipping against the small TopAppBar's fixed height. Close remains a normal48dp action.
- **Library ready hero:** narrow/large-font layouts stack compact decorative artwork above full-width metadata rather than squeezing labels/title beside fixed116dp artwork. Normal-width layout is preserved.
- **Recent episodes:** no heading is shown when the hero is the only ready episode.

The screen semantics suite now has8 methods, adding ready-hero coverage and actual text-layout overflow checks for transport and generation/error titles. Ordinary scrollable body crops remain distinct from clipped controls. Full glyph/visual acceptance still depends on screenshots and independent inspection.

## Next exact lane (Nik only)

Verify the new source/APK hashes, then smoke a base frame, a fresh-window transition and a dialog/IME frame. Confirm previous window IDs are not reused, public cache refresh succeeds, and current-frame content checks match the retained actual merged tree. If successful, collect the default+narrow15-frame/IME matrix and inspect the layout changes. Run ScreenSemanticsTest(8), UiInteractionRegressionTest(3) and PasteImeRegressionTest(1) at both sizes. Freeze all results; do not repeat unchanged failures.

Form submission preservation, native diagnostics and physical TalkBack/runtime validation remain separate. This candidate contains neither new form helpers nor the uncommitted form repository/VM changes; their source hashes are preserved before/after the isolated build.
