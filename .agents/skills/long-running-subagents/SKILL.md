---
name: long-running-subagents
description: Enforce the VibeVoice Android spike's subagent runtime policy. Use this skill whenever launching, resuming, or replacing any pi-subagents worker, scout, researcher, reviewer, oracle, or scripted workflow in this repository. Every new subagent workflow gets a 24-hour runtime allowance so long exports, Android transfers, and model validation are not killed by the harness's 30-minute foreground default.
---

# Long-running subagents

Apply this policy to every `subagent` execution in this repository.

## Runtime policy

Set the workflow-level timeout explicitly:

```json
{
  "async": true,
  "timeoutMs": 86400000
}
```

`86400000` milliseconds is 24 hours. Treat it as a safety ceiling, not an expected task duration.

Do not omit the explicit timeout. Some async launches are projected as foreground runs by the current harness and otherwise inherit a 30-minute default, which already interrupted a valid streaming-decoder implementation.

Do not add a restrictive `turnBudget`, hard `toolBudget`, or smaller child timeout unless the user explicitly requests it. Narrow the task through its scope and acceptance criteria instead.

## Launch checklist

1. Run `subagent({ action: "list" })` and select only an executable, enabled agent.
2. Give the child a bounded milestone, exact repository path, existing evidence, validation contract, and stop conditions.
3. Set `async: true` and `timeoutMs: 86400000` on the workflow.
4. Keep one writer per worktree. Use fresh-context read-only agents in parallel; isolate parallel writers in separate worktrees.
5. Attach implementation work to the active VibeVoice mission when available.
6. Preserve partial files and ignored artifacts when replacing an interrupted worker.
7. Do not interrupt a quiet worker merely because an export, model load, ADB transfer, or inference run takes time.

## Example

```javascript
subagent({
  workflowScript: "return runs.run('lane-a', {agent:'worker', task:'Complete the documented Lane A milestone. Run validation and report changed files, evidence, and residual risks.'})",
  cwd: "/home/moritz/dev/vibevoice-android-spike",
  context: "fork",
  async: true,
  timeoutMs: 86400000,
  missionId: "<active mission id>",
  acceptance: {
    level: "checked",
    evidence: ["changed-files", "commands-run", "validation-output", "residual-risks", "no-staged-files"]
  }
})
```

## User attention

If work is blocked on a physical phone action, authorization prompt, proprietary license, privileged system change, personal-device access, paid service, destructive action, or major architecture pivot, notify the user in chat and with `notify-send`. Routine export/runtime failures should be investigated autonomously.
