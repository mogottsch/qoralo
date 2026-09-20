# UI copy minimalism — validated build

Copy and density only. Generation, schema, repository, player, native runtime and
user data are untouched by this change.

## What moved

- **Delete episode** now asks once: title, the episode name, `Removes this episode
  from your device. This can't be undone.`, then **Cancel** / **Delete**. The
  worker/player lease behaviour it describes did not change — only the wall of text.
- Wizard hint headings, the provider-pipeline paragraphs, per-screen reassurance
  and the diagnostics definitions moved behind `DetailsDisclosure` rows:
  **Voice limits**, **Error details**, **About measurements**. Nothing was deleted
  from the record; the failure panel still states what is preserved and carries the
  runtime's own message plus the fail-closed boundary one tap away.
- Literal labels: **Create audio**, **Edit script**, **Open player**.
  Shorter statuses: `Draft ready`, `Audio queued`, `Deletion pending`,
  `Still generating`, `Waiting for more audio…`, `Chapter 2 of 3`.
- Numbers appear once: the player slider owns position/duration, job progress owns
  chapter counts.

See [the principle note](ui-copy.md).

## Validated build

Source `823d7af4` (pre-rename) validated on device; merged here after a path-aware
rebase onto the `dev.qoralo` package move as `3b63717f`.

- Run `podcast-app/.local/ui-minimal/phone/provider-app-ui-minimal-20260920t092414z`.
- **9/9 owned non-neural cases**: exact-pair blocked-teardown guard, four feature
  cases at default, the same four at 320dp/font2.
- **Six paired owned-window captures inspected: PASS** in both profiles. At
  narrow/font2 the confirmation now fits without scrolling, which the previous
  long-form copy did not.
- Guard: durable failure before self-only termination, stop→PID absence
  **68.609 ms**. Not an in-flight QNN cancellation claim.
- **0 model calls, 0 new user jobs, 0 real user deletions.** Current rows
  (2 episodes, 2 jobs, 2 sources, 4 episode files) and all 930 pre-existing
  persistent files were unchanged across the window; the failed SCRIPT job under
  investigation was present before and after, untouched.
- Host: JVM unit tests, debug/androidTest/release Kotlin all pass on the merged
  `dev.qoralo` source.

### Installed identity

The tested pair is installed under the **old** application id, which is the one
holding all user data:

- App `70394e79a7db70c14ae02d0aeba35dcf1a76caf7dce9e5a906d596dbf9fefffc`
- Test `abe68ac7358c64d7954fdf229559740c2d04e8ce7d2b4e6fd01aefb8c1de240a`
- replacing `bf53c566…721c` / `f1543993…3b0a4`, installed with `-r -t`, no
  uninstall and no data or cache clear.

`dev.qoralo.podcast.internal` is **not installed**. Merging the rename does not
move episodes; that migration remains a separate, undecided step.

## Limitations

- Owned new-cache/in-memory fixtures only; no real episode was deleted and no
  model ran. On-device SDK metric availability is still unverified.
- The `lock` gallery frame remains uncapturable: launching straight into an open
  confirmation trips `ReviewScreen`'s revision-change dismissal guard. Reproduced
  on the unmodified screen (`ui-baseline-lock-probe`); the guard was not weakened.
- Device-identity gating now records the platform build instead of pinning it.
  Earlier physical evidence was produced on `S918BXXSAFZG1`; this run is
  `S918BXXSAFZH3` and prior results were not re-verified on it.
- A leftover app process and its `:generation` process were force-stopped by
  decision before the run, after confirming no queued/running job, no
  `GenerationService` record and no audio ownership; both PID states are recorded.
  That basis does not prove the process was a stale remnant.
