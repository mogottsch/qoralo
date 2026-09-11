import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

PROJECT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PROJECT/'tools'))
from duration_phone_guard import GuardError
from short_product_preservation import TABLES,compare,compare_files
from run_short_product_gate import CONTINUATION_SHA


class ContinuationScopeTests(unittest.TestCase):
    def state(self):
        raw=(PROJECT/'app/src/debug/assets/short-product-continuation/contract.json').read_bytes()
        self.assertEqual(CONTINUATION_SHA,hashlib.sha256(raw).hexdigest());s=json.loads(raw);ep=s['episodeId']
        state={t:[] for t in TABLES}
        instructions=(PROJECT/'app/src/debug/assets/short-product-e2e/instructions.txt').read_text().replace('{TITLE}','Short plumbing ba099f63')
        self.assertEqual(s['instructionsSha256'],hashlib.sha256(instructions.encode()).hexdigest())
        state['episodes']=[{'id':'other','title':'unchanged'}, {'id':ep,'title':s['title'],'instructions':instructions,'phase':'SCRIPT_DRAFT',
            'reviewEnabled':1,'activeRevisionId':s['revisionId'],'lockedRevisionId':None,'lockedContentHash':None,'finalAudioPath':None,'updatedAtEpochMs':1}]
        state['script_revisions']=[{'id':s['baseRevisionId'],'episodeId':ep,'contentHash':s['baseContentHash']},
                                   {'id':s['revisionId'],'episodeId':ep,'contentHash':s['contentHash']}]
        state['episode_sources']=[{**row,'episodeId':ep} for row in s['sources']]
        script=json.loads((PROJECT/'app/src/test/resources/short-continuation-real-final.json').read_text())
        state['chapters']=[{'rowId':str(i),'revisionId':s['revisionId'],'position':i,'stableChapterId':r['id'],'title':r['title'],'text':r['text']} for i,r in enumerate(script['chapters'])]
        state['generation_jobs']=[{'id':v,'episodeId':ep,'kind':k,'status':'COMPLETE'} for k,v in s['priorJobs'].items()]
        state['installed_models']=[{'id':'gemma-4-e2b','route':'GEMMA_4_E2B_LITERT_GPU','manifestSha256':s['gemmaManifestSha256'],'verifiedAtEpochMs':1}]
        return state,s
    def progressed(self,state,s):
        after=copy.deepcopy(state);ep=s['episodeId']
        after['episodes'][1].update(phase='FROZEN_READY',lockedRevisionId=s['revisionId'],lockedContentHash=s['contentHash'],finalAudioPath=f'{ep}/final/new-audio/episode.wav',timelinePath=f'{ep}/final/new-audio/chapter-timeline.json',updatedAtEpochMs=2)
        after['generation_jobs'].append({'id':'new-audio','episodeId':ep,'kind':'AUDIO','status':'COMPLETE','requestedRevisionId':s['revisionId']})
        after['chapter_audio']=[{'id':'audio-'+str(i),'episodeId':ep,'lockedRevisionId':s['revisionId'],'stableChapterId':row['id'],'position':i,'relativePath':f'{ep}/chapters/chapter-{i:03d}.wav'} for i,row in enumerate(s['chapters'])]
        after['playback_state']=[{'episodeId':ep,'positionMs':1000}]
        after['installed_models'].append({'id':'supertonic-3','route':'SUPERTONIC_EXTERNAL_CONTEXT_QNN_HTP','manifestSha256':s['supertonicManifestSha256']})
        return after
    def test_only_owned_audio_transitions_and_new_artifacts_are_allowed(self):
        before,s=self.state();after=self.progressed(before,s)
        result=compare(before,after,s['episodeId'],s)
        self.assertTrue(result['otherExistingRowsUnchanged']);self.assertTrue(result['ownedEpisodeOnlyAllowedTransitions'])
        self.assertFalse(result['existingUserRowsUnchanged'])
        compare(before,before,s['episodeId'],s) # pre-install precondition check, no state change
        files={'files/episodes/'+s['episodeId']+'/script/old.json':'a'*64}
        compare_files(files,{**files,'files/episodes/'+s['episodeId']+'/chapters/new.wav':'b'*64},s['episodeId'])
    def test_prior_title_instructions_revisions_jobs_and_other_episode_cannot_change(self):
        before,s=self.state()
        for table,key in [('episodes','title'),('episodes','instructions'),('script_revisions','contentHash'),('generation_jobs','status')]:
            after=self.progressed(before,s);index=1 if table=='episodes' else 0;after[table][index][key]='changed'
            with self.subTest(table=table,key=key),self.assertRaises(GuardError):compare(before,after,s['episodeId'],s)
        after=self.progressed(before,s);after['episodes'][0]['title']='changed'
        with self.assertRaises(GuardError):compare(before,after,s['episodeId'],s)
    def test_new_llm_jobs_gemma_catalog_updates_and_wrong_lock_are_rejected(self):
        before,s=self.state()
        for kind in ['SCRIPT','AGENT_EDIT']:
            after=self.progressed(before,s);after['generation_jobs'][-1]['kind']=kind
            with self.assertRaises(GuardError):compare(before,after,s['episodeId'],s)
        after=self.progressed(before,s);after['installed_models'][0]['verifiedAtEpochMs']=2
        with self.assertRaises(GuardError):compare(before,after,s['episodeId'],s)
        after=self.progressed(before,s);after['episodes'][1]['lockedContentHash']='bad'
        with self.assertRaises(GuardError):compare(before,after,s['episodeId'],s)
    def test_new_episode_or_seeded_revision_and_existing_audio_are_rejected(self):
        before,s=self.state();after=self.progressed(before,s);after['episodes'].append({'id':'new','title':'x'})
        with self.assertRaises(GuardError):compare(before,after,s['episodeId'],s)
        after=self.progressed(before,s);after['script_revisions'].append({'id':'seed','episodeId':s['episodeId']})
        with self.assertRaises(GuardError):compare(before,after,s['episodeId'],s)
        before['chapter_audio']=[{'id':'old-audio','episodeId':s['episodeId']}]
        with self.assertRaises(GuardError):compare(before,before,s['episodeId'],s)
    def test_continuation_has_a_distinct_zero_llm_method_and_owned_audio_bound(self):
        source=(PROJECT/'app/src/debug/java/dev/vibevoice/podcast/e2e/ShortProductDiagnostics.kt').read_text()
        self.assertIn('if (continuation) require(entity.kind == "AUDIO")',source)
        self.assertIn('if (continuation) listOf("AUDIO")',source)
        self.assertIn('if (continuation) ShortContinuationPolicy.validateStored(context, locked = true)',source)
        policy=(PROJECT/'app/src/debug/java/dev/vibevoice/podcast/e2e/ShortContinuationPolicy.kt').read_text()
        self.assertIn('enforceWordTarget = false',policy)
        test=(PROJECT/'app/src/androidTest/java/dev/vibevoice/podcast/e2e/ShortProductE2eTest.kt').read_text().split('@Test fun continueOwnedReviewToAudioAndExport()',1)[1].split('private fun verifyAssembly',1)[0]
        for forbidden in ['newEpisode(', 'createEpisode(', 'generateScript(', 'Send change request', 'setContent', 'writeRevision(']:self.assertNotIn(forbidden,test)
        controller=(PROJECT/'tools/run_short_product_gate.py').read_text()
        self.assertIn('host_seconds=150 if export_only else 390 if continuation else 930',controller)
        self.assertIn('compare(rows(before),rows(before),owned,scope)',controller)


if __name__=='__main__':unittest.main()
