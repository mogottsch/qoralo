---
name: long-running-subagents
description: Use whenever launching any subagent in this repository. Give every workflow a 24-hour timeout so long exports, Android transfers, and inference jobs do not inherit the 30-minute default.
---

# Long-running subagents

For every `subagent` workflow in this repository:

- set `async: true`;
- set `timeoutMs: 86400000`;
- do not add smaller turn, tool, or child time limits unless the user requests them;
- keep one writer per worktree;
- when a worker finishes, immediately review/integrate its handoff and launch the next unblocked slice before yielding;
- after each validated milestone, update `docs/progress.json` and publish the preview dashboard;
- notify the user in chat and with `notify-send` when physical phone input is required.
