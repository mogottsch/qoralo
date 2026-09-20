# Host scope-test baseline (2026-09-20)

Reference numbers for `podcast-app/tools/tests`, so a dirty shared checkout is not mistaken for a
regression. All three runs used pristine `git archive HEAD` extractions; no `.git` state was touched.

| Tree state | Result |
| --- | --- |
| `HEAD` alone (`2f9af40e`) | 5 failures + 5 errors = **10** |
| `HEAD` + the chapter constrained-decoding/retry change | 5 failures + 5 errors = **10** |
| `HEAD` + nik's uncommitted `tools/duration_phone_guard.py` | **17** |

Reproduce:

```bash
git archive HEAD podcast-app | tar -x -C /tmp/baseline
cd /tmp/baseline/podcast-app && python3 -m unittest discover -s tools/tests
```

The 10 failures at `HEAD` are the documented frozen gates. They predate this note and are not caused
by the package rename: `app/schemas` contains only `dev.qoralo.podcast.data.PodcastDatabase`, tracked
and clean.

The chapter change (constrained chapter decoding plus the bounded parse-failure retry) adds **zero**.
It also leaves the source-string pins in `tools/tests/test_user_script_diagnostic.py` intact.

## Open item for the guard owner

The 10 -> 17 delta is entirely the uncommitted `tools/duration_phone_guard.py` edit that moves
`ro.build.fingerprint` from `IDENTITY` into the new recorded-only `RECORDED_PROPERTIES`. Two effects:

1. **Fixture KeyError (7 errors, `test_duration_phone_guard`).** `PhoneGuard.identity` now also reads
   `RECORDED_PROPERTIES`, but the fake device in `tools/tests/test_duration_phone_guard.py` resolves
   every `getprop` through `g.IDENTITY[key]`, which no longer holds the fingerprint. The fixture needs
   a source that still answers it, e.g. `{**g.IDENTITY, 'ro.build.fingerprint': g.PRIOR_FINGERPRINT}`.
2. **Frozen `host_identity` digests.** `duration_phone_guard.py` is hashed into `host_identity()`, so
   scope tests pinning the old digest fail until the pins are refreshed with the landed change.

Both belong to whoever lands the guard change; they are not caused by the chapter work. The
recorded-only fingerprint decision itself is unreviewed here and is only described, not endorsed.

Note the shared checkout: several sessions work in one tree, so `git status` may show another
session's uncommitted files. Use `git archive HEAD` or a separate worktree for a baseline, never
`git stash`, which can silently disrupt a session mid-edit.
