"""Host-only, fail-closed pre-dispatch guard. Never opens a device database in SQLite."""
from __future__ import annotations
from contextlib import closing
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import struct
import tarfile
import tempfile
import time

from prepare_wiring_gate import PROJECT, digest
from run_wiring_gate import APP, TEST_APP

IDENTITY = {
    'ro.serialno': 'R5CW81PR8SY', 'ro.product.model': 'SM-S918B', 'ro.soc.model': 'SM8550',
    'ro.product.cpu.abi': 'arm64-v8a', 'ro.build.version.release': '16', 'ro.build.version.sdk': '36',
    'ro.build.fingerprint': 'samsung/dm3qxeea/dm3q:16/BP4A.251205.006/S918BXXSAFZG1:user/release-keys',
}
SCHEMA = PROJECT / 'app/schemas/dev.vibevoice.podcast.data.PodcastDatabase/1.json'
SCHEMA_SHA = 'aa0440c6e4636618a3eb9ec50131aef8a66c280e568262e88daae9edd21a8a84'
MAX_BYTES = 64 * 1024 * 1024
FILES = {'databases/podcast.db', 'databases/podcast.db-wal', 'databases/podcast.db-shm'}
GENERATION_TABLES = ('generation_jobs', 'script_revisions', 'chapters', 'agent_messages', 'chapter_audio', 'playback_state')
SETTINGS = ('settings get global window_animation_scale', 'settings get global transition_animation_scale',
            'settings get global animator_duration_scale', 'settings get system font_scale', 'wm size', 'wm density')
SNAPSHOT = (f'run-as {APP} sh -c \'set -eu; [ -r . ] && [ -x . ]; '
            'if [ ! -e databases ] && [ ! -L databases ]; then printf "DATABASES_ABSENT\\n"; '
            'else [ -d databases ] && [ ! -L databases ] && [ -r databases ] && [ -x databases ]; tar -cf - databases; fi\'')


