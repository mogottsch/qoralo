#!/usr/bin/env python3
"""Derive numeric/identifier-only observations; raw user content remains local."""
import hashlib,json,re,sys
from pathlib import Path
from datetime import datetime,timezone
root=Path(sys.argv[1]);data=json.loads((root/'private-rows.json').read_text())
def utf16(s):return len(s.encode('utf-16-le'))//2
def digest(s):return hashlib.sha256(s.encode('utf-8')).hexdigest()
def iso(ms):return datetime.fromtimestamp(ms/1000,timezone.utc).isoformat() if ms else None
edits=sorted([j for j in data['generation_jobs'] if j['kind']=='AGENT_EDIT'],key=lambda j:j['createdAtEpochMs'],reverse=True)
assert edits,'No saved agent-edit job exists'
j=edits[0];e=next(e for e in data['episodes'] if e['id']==j['episodeId']);m=next((m for m in data['agent_messages'] if m['id']==j['requestMessageId']),None)
r=next((r for r in data['script_revisions'] if r['id']==j['requestedRevisionId']),None)
chapters=sorted([c for c in data['chapters'] if r and c['revisionId']==r['id']],key=lambda c:c['position'])
private_request=None
if r and m:
 private_request={'schemaVersion':1,'baseRevisionId':r['id'],'instruction':m['text'],'allowedOperations':['rewrite','shorten','remove','split','combine','rename'],'title':r['title'],'chapters':[{'id':c['stableChapterId'],'title':c['title'],'text':c['text']} for c in chapters]}
 (root/'private-reconstructed-request.json').write_text(json.dumps(private_request,ensure_ascii=False,separators=(',',':')))
failure=j.get('errorMessage') or ''
safe_failure=failure if re.fullmatch(r'(?:Gemma LiteRT GPU edit failed at [A-Z_]+; |Generation failed; )[A-Za-z0-9_.$():;,=\[\] -]{0,1000}',failure) else None
result={'scope':'derived current saved EDIT failure; no generation/retry','episodeId':e['id'],'episodeIsNewestCreated':e['createdAtEpochMs']==max(x['createdAtEpochMs'] for x in data['episodes']),'episodeCreatedUtc':iso(e['createdAtEpochMs']),'episodePhase':e['phase'],'jobId':j['id'],'jobKind':j['kind'],'jobStatus':j['status'],'jobCreatedUtc':iso(j['createdAtEpochMs']),'jobStartedUtc':iso(j.get('startedAtEpochMs')),'jobUpdatedUtc':iso(j['updatedAtEpochMs']),'jobFailureStage':j.get('failureStage'),'safeStoredFailure':safe_failure,'storedFailureSha256':digest(failure),'requestedRevisionId':j['requestedRevisionId'],'activeRevisionId':e['activeRevisionId'],'revisionContentSha256':r['contentHash'] if r else None,'messageId':m['id'] if m else None,'messageBaseMatchesRequestedRevision':bool(m and m['baseRevisionId']==j['requestedRevisionId']),'instructionUtf16Units':utf16(m['text']) if m else None,'instructionSha256':digest(m['text']) if m else None,'chapterCount':len(chapters),'chapters':[{'position':c['position'],'wordsWhitespaceSplit':len(c['text'].split()),'narrationUtf16Units':utf16(c['text']),'narrationUtf8Bytes':len(c['text'].encode()),'textSha256':digest(c['text'])} for c in chapters],'narrationUtf16LowerBoundForRequest':sum(utf16(c['text']) for c in chapters),'requestCharacterGate':20000,'configuredEditOutputTokenCeiling':4096,'configuredContextTokens':8192,'priorEditJobCount':len(edits)-1,'tableCounts':{k:len(v) for k,v in data.items()}}
(root/'derived-edit-observation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
