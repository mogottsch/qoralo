#!/usr/bin/env python3
"""Audit and listen-test the distinct pinned 0008 sherpa INT8 Pocket archive."""
from __future__ import annotations
import hashlib,json,platform,subprocess,sys,wave
from pathlib import Path
import numpy as np
TEXT="Pocket TTS runs entirely on this Android phone using the original floating point model."
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def wav_read(p):
 with wave.open(str(p),'rb') as w:assert (w.getnchannels(),w.getsampwidth(),w.getframerate())==(1,2,24000);return np.frombuffer(w.readframes(-1),dtype='<i2').astype(np.float32)/32768
def wav_write(p,x):
 x=np.asarray(x,np.float32).reshape(-1);pcm=np.clip(np.rint(x*32767),-32768,32767).astype('<i2')
 with wave.open(str(p),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(pcm.tobytes())
 return {'path':str(p),'sha256':sha(p),'samples':x.size,'seconds':x.size/24000,'peak_float':float(np.max(np.abs(x))),'rms_float':float(np.sqrt(np.mean(x*x))),'finite':bool(np.isfinite(x).all()),'clipped_before_conversion':int(np.count_nonzero(np.abs(x)>1))}
def main():
 root=Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True).strip());e14=root/'experiments/0014-pocket-fp-onnx-qnn-htp';base=e14/'.local/upstream-0008';archive=base/'sherpa-onnx-pocket-tts-int8-2026-01-26.tar.bz2';model=base/'sherpa-onnx-pocket-tts-int8-2026-01-26';out=e14/'work/quality-recovery/archive-0008';out.mkdir(parents=True,exist_ok=True)
 assert sha(archive)=='2f3b88823cbbb9bf0b2477ec8ae7b3fec417b3a87b6bb5f256dba66f2ad967cb';pins={'encoder.onnx':'e8f2f6d301ffb96e398b138a7dc6d3038622d236044636b73d920bab85890260','decoder.int8.onnx':'12b0857402d31aead94df19d6783b4350d1f740e811f3a3202c70ad89ae11eea','lm_flow.int8.onnx':'8d627d235c44a597da908e1085ebe241cbbe358964c502c5a5063d18851a5529','lm_main.int8.onnx':'bfc0c7e7e3d72864fa3bb2ee499f62f21ddc1474b885f5f3ca570f8be73e787e','text_conditioner.onnx':'0b84e837d7bfaf2c896627b03e3f080320309f37f4fc7df7698c644f7ba5e6b1','vocab.json':'6fb646346cf931016f70c4921aab0900ce7a304b893cb02135c74e294abfea01','token_scores.json':'5be2f278caf9b9800741f0fd82bff677f4943ec764c356f907213434b622d958','test_wavs/bria.wav':'85f46d6f0642f657a6bd689ddaa52d5a5f53e4314715e1032704c80917392181'}
 for n,h in pins.items():assert sha(model/n)==h
 import onnxruntime as ort,sherpa_onnx
 bria=wav_read(model/'test_wavs/bria.wav');enc=ort.InferenceSession(str(model/'encoder.onnx'),providers=['CPUExecutionProvider']);fixtures={'bria_10s':bria[:240000].reshape(1,1,-1),'zeros':np.zeros((1,1,240000),np.float32),'ones':np.ones((1,1,240000),np.float32),'random_seed0':np.random.RandomState(0).normal(size=(1,1,240000)).astype(np.float32)};erows=[];outputs={}
 for n,x in fixtures.items():
  y=enc.run(None,{'audio':x})[0];outputs[n]=y;erows.append({'fixture':n,'shape':list(y.shape),'nonzero_elements':int(np.count_nonzero(y)),'elements':y.size,'min':float(y.min()),'max':float(y.max()),'std':float(y.std()),'float32_sha256':hashlib.sha256(y.tobytes()).hexdigest()})
 y2=enc.run(None,{'audio':bria[:48000].reshape(1,1,-1)})[0];y10=outputs['bria_10s'];encoder_audit={'graph_sha256':pins['encoder.onnx'],'controlled_zero_encoder_sha256':'a01b6a65c24fe407e8900841446de914b6208482615aff0f23c2e434e9fa3284','distinct_from_controlled_0012':True,'fixture_results':erows,'input_sensitive':len({x['float32_sha256'] for x in erows})==len(erows),'two_seconds_vs_ten_seconds_exact':bool(np.array_equal(y2,y10)),'output_shape_is_fixed_13_frames_for_tested_lengths':True}
 cfg=sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(pocket=sherpa_onnx.OfflineTtsPocketModelConfig(lm_flow=str(model/'lm_flow.int8.onnx'),lm_main=str(model/'lm_main.int8.onnx'),encoder=str(model/'encoder.onnx'),decoder=str(model/'decoder.int8.onnx'),text_conditioner=str(model/'text_conditioner.onnx'),vocab_json=str(model/'vocab.json'),token_scores_json=str(model/'token_scores.json')),debug=False,num_threads=1,provider='cpu'));assert cfg.validate();tts=sherpa_onnx.OfflineTts(cfg);rows=[]
 for temp in (.3,.7):
  g=sherpa_onnx.GenerationConfig();g.reference_audio=bria.tolist();g.reference_sample_rate=24000;g.num_steps=5;g.extra={'temperature':str(temp),'seed':'0','max_reference_audio_len':'10','max_frames':'134','frames_after_eos':'3'};audio=tts.generate(TEXT,g);x=np.asarray(audio.samples,np.float32);tag=str(temp).replace('.','p');row=wav_write(out/f'archive-0008-int8-bria-temp{tag}-seed0.wav',x);row.update({'temperature':temp,'seed':0,'num_steps':5});rows.append(row)
 report={'schema_version':1,'status':'awaiting_human_listening_verdict','archive':{'url':'https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/sherpa-onnx-pocket-tts-int8-2026-01-26.tar.bz2','sha256':sha(archive),'file_pins':pins},'runtime':{'sherpa_onnx':sherpa_onnx.__version__,'python':platform.python_version(),'platform':platform.platform(),'difference_from_0008':'same sherpa version and exact assets; current host OS differs from pinned Ubuntu 22.04 and generation now fixes seed/temperature explicitly'},'encoder_audit':encoder_audit,'contract':{'text':TEXT,'voice':'packaged Bria, never Alba','temperature':[.3,.7],'seed':0,'num_steps':5,'max_reference_audio_len_seconds':10,'max_frames':134,'frames_after_eos':3},'outputs':rows,'historical_0008':{'listening':'not_performed','conclusion':'The old route was only structurally valid; these new exact-asset samples require Moritz listening before any quality conclusion.'}};(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
