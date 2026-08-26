# Android CPU campaign startup diagnostic — 2026-08-26

This is retained failure evidence, not a canonical campaign and not a publishable Android benchmark row.

The authorized SM-S918B was reached from WSL through the Windows-hosted ADB daemon at `tcp:172.27.80.1:5037`. Under a dedicated phone-lock hold, the required preflight inspected only `/data/local/tmp/vibevoice-0027-qwen-3.5-2b-android` and the PID claimed by its `server.pid`. PID 27748 was no longer running, so no process was killed; only the scoped stale stage was removed and verified absent.

A fresh artifact-revision-2 campaign attempt then held a new phone lock, matched device and staged hashes, and launched the server. The server loaded the model and listened on phone port 8027 after about 3.4 seconds, but the WSL client polled `127.0.0.1:8027`. Because ADB forwarding was owned by the Windows-hosted daemon, that listener was reachable at the Windows host address rather than WSL localhost. No logical inference request began. The health deadline expired after 600 seconds, the runner retained logs and memory samples, removed only its forward and scoped remote stage, verified the remote path absent, and released the lock.

The runner was corrected to derive its client base from `ADB_SERVER_SOCKET` (or accept an explicit `CLIENT_BASE`). The complete canonical campaign must start again from a fresh server; none of this attempt may be resumed or counted.
