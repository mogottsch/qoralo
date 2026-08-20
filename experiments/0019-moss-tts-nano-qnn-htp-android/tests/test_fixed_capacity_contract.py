import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_off_by_one_state_abi():
 p=json.load(open(ROOT/'protocol/fixed-capacity-equivalence-policy.json'));a=p['abi']
 valid=[a['prefill_positions']+step for step in range(a['max_generated_frames'])]
 assert len(valid)==375
 assert (valid[0],valid[104],valid[208],valid[209],valid[373],valid[374])==(226,330,434,435,599,600)
 assert valid==list(range(226,601))
 assert max(valid)==a['decode_output_and_logical_state_capacity']-1
 assert a['decode_input_cache_capacity']==600
 assert a['new_kv_always_read_from_fixed_output_index']==600
 assert valid[-2]<a['decode_input_cache_capacity'] and valid[-1]==a['decode_input_cache_capacity']
def test_generated_contract_matches_policy():
 text=(ROOT/'host/generated_contract.h').read_text();p=json.load(open(ROOT/'protocol/fixed-capacity-equivalence-policy.json'))
 values={k:int(v) for k,v in re.findall(r'(k(?:PrefillLength|MaxFrames|DecodeInputCapacity|DecodeStateCapacity))=(\d+)',text)}
 assert values=={'kPrefillLength':226,'kMaxFrames':375,'kDecodeInputCapacity':600,'kDecodeStateCapacity':601}
 assert p['abi']['decode_input_cache_capacity']==values['kDecodeInputCapacity']
 assert p['abi']['decode_output_and_logical_state_capacity']==values['kDecodeStateCapacity']
def test_canonical_v2_and_legacy_v1_are_separate():
 import hashlib
 canonical=(ROOT.parent.parent/'protocols/android-tts-benchmark/transcript.txt').read_bytes();v2=(ROOT/'protocol/canonical-v2-transcript.txt').read_bytes();v1=(ROOT/'protocol/transcript.txt').read_bytes()
 assert canonical==v2 and len(v2)==226 and not v2.endswith(b'\n')
 assert hashlib.sha256(v2).hexdigest()=='424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67'
 assert hashlib.sha256(v1).hexdigest()=='350c8d3d57525e65085b1d7c5ec733985c5467797cf50508b5e2a4eee313471f'
 old=json.load(open(ROOT/'protocol/tokenization.json'));new=json.load(open(ROOT/'protocol/canonical-v2-tokenization.json'))
 assert old['token_count']==new['token_count']==51
 assert [(i,a,b) for i,(a,b) in enumerate(zip(old['token_ids'],new['token_ids'])) if a!=b]==[(5,1583,10364),(40,1583,10364)]
def test_generated_contract_provenance_hash():
 import hashlib
 d=json.load(open(ROOT/'results/generated-contract-provenance.json'));p=ROOT/d['output']
 assert hashlib.sha256(p.read_bytes()).hexdigest()==d['output_sha256']
