---
version: 2
slug: docs-qoralo-blog-index-html
primary_target: docs/qoralo-blog/index.html
related_targets: [docs/qoralo-blog/style.css, docs/qoralo-blog/article.js, docs/qoralo-blog/README.md, docs/qoralo-blog/REVIEW.md, docs/qoralo-blog/evidence/source-audit.md]
---

# Local source-to-podcast technical article

Mode: Read. Audience is technical. Keep the narrative short, explain a real engineering mechanism, and give one concrete takeaway. NotebookLM-inspired local phone inference is the subject; Qoralo is the prototype name, not the headline. Moritz rejects subtext, repeated qualifications and AI-sounding copy, and wants to edit the text himself. No new phone activity, model inference, app/runtime/deck changes or public publication.

## Direction contract

THESIS: A port that produces a valid-looking audio file has not shown its inference was valid. Show the phone placement, let the reader hear the original and recovered Pocket TTS clips, then explain a concrete source defect found in the old runner: a non-owning tensor outliving its buffer.

OWN-WORLD: Inherit the presentation's #0b1017 canvas, mint #8ee8c2 HTP, lilac #c2a9f4 GPU and blue #9bbdff CPU. Flat technical drawings, restrained local sans. No decorative gradients/cards/hero metrics/eyebrows, generated mockups or invented waveforms.

STORY: NotebookLM prompts the phone question; the intro is plain placeholder text for Moritz to rewrite. Phone placement, then the first Android port with exact historical recordings, then the lifetime bug. The one-voice format is explicit. The whole-chapter section, setup chart and EOS-logit diagram are removed.

CLAIM LIMITS (must stay visible): the lifetime bug is confirmed in retained source and a host ASAN test; it is not proved to have caused the 10.72 s clip. The old binary is not bound to the source, the old model was not replayed with only the fix, and the fixed-cache graph changed more than this. The zero-encoder/invalid-Bria failure is a separate cause. The 10.72 s clip is Android CPU, not HTP.

FORM: Two custom progressively enhanced figures (processor route; buffer/tensor lifetime with a keep-alive variant), native exact-file players, inline plain-text editing with local restore, and `Save HTML copy`. Static content stays meaningful when JavaScript fails. No external fonts, UI dependencies, analytics or raster assets.

## Editing contract

`[data-edit]` text becomes `contenteditable="plaintext-only"` on request. Edits persist in localStorage keyed by path. Saving builds from the original page source, not the live DOM, strips editor state, and adds a `<base>` so the copy finds its assets. Never writes into the repository.

## Motion and interaction thesis

Focal moment: the four-step buffer lifetime (allocate, wrap, leave scope, consume), user-stepped, with an optional bounded replay that stops at the last step and cancels on manual input, hidden tab or offscreen. Route buttons emit one illustrative signal. Meaning survives reduced motion through text and border/color states. No endless animation; audio never autoplays and players do not overlap.

## Finish record

See REVIEW.md. Browser suite passed five widths × two scopes × four stages, keyboard sources, bounded replay, reduced motion, exact WAV decoding, editing, local restore, a saved copy reopened from disk, and script-failure fallback. Desktop and mobile captures inspected; one measure fix to the title. Pi independently confirmed the source defect and claim limits; no new three-pass review of this copy.

Disposition: finish at this scope for Moritz to edit and review. Final app demo/audio and any public publication remain separate.
