---
version: 4
slug: docs-qoralo-blog-index-html
primary_target: docs/qoralo-blog/index.html
related_targets: [docs/qoralo-blog/style.css, docs/qoralo-blog/article.js, docs/qoralo-blog/browser-checks.js, docs/qoralo-blog/README.md, docs/qoralo-blog/REVIEW.md, docs/qoralo-blog/evidence/]
---

# Local source-to-podcast technical article

Mode: Read. Technical but general blog readers. Short, condensed, no subtext, no meaningless values (a number stays only if a reader would act on or understand it: RTF yes, frame cap no). NotebookLM-inspired local phone inference is the subject; Qoralo is the prototype name, not the headline. Moritz wants to edit the text himself and dislikes AI-sounding copy. Do not publish or deploy the article (the repository is public, the article is an unpublished draft Moritz is still editing); no new phone activity, model runs or app/runtime/deck changes without his go-ahead.

## Direction contract

THESIS: How close can a NotebookLM-like source-to-podcast workflow get with all inference on a phone? Show what we tried, what we ended up with, and one instructive failure.

OWN-WORLD: Inherit the presentation's #0b1017 canvas, mint #8ee8c2 NPU/HTP, lilac #c2a9f4 GPU, blue #9bbdff CPU, amber #efb578 for failures. Flat technical drawings, restrained system sans. No decorative gradients, cards, hero metrics, eyebrows, generated imagery or invented data.

STRUCTURE (agreed with Moritz):
1. Title, intro and the "So I wondered" question: **approved and frozen** (a test fails if the text changes).
2. Demo video slot (explicit missing-asset notice until `media/demo.mp4` exists; no synthetic footage).
3. What I tried (first person; the whole article is first person): Speech (five-row table, "CPU RTF" / "NPU RTF", a rendered RTF formula) and Script writing (seven-row Prefill / Decode tokens-per-second table, grouped by model). Tables are sorted by explicit rules in the generators. No footnotes under the tables; their caveats are in the technical notes.
4. Where it ends up: the full-system flow as device swimlanes (Computer, Phone CPU, Phone GPU, Phone NPU), one column per step in order. Review & edit is an optional chat with Gemma (CPU you, GPU Gemma, two-way loop). Narrow screens: a single-column list with device chips.
5. The first Android port: the exact historical Pocket TTS clips, working one first.
6. Why it went wrong: a plain gist and one chart (stop score over seconds of speech, both lines from the same controlled phone window).
7. Close: "If you wanna take a look, here it is" linking the repository (now public). No fix section, no code excerpt, no takeaway, no "what is left".

CLAIM LIMITS: the phone check observed the first input as zeros in the instrumented build and NaNs with the buffer kept alive; the old executable and the original graph are not retained; the second unmodified run differed (the failure is nondeterministic); no allocator explanation; no listening verdict on new audio. These live in the technical notes and `evidence/`, not in the way of the explanation. Review vetoes: RTF only within comparable rows and as plain values; "sounds good" only for a row's own exact reviewed output; a package size is not measured memory; LLM rates never mixed with TTS RTF and never presented as script speed or quality; the Gemma NPU row shows its different build and its repetition failure; flow tags describe the selected neural routes, not every operation.

FORM: Static figures (no animation): the system flow (generated HTML/CSS grid with exact SVG connectors, `evidence/build-system-flow.py`) and the stop-score chart (baked-in SVG from the phone raw results); two tables generated from committed packets (`evidence/build-table.py`, `build-llm-table.py`); a MathML formula; native exact-file audio players that never autoplay and never overlap; a video slot. Inline plain-text editing with local restore and `Save HTML copy`. Everything works without JavaScript except editing. No external fonts, libraries, analytics or runtime requests.

## Editing contract

`[data-edit]` text becomes `contenteditable="plaintext-only"` on request. Only edited paragraphs are stored (localStorage keyed by path) or exported. Saving builds from the original page source, strips editor state, and adds a `<base>` so the copy finds its assets. It never writes into the repository.

## Verification

`browser-checks.js` (Playwright via the Chrome wrapper) checks: the frozen opening, the demo slot and closing line, the gist, the chart against the phone raw results, both tables value by value against their packets, the formula as a rendered fraction, the system diagram (eleven steps, lane per device, the review chat loop, caption, banned content, exact connector, loop and NPU-box geometry), receipts against the notes in both directions, five widths (320 to 1440) of layout, exact WAV order and decoding, editing and export, print, script-failure fallback, and no external requests. See REVIEW.md for provenance and review history.
