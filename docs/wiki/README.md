---
title: Using this vault
kind: guide
project: vibevoice-android-spike
---

# Using the VibeVoice Android Wiki in Obsidian

Open this directory as a separate Obsidian vault:

```text
/home/moritz/dev/vibevoice-android-spike/docs/wiki
```

In Obsidian, choose **Open folder as vault** and select that directory. No community plugins are required. The repository ignores `.obsidian/`, so workspace layout, enabled plugins, and other personal UI state remain local.

The Markdown files in this directory are canonical project wiki sources. Do not export or copy them into a personal vault. Git keeps this project vault current; a personal vault may link into it with an Obsidian URI if desired.

## Conventions

- Use ordinary relative Markdown links so pages remain portable outside Obsidian.
- Lead with a plain-language explanation.
- Treat committed experiment files and the benchmark registry as authoritative evidence.
- Cite repository paths and evidence commits for technical claims.
- Keep execution proof, structural audio validity, numerical comparison, and listening review distinct.
- Add every maintained page to `index.md` and record substantive work in `log.md`.
