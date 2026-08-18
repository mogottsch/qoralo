#!/usr/bin/env python3
"""Validate Pocket benchmark PCM16 WAVs without third-party dependencies."""
import argparse, array, hashlib, json, math, sys, wave
from pathlib import Path

p=argparse.ArgumentParser(); p.add_argument("wav", type=Path, nargs="+"); p.add_argument("--output", type=Path); a=p.parse_args()
rows=[]
for path in a.wav:
    with wave.open(str(path),"rb") as w:
        channels,width,rate,frames=w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes(); data=w.readframes(frames)
    if (channels,width,rate)!=(1,2,24000) or len(data)!=frames*2 or frames<=0: raise SystemExit(f"invalid WAV contract: {path}")
    samples=array.array("h"); samples.frombytes(data)
    if sys.byteorder!="little": samples.byteswap()
    peak=max(abs(int(x)) for x in samples); rms=math.sqrt(sum(int(x)**2 for x in samples)/len(samples))
    if peak==0 or rms<1 or peak>=32767: raise SystemExit(f"silent or clipped WAV: {path}")
    rows.append({"path":str(path.resolve()),"bytes":path.stat().st_size,"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"channels":channels,"sample_width_bytes":width,"sample_rate_hz":rate,"samples":frames,"duration_seconds":frames/rate,"peak_abs_pcm16":peak,"rms_pcm16":rms,"finite":True,"non_silent":True,"unclipped":True})
text=json.dumps({"schema_version":1,"files":rows},indent=2)+"\n"
if a.output: a.output.write_text(text)
else: print(text,end="")
