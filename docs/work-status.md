# Local one-page work status

The dashboard is a **local HTML file**, not a web server:

```text
~/.cache/vibevoice-work-status/index.html
```

Run the small local refresher, then open the file normally:

```sh
python3 scripts/work_status_dashboard.py
# In another terminal:
xdg-open "$HOME/.cache/vibevoice-work-status/index.html"
```

`--once` writes one snapshot without keeping a refresher running. The source template is `docs/work-status.html`; open the generated cache file, not the template. The refresher reads the curated JSON and whitelisted agent-presence metadata, atomically updates the cache file every 12 seconds, and never changes the reports or registry. HTML self-reloads every 12 seconds. A tiny local-clock script updates age labels and warns if the refresher has stopped for >35 seconds; it performs no fetch/network/file access and marks presence unknown when stale.

The existing listening page at <http://127.0.0.1:40187/> is a separate, unchanged service. The dashboard does not start, stop or navigate that service/tab. Documentation links open local files directly.

## Plain labels

- **Phone:** last reported assignment—not a connection or lock check.
- **On this computer:** reported computer work, such as source review; not device execution.
- **Sharing changes:** commit and push state for the private origin.

## Milestone update contract

Kate maintains `docs/work-status.json` from Pi/owner reports. Polling never invents progress or renews `reported_at`.

- Top level: `schema_version: 1`, `updated_at`, `updated_by`, `timestamp_note`, `workstreams`, `resources`, `agents`, `listening`.
- Workstream/resource: stable `id`, `title`, `status`, `owner`, `now`, `next`, `reported_at`, `reported_by`, `stale_after_seconds`; optional `links: [{label,url}]`.
- Agent: `name`, `task`, `reported_at`, `reported_by`, `stale_after_seconds`.
- ISO timestamps include timezone and mean report capture, not invented execution/playback time. Change a record's report timestamp only on an actual report. Editorial shortening does not make the report fresh.
- Keep `now` and `next` to one short line each where practical. Use plain words. Separate constructor/compile success from inference, and sample acceptance from capacity/quality claims.
- Old or invalid timestamps are visibly stale/unknown. Presence never changes a workstream's status.
- Write JSON atomically: temporary file in `docs/`, then `os.replace(temporary, 'docs/work-status.json')`. No refresher restart is needed.
- Do not add credential values or message/session bodies. Exact-WAV listening acceptance stays hash-bound. Commit and push board updates to the private origin as normal.

## Read-only presence

Pi Messenger's README documents the file-based registry under `~/.pi/agent/messenger/`. The collector follows installed `AgentRegistration`/`AgentActivity` fields and reads only `registry/*.json` records matching this exact project directory. It exposes name, model metadata, activity time, recognized tool **kind** (not arguments), registry modification time and a signal-0 PID-existence observation. No signal is delivered, and no stale registration is deleted.

No inboxes, feed, session bodies, process command lines, private evidence or device queries are read. Active means activity <30 seconds, idle <5 minutes, away older; unknown/absent process state is explicit. PID existence is not identity attestation, and away can include a long-running task. Reported assignments and their dates are separate.

## Checks

```sh
python3 -m unittest discover -s scripts/tests -p 'test_work_status_dashboard.py'
python3 scripts/work_status_dashboard.py --once
```

Verify report ages and file refresh, no registry/curated-data mutations, escaped text, local links, and a one-screen layout on a normal laptop window. No framework, HTTP listener, model/ADB execution, agent spawning, external fonts/scripts or push is required.
