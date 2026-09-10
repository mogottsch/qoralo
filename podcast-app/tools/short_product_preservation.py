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


def continuation_episode(before, after, owned, scope):
    require(owned==scope['episodeId'],'wrong continuation episode')
    old=next((r for r in before['episodes'] if r['id']==owned),None)
    new=next((r for r in after['episodes'] if r['id']==owned),None)
    require(old is not None and new is not None,'continuation episode missing')
    require(old['phase']=='SCRIPT_DRAFT' and old['reviewEnabled']==1 and old['activeRevisionId']==scope['revisionId']
            and old['title']==scope['title'] and old['lockedRevisionId'] is None and old['finalAudioPath'] is None,'continuation preconditions changed')
    rev=next((r for r in before['script_revisions'] if r['id']==scope['revisionId']),None)
    require(rev is not None and rev['episodeId']==owned and rev['contentHash']==scope['contentHash'],'continuation revision binding changed')
    require(hashlib.sha256(old['instructions'].encode()).hexdigest()==scope['instructionsSha256'],'continuation original instructions changed')
    base=next((r for r in before['script_revisions'] if r['id']==scope['baseRevisionId']),None)
    require(base is not None and base['episodeId']==owned and base['contentHash']==scope['baseContentHash'],'continuation original base revision changed')
    sources=[{k:r[k] for k in ('id','relativePath','sha256','byteCount')} for r in before['episode_sources'] if r['episodeId']==owned]
    require(sorted(sources,key=lambda r:r['id'])==sorted(scope['sources'],key=lambda r:r['id']),'continuation original sources changed')
    chapters=sorted([r for r in before['chapters'] if r['revisionId']==scope['revisionId']],key=lambda r:r['position'])
    require(len(chapters)==2 and all(r['stableChapterId']==pin['id'] and r['title']==pin['title'] and hashlib.sha256(r['text'].encode()).hexdigest()==pin['textSha256']
                                   for r,pin in zip(chapters,scope['chapters'])),'continuation chapter text/identity changed')
    require(not any(r['episodeId']==owned for r in before['chapter_audio']+before['playback_state']),'continuation must not rerender existing audio')
    prior=scope['priorJobs']
    jobs=[r for r in before['generation_jobs'] if r['episodeId']==owned]
    require(len(jobs)==2 and {r['kind']:r['id'] for r in jobs}==prior and all(r['status']=='COMPLETE' for r in jobs),'prior five-call job provenance differs')
    mutable={'phase','lockedRevisionId','lockedContentHash','lockedAtEpochMs','finalAudioPath','durationMs','currentChapterPosition',
             'failurePhase','failureMessage','updatedAtEpochMs','finalAudioSha256','finalAudioByteCount','timelinePath','timelineSha256','timelineByteCount'}
    require({k:v for k,v in old.items() if k not in mutable}=={k:v for k,v in new.items() if k not in mutable},'immutable owned episode fields changed')
    require(new['phase'] in ('SCRIPT_DRAFT','LOCKED','GENERATING_AUDIO','FROZEN_READY','FAILED'),'unexpected continuation phase')
    if new['lockedRevisionId'] is not None:
        require(new['lockedRevisionId']==scope['revisionId'] and new['lockedContentHash']==scope['contentHash'],'wrong locked continuation content')
    added_jobs=[r for r in after['generation_jobs'] if r['episodeId']==owned and r['id'] not in {j['id'] for j in jobs}]
    if new['phase']!='SCRIPT_DRAFT':
        require(len(added_jobs)==1 and added_jobs[0]['kind']=='AUDIO' and new['lockedRevisionId']==scope['revisionId'],'owned transition lacks its one audio job/lock')
    if new['phase']=='FROZEN_READY':
        job=added_jobs[0]
        require(job['status']=='COMPLETE' and new['finalAudioPath']==f"{owned}/final/{job['id']}/episode.wav"
                and new['timelinePath']==f"{owned}/final/{job['id']}/chapter-timeline.json",'final artifacts do not belong to continuation audio job')


def compare(before, after, owned, continuation=None):
    """No writes. Report only aggregate counts; never expose existing row text or IDs."""
    old_ids={r['id'] for r in before['episodes']}
    new_ids={r['id'] for r in after['episodes']}-old_ids
    if continuation:
        require(not new_ids and {r['id'] for r in after['episodes']}==old_ids,'continuation cannot add/remove episodes')
        continuation_episode(before,after,owned,continuation)
    else:require(owned not in old_ids and new_ids <= ({owned} if owned else set()), 'unowned episode addition/reuse')
    owned_revisions={r['id'] for r in after['script_revisions'] if r['episodeId']==owned}
    counts={}
    for table in TABLES:
        if table=='installed_models':
            # Only these exact catalog IDs may be upserted by normal recordVerifiedPack.
            expected={'gemma-4-e2b':('GEMMA_4_E2B_LITERT_GPU','9fb627ef9a4eb0ed49056c32bc16f2846e6edf68dc8d854b02af90e24e4e96cd'),
                      'supertonic-3':('SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP','dc4ac737924d7d62e57ff5e166707198095c49e51d77cfed04a44d9e9435952d')}
            if continuation:expected={'supertonic-3':expected['supertonic-3']} # ZERO new Gemma load/catalog update
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
        require(all(new.get(k)==v for k,v in old.items() if not (continuation and table=='episodes' and k==owned)), 'existing user row changed: '+table)
        additions=[r for k,r in new.items() if k not in old]
        if continuation:
            require(table in ('generation_jobs','chapter_audio','playback_state') or not additions,'continuation added non-audio data: '+table)
            if table=='generation_jobs':
                require(len(additions)<=1 and all(r['kind']=='AUDIO' and r['requestedRevisionId']==continuation['revisionId'] for r in additions),'extra/wrong continuation job')
            if table=='chapter_audio':
                require(len(additions)<=2 and all(r['lockedRevisionId']==continuation['revisionId'] and r['position'] in (0,1)
                        and r['stableChapterId']==continuation['chapters'][r['position']]['id']
                        and r['relativePath']==f"{owned}/chapters/chapter-{r['position']:03d}.wav" for r in additions),'wrong continuation audio')
        def is_owned(r):
            if table=='episodes':return r['id']==owned
            if table=='chapters':return r['revisionId'] in owned_revisions
            return r['episodeId']==owned
        require(all(is_owned(r) for r in additions),'unowned row addition: '+table)
        counts[table]={'existingUnchanged':len(old),'ownedAdded':len(additions)}
    return {'existingUserRowsUnchanged':not bool(continuation),'otherExistingRowsUnchanged':True,
            'ownedEpisodeOnlyAllowedTransitions':bool(continuation),'tables':counts,
            'allowedGlobalChanges':'only supertonic-3 catalog upsert' if continuation else 'only normal verified catalog upserts for the two exact exercised IDs; existing IDs retained'}


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
