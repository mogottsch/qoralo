# UI polish and synthetic capture lane

This milestone addresses Nik's emulator-confirmed Library clipping, instructions back-navigation loss, and keyboard/inset problems, plus source-confirmed playback ownership, resume metadata, hint-limit and scrub races. Host tests are not visual approval: the updated APK still needs Nik's explicit `emulator-5556` interaction/screenshot pass. Frozen wiring and duration-diagnostic candidates remain separate and unchanged. No physical-phone activity is authorized.

## Production changes

- The outer snackbar scaffold no longer duplicates screen-owned system insets. MainActivity requests resize for the IME. Snackbars avoid navigation/IME occlusion.
- Library measures the complete New episode action intrinsically, or gives it a full-width row at narrow/large-font sizes. Navigation labels no longer compete with a weighted center box. Empty-state artwork is smaller at large font sizes.
- Primary actions use a minimum height, not a fixed height, so labels can wrap. Review/agent actions remain visible in a measured bottom panel.
- Paste has a safe-inset/IME-aware dialog with a bounded scroll area for fields and separate title/action rows. Instructions and agent input respect IME space; long generation/failure content can scroll.
- Instructions/review drafts are keyed by immutable episode ID in SavedStateHandle and persisted through serialized Room writes. A delayed write cannot mutate queued/claimed/locked input. Hint insertion uses the same 2,000-character cap as typing, disables hints that do not fit, and preserves editing/recovery without silent truncation.
- Playback persistence and export receive the episode ID explicitly, not mutable current selection. Player disposal keeps its original callback owner even through A→B recomposition. Late playback hydration is episode-filtered. Library resume position/progress/chapter count uses persisted metadata rather than hardcoded progress.
- Slider preview is separate from polled playback position. The transport/control panel stays visible while artwork/title content can scroll, and action chips wrap. Transcript remains chapter-only, read-only and without estimated sentence timing.
- Agent request failures show a clear unchanged-draft message without a misleading current Changes ready card. No retry/recovery lifecycle or post-lock editing was added.

## Focused tests

Host `UiPersistenceTest` checks:

- Save A after returning to Library or selecting B; A retains 30s/1.5 speed and B is untouched.
- Instructions and review toggle survive source navigation, episode switch and SavedStateHandle reconstruction without creating jobs.
- Late Room draft writes after queue, claim and lock leave frozen inputs unchanged.
- Near-cap hint insertion is rejected without truncation; subsequent valid editing/insertion works.

Android `UiInteractionRegressionTest` uses production composables with synthetic media:

- Real hint chip disabled near 1,990 characters; editing back to a valid value re-enables exact insertion.
- Paused synthetic 60-second WAV: drag and hold for more than one polling interval before release; the preview target must win.
- A→B PlayerScreen replacement must dispose A's position/speed into A's callback only.

These Android methods must be executed on the named emulator before claiming they passed. The existing seven screen semantics tests remain separate. Offscreen content may need ordinary scrolling; semantics presence alone is not a no-clipping assertion.

## Passive debug gallery

`SyntheticGalleryActivity` exists only in the debug manifest, is **non-exported**, and runs in **`:ui_gallery`**. `PodcastApplication` starts the queued dispatcher/watchdog only when its process name equals the main package; gallery startup bypasses those paths. Gallery code references no repository, model engine or generation service and never creates jobs. Its actions change fixture state in memory only.

It renders the real production composables, not screenshot mockups. Audio is a locally generated, quiet 30-second test tone, never model output. Sources/messages/progress/error states are explicitly synthetic. No native inference or GPU/QNN proof is possible from this lane.

Stable frames:

```text
library, library-empty, sources, sources-empty, paste, instructions,
review, agent, agent-error, lock, generating, script-loading, failure,
player, transcript
```

`failure` contains deliberately long error text; `agent-error` contains validation failure without a changed draft. `paste`, `instructions`, `agent`, and `agent-error` also support an IME capture request. A successful click is recorded separately from screenshot review; the actual keyboard must be inspected, not assumed present.

