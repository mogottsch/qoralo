# Streaming playback guard correction

The prior attempt remains an **implementation failure / UNKNOWN**, with no capture or model consumed. Its `printf: Argument list too long` error is preserved; no busy/idle conclusion is inferred.

The corrected guard streams `dumpsys audio` directly into a UID-filtered awk parser. The complete dump is never stored in a shell variable, passed through argv, or saved. Only a small explicit upstream exit-status marker is printed after the source command. Package-UID lookup also has an independently checked source status.

The parser identifies the current-player section, reports only target-UID active/inactive counts, and excludes unrelated players and event history. Missing/duplicate source markers, nonzero upstream exit, missing schema or malformed current-player rows yield UNKNOWN; target active playback blocks without stopping it. Explicit empty/paused/stopped target state can establish quiescence alongside the separate generation/test checks and Pi's scheduling attestation. Main-process absence needs no audio dump.

Nine bounded synthetic tests passed, including >2 MiB streamed input, idle/active, unrelated UID, malformed data, upstream failure and missing/duplicate status. No phone or model was run for this correction. Model, observer, stage and capture budgets are unchanged.

Pi granted one fresh short window after this corrected controller is frozen, subject to live `phone.lock`, fresh full APK identities and actual quiescence checks. Janek's app E2E takes priority if ready. No additional user approval or repeated blind preflight is implied.
