# Building a NotebookLM-like podcast on my phone

Open `index.html`, or serve the repository root:

```sh
python3 -m http.server 8766 --bind 127.0.0.1
# http://127.0.0.1:8766/docs/qoralo-blog/
```

A short technical article about a source-to-podcast workflow with local phone inference. Qoralo is the experiment's app name, not the article's subject. The prototype generates a script and narrates it in one voice; this is not NotebookLM's conversational format or an established quality match.

## What the page contains

1. **Phone placement:** Gemma on GPU, Supertonic on NPU/HTP, CPU orchestration. The route buttons show one illustrative signal; they are not timing.
2. **The first Android port:** the exact historical Pocket TTS Android CPU recordings, original dynamic graph (10.72 s) and fixed-cache derivative (4.48 s). No audio was generated, trimmed, normalized or re-encoded for the page.
3. **A tensor lifetime bug:** the retained original runner wraps `bos.data()` in a non-owning `Ort::Value`, then lets `bos` go out of scope before `Run()`. The interactive diagram steps through allocate, wrap, leave scope and consume, with a keep-alive variant.

The whole-chapter section, the EOS-logit comparison and the setup-time chart were removed. The first-logit difference was an observation, not an explanation, and the lifetime bug makes "identical input" unproven for that run.

## What is and is not established

Established: the source defect (`evidence/source-audit.md`), and a host-only AddressSanitizer reproduction using the real ORT non-owning tensor API (`evidence/bos-lifetime-repro.cc`). No model was loaded; no phone was used.

Not established: that this defect caused the exact historical recording. The old phone binary hash is not bound to the retained source, and nobody has replayed the old model with only the lifetime fixed. The fixed-cache graph changed more than this one lifetime. The separate invalid-Bria/zero-encoder failure is a different cause. The article says this on the page.

## Editing the copy

`Edit text` makes the outlined paragraphs and headings editable as **plain text**. Edits persist in this browser's local storage so a reload keeps them. `Save HTML copy` downloads `phone-podcast-edited.html`, built from the original page source rather than the live DOM, so it carries your text but no editor state. It adds a `<base>` pointing at the original folder, so the saved copy still finds `style.css`, `article.js` and the WAVs if you move it. Nothing writes into the repository; to keep a revision, copy that file in yourself. Escape leaves edit mode; Ctrl/Cmd+S saves while editing.

The intro is placeholder wording, not Moritz's voice. Replace it.

## Browser checks

```sh
PW="$HOME/.pi/agent/skills/chrome-browser/scripts/pw"
"$PW" -s=qoralo-story open http://127.0.0.1:8766/docs/qoralo-blog/
"$PW" -s=qoralo-story run-code "$(python3 -c 'from pathlib import Path; print(Path("docs/qoralo-blog/browser-checks.js").read_text())')"
"$PW" -s=qoralo-story close
```

Covers five widths × two scopes × four lifetime stages, keyboard sources, bounded replay and interruption, reduced motion, muted decoding of both WAVs with exclusive playback, inline editing with local restore, an exported copy reopened from disk with working styles, script and diagram, and script-failure fallback. Browser playback is not a human listening verdict.

`article.js` is local only: no libraries, fonts, analytics or remote requests. Nothing autoplays.

Private draft. No public article or app release is announced.
