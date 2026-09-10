"""Read-only comparison of private snapshots for ONE owned short-product episode."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from duration_phone_guard import logical_database, require

TABLES = ('episodes','episode_sources','script_revisions','chapters','agent_messages','generation_jobs','chapter_audio','playback_state','installed_models')
ROUTES = {'GEMMA_4_E2B_LITERT_GPU','SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP'}


def rows(files):
    if not files:
        return {table: [] for table in TABLES}
    with tempfile.TemporaryDirectory(prefix='short-product-readonly-') as temp:
        p = Path(temp)/'logical.sqlite'; p.write_bytes(logical_database(files))
        with closing(sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1', uri=True)) as db:
            db.execute('PRAGMA query_only=ON'); db.execute('PRAGMA trusted_schema=OFF'); db.row_factory=sqlite3.Row
            return {table:[dict(row) for row in db.execute('SELECT * FROM '+table)] for table in TABLES}


def compare(before, after, owned):
    """No writes. Report only aggregate counts; never expose existing row text or IDs."""
    old_ids={r['id'] for r in before['episodes']}
    new_ids={r['id'] for r in after['episodes']}-old_ids
    require(owned not in old_ids and new_ids <= ({owned} if owned else set()), 'unowned episode addition/reuse')
    owned_revisions={r['id'] for r in after['script_revisions'] if r['episodeId']==owned}
    counts={}
    for table in TABLES:
        if table=='installed_models':
            # Normal recordVerifiedPack legitimately upserts the two exercised route catalog rows.
            # Other route catalog rows remain byte-for-byte equivalent.
            previous=[r for r in before[table] if r['route'] not in ROUTES]
            current=[r for r in after[table] if r['route'] not in ROUTES]
            require(sorted(previous,key=lambda r:r['id'])==sorted(current,key=lambda r:r['id']), 'unrelated route catalog changed')
            for row in after[table]:
                if row['route'] in ROUTES:
                    expected={'GEMMA_4_E2B_LITERT_GPU':('gemma-4-e2b','9fb627ef9a4eb0ed49056c32bc16f2846e6edf68dc8d854b02af90e24e4e96cd'),
                              'SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP':('supertonic-3','dc4ac737924d7d62e57ff5e166707198095c49e51d77cfed04a44d9e9435952d')}[row['route']]
                    require((row['id'],row['manifestSha256'])==expected,'unexpected verified route catalog pin')
            continue
        key='rowId' if table=='chapters' else ('episodeId' if table=='playback_state' else 'id')
        old={r[key]:r for r in before[table]}; new={r[key]:r for r in after[table]}
        require(all(new.get(k)==v for k,v in old.items()), 'existing user row changed: '+table)
        additions=[r for k,r in new.items() if k not in old]
        def is_owned(r):
            if table=='episodes':return r['id']==owned
            if table=='chapters':return r['revisionId'] in owned_revisions
            return r['episodeId']==owned
        require(all(is_owned(r) for r in additions),'unowned row addition: '+table)
        counts[table]={'existingUnchanged':len(old),'ownedAdded':len(additions)}
    return {'existingUserRowsUnchanged':True,'tables':counts,'allowedGlobalChanges':'only normal verified catalog upserts for the two exercised pinned routes'}


def parse_inventory(raw):
    result={}
    for line in raw.decode().splitlines():
        digest, name=line.split('  ',1)
        require(len(digest)==64 and all(c in '0123456789abcdef' for c in digest),'invalid file hash')
        require(name.startswith('files/episodes/') and name not in result,'unsafe/duplicate episode file')
        require('..' not in Path(name).parts,'unsafe episode file path')
        result[name]=digest
    return result


def compare_files(before, after, owned):
    require(all(after.get(k)==v for k,v in before.items()),'existing episode artifact changed/removed')
    extra=set(after)-set(before)
    require(all(owned and p.startswith('files/episodes/'+owned+'/') for p in extra),'unowned artifact addition')
    return {'existingFilesUnchanged':len(before),'ownedAddedFiles':len(extra)}