class GuardError(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise GuardError(message)


def close_inherited_fds():
    # CLI entry only, before opening our lock/files. Also covers an ADB daemon spawned later.
    for entry in list(Path('/proc/self/fd').iterdir()):
        fd = int(entry.name)
        if fd > 2:
            try:
                os.close(fd)
            except OSError:
                pass


def host_identity():
    paths = ['tools/run_duration_load_gate.py', 'tools/duration_phone_guard.py', 'tools/run_wiring_gate.py',
             'tools/prepare_duration_load_gate.py', 'tools/prepare_wiring_gate.py', str(SCHEMA.relative_to(PROJECT))]
    files = {p: digest(PROJECT / p) for p in paths}
    return {'files': files, 'sha256': hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}


def archive_files(raw):
    require(len(raw) <= MAX_BYTES, 'private snapshot exceeds bound')
    if raw == b'DATABASES_ABSENT\n':
        return {}
    result = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for item in archive:
            if item.isdir() and item.name.rstrip('/') == 'databases':
                continue
            require(item.name in FILES and item.isfile() and item.name not in result, 'unknown/duplicate/unsafe database member')
            require(0 <= item.size <= MAX_BYTES and sum(map(len, result.values())) + item.size <= MAX_BYTES, 'database files exceed bound')
            result[item.name] = archive.extractfile(item).read()
    require('databases/podcast.db' in result, 'existing database directory has no recognized database')
    return result


def checksum(data, order, state=(0, 0)):
    require(len(data) % 8 == 0, 'unaligned WAL checksum input')
    a, b = state
    for x, y in struct.iter_unpack(order + 'II', data):
        a = (a + x + b) & 0xffffffff
        b = (b + y + a) & 0xffffffff
    return a, b


def logical_database(files):
    """Validate every WAL frame, then materialize a LOCAL read-only inspection view.

    Never let SQLite silently ignore a torn/uncommitted WAL tail or inspect stale base pages.
    Original device files and private raw archives are never changed/checkpointed.
    """
    base = files['databases/podcast.db']
    require(len(base) >= 100 and base[:16] == b'SQLite format 3\x00', 'invalid SQLite base')
    page = int.from_bytes(base[16:18], 'big'); page = 65536 if page == 1 else page
    require(512 <= page <= 65536 and page & (page - 1) == 0 and len(base) % page == 0, 'invalid SQLite page geometry')
    wal = files.get('databases/podcast.db-wal', b'')
    if not wal:
        return base
    require(len(wal) >= 32 and (len(wal) - 32) % (24 + page) == 0, 'truncated WAL')
    magic, version, wal_page = struct.unpack('>III', wal[:12])
    require(magic in (0x377f0682, 0x377f0683) and version == 3007000 and wal_page == page, 'unknown WAL header')
    order = '<' if magic == 0x377f0682 else '>'
    state = checksum(wal[:24], order)
    require(state == struct.unpack('>II', wal[24:32]), 'WAL header checksum mismatch')
    result = bytearray(base); final_size = 0
    for offset in range(32, len(wal), 24 + page):
        header = wal[offset:offset+24]; payload = wal[offset+24:offset+24+page]
        number, committed = struct.unpack('>II', header[:8])
        require(0 < number <= MAX_BYTES // page and committed <= MAX_BYTES // page, 'WAL page bound')
        require(header[8:16] == wal[16:24], 'WAL frame salt mismatch')
        state = checksum(header[:8] + payload, order, state)
        require(state == struct.unpack('>II', header[16:24]), 'WAL frame checksum mismatch')
        end = number * page
        if len(result) < end:
            result.extend(b'\x00' * (end-len(result)))
        result[end-page:end] = payload
        final_size = committed
    if len(wal) > 32:
        require(final_size > 0, 'uncommitted/recovery WAL tail; no repair allowed')
        result = result[:final_size*page]
        require(len(result) == final_size*page, 'WAL commit exceeds available database pages')
    return bytes(result)


def validate_snapshot(files):
    require(digest(SCHEMA) == SCHEMA_SHA, 'unknown host schema reference')
    if not files:
        return {'database': 'absent', 'generationHistoryRows': 0, 'episodeCount': 0}
    data = logical_database(files)
    schema = json.loads(SCHEMA.read_text())['database']
    with tempfile.TemporaryDirectory(prefix='duration-readonly-db-') as temporary:
        path = Path(temporary) / 'logical.sqlite'; path.write_bytes(data)
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)) as db, closing(sqlite3.connect(':memory:')) as expected:
            db.execute('PRAGMA query_only=ON'); db.execute('PRAGMA trusted_schema=OFF')
            deadline = time.monotonic() + 5
            db.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            require(db.execute('PRAGMA integrity_check').fetchall() == [('ok',)], 'SQLite integrity failure')
            require(not db.execute('PRAGMA foreign_key_check').fetchall(), 'foreign-key inconsistency')
            require(db.execute('PRAGMA user_version').fetchone()[0] == schema['version'], 'unknown database version')
            for entity in schema['entities']:
                expected.execute(entity['createSql'].replace('${TABLE_NAME}', entity['tableName']))
                for index in entity['indices']:
                    expected.execute(index['createSql'].replace('${TABLE_NAME}', entity['tableName']))
            for sql in schema['setupQueries']:
                expected.execute(sql)
            def structure(connection):
                return {(kind, name, table): ' '.join((sql or '').split()) for kind, name, table, sql in
                        connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name != 'android_metadata'")}
            require(structure(db) == structure(expected), 'unknown database schema/index/trigger/view')
            metadata = db.execute("SELECT type,sql FROM sqlite_master WHERE name='android_metadata'").fetchall()
            if metadata:
                require(metadata == [('table', 'CREATE TABLE android_metadata (locale TEXT)')], 'unknown android metadata schema')
            require(db.execute('SELECT id,identity_hash FROM room_master_table').fetchall() == [(42, schema['identityHash'])], 'Room identity mismatch')
            counts = {table: db.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for table in GENERATION_TABLES}
            active = db.execute("SELECT count(*) FROM generation_jobs WHERE status IN ('QUEUED','RUNNING')").fetchone()[0]
            require(active == 0, 'pending/reconcilable work found')
            require(not any(counts.values()), 'guard cannot establish safe state: conservative no-generation-history eligibility rule')
            # Deliberately conservative: even terminal/recoverable history is a STOP, never a cleanup request.
            episodes = db.execute('SELECT phase,activeRevisionId,lockedRevisionId,lockedContentHash,lockedAtEpochMs,finalAudioPath,durationMs,currentChapterPosition,failurePhase,failureMessage,finalAudioSha256,finalAudioByteCount,timelinePath,timelineSha256,timelineByteCount FROM episodes').fetchall()
            require(all(row[0] in ('SOURCES', 'INSTRUCTIONS') and all(value is None for value in row[1:]) for row in episodes), 'guard cannot establish safe state: unsupported episode state or metadata')
            require(db.execute("SELECT count(*) FROM episodes e WHERE phase='INSTRUCTIONS' AND NOT EXISTS (SELECT 1 FROM episode_sources s WHERE s.episodeId=e.id)").fetchone()[0] == 0, 'instructions episode has no source')
            return {'database': 'known-schema-pristine-generation-state', 'episodeCount': len(episodes), 'generationHistoryRows': 0}


class PhoneGuard:
    def __init__(self, device, output, candidate, approved_candidate, approved_host):
        self.device = device; self.output = output; self.candidate = candidate
        self.approved_candidate = approved_candidate; self.approved_host = approved_host
        self.baseline = None; self.settings = None; self.identity_verified = False

    def identity(self):
        require(self.device.prefix[-1] == IDENTITY['ro.serialno'], 'wrong target serial')
        observed = {key: self.device.shell('getprop ' + key).strip() for key in IDENTITY}
        (self.output/'guard-device-identity.json').write_text(json.dumps(observed, indent=2)+'\n')
        require(observed == IDENTITY, 'exact phone identity mismatch')
        self.identity_verified = True

    def idle(self):
        result = self.device.shell(f'pidof {APP} {APP}:generation {TEST_APP}', check=False)
        record = self.output/f'{self.device.counter:03d}-command'
        require(not result.strip() and record.with_suffix('.exit').read_text() == '1' and not record.with_suffix('.stderr').read_text().strip(), 'app PID absence unproven')

    def snapshot(self, phase, number):
        private = self.output/'.private-db'; private.mkdir(mode=0o700, exist_ok=True)
        counter = self.device.counter + 1
        destination = private/f'{phase}-{number}.tar'
        try:
            self.device.run(['exec-out', SNAPSHOT], timeout=30, binary=True)
        finally:
            raw = self.output/f'{counter:03d}-command.stdout'
            if raw.exists():
                raw.rename(destination); destination.chmod(0o600)
        return archive_files(destination.read_bytes())

    def checkpoint(self, phase):
        require(digest(self.candidate) == self.approved_candidate, 'candidate changed under lock')
        value = json.loads(self.candidate.read_text())
        for item in (value['app'], value['test']):
            require(digest(Path(item['path'])) == item['sha256'], 'APK changed under lock')
        require(host_identity()['sha256'] == self.approved_host, 'host controller/guard changed')
        self.identity(); self.idle()
        if self.settings is None:
            self.settings = {cmd: self.device.shell(cmd).strip() for cmd in SETTINGS}
            (self.output/'guard-settings-before.json').write_text(json.dumps(self.settings, indent=2)+'\n')
        first = self.snapshot(phase, 1); second = self.snapshot(phase, 2)
        hashes = {name: {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)} for name, data in first.items()}
        second_hashes = {name: {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)} for name, data in second.items()}
        (self.output/f'guard-{phase}-snapshot.json').write_text(json.dumps({'first': hashes, 'second': second_hashes,
            'identical': first == second, 'privateRawDirectory': '.private-db; NEVER publish DB contents'}, indent=2)+'\n')
        require(first == second, 'DB/WAL snapshot changed between bounded reads')
        require(self.baseline is None or hashes == self.baseline, 'database changed between guarded actions')
        summary = validate_snapshot(first)
        self.idle()
        self.baseline = hashes
        (self.output/f'guard-{phase}.json').write_text(json.dumps({'files': hashes, 'state': summary,
            'twoSnapshotsIdentical': True, 'lastCheckMonotonicNs': time.monotonic_ns(),
            'raceBoundary': 'Not an atomic Android transaction. External launch/write after this check remains possible; no other phone interaction is permitted.'}, indent=2)+'\n')

    def readback_settings(self):
        if self.settings is None:
            return []
        try:
            after = {cmd: self.device.shell(cmd).strip() for cmd in SETTINGS}
            (self.output/'guard-settings-after.json').write_text(json.dumps(after, indent=2)+'\n')
            return [] if after == self.settings else ['Settings changed unexpectedly; no repair attempted']
        except Exception as error:
            return [repr(error)]
