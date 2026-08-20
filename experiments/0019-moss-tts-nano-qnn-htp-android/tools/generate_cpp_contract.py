#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];REPO=R.parent.parent;E=R.parent/'0018-moss-tts-nano-onnx-android';mfile=E/'.local/tts/browser_poc_manifest.json';tfile=R/'protocol/canonical-v2-tokenization.json';canonical=REPO/'protocols/android-tts-benchmark/transcript.txt';m=json.load(open(mfile));t=json.load(open(tfile));raw=canonical.read_bytes();assert len(raw)==226 and not raw.endswith(b'\n') and raw.decode()==t['effective_text'];assert (R/'protocol/canonical-v2-transcript.txt').read_bytes()==raw;cfg=m['tts_config'];v=next(x for x in m['builtin_voices'] if x['voice']=='Junhao');rows=[]
prefix=m['prompt_templates']['user_prompt_prefix_token_ids']+[cfg['audio_start_token_id']];suffix=[cfg['audio_end_token_id']]+m['prompt_templates']['user_prompt_after_reference_token_ids']+t['token_ids']+m['prompt_templates']['assistant_prompt_prefix_token_ids']+[cfg['audio_start_token_id']]
for x in prefix:rows.append([x]+[cfg['audio_pad_token_id']]*16)
for x in v['prompt_audio_codes']:rows.append([cfg['audio_user_slot_token_id']]+x[:16])
for x in suffix:rows.append([x]+[cfg['audio_pad_token_id']]*16)
assert len(rows)==226 and all(len(x)==17 for x in rows)
flat=[x for row in rows for x in row];h=R/'host/generated_contract.h'
body='''#pragma once
#include <array>
#include <cstdint>
namespace moss_contract {
constexpr int64_t kPrefillLength=226, kRowWidth=17, kQuantizers=16, kCodebookSize=1024;
constexpr int64_t kMaxFrames=375, kDecodeInputCapacity=600, kDecodeStateCapacity=601;
constexpr int32_t kAssistantSlot=%d, kAudioPad=%d, kSampleRate=48000;
constexpr uint64_t kSeed=20260818ULL;
constexpr std::array<int32_t, %d> kPrefillIds={
%s
};
}
'''%(cfg['audio_assistant_slot_token_id'],cfg['audio_pad_token_id'],len(flat),',\n'.join('  '+','.join(map(str,row)) for row in rows))
h.write_text(body)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
out={'schema_version':1,'sources':{'canonical_transcript':str(canonical.relative_to(REPO)),'canonical_transcript_bytes':len(raw),'canonical_transcript_sha256':sha(canonical),'canonical_transcript_trailing_newline':raw.endswith(b'\n'),'experiment_transcript_sha256':sha(R/'protocol/canonical-v2-transcript.txt'),'legacy_v1_transcript_sha256':sha(R/'protocol/transcript.txt'),'legacy_v1_tokenization_sha256':sha(R/'protocol/tokenization.json'),'manifest':str(mfile.relative_to(REPO)),'manifest_sha256':sha(mfile),'tokenization':'protocol/canonical-v2-tokenization.json','tokenization_sha256':sha(tfile),'effective_text_sha256':hashlib.sha256(t['effective_text'].encode()).hexdigest()}, 'contract':{'voice':'Junhao','seed':20260818,'prefill_rows':226,'row_width':17,'max_frames':375,'decode_input_capacity':600,'decode_output_state_capacity':601},'output':'host/generated_contract.h','output_sha256':sha(h)}
(R/'results/generated-contract-provenance.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
