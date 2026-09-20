import contextlib
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import duration_phone_guard as g
import run_duration_load_gate as controller
from run_wiring_gate import Device


def database(root, wal=False):
    path = root/'podcast.db'
    db = sqlite3.connect(path)
    if wal:
        db.execute('PRAGMA journal_mode=WAL'); db.execute('PRAGMA wal_autocheckpoint=0')
    schema = json.loads(g.SCHEMA.read_text())['database']
    for entity in schema['entities']:
        db.execute(entity['createSql'].replace('${TABLE_NAME}', entity['tableName']))
        for index in entity['indices']:
            db.execute(index['createSql'].replace('${TABLE_NAME}', entity['tableName']))
    for sql in schema['setupQueries']: db.execute(sql)
    db.execute('PRAGMA user_version=1'); db.commit()
    return db


def row(db, table, **overrides):
    entity = next(e for e in json.loads(g.SCHEMA.read_text())['database']['entities'] if e['tableName'] == table)
    values = {f['fieldPath']: (None if not f['notNull'] else 0 if f['affinity'] in ('INTEGER','REAL') else 'x') for f in entity['fields']}
    values.update(overrides)
    db.execute(f"INSERT INTO {table} ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))
    db.commit()


def snapshot(root):
    return {'databases/'+p.name: p.read_bytes() for p in root.glob('podcast.db*')}


def candidate(root):
    source = json.loads((g.PROJECT/'app/src/debug/assets/duration-load/contract.json').read_text())
    result = {'kind':'duration-load-only', 'sourceDirty':False, 'contract':source, 'contractSha256':controller.CONTRACT_SHA}
    for name in ('app','test'):
        path=root/(name+'.apk'); path.write_bytes(name.encode())
        result[name]={'path':str(path),'bytes':path.stat().st_size,'sha256':g.digest(path)}
    path=root/'candidate.json'; path.write_text(json.dumps(result)); return path


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()

    def test_absent_and_known_empty_database_are_eligible(self):
        self.assertEqual(0,g.validate_snapshot({})['episodeCount'])
        with contextlib.closing(database(self.root)):
            self.assertEqual(0,g.validate_snapshot(snapshot(self.root))['generationHistoryRows'])

    def test_input_draft_is_allowed_without_generation_history(self):
        with contextlib.closing(database(self.root)) as db:
            row(db,'episodes',id='ep',phase='SOURCES')
            self.assertEqual(1,g.validate_snapshot(snapshot(self.root))['episodeCount'])

    def test_active_job_existing_only_in_wal_is_not_missed(self):
        with contextlib.closing(database(self.root,wal=True)) as db:
            db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            row(db,'episodes',id='ep',phase='GENERATING_SCRIPT')
            row(db,'generation_jobs',id='job',episodeId='ep',kind='SCRIPT',status='QUEUED')
            before=snapshot(self.root)
            self.assertEqual(0,g.validate_snapshot({'databases/podcast.db':before['databases/podcast.db']})['episodeCount'])
            with self.assertRaisesRegex(g.GuardError,'pending/reconcilable'):g.validate_snapshot(before)
            self.assertEqual(before,snapshot(self.root))

    def test_valid_wal_input_draft_is_read_without_mutating_originals(self):
        with contextlib.closing(database(self.root,wal=True)) as db:
            row(db,'episodes',id='ep',phase='SOURCES'); before=snapshot(self.root)
            self.assertEqual(1,g.validate_snapshot(before)['episodeCount']); self.assertEqual(before,snapshot(self.root))

    def test_unknown_schema_identity_and_version_fail_closed(self):
        with contextlib.closing(database(self.root)) as db:
            for sql in ['PRAGMA user_version=2', "UPDATE room_master_table SET identity_hash='wrong'", 'CREATE TABLE surprise(x)']:
                with self.subTest(sql=sql):
                    db.execute(sql);db.commit()
                    with self.assertRaises(g.GuardError):g.validate_snapshot(snapshot(self.root))
                    if sql.startswith('PRAGMA'):db.execute('PRAGMA user_version=1')
                    elif sql.startswith('UPDATE'):db.execute('UPDATE room_master_table SET identity_hash=?',(json.loads(g.SCHEMA.read_text())['database']['identityHash'],))
                    db.commit()

    def test_known_phases_and_metadata_alone_do_not_dispatch_but_unknown_phase_rejects(self):
        with contextlib.closing(database(self.root)) as db:
            for phase in ['SOURCES','INSTRUCTIONS','GENERATING_SCRIPT','GENERATING_AUDIO','LOCKED','FAILED','SCRIPT_DRAFT','FROZEN_READY']:
                with self.subTest(phase=phase):
                    db.execute('DELETE FROM episodes')
                    row(db,'episodes',id='ep',phase=phase,activeRevisionId='private-revision',failureMessage='private-content',finalAudioPath='private-path')
                    before=snapshot(self.root); summary=g.validate_snapshot(before)
                    self.assertEqual(1,summary['episodeCount']); self.assertEqual(before,snapshot(self.root))
                    self.assertNotIn('private-',json.dumps(summary))
            db.execute('DELETE FROM episodes');row(db,'episodes',id='ep',phase='unknown')
            with self.assertRaisesRegex(g.GuardError,'unsupported episode state'):g.validate_snapshot(snapshot(self.root))

    def test_known_terminal_history_in_wal_is_eligible_and_unchanged(self):
        with contextlib.closing(database(self.root,wal=True)) as db:
            row(db,'episodes',id='ep',phase='FAILED')
            db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            for status in ['COMPLETE','FAILED']:
                row(db,'generation_jobs',id=status,episodeId='ep',kind='SCRIPT',status=status)
            before=snapshot(self.root);summary=g.validate_snapshot(before)
            self.assertEqual({'COMPLETE':1,'FAILED':1},summary['jobStatusCounts'])
            self.assertEqual(2,summary['generationHistoryRows']);self.assertEqual(0,summary['queuedOrRunningJobs'])
            self.assertEqual(before,snapshot(self.root))
            self.assertEqual(0,g.validate_snapshot({'databases/podcast.db':before['databases/podcast.db']})['generationHistoryRows'])

    def test_unknown_job_status_cannot_hide_behind_known_terminal_history(self):
        with contextlib.closing(database(self.root)) as db:
            row(db,'episodes',id='ep',phase='FAILED')
            row(db,'generation_jobs',id='known',episodeId='ep',kind='SCRIPT',status='FAILED')
            for status in ['unknown','CANCELLED','complete','WAITING']:
                with self.subTest(status=status):
                    row(db,'generation_jobs',id='other',episodeId='ep',kind='SCRIPT',status=status)
                    with self.assertRaisesRegex(g.GuardError,'unsupported job status'):g.validate_snapshot(snapshot(self.root))
                    db.execute("DELETE FROM generation_jobs WHERE id='other'");db.commit()

    def test_other_history_tables_do_not_trigger_startup_work(self):
        with contextlib.closing(database(self.root)) as db:
            row(db,'episodes',id='ep',phase='FROZEN_READY',lockedRevisionId='rev',finalAudioPath='private-audio')
            row(db,'generation_jobs',id='j',episodeId='ep',kind='AUDIO',status='COMPLETE')
            row(db,'script_revisions',id='rev',episodeId='ep')
            row(db,'chapters',rowId='chapter',revisionId='rev')
            row(db,'agent_messages',id='message',episodeId='ep')
            row(db,'chapter_audio',id='audio',episodeId='ep',lockedRevisionId='rev')
            row(db,'playback_state',episodeId='ep')
            before=snapshot(self.root);summary=g.validate_snapshot(before)
            self.assertEqual({table:1 for table in g.GENERATION_TABLES},summary['historyRowCounts'])
            self.assertEqual(6,summary['generationHistoryRows']);self.assertEqual(before,snapshot(self.root))
            self.assertNotIn('private-',json.dumps(summary))

    def test_active_job_cannot_hide_behind_terminal_history(self):
        with contextlib.closing(database(self.root)) as db:
            row(db,'episodes',id='ep',phase='FAILED')
            row(db,'generation_jobs',id='terminal',episodeId='ep',kind='SCRIPT',status='FAILED')
            for status in ['QUEUED','RUNNING']:
                with self.subTest(status=status):
                    row(db,'generation_jobs',id='active',episodeId='ep',kind='SCRIPT',status=status)
                    with self.assertRaisesRegex(g.GuardError,'pending/reconcilable'):g.validate_snapshot(snapshot(self.root))
                    db.execute("DELETE FROM generation_jobs WHERE id='active'");db.commit()

    def test_running_job_and_foreign_key_corruption_rejected(self):
        with contextlib.closing(database(self.root)) as db:
            row(db,'generation_jobs',id='j',episodeId='missing',kind='SCRIPT',status='RUNNING')
            with self.assertRaisesRegex(g.GuardError,'foreign-key'):g.validate_snapshot(snapshot(self.root))
            row(db,'episodes',id='missing',phase='SOURCES')
            with self.assertRaisesRegex(g.GuardError,'pending/reconcilable'):g.validate_snapshot(snapshot(self.root))

    def test_torn_checksum_salt_and_uncommitted_wal_rejected(self):
        with contextlib.closing(database(self.root,wal=True)) as db:
            row(db,'episodes',id='ep',phase='SOURCES'); original=snapshot(self.root); wal=original['databases/podcast.db-wal']
            variants=[wal[:-1],wal[:100]+bytes([wal[100]^1])+wal[101:],wal[:40]+bytes([wal[40]^1])+wal[41:]]
            page=struct.unpack('>I',wal[8:12])[0]; end=len(wal)-(24+page); order='<' if wal[:4]==bytes.fromhex('377f0682') else '>'
            uncommitted=bytearray(wal);uncommitted[end+4:end+8]=b'\0'*4
            prior=struct.unpack('>II',wal[end-(24+page)+16:end-(24+page)+24]) if end>32 else struct.unpack('>II',wal[24:32])
            sums=g.checksum(bytes(uncommitted[end:end+8])+bytes(uncommitted[end+24:]),order,prior)
            uncommitted[end+16:end+24]=struct.pack('>II',*sums);variants.append(bytes(uncommitted))
            for invalid in variants:
                with self.subTest(length=len(invalid)),self.assertRaises(g.GuardError):
                    g.validate_snapshot({**original,'databases/podcast.db-wal':invalid})

    def test_archive_rejects_unknown_paths_and_symlinks(self):
        for name,symlink in [('../escape',False),('databases/podcast.db-journal',False),('databases/podcast.db',True)]:
            data=io.BytesIO()
            with tarfile.open(fileobj=data,mode='w') as tar:
                item=tarfile.TarInfo(name);item.size=0
                if symlink:item.type=tarfile.SYMTYPE;item.linkname='/tmp/other'
                tar.addfile(item)
            with self.assertRaises(g.GuardError):g.archive_files(data.getvalue())
        self.assertEqual({},g.archive_files(b'DATABASES_ABSENT\n'))


class GuardOrderingTests(unittest.TestCase):
    def run_controller(self, fail=None):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name)
        pin=candidate(root);output=root/'run';events=[];held=[False]
        project=root/'project';contract=project/'app/src/debug/assets/duration-load/contract.json'
        contract.parent.mkdir(parents=True);contract.write_bytes((g.PROJECT/'app/src/debug/assets/duration-load/contract.json').read_bytes())
        (root/'artifacts/locks').mkdir(parents=True)
        class FakeDevice:
            def __init__(self,adb,serial,out):self.output=out;self.counter=0;self.enforce_quota=True;self.prefix=[adb,'-s',serial]
            def run(self,args,timeout=30,check=True,binary=False):
                assert held[0];events.append(('device',tuple(args)));self.counter+=1
                base=self.output/f'{self.counter:03d}-command'
                pid=args[0]=='shell' and args[1].startswith('pidof')
                text='' if pid else 'OK (1 test)' if args[0]=='shell' and args[1].startswith('am instrument') else '1'
                if args[0]=='shell' and 'sha256sum' in args[1]:text=json.loads(pin.read_text())['contract']['manifestSha256']+' manifest.json'
                base.with_suffix('.exit').write_text('1' if pid else '0');base.with_suffix('.stderr').write_text('');base.with_suffix('.stdout').write_text(text)
                return base.with_suffix('.stdout') if binary else text
            def shell(self,command,**kwargs):return self.run(['shell',command],**kwargs)
        class FakeGuard:
            def __init__(self,*args):pass
            def identity(self):assert held[0];events.append(('identity',))
            def checkpoint(self,name):
                assert held[0];events.append(('guard',name))
                if name==fail:raise g.GuardError('test mismatch')
            def idle(self):assert held[0];events.append(('idle',))
            def readback_settings(self):assert held[0];events.append(('readback',));return []
        def flock(fd,op):
            if op==fcntl.LOCK_UN:events.append(('unlock',));held[0]=False
            else:assert not held[0];held[0]=True;events.append(('lock',))
        argv=['test','--candidate',str(pin),'--output',str(output),'--run-id','duration-host-mock','--execute','--approved-candidate-sha256',g.digest(pin),'--approved-host-guard-sha256',g.host_identity()['sha256']]
        with patch.object(sys,'argv',argv),patch.object(controller,'PROJECT',project),patch.dict(os.environ,{'PODCAST_PHONE_PRIORITY':'approved'}),patch.object(controller.fcntl,'flock',side_effect=flock),patch.object(controller,'Device',FakeDevice),patch.object(controller,'PhoneGuard',FakeGuard),patch.object(controller.subprocess,'Popen',return_value=object()),patch.object(controller,'stop_child',side_effect=lambda _:events.append(('logcat-reaped',))),patch.object(controller.signal,'signal'):
            original_umask=os.umask(0o077)
            try:
                if fail:
                    with self.assertRaises(g.GuardError):controller.main()
                else:controller.main()
            finally:os.umask(original_umask)
        return events,output

    def test_one_lock_brackets_guards_installs_instrumentation_and_readback(self):
        events,output=self.run_controller()
        self.assertEqual(1,events.count(('lock',)));self.assertEqual(('unlock',),events[-1])
        app_install=next(i for i,e in enumerate(events) if e[0]=='device' and e[1][0]=='install')
        instrument=next(i for i,e in enumerate(events) if e[0]=='device' and e[1][0]=='shell' and e[1][1].startswith('am instrument'))
        self.assertLess(events.index(('guard','before-app-install')),app_install)
        self.assertLess(events.index(('guard','before-instrument')),instrument)
        self.assertLess(events.index(('readback',)),events.index(('unlock',)))
        self.assertFalse(json.loads((output/'host-guard-identity.json').read_text())['lockInheritable'])

    def test_mismatch_stops_downstream_actions_without_retry(self):
        for phase,installs in [('before-app-install',0),('before-test-install',1),('before-instrument',2)]:
            with self.subTest(phase=phase):
                events,_=self.run_controller(phase)
                self.assertEqual(installs,sum(e[0]=='device' and e[1][0]=='install' for e in events))
                self.assertFalse(any(e[0]=='device' and e[1][0]=='shell' and e[1][1].startswith('am instrument') for e in events))
                self.assertEqual(('unlock',),events[-1])

    def test_snapshot_change_and_settings_mismatch_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);pin=candidate(root)
            fake=type('Fake',(),{'shell':lambda self,cmd:'changed'})()
            guard=g.PhoneGuard(fake,root,pin,g.digest(pin),g.host_identity()['sha256'])
            with patch.object(guard,'identity'),patch.object(guard,'idle'),patch.object(guard,'snapshot',side_effect=[{}, {'databases/podcast.db':b'changed'}]):
                with self.assertRaisesRegex(g.GuardError,'snapshot changed'):guard.checkpoint('mock')
            guard.settings={cmd:'original' for cmd in g.SETTINGS}
            self.assertTrue(guard.readback_settings())

    def test_exact_identity_and_pid_errors_reject_without_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);pin=candidate(root)
            class Fake:
                prefix=['adb','-s','R5CW81PR8SY'];counter=0;wrong=None;pid_error=False
                def shell(self,cmd,**kwargs):
                    if cmd.startswith('getprop '):
                        key=cmd.split()[1]
                        if key==self.wrong:return 'mismatch'
                        return g.IDENTITY.get(key) or {'ro.build.fingerprint':g.PRIOR_FINGERPRINT}[key]
                    self.counter+=1;record=root/f'{self.counter:03d}-command'
                    record.with_suffix('.exit').write_text('1');record.with_suffix('.stderr').write_text('offline' if self.pid_error else '')
                    return ''
            fake=Fake();guard=g.PhoneGuard(fake,root,pin,g.digest(pin),g.host_identity()['sha256'])
            for key in g.IDENTITY:
                fake.wrong=key
                with self.subTest(key=key),self.assertRaisesRegex(g.GuardError,'identity mismatch'):guard.identity()
            fake.wrong=None;guard.identity()
            # A newer platform build on the same phone is recorded, not blocked (decision 2026-09-20).
            for key in g.RECORDED_PROPERTIES:
                fake.wrong=key
                with self.subTest(recorded=key):guard.identity()
                observed=json.loads((root/'guard-device-identity.json').read_text())
                self.assertEqual('mismatch',observed[key])
                self.assertEqual(sorted(g.IDENTITY),observed['blockingProperties'])
                self.assertEqual(sorted(g.RECORDED_PROPERTIES),observed['recordedOnlyProperties'])
            fake.wrong=None;guard.identity();guard.idle();fake.pid_error=True
            with self.assertRaisesRegex(g.GuardError,'absence unproven'):guard.idle()

    def test_failed_private_pull_retains_partial_only_in_private_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);pin=candidate(root)
            class Fake:
                counter=0
                def run(self,*args,**kwargs):
                    assert args[0] == ['exec-out', g.SNAPSHOT]  # already-quoted remote command; no extra sh -c
                    self.counter+=1;(root/f'{self.counter:03d}-command.stdout').write_bytes(b'private partial')
                    raise RuntimeError('transport lost')
            guard=g.PhoneGuard(Fake(),root,pin,g.digest(pin),g.host_identity()['sha256'])
            with self.assertRaisesRegex(RuntimeError,'transport lost'):guard.snapshot('mock',1)
            self.assertFalse((root/'001-command.stdout').exists())
            self.assertEqual(b'private partial',(root/'.private-db/mock-1.tar').read_bytes())

    def test_real_child_does_not_inherit_even_an_inheritable_lock_fd(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with (root/'lock').open('w') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX);os.set_inheritable(lock.fileno(),True)
                device=Device('unused','unused',root);device.prefix=[sys.executable]
                script=f"import os; print(os.path.exists('/proc/self/fd/{lock.fileno()}'))"
                self.assertEqual('False',device.run(['-c',script]).strip())
                # The parent still owns the same lease; no child inheritance or unlock/relock.
                code="import fcntl,sys; f=open(sys.argv[1],'a');\ntry: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB); print('free')\nexcept BlockingIOError: print('held')"
                self.assertEqual('held',device.run(['-c',code,str(root/'lock')]).strip())

    def test_cli_fd_sanitizer_closes_passed_descriptor(self):
        with tempfile.TemporaryFile() as file:
            code=f"import sys,os;sys.path.insert(0,{str(g.PROJECT/'tools')!r});from duration_phone_guard import close_inherited_fds;close_inherited_fds();print(os.path.exists('/proc/self/fd/{file.fileno()}'))"
            out=subprocess.check_output([sys.executable,'-c',code],pass_fds=(file.fileno(),),text=True)
            self.assertEqual('False',out.strip())


if __name__=='__main__':unittest.main()
