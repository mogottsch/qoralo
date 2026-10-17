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
3. **Why it went wrong (the main section):** the graph replaces a NaN first input with a learned start-of-sequence vector (`Where(IsNaN(x), bos_emb, x)`). The old runner frees that NaN buffer before inference. On the phone, a build that prints the 32 start values showed zeros (2 of 2 runs); keeping the buffer alive alone gave NaNs, a stop at frame 53 and 4.48 s of audio (4 of 4 runs). The page shows the phone's stop scores against a desktop replay that changes only the first input, with a frame scrubber and exact readouts, and the source excerpt.
4. **The fix we applied:** the fixed-cache graphs, built for the NPU, take no NaN marker; one short section.

The whole-chapter section, the EOS-logit-only diagram, the setup chart and the buffer-lifetime stepper were removed. The chart is baked into the HTML (works without JavaScript) by `evidence/build-chart.py` from `evidence/bos-zero-replay.json`.

## What is and is not established

**Observed on the phone** (`evidence/phone-bos-check/`, one CPU-only window, Pi-scheduled, 8 planned runs, no retries; rebuilt retained source, NDK 27, same ORT 1.27.1): the instrumented build printed 32 zero words before `Run()` with the original lifetime (2 of 2) and 32 NaN words with the buffer kept alive (2 of 2). The unmodified original's first run reproduced the retained 10.72 s failure recording byte for byte (and both dump runs did too). A second unmodified run gave a different wrong answer (first stop score -4.37, no stop), so the failure is nondeterministic. The four kept-alive runs stopped at frame 53 with identical 4.48 s audio (correlation 0.999996 with the accepted fixed-cache recording; no new listening verdict).

**Reproduced on a host:** with the same text, voice cache and noise, an all-zero first input matches the retained Android stop scores over 134 frames (max difference 0.074, mean 0.006) with no stop; the correct NaN input differs by up to 16.4 and stops at 53. None of 62 prefix/suffix partly zeroed inputs matched. Pi independently reran it.

**Confirmed in source:** the old runner wraps a NaN buffer in a non-owning tensor and frees it before `Run()`; a host AddressSanitizer test using ONNX Runtime's real tensor API shows the dangling read (`evidence/source-audit.md`).

**Not shown (kept in the page notes, not in the way of the explanation):** the old phone executable (`a11685f5...`) is not retained, so nothing is bound to it; the exact original `flow_lm_main` graph is missing and a same-size reconstruction was used (it reproduced the failing recording exactly); the dump build may perturb allocation and the unmodified build's start values were never printed; there is no explanation for why this allocator returned zeros; no replay or phone output has been listened to. The invalid-Bria/zero-encoder failure is a different cause.

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

Covers chart data and the phone-check receipts against the evidence JSON (including that the page text matches the exact run counts), five widths × three input modes with chart/tick/annotation geometry, the keyboard scrubber with exact readouts, wording guards in both directions (no stale "inferred", no invented allocator explanation, limits kept in the notes), reduced motion, muted decoding of both WAVs with exclusive playback, inline editing with local restore, an exported copy reopened from disk with a working chart, print, and script-failure fallback. Browser playback is not a human listening verdict.

Reproduce the replay (about 3 s, host CPU, needs the retained local model files):

```sh
experiments/0024-pocket-tts-qnn-precompiled-context-startup/.local/export-venv/bin/python docs/qoralo-blog/evidence/bos-zero-replay.py
python3 docs/qoralo-blog/evidence/build-chart.py
```

`article.js` is local only: no libraries, fonts, analytics or remote requests. Nothing autoplays.

Private draft. No public article or app release is announced.
