# UI copy and density

Minimal by default, details on demand.

- One idea per line. Controls name their action: **Delete**, **Create audio**,
  **Edit script**, **Open player**. No sentence explains what the button already says.
- Screens carry the content, not reassurance. Guarantees the app already honors
  (no fallback route, unchanged drafts, retained sources, lease-safe deletion)
  are not repeated on every screen.
- Warnings stay where the risk is. The delete dialog keeps exactly two facts:
  what is removed, and that it cannot be undone.
- Everything technical still reachable: `DetailsDisclosure` holds voice limits,
  error details, and diagnostics definitions behind a labelled row. Nothing is
  deleted from the record, only from first sight.
- Status text is short and literal: `Draft ready`, `Audio queued`,
  `Deletion pending`, `Still generating`, `Waiting for more audio…`.
- Numbers appear once. The player slider already shows position and duration, so
  no second duration line; job progress shows `Chapter 2 of 3`, not a second
  complete/remaining pair.

Actionable failure information is never hidden behind a summary alone: the
failure panel states what is preserved, and the disclosure carries the runtime's
own message plus the fail-closed boundary.
