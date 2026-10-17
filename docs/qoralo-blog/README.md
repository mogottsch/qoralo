# Building a NotebookLM-like podcast on my phone

Open `index.html`, or serve the repository root:

```sh
python3 -m http.server 8766 --bind 127.0.0.1
# http://127.0.0.1:8766/docs/qoralo-blog/
```

A short technical article about a source-to-podcast workflow with local phone inference. Qoralo is the experiment's app name, not the article's subject. The prototype generates a script and narrates it in one voice; this is not NotebookLM's conversational format or an established quality match.

## What the page contains

1. **Phone placement:** Gemma on GPU, Supertonic on NPU/HTP, CPU orchestration. The route buttons show one illustrative signal; they are not timing.
2. **The first Android port:** the exact historical Pocket TTS Android CPU recordings, listed working clip first (fixed-cache derivative, 4.48 s) and then the broken one (original dynamic graph, 10.72 s). No audio was generated, trimmed, normalized or re-encoded for the page.
3. **Why it went wrong (the main section):** the graph replaces a NaN first input with a learned start-of-sequence vector (`Where(IsNaN(x), bos_emb, x)`). A desktop replay of the old loop that changes only that first input reproduces the retained Android stop scores when the input is all zeros, and does not when it is NaN. The page shows the three score trajectories, a frame scrubber with exact readouts, and the source excerpt that explains how a freed buffer could turn the NaN marker into something else.
4. **The fix we applied:** the fixed-cache graphs, built for the NPU, take no NaN marker; one sentence.

The whole-chapter section, the EOS-logit-only diagram, the setup chart and the four-step buffer-lifetime stepper were removed. The chart is baked into the HTML (works without JavaScript) by `evidence/build-chart.py` from `evidence/bos-zero-replay.json`.

## What is and is not established

Reproduced on a host: with the same text, voice cache and noise, an all-zero first input matches the retained Android original-graph stop scores over all 134 frames (max difference 0.074, mean 0.006) and never reaches the stop threshold, as on the phone. The correct NaN input differs by up to 16.4 and stops at frame 53. Of 62 partly zeroed prefix/suffix inputs, none matched. The same replay with the correct input matches the retained Android fixed-cache stop scores within 0.0021. Pi independently reran the replay.

Confirmed in source: the old runner wraps a NaN buffer in a non-owning tensor and frees it before `Run()`; a host AddressSanitizer test using ONNX Runtime's real tensor API shows the dangling read (`evidence/source-audit.md`).

**Inferred, not observed:** that the phone's freed buffer held zeros. Nothing read the phone's memory. Also not shown: that the retained source is exactly what was built into the old phone executable, and anything about how the replay would sound (no audio was produced). The exact original `flow_lm_main` graph is not retained; the replay uses a same-size reconstruction that reproduces the retained desktop run (first score -9.8847, stop at 53). The scan is over prefix/suffix patterns, not all possible inputs. The separate invalid-Bria/zero-encoder failure is a different cause.

## Editing the copy

`Edit text` makes the outlined paragraphs and headings editable as **plain text**. Edits persist in this browser's local storage so a reload keeps them. `Save HTML copy` downloads `phone-podcast-edited.html`, built from the original page source rather than the live DOM, so it carries your text but no editor state. It adds a `<base>` pointing at the original folder, so the saved copy still finds `style.css`, `article.js` and the WAVs if you move it. Nothing writes into the repository; to keep a revision, copy that file in yourself. Escape leaves edit mode; Ctrl/Cmd+S saves while editing.

Only paragraphs you change are stored or exported, so untouched text keeps its inline formatting; a paragraph you edit becomes plain text. The intro is placeholder wording, not Moritz's voice. Replace it.

## Browser checks

```sh
PW="$HOME/.pi/agent/skills/chrome-browser/scripts/pw"
"$PW" -s=qoralo-story open http://127.0.0.1:8766/docs/qoralo-blog/
"$PW" -s=qoralo-story run-code "$(python3 -c 'from pathlib import Path; print(Path("docs/qoralo-blog/browser-checks.js").read_text())')"
"$PW" -s=qoralo-story close
```

Covers chart data against the evidence JSON, five widths × three input modes with chart/tick/annotation geometry, the keyboard scrubber with exact readouts, wording guards against overclaiming, reduced motion, muted decoding of both WAVs with exclusive playback, inline editing with local restore, an exported copy reopened from disk with a working chart, print, and script-failure fallback. Browser playback is not a human listening verdict.

Reproduce the replay (about 3 s, host CPU, needs the retained local model files):

```sh
experiments/0024-pocket-tts-qnn-precompiled-context-startup/.local/export-venv/bin/python docs/qoralo-blog/evidence/bos-zero-replay.py
python3 docs/qoralo-blog/evidence/build-chart.py
```

`article.js` is local only: no libraries, fonts, analytics or remote requests. Nothing autoplays.

Private draft. No public article or app release is announced.
