#!/usr/bin/env python3
"""Prepare exact canonical transcript/token/noise fixtures for Pocket text64/cache512."""
from __future__ import annotations
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
import sentencepiece as spm
EXPECTED_TEXT_SHA="424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67"
EXPECTED_TOKENIZER_SHA="d461765ae179566678c93091c5fa6f2984c31bbe990bf1aa62d92c64d91bc3f6"
EXPECTED_ALBA_SHA="e4a323e8e771f14fd669428d83e7af6d83b4d6d0f0e282c30122f04824f17b1c"
def sha_bytes(x):return hashlib.sha256(x).hexdigest()
def sha_file(p):return sha_bytes(p.read_bytes())
def main():
 root=Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True).strip());e12=root/'experiments/0012-pocket-onnx-vs-executorch-android';e14=root/'experiments/0014-pocket-fp-onnx-qnn-htp';text_path=root/'protocols/android-tts-benchmark/transcript.txt';tokenizer=e12/'.local/source-assets/languages/english/tokenizer.model';alba=e12/'.local/source-assets/languages/english/embeddings/alba.safetensors';old_assets=e14/'work/quality-recovery/alba-assets';out=e14/'work/canonical-benchmark/assets';out.mkdir(parents=True,exist_ok=True)
 subprocess.run(['git','diff','--quiet','HEAD','--','protocols/android-tts-benchmark/transcript.txt'],cwd=root,check=True);text_bytes=text_path.read_bytes();assert len(text_bytes)==226 and not text_bytes.endswith(b'\n') and sha_bytes(text_bytes)==EXPECTED_TEXT_SHA;assert sha_file(tokenizer)==EXPECTED_TOKENIZER_SHA and sha_file(alba)==EXPECTED_ALBA_SHA
 text=text_bytes.decode('utf-8');processor=spm.SentencePieceProcessor(model_file=str(tokenizer));ids=np.asarray(processor.encode(text),dtype='<i8');assert ids.shape==(64,);token_file=out/'canonical-token-ids-64.i64';token_file.write_bytes(ids.tobytes());noise=np.random.RandomState(0).normal(0,np.sqrt(.3),(292,32)).astype('<f4');noise_file=out/'numpy-randomstate-seed0-temp0p3-292x32.f32';noise_file.write_bytes(noise.tobytes());cache=old_assets/'alba-flow-cache-v1.f32';assert sha_file(cache)=='eb6e2d714fe75cb9a726c7742f32e7c6b500cc6de4dae8b533f2bfa7b41bc6d2'
 report={'schema_version':1,'route_id':'pocket-fixed-alba-text64-cache512','canonical_transcript':{'version':2,'path':'protocols/android-tts-benchmark/transcript.txt','pinned_revision':'2de8b80','bytes':len(text_bytes),'trailing_newline':False,'sha256':sha_bytes(text_bytes),'utf8':text},'frontend':{'tokenizer_sha256':sha_file(tokenizer),'token_count':len(ids),'token_ids':ids.tolist(),'token_ids_encoding':'little-endian int64','token_ids_path':str(token_file),'token_ids_sha256':sha_file(token_file)},'voice':{'contract':'official pinned fixed Alba state; not voice cloning','state_sha256':sha_file(alba),'cache_pack_reused_path':str(cache),'cache_pack_sha256':sha_file(cache),'voice_positions':126},'generation':{'temperature':.3,'seed':0,'noise_algorithm':'NumPy RandomState MT19937 normal','noise_shape':[292,32],'noise_encoding':'little-endian float32','noise_path':str(noise_file),'noise_sha256':sha_file(noise_file),'lsd_steps':1,'eos_threshold':-4.0,'frames_after_eos':3,'frame_cap':292},'static_abi':{'capacity':512,'voice_positions':126,'text_positions':64,'maximum_generated_positions':292,'total_required_positions':482,'spare_positions':30,'bos_absolute_position':190,'first_latent_absolute_position':191},'separation':'Distinct derivative benchmark; does not alter or relabel committed text26/cache256 artifacts or verdicts.'};(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
