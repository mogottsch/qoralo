// Deterministic Android CPU benchmark for the controlled FP Pocket ONNX split.
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "sherpa-onnx/c-api/c-api.h"

static double now_s(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec / 1e9; }
static long vm_hwm_kb(void) {
  FILE *f=fopen("/proc/self/status","r"); if(!f) return -1; char line[256]; long v=-1;
  while(fgets(line,sizeof(line),f)) if(sscanf(line,"VmHWM: %ld kB",&v)==1) break;
  fclose(f); return v;
}
static void path(char *out,size_t n,const char *root,const char *name){ if(snprintf(out,n,"%s/%s",root,name)>=(int)n){fprintf(stderr,"path too long\n");exit(2);} }
int main(int argc,char **argv){
  if(argc!=3){fprintf(stderr,"usage: %s MODEL_DIR OUTPUT_DIR\n",argv[0]);return 2;}
  const char *root=argv[1],*outdir=argv[2];
  const char *text="Pocket TTS runs entirely on this Android phone using the original floating point model.";
  char lm_flow[1024],lm_main[1024],enc[1024],dec[1024],tc[1024],vocab[1024],scores[1024],ref[1024];
  path(lm_flow,sizeof lm_flow,root,"lm_flow.onnx"); path(lm_main,sizeof lm_main,root,"lm_main.onnx");
  path(enc,sizeof enc,root,"encoder.onnx"); path(dec,sizeof dec,root,"decoder.onnx");
  path(tc,sizeof tc,root,"text_conditioner.onnx"); path(vocab,sizeof vocab,root,"vocab.json");
  path(scores,sizeof scores,root,"token_scores.json"); path(ref,sizeof ref,root,"bria.wav");
  SherpaOnnxOfflineTtsConfig c; memset(&c,0,sizeof c);
  c.model.pocket.lm_flow=lm_flow;c.model.pocket.lm_main=lm_main;c.model.pocket.encoder=enc;
  c.model.pocket.decoder=dec;c.model.pocket.text_conditioner=tc;c.model.pocket.vocab_json=vocab;
  c.model.pocket.token_scores_json=scores;c.model.pocket.voice_embedding_cache_capacity=50;
  c.model.num_threads=1;c.model.provider="cpu";c.model.debug=0;
  double l0=now_s(); const SherpaOnnxOfflineTts *tts=SherpaOnnxCreateOfflineTts(&c); double load=now_s()-l0;
  if(!tts){fprintf(stderr,"create OfflineTts failed\n");return 3;}
  const SherpaOnnxWave *w=SherpaOnnxReadWave(ref); if(!w){fprintf(stderr,"read reference failed\n");return 4;}
  SherpaOnnxGenerationConfig g; memset(&g,0,sizeof g);g.reference_audio=w->samples;g.reference_audio_len=w->num_samples;
  g.reference_sample_rate=w->sample_rate;g.num_steps=1;g.extra="{\"max_reference_audio_len\":10.0,\"seed\":0}";
  printf("{\"runtime\":{\"sherpa\":\"%s\",\"git\":\"%s\",\"onnxruntime\":\"%s\",\"provider\":\"cpu\",\"threads\":1,\"qnn_events\":0},\"load_seconds\":%.9f,\"load_vm_hwm_kb\":%ld,\"runs\":[",SherpaOnnxGetVersionStr(),SherpaOnnxGetGitSha1(),SherpaOnnxGetOnnxruntimeVersionStr(),load,vm_hwm_kb());
  for(int i=0;i<6;i++){
    double t0=now_s(); const SherpaOnnxGeneratedAudio *a=SherpaOnnxOfflineTtsGenerateWithConfig(tts,text,&g,NULL,NULL); double elapsed=now_s()-t0;
    if(!a||!a->samples||a->n<=0){fprintf(stderr,"generation %d failed\n",i);return 5;}
    char wav[1024],name[64];snprintf(name,sizeof name,"pocket-fp-onnx-%s-%d.wav",i?"warm":"cold",i);path(wav,sizeof wav,outdir,name);
    if(!SherpaOnnxWriteWave(a->samples,a->n,a->sample_rate,wav)){fprintf(stderr,"write failed\n");return 6;}
    double dur=(double)a->n/a->sample_rate;
    printf("%s{\"index\":%d,\"state\":\"%s\",\"seconds\":%.9f,\"samples\":%d,\"sample_rate\":%d,\"audio_seconds\":%.9f,\"rtf\":%.9f,\"vm_hwm_kb\":%ld,\"inferred_ar_frames\":%d,\"inferred_flow_calls\":%d,\"wav\":\"%s\"}",i?",":"",i,i?"warm":"cold",elapsed,a->n,a->sample_rate,dur,elapsed/dur,vm_hwm_kb(),a->n/1920,a->n/1920,name);
    SherpaOnnxDestroyOfflineTtsGeneratedAudio(a); fflush(stdout);
  }
  printf("],\"voice_cache_capacity\":50,\"text\":\"Pocket TTS runs entirely on this Android phone using the original floating point model.\"}\n");
  SherpaOnnxFreeWave(w);SherpaOnnxDestroyOfflineTts(tts);return 0;
}
