"""Read-only comparison of private snapshots for ONE owned short-product episode."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from duration_phone_guard import logical_database, require

TABLES = ('episodes','episode_sources','script_revisions','chapters','agent_messages','generation_jobs','chapter_audio','playback_state','installed_models')


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
            # Only these exact catalog IDs may be upserted by normal recordVerifiedPack.
            expected={'gemma-4-e2b':('GEMMA_4_E2B_LITERT_GPU','9fb627ef9a4eb0ed49056c32bc16f2846e6edf68dc8d854b02af90e24e4e96cd'),
                      'supertonic-3':('SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP','dc4ac737924d7d62e57ff5e166707198095c49e51d77cfed04a44d9e9435952d')}
            previous={r['id']:r for r in before[table]};current={r['id']:r for r in after[table]}
            require({k:v for k,v in previous.items() if k not in expected}=={k:v for k,v in current.items() if k not in expected},
                    'unrelated catalog row changed, even if its route matches')
            require(set(previous)&set(expected)<=set(current),'existing exercised catalog row removed')
            for key,row in current.items():
                if key in expected and previous.get(key)!=row:
                    require((row['route'],row['manifestSha256'])==expected[key],'unexpected verified catalog upsert route/id/manifest')
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
    return {'existingUserRowsUnchanged':True,'tables':counts,'allowedGlobalChanges':'only normal verified catalog upserts for the two exact exercised IDs; existing IDs retained'}


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


def validate_owned_control(current, original, run, owned, contract):
    require(original is not None and current==original,'foreign/mismatched control; preserve without deletion')
    value=json.loads(current)
    require(value=={'runId':run,'episodeId':owned,'contractSha256':contract} and owned is not None,
            'control run/episode/contract ownership unproven')
    return hashlib.sha256(current).hexdigest()
