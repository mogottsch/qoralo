"""Real SQLite recycled-WAL fixtures. No phone, original snapshot mutation or model calls."""
import contextlib
from pathlib import Path
import sqlite3
import struct
import tempfile
import unittest
from test_duration_phone_guard import database, row, snapshot
import duration_phone_guard as g


class LiveWalPrefixTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.db=database(self.root,wal=True)
        row(self.db,'episodes',id='ep',phase='SOURCES')
        self.db.execute('PRAGMA wal_checkpoint(RESTART)')
        self.db.execute("UPDATE episodes SET title='after reset' WHERE id='ep'");self.db.commit()
        self.files=snapshot(self.root)
        self.wal=self.files['databases/podcast.db-wal'];self.shm=self.files['databases/podcast.db-shm']
        self.page=struct.unpack('>I',self.wal[8:12])[0];self.live=struct.unpack('<I',self.shm[16:20])[0]
        self.end=32+self.live*(24+self.page)
        assert self.end<len(self.wal), 'fixture must retain physical tail after reset'
    def tearDown(self):self.db.close();self.temp.cleanup()
    def changed_header(self, offset, data):
        value=bytearray(self.shm);value[offset:offset+len(data)]=data
        value[40:48]=struct.pack('<II',*g.checksum(bytes(value[:40]),'<'));value[48:96]=value[:48]
        return {**self.files,'databases/podcast.db-shm':bytes(value)}

    def test_real_reset_tail_is_read_only_and_current_commit_is_verified(self):
        before=snapshot(self.root)
        self.assertEqual(1,g.validate_snapshot(self.files)['episodeCount'])
        boundary=g.wal_index_boundary(self.files,self.wal,self.page,'<')
        self.assertEqual(self.live,boundary['liveFrames']);self.assertGreater(boundary['physicalFrames'],self.live)
        self.assertEqual(before,snapshot(self.root))

    def test_cleared_first_stale_header_matches_phone_shape_without_touching_original(self):
        altered=bytearray(self.wal);altered[self.end:self.end+16]=bytes(16)
        self.assertEqual(1,g.validate_snapshot({**self.files,'databases/podcast.db-wal':bytes(altered)})['episodeCount'])
        self.assertEqual(self.wal,snapshot(self.root)['databases/podcast.db-wal'])

    def test_live_prefix_page_salt_and_checksum_corruption_are_not_ignored(self):
        for index in [32,40,100]:
            bad=bytearray(self.wal);bad[index]^=1
            with self.subTest(index=index),self.assertRaises(g.GuardError):g.validate_snapshot({**self.files,'databases/podcast.db-wal':bytes(bad)})
        with self.assertRaises(g.GuardError):g.validate_snapshot({**self.files,'databases/podcast.db-wal':self.wal[:-1]})

    def test_current_epoch_tail_is_rejected_even_with_matching_index_boundary(self):
        bad=bytearray(self.wal);bad[self.end+8:self.end+16]=self.wal[16:24]
        with self.assertRaisesRegex(g.GuardError,'current-epoch/uncommitted'):
            g.validate_snapshot({**self.files,'databases/podcast.db-wal':bytes(bad)})

    def test_missing_stale_mismatched_or_unknown_index_cannot_authorize_tail(self):
        bads=[{**self.files,'databases/podcast.db-shm':b''},
              self.changed_header(0,struct.pack('<I',3007001)),self.changed_header(32,bytes(8)),
              self.changed_header(16,struct.pack('<I',self.live+1)),
              self.changed_header(20,struct.pack('<I',struct.unpack('<I',self.shm[20:24])[0]+1)),
              self.changed_header(24,bytes(8))]
        bad=bytearray(self.shm);bad[8]^=1;bads.append({**self.files,'databases/podcast.db-shm':bytes(bad)})
        bad=bytearray(self.shm);bad[56]^=1;bads.append({**self.files,'databases/podcast.db-shm':bytes(bad)})
        bad=bytearray(self.shm);bad[96:100]=struct.pack('<I',self.live+1);bads.append({**self.files,'databases/podcast.db-shm':bytes(bad)})
        for i,value in enumerate(bads):
            with self.subTest(i=i),self.assertRaises(g.GuardError):g.validate_snapshot(value)

    def test_current_committed_active_job_remains_ineligible(self):
        row(self.db,'generation_jobs',id='job',episodeId='ep',kind='SCRIPT',status='QUEUED')
        with self.assertRaisesRegex(g.GuardError,'pending/reconcilable'):g.validate_snapshot(snapshot(self.root))


if __name__=='__main__':unittest.main()
