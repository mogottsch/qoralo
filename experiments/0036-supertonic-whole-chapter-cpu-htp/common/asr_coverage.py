#!/usr/bin/env python3
"""One private, offline, unprompted Whisper-small pass. Read-only coverage aid.

Run on a known control WAV first; failed qualification cannot certify a chapter.
Whisper's internal windows are ASR analysis only, never TTS splitting or repair.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import sys
import time

MODEL_SHA='9ecf779972d90ba49c06d968637d720dd632c55bbf19d441fb42bf17a411e794'

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def words(text):return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?",text.lower())

def alignment(reference,hypothesis):
    r=words(reference);h=words(hypothesis)
    table=[[0]*(len(h)+1) for _ in range(len(r)+1)]
    for i in range(len(r)+1):table[i][0]=i
    for j in range(len(h)+1):table[0][j]=j
    for i in range(1,len(r)+1):
        for j in range(1,len(h)+1):table[i][j]=min(table[i-1][j]+1,table[i][j-1]+1,table[i-1][j-1]+(r[i-1]!=h[j-1]))
    i,j=len(r),len(h);matched=[];ops={'substitutions':0,'deletions':0,'insertions':0}
    while i or j:
        if i and j and table[i][j]==table[i-1][j-1]+(r[i-1]!=h[j-1]):
            if r[i-1]==h[j-1]:matched.append(i-1)
            else:ops['substitutions']+=1
            i-=1;j-=1
        elif i and table[i][j]==table[i-1][j]+1:ops['deletions']+=1;i-=1
        else:ops['insertions']+=1;j-=1
    matched=set(matched)
    bins=[]
    for b in range(10):
        lo=len(r)*b//10;hi=len(r)*(b+1)//10
        bins.append({'start_reference_word_index':lo,'end_reference_word_index':hi,'matched_reference_words':sum(k in matched for k in range(lo,hi)),'reference_words':hi-lo})
    return {'reference_words':len(r),'hypothesis_words':len(h),'word_error_rate':table[-1][-1]/max(1,len(r)),**ops,'exactly_matched_reference_words':len(matched),'reference_deciles':bins,'last_30_reference_words_matched':sum(k in matched for k in range(max(0,len(r)-30),len(r))),'first_30_reference_words_matched':sum(k in matched for k in range(min(30,len(r))))}

def main():
    p=argparse.ArgumentParser();p.add_argument('--wav',type=Path,required=True);p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--model',type=Path,default=Path.home()/'.cache/whisper/small.pt');a=p.parse_args()
    if '.local' not in a.output.parts:p.error('private .local output required')
    a.output.mkdir(parents=True,exist_ok=False);os.umask(0o077)
    start=time.monotonic();signal.alarm(900);resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
    os.environ['CUDA_VISIBLE_DEVICES']=''
    for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS'):os.environ[k]='4'
    for k in ('OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
    os.environ['NUMBA_CACHE_DIR']=str(a.output/'numba-cache')
    def audit(event,args):
        if event in ('socket.connect','socket.getaddrinfo','urllib.Request'):raise RuntimeError('ASR network forbidden')
    sys.addaudithook(audit)
    if sha(a.model)!=MODEL_SHA:raise ValueError('wrong local ASR model')
    import numpy as np
    import torch
    import whisper
    torch.set_num_threads(4);torch.set_num_interop_threads(1)
    command=['ffmpeg','-nostdin','-threads','4','-filter_threads','1','-i',str(a.wav),'-f','s16le','-ac','1','-acodec','pcm_s16le','-ar','16000','-']
    proc=subprocess.run(command,capture_output=True,timeout=60);(a.output/'ffmpeg.stderr').write_bytes(proc.stderr);proc.check_returncode()
    audio=np.frombuffer(proc.stdout,np.int16).astype(np.float32)/32768.0
    settings={'language':'en','task':'transcribe','temperature':[0.0],'beam_size':1,'fp16':False,'condition_on_previous_text':False,'initial_prompt':None,'compression_ratio_threshold':None,'logprob_threshold':None,'no_speech_threshold':None,'word_timestamps':False,'verbose':False}
    model=whisper.load_model(str(a.model),device='cpu');ready=time.monotonic()
    with torch.inference_mode():result=model.transcribe(audio,**settings)
    done=time.monotonic();(a.output/'asr-result.json').write_text(json.dumps(result,indent=2)+'\n');(a.output/'transcript.txt').write_text(result['text'].strip()+'\n')
    metrics=alignment(a.reference.read_text(),result['text'])
    metrics.update(wav_sha256=sha(a.wav),reference_sha256=sha(a.reference),model_sha256=MODEL_SHA,transcript_sha256=sha(a.output/'transcript.txt'),model='openai-whisper-small',whisper_version=whisper.__version__,torch_version=torch.__version__,device='cpu',threads=4,settings=settings,logical_asr_passes=1,load_and_prepare_seconds=ready-start,transcribe_seconds=done-ready,maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,audio_seconds=len(audio)/16000,listening_acceptance='not_reviewed',limitation='Fallible unprompted automatic transcription supports coverage only. Decile word matches are alignment-derived, not timestamps. No supplied source prompt, fallback retries, cloud calls or audio modification.')
    (a.output/'coverage.json').write_text(json.dumps(metrics,indent=2)+'\n')
    print(json.dumps({'output':str(a.output),'word_error_rate':metrics['word_error_rate'],'reference_words':metrics['reference_words'],'hypothesis_words':metrics['hypothesis_words']}))

if __name__=='__main__':main()
