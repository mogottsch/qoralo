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
  complete/remaining pair. Chapter counts belong to the player and the review
  screen, not to library rows.

## The test every string has to pass

*Would a person listening to podcasts care?* If not, it goes — or it goes behind
a disclosure. Applied in the second pass:

- **Never say it twice.** A status eyebrow above a button that says the same
  thing, a screen title above a headline of the same state, `Playing` next to a
  pause button, a chapter count under `CHAPTER 2 OF 7`, a second *Return to
  library* next to the ✕ — all removed.
- **No build configuration on user screens.** Settings names two things, *Script
  model* and *Voice model*, each ready or missing. Pack IDs, runtime backends,
  step counts, manifest hashes and the no-fallback guarantee live behind
  **Technical details**.
- **Success needs no receipt.** State the missing pack, not the present one;
  state the stall, not the healthy playback.
- **One prompt per input.** A field gets a label or a placeholder, not both plus
  a chat bubble asking the same question.
- **Our vocabulary is not theirs.** `Lock & create` became `Create audio`;
  `Audio attempt changed` became `This recording was replaced`.
- **Transient technical states are not news.** `Checking voice…`,
  `Sending request…` and similar sub-second lines are gone; the control's own
  state carries it.

Actionable failure information is never hidden behind a summary alone: the
failure panel states what is preserved, and the disclosure carries the runtime's
own message. The fail-closed boundary (no alternate model, no CPU fallback, no
hidden chapter splitting) is a property of the system recorded in the docs and
evidence, not a line the listener needs at the moment of failure.
