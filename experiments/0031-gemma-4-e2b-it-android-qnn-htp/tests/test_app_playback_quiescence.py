from pathlib import Path
import subprocess
import sys
import unittest

TRACK=Path(__file__).resolve().parents[1]/'improvements/0001-long-collapse-speed-quality'
sys.path.insert(0,str(TRACK/'tools'))
import app_playback_quiescence as q


def filtered(body,code=0,marker=True):
    text=body+(f'\nGEMMA_AUDIO_SOURCE_EXIT {code}\n' if marker else '')
    return subprocess.run(['awk','-v','target_uid=4242',q.AUDIO_FILTER],input=text.encode(),capture_output=True,timeout=10)


class StreamingPlaybackTests(unittest.TestCase):
    def test_idle_and_other_UID_active_do_not_become_target_playback(self):
        p=filtered('PlaybackActivityMonitor dump time:\n  players:\nAudioPlaybackConfiguration piid:1 u/pid:4242/50 state:paused attr:owned\nAudioPlaybackConfiguration piid:2 u/pid:9999/60 state:started attr:UNRELATED_SECRET\n\n  event history:\nUNRELATED_SECRET\n')
        self.assertEqual(p.returncode,0,p.stderr)
        x=q.validate(p.stdout);self.assertEqual(x['owned_inactive_players'],1)
        self.assertNotIn(b'UNRELATED_SECRET',p.stdout+p.stderr);self.assertNotIn(b'9999',p.stdout+p.stderr)

    def test_empty_current_players_is_explicit_idle(self):
        p=filtered('PlaybackActivityMonitor dump time:\n  players:\n\n  ducked players:\n')
        self.assertEqual(p.returncode,0);self.assertTrue(q.validate(p.stdout)['playback_quiescence_observed'])

    def test_active_target_is_not_stopped_or_relabelled(self):
        p=filtered('PlaybackActivityMonitor dump time:\n  players:\npiid:1 u/pid:4242/50 state:started attr:owned\n')
        self.assertEqual(p.returncode,55);self.assertIn(b'verdict=active',p.stdout)
        with self.assertRaises(ValueError):q.validate(p.stdout)

    def test_malformed_current_player_is_unknown_not_idle(self):
        for row in ['piid:1 uid??? state:started','piid:1 u/pid:4242/50 state:unexpected','piid:1 u/pid:4242/50']:
            with self.subTest(row=row):
                p=filtered('PlaybackActivityMonitor dump time:\n  players:\n'+row+'\n')
                self.assertEqual(p.returncode,54);self.assertIn(b'parse=malformed_player',p.stdout)

    def test_explicit_upstream_failure_even_with_plausible_idle_partial_dump(self):
        p=filtered('PlaybackActivityMonitor dump time:\n  players:\n',code=42)
        self.assertEqual(p.returncode,54);self.assertIn(b'upstream=42 parse=upstream_error',p.stdout)
        with self.assertRaises(ValueError):q.validate(p.stdout)

    def test_missing_duplicate_source_status_and_missing_schema_are_unknown(self):
        for body,marker in [('PlaybackActivityMonitor dump time:\n  players:\n',False),('PlaybackActivityMonitor dump time:\n  players:\n\nGEMMA_AUDIO_SOURCE_EXIT 0\n',True),('unexpected output\n',True)]:
            p=filtered(body,marker=marker);self.assertEqual(p.returncode,54);self.assertIn(b'verdict=unknown',p.stdout)

    def test_large_input_is_streamed_not_put_in_argv(self):
        unrelated='piid:99 u/pid:9999/10 state:started attr:'+('UNRELATED_'*20)+'\n'
        body='PlaybackActivityMonitor dump time:\n  players:\n'+unrelated*14000+'piid:1 u/pid:4242/50 state:stopped\n'
        self.assertGreater(len(body),2*1024*1024)
        p=filtered(body);self.assertEqual(p.returncode,0,p.stderr)
        self.assertLess(len(p.stdout),160);self.assertNotIn(b'UNRELATED',p.stdout+p.stderr)
        self.assertEqual(q.validate(p.stdout)['owned_inactive_players'],1)
        script=q.probe_script();self.assertNotIn('audio=$(',script);self.assertNotIn('"$audio"',script)
        self.assertIn('{ dumpsys audio 2>/dev/null; status=$?',script)

    def test_UID_lookup_source_status_and_exact_package(self):
        cmd=['awk',q.UID_FILTER]
        good=b'package:dev.vibevoice.podcast.internal uid:4242\npackage:dev.vibevoice.podcast.internal.test uid:9999\nGEMMA_UID_SOURCE_EXIT 0\n'
        self.assertEqual(subprocess.run(cmd,input=good,capture_output=True,timeout=5).stdout.strip(),b'4242')
        for bad in [good.replace(b'EXIT 0',b'EXIT 7'),good.replace(b'uid:4242',b'uid:bad'),good+good]:
            self.assertEqual(subprocess.run(cmd,input=bad,capture_output=True,timeout=5).stdout.strip(),b'UNKNOWN')

    def test_main_absence_uses_no_audio_dump(self):
        x=q.validate(b'PLAYBACK_GUARD_V2 main=absent verdict=quiescent\n')
        self.assertFalse(x['audio_dump_requested']);self.assertTrue(x['main_absent'])


if __name__=='__main__':unittest.main()
