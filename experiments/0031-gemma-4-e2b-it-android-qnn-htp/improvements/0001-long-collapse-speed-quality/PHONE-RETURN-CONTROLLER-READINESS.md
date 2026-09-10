# Candidate phone-return controller — mocked readiness, not phone permission

`tools/phone_return_controller.py` and `tools/phone_return_shell.py` implement the candidate-specific lifecycle proposed in the earlier plan. The default is **plan-only**. Preparation/testing did not call real ADB, open the repository's actual phone lock, hash/load the real model payloads, start Genie, or alter the frozen stage/baseline runner.

## Fixed scope and authorization gates

The controller has no long/prompt/model/backend override. Its only executable scope is the frozen stage's **one fresh-dialog short request with a 16-token engineering/noncanonical cap**. The base config stays at 2048; the reviewed script performs the explicit diagnostic override. No campaign/registry or long-fidelity result is implied.

Execution requires all of:

1. `--execute` (absent by default).
2. Exact externally reviewed stage digest `584841604ecf97a1a916c9a7f765e49ff9f7a2ee751a61fda9e9e6588f02fe25`.
3. A safe, explicit `--pi-slot` ID from an actual fresh Pi grant. The string is a manual attestation, **not cryptographic permission** and must not be invented by the caller.
4. A fresh safe `--run-id` and exclusive output-directory creation. One controller object may execute only once.
5. Full local stage byte/mode verification against the external digest.
6. A nonblocking `phone.lock` lease before every ADB action, including identity, staging, polling, signals, pull and cleanup.
7. A one-use slot marker, claimed under the lock before the first ADB call. Transport failure consumes the slot; no automatic retry/reconnection is implemented.

The reviewed device is serial `R5CW81PR8SY`, Samsung SM-S918B/dm3q, SM8550, arm64-v8a, Android16/SDK36, boot-complete/green/locked. The exact retained build fingerprint is pinned too. A changed build stops for review rather than silently changing comparison conditions.

Local and remote stage hashes include the frozen manifest, checksum list and **every payload**, plus the generated control-script hashes. Runner mode must be 0555. No old-context gate is weakened; no NativeKV/cache-export/import/spec or fallback path is added. The frozen stage is not edited: generated launcher files live in the new host output/control directory and then the new remote root.

## Process and lock safeguards

The remote root is `/data/local/tmp/vibevoice-0031-fp16-<safe-run-id>` and must be newly created. It is never confused with the completed campaign's root.

Three roles are recorded: model-entry/Genie, wrapper, and watchdog. Each writes its PID and Linux starttime before progressing. The model entry must persist its identity before `exec` of the exact staged binary with exactly `-s first-short.script`. The controller validates `/proc` starttime, resolved executable and exact NUL-delimited argv. Changed records, PID reuse, wrong executable/argv, extra empty arguments, malformed records, and unknown identity refuse signals and destructive cleanup.

Before a controller-directed signal, trusted host-generated shell logic rechecks the current identity again. The watchdog applies the same checks. No process-name-wide kill is used. Zombie/exit races are waited for or confirmed absent, not blindly signalled. Missing identity never means absence.

**Residual race:** these are sequential `/proc` checks followed by a numeric-PID `kill`, not an atomic operation. No pidfd or equivalent kernel identity-bound signal primitive is used. Starttime/executable/argv/byte-count rechecks narrow the race but cannot eliminate the final check-to-signal window. Mock tests prove refusal on observed mismatches; they cannot establish that this real race is impossible. This limitation requires acceptance during phone-run review.

The lease descriptor is explicitly non-inheritable/CLOEXEC, and every real ADB subprocess uses `close_fds=True` with no passed descriptors. A server spawned by that client therefore does not inherit the lease. Client subprocesses have their own host process group for bounded TERM/KILL/reap on command timeout; no existing global ADB server is deliberately killed or restarted.

## Independent deadlines

