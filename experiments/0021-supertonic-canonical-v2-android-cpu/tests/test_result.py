from __future__ import annotations
import hashlib,json,wave
from pathlib import Path
EXP=Path(__file__).resolve().parents[1]
def load(name):return json.loads((EXP/name).read_text())
def test_canonical_v2_bytes():
 p=EXP/'protocol/transcript.txt';b=p.read_bytes();assert len(b)==226 and not b.endswith(b'\n');assert hashlib.sha256(b).hexdigest()=='424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67'
def test_first_and_five_warm_contract():
 r=load('results/phone-cpu-result.json');m=r['measurement'];assert m['first']['state']=='cold';assert len(m['warm'])==5;assert all(x['state']=='warm' for x in m['warm']);assert sorted(m['warm_rtf_values'])[2]==m['warm_median_rtf'];assert m['all_output_durations_equal'];assert r['route']['threads']==1 and r['route']['provider']=='cpu'
def test_all_wavs_structurally_valid():
 r=load('results/phone-cpu-result.json');runs=[r['measurement']['first'],*r['measurement']['warm']];assert len(runs)==6
 for run in runs:
  w=run['structural_wav'];assert (w['channels'],w['sample_rate_hz'],w['sample_width_bytes'],w['frames'])==(1,44100,2,696523);assert w['finite'] and w['non_silent'] and w['unclipped'];assert abs(w['duration_seconds']-run['actual_audio_duration_seconds'])<1e-12
def test_representative_wav_hash_and_review():
 r=load('results/phone-cpu-result.json');w=EXP/r['representative_wav']['path'];assert hashlib.sha256(w.read_bytes()).hexdigest()==r['representative_wav']['sha256'];assert r['representative_wav']['listening_review']['status']=='not_reviewed'
 with wave.open(str(w),'rb') as f:assert (f.getnchannels(),f.getframerate(),f.getsampwidth(),f.getnframes())==(1,44100,2,696523)
def test_cleanup_and_frontend():
 r=load('results/phone-cpu-result.json');assert all(r['cleanup'].values());f=load('results/frontend-provenance.json');assert f['input']['sha256']==r['canonical_transcript']['sha256'];assert f['frontend']['mapped_id_count']==f['frontend']['unicode_codepoint_count']
