#!/usr/bin/env python3
"""Configuration-only smoke using the pinned sherpa runtime; emits no timing."""
from __future__ import annotations
import argparse, hashlib, json, math, platform, struct, sys, wave
from pathlib import Path

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--model-root",type=Path,required=True); ap.add_argument("--transcript",type=Path,required=True); ap.add_argument("--output",type=Path,required=True); ap.add_argument("--report",type=Path,required=True); a=ap.parse_args()
    import sherpa_onnx
    if sherpa_onnx.__version__ != "1.13.5" or sys.version_info[:3] != (3,11,9): raise SystemExit("unpinned host runtime")
    r=a.model_root
    model=sherpa_onnx.OfflineTtsModelConfig(supertonic=sherpa_onnx.OfflineTtsSupertonicModelConfig(duration_predictor=str(r/'duration_predictor.int8.onnx'),text_encoder=str(r/'text_encoder.int8.onnx'),vector_estimator=str(r/'vector_estimator.int8.onnx'),vocoder=str(r/'vocoder.int8.onnx'),tts_json=str(r/'tts.json'),unicode_indexer=str(r/'unicode_indexer.bin'),voice_style=str(r/'voice.bin')),num_threads=1,provider='cpu',debug=False)
    cfg=sherpa_onnx.OfflineTtsConfig(model=model)
    if not cfg.validate(): raise SystemExit("sherpa configuration validation failed")
    tts=sherpa_onnx.OfflineTts(cfg); generation=sherpa_onnx.GenerationConfig(); generation.sid=5; generation.num_steps=8; generation.speed=1; generation.extra['lang']='en'
    audio=tts.generate(a.transcript.read_text(encoding='utf-8'),generation); samples=list(audio.samples)
    if not samples or audio.sample_rate <= 0 or any(not math.isfinite(x) for x in samples): raise SystemExit("invalid generated samples")
    pcm=[max(-32768,min(32767,round(x*32767))) for x in samples]; a.output.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(a.output),'wb') as out: out.setnchannels(1); out.setsampwidth(2); out.setframerate(audio.sample_rate); out.writeframes(struct.pack('<'+'h'*len(pcm),*pcm))
    with wave.open(str(a.output),'rb') as inp:
        frames=inp.readframes(inp.getnframes()); fully=len(frames)==inp.getnframes()*inp.getsampwidth()*inp.getnchannels(); frame_count=inp.getnframes(); rate=inp.getframerate()
    peak=max(abs(x) for x in samples); rms=math.sqrt(sum(x*x for x in samples)/len(samples))
    report={'schema_version':1,'evidence_type':'host_configuration_smoke_not_android_performance','deployment_evidence':False,'android_comparison_eligible':False,'result':'passed','runtime':{'sherpa_onnx':sherpa_onnx.__version__,'python':platform.python_version(),'system':platform.system(),'machine':platform.machine(),'wheels':{'sherpa_onnx':'452bb53ca6464a6809b1ea338dd869bc05ba6b7a71b4674545b594045501b853','sherpa_onnx_core':'485b20188ddf905ffbd7504ed456a05d0ff84d10c592a16c0adb7d69bb845f82'}},'configuration':{'provider':'cpu','num_threads':1,'language':'en','speaker_id':5,'voice':'M1','transcript_sha256':sha(a.transcript)},'audio':{'artifact_sha256':sha(a.output),'sample_rate_hz':rate,'frame_count':frame_count,'duration_seconds':frame_count/rate,'fully_decoded':fully,'non_silent':rms>1e-5,'finite':True,'peak_abs':peak,'rms':rms}}
    if not fully or not report['audio']['non_silent']: raise SystemExit("independent WAV validation failed")
    a.report.write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__': main()
