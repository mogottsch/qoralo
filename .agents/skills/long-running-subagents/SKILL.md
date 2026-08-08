---
name: long-running-subagents
description: Use whenever launching any subagent in this repository. Give every workflow a 24-hour timeout so long exports, Android transfers, and inference jobs do not inherit the 30-minute default.
---

# Long-running subagents

The goal is to complete all 39 steps in `docs/progress.json` autonomously. Keep looping—launch, validate, integrate, update progress, and launch the next unblocked work—until all 39 steps are complete or a hard blocker in `autonomy.stop_conditions` requires the user. Never leave the fleet idle while an unblocked step remains.

For every `subagent` workflow in this repository:

- set `async: true`;
- set `timeoutMs: 86400000`;
- do not add smaller turn, tool, or child time limits unless the user requests them;
- keep one writer per worktree;
- when a worker finishes, immediately review/integrate its handoff and launch the next unblocked slice before yielding;
- after each validated milestone, update `docs/progress.json` and publish the preview dashboard;
- notify the user in chat and with `notify-send` when physical phone input is required.
