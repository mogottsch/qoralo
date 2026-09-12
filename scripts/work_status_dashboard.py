#!/usr/bin/env python3
"""Refresh a local HTML file from curated reports + read-only Messenger presence.
No HTTP server, browser fetches, inbox/session/log reads, ADB or model execution.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.parse import unquote, urlsplit

REPO = Path(__file__).resolve().parents[1]
REGISTRY = Path.home() / '.pi/agent/messenger/registry'
OUTPUT = Path.home() / '.cache/vibevoice-work-status/index.html'
MAX_JSON = 256 * 1024
TOOLS = {'bash', 'read', 'write', 'edit', 'commit', 'pi_messenger', 'interactive_shell',
         'web_search', 'fetch_content', 'source_check', 'get_search_content'}
STATES = {'active', 'reviewing', 'preparing', 'released', 'blocked', 'offline', 'hold',
          'stale', 'waiting', 'standby', 'paused', 'away', 'idle', 'fresh', 'unknown',
          'unassigned', 'stopped'}


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.astimezone(timezone.utc).isoformat() if parsed.tzinfo else None
    except ValueError:
        return None


def read_json(path):
    # Registrations are small JSON files, not symlinks to arbitrary data.
    if path.is_symlink() or path.stat().st_size > MAX_JSON:
        raise ValueError('Not a bounded regular JSON source')
    with path.open('rb') as stream:
        data = stream.read(MAX_JSON + 1)
    if len(data) > MAX_JSON:
        raise ValueError('Source too large')
    def reject_constant(_):
        raise ValueError('Nonfinite JSON value')
    return json.loads(data, parse_constant=reject_constant)


def valid_curated(data):
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        return False
    for group, fields in (('workstreams', ('id', 'title', 'status', 'owner', 'now', 'next')),
                          ('resources', ('id', 'title', 'status', 'owner', 'now', 'next')),
                          ('agents', ('name', 'task'))):
        rows = data.get(group)
        if not isinstance(rows, list) or len(rows) > 100:
            return False
        seen = set()
        for row in rows:
            if not isinstance(row, dict) or not all(isinstance(row.get(k), str) for k in fields):
                return False
            identity = row[fields[0]]
            if not identity or identity in seen:
                return False
            seen.add(identity)
            links = row.get('links', [])
            if not isinstance(links, list) or not all(isinstance(l, dict) and
                    isinstance(l.get('label'), str) and isinstance(l.get('url'), str) for l in links):
                return False
    return True


def pid_exists(pid):
    if type(pid) is not int or pid < 2:
        return None
    try:
        os.kill(pid, 0)  # Existence/permission check only; sends no signal.
        return True
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return None


def collect_presence(registry=REGISTRY, repo=REPO, now=None, probe=pid_exists):
    now = now or datetime.now(timezone.utc)
    agents, errors = [], 0
    try:
        files = sorted(registry.glob('*.json')) if registry.is_dir() else None
    except OSError:
        files = None
    if files is None:
        return {'available': False, 'errors': 0, 'agents': []}
    for path in files[:256]:
        try:
            r = read_json(path)
            if not isinstance(r, dict) or r.get('cwd') != str(repo.resolve()):
                continue
            name = r.get('name')
            if not isinstance(name, str) or not re.fullmatch(r'[\w -]{1,64}', name):
                raise ValueError('Invalid name')
            activity = r.get('activity') or {}
            if not isinstance(activity, dict):
                activity = {}
            at = timestamp(activity.get('lastActivityAt'))
            age = (now - datetime.fromisoformat(at)).total_seconds() if at else None
            alive = probe(r.get('pid'))
            if alive is False:
                state = 'offline'
            elif alive is None or age is None or age < -30:
                state = 'unknown'
            elif age < 30:
                state = 'active'
            elif age < 300:
                state = 'idle'
            else:
                state = 'away'
            # Never expose free-text command arguments, statusMessage, reservations or session data.
            tool = str(activity.get('lastToolCall') or '').split(':', 1)[0].strip()
            tool = tool if tool in TOOLS else None
            model = r.get('model')
            model = model if isinstance(model, str) and re.fullmatch(r'[\w./:-]{1,100}', model) else None
            agents.append({'name': name, 'model': model, 'presence': state,
                           'pid_exists': alive, 'last_activity_at': at,
                           'last_tool_kind': tool,
                           'registry_modified_at': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()})
        except (OSError, ValueError, TypeError, OverflowError):
            errors += 1
    if len(files) > 256:
        errors += 1
    return {'available': True, 'errors': errors, 'agents': agents}


def snapshot(repo=REPO, registry=REGISTRY):
    result = {'checked_at': stamp(), 'refresh_seconds': 12,
              'curated': None, 'curated_error': None,
              'presence': collect_presence(registry, repo)}
    try:
        data = read_json(repo / 'docs/work-status.json')
        if not valid_curated(data):
            raise ValueError('Invalid curated schema')
        result['curated'] = data
    except (OSError, ValueError, TypeError):
        result['curated_error'] = 'Curated status unavailable or invalid; no current task claims.'
    return result


def esc(value):
    return html.escape(str(value), quote=True)


def badge(value):
    value = value or 'unknown'
    css = value if value in STATES else 'unknown'
    return f'<span class="badge {css}">{esc(value)}</span>'


def age_seconds(value, now):
    at = timestamp(value)
    if not at:
        return None
    seconds = (now - datetime.fromisoformat(at)).total_seconds()
    return max(0, seconds) if seconds >= -30 else None


def ago(seconds):
    if seconds is None:
        return 'unknown time'
    if seconds < 60:
        return f'{int(seconds)}s ago'
    if seconds < 3600:
        return f'{int(seconds // 60)}m ago'
    return f'{seconds / 3600:.1f}h ago'


def report(row, now):
    value = timestamp(row.get('reported_at'))
    age = age_seconds(value, now)
    configured_ttl = row.get('stale_after_seconds', 900)
    persistent = configured_ttl == 'persistent'
    ttl = float('inf') if persistent else configured_ttl
    ttl = ttl if type(ttl) in (int, float) and ttl > 0 else 900
    state = 'unknown' if age is None else 'stale' if age > ttl else ''
    label = ('Recorded · ' if persistent and age is not None else 'Stale · ' if state == 'stale' else '') + ago(age)
    date = datetime.fromisoformat(value).astimezone().strftime('%d %b %H:%M') if value else 'Unknown'
    title = f"Reported {value or 'unknown'} · {row.get('reported_by', 'unknown reporter')}"
    ttl_attribute = 'Infinity' if persistent else ttl
    return (f'<div class="report" data-at="{esc(value or "")}" data-ttl="{ttl_attribute}" title="{esc(title)}">'
            f'<time>{esc(date)}</time><span class="report-age {state}">{esc(label)}</span></div>')


def safe_link(url, repo):
    if not isinstance(url, str):
        return None
    if url.startswith('/docs/'):
        target = (repo / url.lstrip('/')).resolve()
        if target.is_relative_to(repo.resolve() / 'docs') and target.suffix in ('.html', '.md'):
            return target.as_uri()
        return None
    parsed = urlsplit(url)
    if parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost'):
        return url
    return None


def safe_listening_link(url):
    """Allow only the local exact-WAV handoff cache in the dashboard header."""
    if not isinstance(url, str):
        return None
    parsed = urlsplit(url)
    if parsed.scheme != 'file':
        return None
    try:
        target = Path(unquote(parsed.path)).resolve()
        root = (Path.home() / '.cache' / 'vibevoice-listening').resolve()
        if target.is_relative_to(root) and target.name == 'index.html':
            return target.as_uri()
    except (OSError, ValueError):
        pass
    return None


def render(data, repo=REPO):
    now = datetime.fromisoformat(data['checked_at'])
    c = data.get('curated') or {'resources': [], 'workstreams': [], 'agents': []}
    presence = data['presence']
    warnings = []
    if data.get('curated_error'):
        warnings.append(data['curated_error'])
    if not presence['available']:
        warnings.append('Agent presence is unavailable.')
    if presence['errors']:
        warnings.append('Some presence records are unreadable; unknown is not offline.')
    resources = []
    labels = {'phone': 'Phone', 'host': 'On this computer', 'push': 'Sharing changes'}
    for r in c['resources']:
        old = age_seconds(r.get('reported_at'), now)
        configured_ttl = r.get('stale_after_seconds', 900)
        stale = old is None or (configured_ttl != 'persistent' and old > configured_ttl)
        state_label = 'recorded' if configured_ttl == 'persistent' else 'stale report' if stale else 'reported'
        resources.append(f'<div class="resource" title="{esc(r["next"])}"><strong>{esc(labels.get(r["id"], r["title"]))}:</strong> '
                         f'{esc(r["now"])} <small class="{"warn" if stale else ""}">{state_label}</small></div>')
    streams = []
    for r in c['workstreams']:
        title = esc(r['title'])
        for item in r.get('links', []):
            url = safe_link(item.get('url'), repo)
            if url:
                title = f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{title}</a>'
                break
        streams.append(f'<tr><td>{title}</td><td>{esc(r["owner"])}</td><td>{badge(r["status"])}</td>'
                       f'<td><div>{esc(r["now"])}</div><div class="next">{esc(r["next"])}</div></td>'
                       f'<td>{report(r, now)}</td></tr>')
    live = {a['name']: a for a in presence['agents']}
    tasks = {a['name']: a for a in c['agents']}
    agents = []
    # The board is a compact curated work view, not a roster. Presence enriches
    # current assigned agents only; retired/unassigned registry names stay out.
    for name, r in tasks.items():
        a = live.get(name)
        activity = (f'{a["last_tool_kind"] or "activity"} · {ago(age_seconds(a["last_activity_at"], now))}'
                    if a else 'Presence unknown')
        agents.append(f'<article class="agent"><div class="agent-head"><strong>{esc(name)}</strong>'
                      f'<span data-presence>{badge(a["presence"] if a else "unknown")}</span></div>'
                      f'<div class="task" title="{esc(r["task"])}">{esc(r["task"])}</div>'
                      f'<div class="activity">{esc(activity)}</div>{report(r, now)}</article>')
    listening = c.get('listening', {})
    listening_url = safe_listening_link(listening.get('url'))
    listening_label = listening.get('current_label', 'Open current listening page')
    listening_link = (f'<a href="{esc(listening_url)}" target="_blank" rel="noopener noreferrer">'
                      f'{esc(listening_label)} ↗</a>' if listening_url else '')
    fields = {
        'CHECKED': esc(now.astimezone().strftime('%H:%M:%S')),
        'CHECKED_ISO': esc(data['checked_at']),
        'WARNINGS': ''.join(f'<div class="error">{esc(w)}</div>' for w in warnings),
        'RESOURCES': ''.join(resources),
        'STREAMS': ''.join(streams) or '<tr><td colspan="5">No current work reports.</td></tr>',
        'AGENTS': ''.join(agents),
        'CONTRACT': esc((repo / 'docs/work-status.md').resolve().as_uri()),
        'LISTENING_LINK': listening_link,
    }
    page = (repo / 'docs/work-status.html').read_text()
    return re.sub(r'@@([A-Z_]+)@@', lambda match: fields.get(match[1], match[0]), page)


def write_snapshot(output=OUTPUT, repo=REPO, registry=REGISTRY):
    page = render(snapshot(repo, registry), repo)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=output.parent, prefix='.status-', suffix='.html')
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(page)
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return output


def renderer_source_changed(loaded_mtime_ns, source=Path(__file__)):
    """Detect a local renderer edit so the long-lived loop can re-exec safely."""
    try:
        return source.stat().st_mtime_ns != loaded_mtime_ns
    except OSError:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', help='Write one snapshot and exit')
    args = parser.parse_args()
    print(str(OUTPUT), flush=True)
    loaded_mtime_ns = Path(__file__).stat().st_mtime_ns
    while True:
        write_snapshot()
        if args.once:
            return
        time.sleep(12)
        if renderer_source_changed(loaded_mtime_ns):
            os.execv(sys.executable, [sys.executable, *sys.argv])


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