| Phase | Wait budget / deadline |
|---|---:|
| Typical identity/preflight call | 15 s |
| Stage push | 600 s |
| Remote full payload hash check | 180 s |
| Control-script transfer | 60 s |
| PID/progress call | 10 s, clamped to its enclosing deadline |
| Missing model identity at startup | 60 s |
| Full first-short process (including load) | 1,800 s host monotonic deadline |
| Independent remote watchdog | 1,800 s using `/proc/uptime`, then validated TERM / 5 s grace / revalidated KILL |
| Owned-process cleanup | 120 s overall |
| Raw pull | 180 s independently, even after process timeout |
| Scoped root removal/absence | 60 s overall |

ADB wait budgets can add up to five seconds of local client termination/reap grace. They are not a promise that an uninterruptible kernel operation can always be reaped immediately; spawn PID/group evidence is retained if a client fails to finish. Absence checks cover the three recorded roles, with a settling interval for the watchdog's short sleep children, not unrelated DSP/system services.

SIGINT/SIGTERM trigger bounded retention/cleanup, not SIGSTOP. Unknown identity or failed signal/absence proof can leave a remote process unresolved; the controller reports that explicitly instead of claiming deadline enforcement or clean termination. A later cleanup/retrieval attempt needs new permission.

## Raw first; do not discard the only evidence

Every attempted ADB command gets argv/deadline/exit/error metadata and exact stdout/stderr files before further processing. The model writes its own stdout/stderr/output/profile/log files into the remote evidence directory. After completion/error/timeout, stop and verify the owned roles, then pull that directory **before** calling the optional metric hook.

The default hook does not compute metrics. Query success, provider placement and fidelity remain null even with process exit0. A warning/aborted query may return normally in the SDK; offline raw review must determine what occurred. Optional parser failure produces null/reason without replacing a collected process exit or deleting partial output.

If raw pull fails or is incomplete, preserve the local partials **and retain the remote root**, even when processes are confirmed absent. The result records `processes_absent_raw_incomplete_remote_root_retained` and its exact `retained_remote_root`. Do not delete the only remaining evidence. Unknown PID state similarly yields a retained-root/cleanup-incomplete result. Only a completed raw pull plus confirmed process absence allows removal of the owned root and a separate absence check. Failed absence confirmation is unknown, never success.

## Safe command now

```bash
python3 experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/tools/phone_return_controller.py
```

This only prints a plan. It does not create an execution directory or touch ADB/phone.lock/model payloads.

Future invocation **only after this controller is reviewed and Pi grants a fresh slot**:

```bash
python3 experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/tools/phone_return_controller.py \
  --execute \
  --reviewed-stage-digest 584841604ecf97a1a916c9a7f765e49ff9f7a2ee751a61fda9e9e6588f02fe25 \
  --pi-slot "$PI_GRANTED_SLOT_ID" \
  --run-id "$NEW_FIRST_SHORT_RUN_ID"
```

Unset slot/run variables are rejected. Set them only from a fresh actual Pi grant and a new run ID; no permission is granted by this example. Do not add a long script or run a second request. The exact-long/max2048 comparison remains separately gated.

## What the offline tests cover

Tests inject a fake device transport and tiny stage verifier. Temporary host flock files test lease coverage; mocked `Popen` checks descriptor/timeout behavior. Host `bash -n` checks shell syntax only, not Android behavior. Cases cover authorization, slot reuse, output reuse, device/build/hash/mode mismatch, transfer/launch/poll deadlines, native exit/error, raw-first optional-metric failure, partial pull retention, stale/reused/wrong PIDs and argv, signal recheck refusal, nonterminating processes, exit/zombie races, cleanup errors and client escalation/reaping.

Actual Android shell/proc behavior, shipped Genie FP16 semantics, physical neural placement and text fidelity remain untested. A conservative refusal on an unrecognized real process identity must be reviewed, not automatically relaxed. Completed campaign, frozen stage and registry remain unchanged.