The original `a2dc5cb` driver failed on null active-window roots; `polish-02` then preserved a live root/PNG but incorrectly expected a requested LayoutParams title to appear as the accessibility title. Neither is an app-rendering failure. `polish-03` connects UiAutomation before launch and reads **actual accessibility window IDs** through the SDK-public `View.createAccessibilityNodeInfo().windowId` on attached, shown gallery-process decor views, including dialogs. It refreshes the private frame/token/process/PID/observed-ID acknowledgement every200ms. The driver accepts only IDs in a matching acknowledgement from the initially acknowledged PID sampled within the preceding1500ms, paired with the same live UiAutomation window/root ID and expected package. Identity/bounds must remain stable for400ms. Requested titles do not authorize anything; actual titles such as `VibeVoice` remain recorded. No platform titles or Compose semantic nodes are changed. A visible matching app root may remain unfocused when the requested IME owns focus. Focus, type, layer, package, observed title, IDs, bounds and recent ownership/window snapshots are retained.

`polish-04` additionally launches each frame in a fresh activity/window in a **private debug task affinity**, verified before CLEAR_TASK so the main app task cannot be cleared. Previously used window IDs cannot satisfy a later frame. On Android34+ it clears the public UiAutomation cache, refreshes the root and validates existing production content landmarks/state (not marker nodes), including Continue's enabled state for Sources versus empty Sources. This closes the separate `polish-03` stale-content/false-completion defect: valid window ownership alone did not prove that its cached tree belonged to the current frame.

It retains partial metadata and a screenshot **before** optional full-tree extraction, using actual merged `AccessibilityWindowInfo.root` trees, never unmerged Compose selectors. Missing/changed roots or extraction failure cannot discard the PNG and are explicitly marked unavailable/partial. Content readiness has a separate10s deadline. Every distinct intermediate tree is retained by hash with its landmark checks; missing/wrong-frame content remains partial even if the window ownership passed. Each requested frame is launched once; later distinct frames continue after capture failures, while `run-summary.json` and instrumentation fail overall if any capture is incomplete. Existing run IDs cannot be reused. Screenshots with unavailable window identity are unverified screen evidence, not automatically app frames. Screenshots still require independent visual inspection; stable accessibility identity is not a pixel-stability or layout verdict. Finishing a capture closes only the gallery activity and restores the UiAutomation service flags.

## Exact emulator handoff (Nik is sole operator)

Install only the newly frozen polish app/test APKs on **`emulator-5556`**, under the shared phone lock. Do not use a default serial or a physical serial. This emulator has ARM translation; synthetic UI/media testing is not native model/provider evidence. No model packs are needed or permitted.

After exact APK hash checks, invoke ONLY the named UI class:

```bash
adb -s emulator-5556 shell am instrument -w -r \
  -e class dev.vibevoice.podcast.gallery.SyntheticGalleryCaptureTest \
  -e galleryApproved synthetic-only -e galleryRunId ui-polish-01-default \
  -e galleryFrame all \
  dev.vibevoice.podcast.internal.test/androidx.test.runner.AndroidJUnitRunner
```

For an IME frame:

```bash
adb -s emulator-5556 shell am instrument -w -r \
  -e class dev.vibevoice.podcast.gallery.SyntheticGalleryCaptureTest \
  -e galleryApproved synthetic-only -e galleryRunId ui-polish-01-paste-ime \
  -e galleryFrame paste -e galleryIme true \
  dev.vibevoice.podcast.internal.test/androidx.test.runner.AndroidJUnitRunner
```

Artifacts are in app-private `files/ui-gallery/<run-id>/`. Pull with an explicitly targeted, locked emulator command. The instrument rejects non-ranchu/goldfish hardware, Android versions below34, non-private gallery task affinity, duplicate run IDs and unsupported frames. It does not accept wiring or duration-load approval. Frame acknowledgement is bounded to 10s; window readiness to 10s (another 10s after an IME request); each tree extraction to512 nodes /5s within a10s content-readiness deadline. Optional single-frame hold is capped at30s. Platform accessibility/screenshot calls can themselves block, so retain an external supervisor limit of **600s per all-frame capture /100s per single-frame or IME capture**. Seventeen deterministic host tests cover fresh-window/content enforcement (including the six observed stale-frame relationships) as well as acknowledgement mismatches, observed-ID/freshness/PID checks, requested-versus-observed title mismatch, delayed/absent/stale/invisible/wrong-ID roots, stable identity, keyboard focus, and screenshot/metadata retention across tree failure.

Run `ScreenSemanticsTest` and `UiInteractionRegressionTest` separately by class, with no model approval arguments. Capture both ordinary Galaxy-like sizing and320dp/2× font, restoring emulator settings afterward. Before/after screenshots and the exact tested commit/APK hashes must accompany the next UI QA result. Physical TalkBack, physical playback/export and model runtime validation remain separate unproven gates.
