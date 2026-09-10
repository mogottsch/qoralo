#!/usr/bin/env python3
"""Local work dashboard. Read-only curated JSON + whitelisted Messenger registry fields.

Never reads inboxes, feeds, sessions, process command lines, device state or raw evidence.
See docs/work-status.md for the update contract and source boundaries.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit, unquote

REPO = Path(__file__).resolve().parents[1]
REGISTRY = Path.home() / '.pi/agent/messenger/registry'
MAX_JSON = 256 * 1024
DOCS = (
    'docs/work-status.html', 'docs/work-status.md',
    'docs/android-llm-benchmarks/index.html', 'docs/android-benchmarks/index.html',
    'docs/experiments/0023-supertonic-qnn-precompiled-context-startup/index.html',
    'docs/experiments/0031-gemma-4-e2b-it-android-qnn-htp/index.html',
    'docs/experiments/0032-qwen-3.5-2b-android-qnn-htp/index.html',
    'docs/experiments/0034-lfm2.5-2.6b-android-qnn-htp/index.html',
)
TOOLS = {'bash', 'read', 'write', 'edit', 'commit', 'pi_messenger', 'interactive_shell',
         'web_search', 'fetch_content', 'source_check', 'get_search_content'}


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


def handler_factory(repo=REPO, registry=REGISTRY):
    allowed = {'/' + p: repo / p for p in DOCS}
    allowed['/'] = repo / 'docs/work-status.html'

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # No request/body logging.

        def do_GET(self):
            self.respond(False)

        def do_HEAD(self):
            self.respond(True)

        def respond(self, head):
            port = self.server.server_address[1]
            hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
            if self.headers.get('Host') not in hosts:
                self.send_error(403, 'Loopback Host required')
                return
            origin = self.headers.get('Origin')
            if origin and origin not in {f'http://{h}' for h in hosts}:
                self.send_error(403, 'Same origin required')
                return
            path = unquote(urlsplit(self.path).path)
            if path == '/api/status':
                payload = json.dumps(snapshot(repo, registry), ensure_ascii=False, allow_nan=False).encode()
                mime = 'application/json; charset=utf-8'
            elif path in allowed:
                file = allowed[path]
                try:
                    if file.is_symlink() or not file.resolve().is_relative_to(repo.resolve() / 'docs'):
                        raise OSError('Disallowed path')
                    payload = file.read_bytes()
                except OSError:
                    self.send_error(404)
                    return
                mime = 'text/html; charset=utf-8' if file.suffix == '.html' else 'text/plain; charset=utf-8'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Frame-Options', 'DENY')
            self.end_headers()
            if not head:
                self.wfile.write(payload)
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=40188)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_factory())
    print(f'http://127.0.0.1:{server.server_address[1]}/docs/work-status.html', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
