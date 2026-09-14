# Episode diagnostics/deletion — final non-neural feature check

**PASS at this scope; exact tested pair left installed.** See the
[user handoff](../../../docs/episode-management-handoff-2026-09-14.md) for navigation,
implementation boundaries and the original failure history.

- Tested source `012c965f`; merged into current main as `51993598` without changing
  the tested app source/config or unrelated dirty working files.
- App `bf53c566a160c018e56d19e0aac5e7f9578a6d3f168326fa82163bdcf1c7721c`.
- Test `f1543993c2ff77441b3fd1e4c4fa131975a6a30bee2d347619a0adc646f3b0a4`.
- Final9/9 Android cases: four new-owned feature fixtures at default and narrow/
  font2, plus the exact-pair non-neural blocked-teardown guard.
- Six real focused-window/compositor images inspected: menus, settled deletion
  confirmations and unavailable-history details pass in both profiles. Font2
  confirmation text scrolls while actions remain visible. No visual pass is
  inferred merely from test semantics or metadata.
- Guard failure was durable before self-only termination; observed stop→PID
  absence60.120833ms. Not a QNN in-flight cancellation or DSP latency claim.
- All14 current episodes,20 jobs,183 episode files and every other user row
  unchanged. All1058 existing persistent files, shared model roots and private
  benchmark evidence unchanged. The versioned24-byte ProfileVerifier cache was
  captured/decoded/bound to actual PackageInfo and was unchanged, not excluded.
- Settings restored, owner processes/leases and new fixture cache roots absent,
  cleanup errors0, phone lock released, post-installed hashes verified.
- Zero model calls, new user jobs or actual user-podcast deletions. SDK throughput/
  TTFT availability remains unverified; old statistics are not fabricated.

This folder contains bounded receipts and hashes only. Raw DB/WAL snapshots,
user-file inventories, before/after framework-cache bytes, full command records,
and images (including system bars) remain private under `.local/episode-management/`.
Earlier failed, cropped, unavailable or unpaired captures remain retained and
are not retroactively passed. The earlier same-app player profiles and retained
IO replay are separate evidence, not claimed rerun in this final nine-case check.
