# Local work-status dashboard

Start from the repository root:

```sh
python3 scripts/work_status_server.py --port 40188
```

Open <http://127.0.0.1:40188/docs/work-status.html>. The existing accepted listening page remains at <http://127.0.0.1:40187/>; this server does not replace or control it. Open the status board in a new tab. No audio autoplay.

## Update contract

`docs/work-status.json` is curated milestone state, owned by Kate with reports from Pi/stream owners. The server rereads it on each request; no restart/build is needed. Browser polling is every 12 seconds. Polling **never advances a report timestamp** or guesses that work completed.

- Top level: `schema_version: 1`, `updated_at`, `updated_by`, `timestamp_note`, `workstreams`, `resources`, `agents`, `listening`.
- Workstream/resource records: stable `id`, `title`, `status`, `owner`, `now`, `next`, `reported_at`, `reported_by`, `stale_after_seconds`; optional `links: [{label,url}]`.
- Agent task records: `name`, `task`, `reported_at`, `reported_by`, `stale_after_seconds`.
- Timestamps are ISO 8601 **with timezone**. They record when the report was captured, not invented model execution, completion or playback times.
- Change only records affected by a real milestone. Keep old report timestamps on unaffected records. Update the top-level file timestamp separately. Missing/invalid timestamps are unknown; old records remain visible with **STALE** labels.
- Use `blocked` for a real blocker, not a guessed failure from idle agent activity. State what failed, what is known, and what remains unknown. Counts and individual-run observations are not campaign/quality approval.
- Do not put private logs, learned battery/sleep histories, private inventory paths, credentials or session/message bodies in this JSON. Curate safe summaries only. Listening acceptance must bind the exact WAV SHA and Moritz's verdict.
- Write atomically (temporary file beside the JSON, then `os.replace`) to avoid partial reads. If input is missing/malformed the server reports unavailable, not a fabricated current state. Keep updates scoped; no push while the privacy hold applies.

Example update (substitute an actually received report, not a prediction):

```python
import json, os, tempfile
from datetime import datetime, timezone
from pathlib import Path
p = Path('docs/work-status.json')
data = json.loads(p.read_text())
now = datetime.now(timezone.utc).isoformat(timespec='seconds')
row = next(r for r in data['workstreams'] if r['id'] == 'tts-capacity')
row.update(status='blocked', now='Exact safe milestone summary',
           next='Reviewed next action or blocker', reported_at=now,
           reported_by='Pi — relayed milestone captured by Kate')
data.update(updated_at=now, updated_by='Kate')
fd, temporary = tempfile.mkstemp(dir=p.parent, prefix='.work-status-', suffix='.tmp')
with os.fdopen(fd, 'w') as stream:
    json.dump(data, stream, ensure_ascii=False, indent=2)
    stream.write('\n')
os.replace(temporary, p)
```

## Read-only presence source

Pi Messenger's installed README documents its file-based shared registry under `~/.pi/agent/messenger/`. The adapter follows the `AgentRegistration` / `AgentActivity` structures in the installed `pi-messenger/lib.ts`, and reads **only** `registry/*.json` records with this exact project `cwd`.

Exposed fields are name, model, last activity timestamp, a recognized tool **kind** (not its arguments), registry modification time and a signal-0 PID-existence observation. No signal is sent. No registration is deleted or modified, unlike Messenger's own stale-entry cleanup. No extension/tool invocation, CLI agent, inbox, activity feed, session body, process command line, battery dump or device query is used.

`active` means last activity <30 s; `idle` <5 min; `away` older. These thresholds follow Messenger's basic activity thresholds, but this dashboard deliberately does not infer `stuck`. An absent PID is offline. Missing/malformed timestamps, unknown PID state or absent registration are unknown. PID reuse cannot be ruled out by existence alone; a long-running task can look away. **Presence is not task completion, native progress, phone connection or authorization.** Per-record task report age is shown separately.

This is a small adapter to the installed registry schema, not a stable external Messenger service. Source failure is visible. The collector is read-only and runs only when the local page polls.

## Local serving / privacy boundary

The standard-library server binds **127.0.0.1 only**, rejects other Host/Origin values, provides no write endpoints/CORS/directory listing, and uses no-store responses. Its static route allowlist contains only this page/contract and selected generated documentation HTML. It does not serve the repository, `.git`, `.local`, raw evidence or the Messenger registry itself. Deeper links from those documentation views can return 404 by design; use existing local evidence access rather than widening the server to private artifacts.

No framework, external scripts/fonts, remote telemetry, model/ADB operation or agent spawning. Request logging is disabled. The local listening server's lifetime/availability is independent. If refresh fails, the page retains the last snapshot and visibly labels the failure; report ages continue to advance on retry.

## Validation

```sh
python3 -m unittest discover -s scripts/tests -p 'test_work_status_server.py'
```

Verify HTML/API loading, a changed `checked_at` on the next 12-second refresh, stale/unknown and unavailable states, safe document links, narrow viewport overflow, and preservation of the existing listening tab. A green collector indicator means metadata was fetched, not that every reported workstream is current or successful.
