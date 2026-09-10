"""Pure stdlib, temporary registries/HTTP server only; no real Messenger writes or agents."""
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

MODULE = Path(__file__).resolve().parents[1] / 'work_status_server.py'
spec = importlib.util.spec_from_file_location('work_status_server', MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        (self.repo / 'docs').mkdir(parents=True)
        self.registry = self.root / 'registry'
        self.registry.mkdir()
        self.now = datetime(2026, 9, 10, 18, tzinfo=timezone.utc)

    def registration(self, name='Ben', seconds=10, **extra):
        r = dict(name=name, cwd=str(self.repo.resolve()), pid=123,
                 model='test-model', startedAt=self.now.isoformat(),
                 activity={'lastActivityAt': (self.now-timedelta(seconds=seconds)).isoformat(),
                           'lastToolCall': 'bash: PRIVATE_COMMAND_BODY'},
                 sessionId='PRIVATE_SESSION', statusMessage='PRIVATE_STATUS',
                 session={'filesModified':['PRIVATE_PATH']}, reservations=['PRIVATE_RESERVATION'])
        r.update(extra)
        p = self.registry / (name+'.json')
        p.write_text(json.dumps(r))
        return p

    def collect(self, **kwargs):
        return m.collect_presence(self.registry, self.repo, self.now,
                                  kwargs.get('probe', lambda _: True))

    def test_whitelist_and_project_filter(self):
        self.registration()
        self.registration('Other', cwd='/other/project')
        result = self.collect()
        self.assertEqual(['Ben'], [a['name'] for a in result['agents']])
        encoded = json.dumps(result)
        self.assertNotIn('PRIVATE', encoded)
        self.assertNotIn('sessionId', encoded)
        self.assertNotIn('cwd', encoded)
        self.assertEqual('bash', result['agents'][0]['last_tool_kind'])

    def test_active_idle_away_do_not_guess_task_progress(self):
        for name, seconds in [('Active', 10), ('Idle', 60), ('Away', 600)]:
            self.registration(name, seconds)
        self.assertEqual(['active','away','idle'], [a['presence'] for a in self.collect()['agents']])
        self.assertNotIn('progress', json.dumps(self.collect()))

    def test_dead_pid_is_offline_without_registry_cleanup(self):
        p = self.registration()
        before = p.read_bytes()
        self.assertEqual('offline', self.collect(probe=lambda _:False)['agents'][0]['presence'])
        self.assertEqual(before, p.read_bytes())

    def test_invalid_future_and_missing_timestamps_unknown(self):
        self.registration('Future', -600)
        self.registration('Missing', activity={})
        self.assertTrue(all(a['presence']=='unknown' for a in self.collect()['agents']))

    def test_unknown_pid_is_not_assumed_offline(self):
        self.registration()
        self.assertEqual('unknown', self.collect(probe=lambda _:None)['agents'][0]['presence'])
        self.assertIsNone(m.pid_exists(True))
        self.assertIsNone(m.pid_exists(0))

    def test_bad_partial_oversized_and_symlink_files_not_exposed(self):
        (self.registry/'bad.json').write_text('{')
        (self.registry/'huge.json').write_bytes(b' '*(m.MAX_JSON+1))
        secret = self.root/'secret'; secret.write_text('PRIVATE')
        (self.registry/'link.json').symlink_to(secret)
        r = self.collect()
        self.assertEqual([], r['agents'])
        self.assertEqual(3, r['errors'])
        self.assertTrue(secret.exists())

    def test_missing_registry_explicit(self):
        r = m.collect_presence(self.root/'absent', self.repo)
        self.assertFalse(r['available'])

    def test_refresh_never_rewrites_reported_times_or_source(self):
        data = {'schema_version':1,'workstreams':[{'id':'a','title':'A','status':'blocked','owner':'Ben','now':'Report','next':'Wait','reported_at':'2020-01-01T00:00:00Z'}],
                'resources':[],'agents':[]}
        p = self.repo/'docs/work-status.json';p.write_text(json.dumps(data))
        before = p.read_bytes()
        for _ in range(2):
            result = m.snapshot(self.repo,self.registry)
            self.assertEqual('2020-01-01T00:00:00Z', result['curated']['workstreams'][0]['reported_at'])
        self.assertEqual(before,p.read_bytes())

    def test_invalid_curated_data_is_unknown_not_a_fresh_empty_report(self):
        p=self.repo/'docs/work-status.json';p.write_text('{')
        r=m.snapshot(self.repo,self.registry)
        self.assertIsNone(r['curated']);self.assertTrue(r['curated_error'])

    def test_invalid_record_duplicate_and_nonfinite_json_fail_closed(self):
        p=self.repo/'docs/work-status.json'
        row={'id':'a','title':'A','status':'blocked','owner':'Ben','now':'Report','next':'Wait'}
        for rows in ([None], [row, row], [{'id':'a'}]):
            p.write_text(json.dumps({'schema_version':1,'workstreams':rows,'resources':[],'agents':[]}))
            self.assertIsNone(m.snapshot(self.repo,self.registry)['curated'])
        p.write_text('{"schema_version":1,"workstreams":[],"resources":[],"agents":[],"invalid":NaN}')
        self.assertIsNone(m.snapshot(self.repo,self.registry)['curated'])

    def server(self):
        (self.repo/'docs/work-status.html').write_text('<!doctype html><title>Test</title>')
        (self.repo/'docs/work-status.md').write_text('Contract')
        s=m.ThreadingHTTPServer(('127.0.0.1',0),m.handler_factory(self.repo,self.registry))
        thread=threading.Thread(target=s.serve_forever,daemon=True);thread.start()
        self.addCleanup(lambda: (s.shutdown(),s.server_close(),thread.join(timeout=2)))
        return 'http://127.0.0.1:'+str(s.server_address[1])

    def test_http_allowlist_and_readonly_headers(self):
        base=self.server()
        with urlopen(base+'/docs/work-status.html') as r:
            self.assertEqual(200,r.status);self.assertEqual('no-store',r.headers['Cache-Control'])
            self.assertNotIn('Access-Control-Allow-Origin',r.headers)
        for path in ('/.git/config','/docs/../private','/docs/%2e%2e/private','/docs/work-status.json','/raw/battery.txt','/registry/Ben.json'):
            with self.assertRaises(HTTPError) as e:urlopen(base+path)
            self.assertEqual(404,e.exception.code)
            e.exception.close()
        with self.assertRaises(HTTPError) as e:urlopen(Request(base+'/api/status',method='POST',data=b'change'))
        self.assertEqual(501,e.exception.code)
        e.exception.close()

    def test_http_rejects_foreign_host_and_origin(self):
        base=self.server()
        for header in ({'Host':'attacker.invalid'},{'Origin':'http://attacker.invalid'}):
            with self.assertRaises(HTTPError) as e:urlopen(Request(base+'/api/status',headers=header))
            self.assertEqual(403,e.exception.code)
            e.exception.close()

    def test_static_symlink_not_served(self):
        base=self.server();p=self.repo/'docs/work-status.html';p.unlink()
        secret=self.root/'secret';secret.write_text('PRIVATE');p.symlink_to(secret)
        with self.assertRaises(HTTPError) as e:urlopen(base+'/docs/work-status.html')
        self.assertEqual(404,e.exception.code)
        e.exception.close()

    def test_owned_page_uses_text_nodes_and_no_external_script(self):
        text=(MODULE.parents[1]/'docs/work-status.html').read_text()
        self.assertIn('textContent',text)
        self.assertNotIn('innerHTML',text)
        self.assertNotIn('<script src=',text)
        self.assertIn('setInterval(refresh,12000)',text)
        self.assertIn("cache:'no-store'",text)


if __name__=='__main__':unittest.main()
