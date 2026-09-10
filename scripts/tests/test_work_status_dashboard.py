"""Read-only collector + local file renderer tests. No HTTP, browser or agents."""
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'work_status_dashboard.py'
spec = importlib.util.spec_from_file_location('work_status_dashboard', MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        (self.repo / 'docs').mkdir(parents=True)
        (self.repo/'docs/work-status.html').write_text((MODULE.parents[1]/'docs/work-status.html').read_text())
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

    def sample(self):
        return {'schema_version':1,'workstreams':[{'id':'a','title':'A','status':'blocked',
                'owner':'Ben','now':'<img src=x onerror=alert(1)> @@AGENTS@@','next':'Wait',
                'reported_at':'2020-01-01T00:00:00Z','stale_after_seconds':60,
                'links':[{'label':'bad','url':'javascript:alert(1)'}]}],
                'resources':[],'agents':[]}

    def test_render_escapes_text_and_shows_stale_unknown(self):
        data={'checked_at':self.now.isoformat(),'curated':self.sample(),'curated_error':None,
              'presence':{'available':False,'errors':0,'agents':[]}}
        text=m.render(data,self.repo)
        self.assertIn('&lt;img',text)
        self.assertNotIn('<img',text)
        self.assertIn('@@AGENTS@@',text)  # Inserted text is never interpreted as a template.
        self.assertNotIn('javascript:',text)
        self.assertIn('Stale',text)
        self.assertIn('Agent presence is unavailable',text)
        self.assertIn('http-equiv="refresh" content="12"',text)
        self.assertNotIn('fetch(',text)
        self.assertIn('refresher-warning',text)

    def test_links_open_local_files_not_a_dashboard_server(self):
        self.assertTrue(m.safe_link('/docs/work-status.md',self.repo).startswith('file:///'))
        self.assertIsNone(m.safe_link('/docs/../../private.html',self.repo))
        self.assertIsNone(m.safe_link('/docs/raw/battery.txt',self.repo))
        self.assertIsNone(m.safe_link('https://remote.invalid/',self.repo))
        self.assertEqual('http://127.0.0.1:40187/',m.safe_link('http://127.0.0.1:40187/',self.repo))

    def test_file_refresh_only_updates_generated_cache(self):
        self.registration()
        p=self.repo/'docs/work-status.json';p.write_text(json.dumps(self.sample()))
        registry_before={p.name:p.read_bytes() for p in self.registry.iterdir()}
        curated_before=p.read_bytes()
        output=self.root/'cache/index.html'
        m.write_snapshot(output,self.repo,self.registry)
        self.assertTrue(output.exists())
        self.assertNotIn('@@STREAMS@@',output.read_text())
        m.write_snapshot(output,self.repo,self.registry)
        self.assertEqual(curated_before,p.read_bytes())
        self.assertEqual(registry_before,{p.name:p.read_bytes() for p in self.registry.iterdir()})
        self.assertEqual(['index.html'],[p.name for p in output.parent.iterdir()])

    def test_missing_curated_file_produces_explicit_unknown_view(self):
        data=m.snapshot(self.repo,self.registry)
        self.assertIn('unavailable',m.render(data,self.repo))
        self.assertIn('No current work reports',m.render(data,self.repo))


if __name__=='__main__':unittest.main()
