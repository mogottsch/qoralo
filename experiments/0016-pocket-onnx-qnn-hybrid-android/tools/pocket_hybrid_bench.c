// Pocket TTS mixed QNN HTP + CPU benchmark. Never describe this route as full HTP.
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "sherpa-onnx/c-api/c-api.h"
static double now_s(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
static long vm_hwm_kb(void){FILE*f=fopen("/proc/self/status","r");if(!f)return-1;char l[256];long v=-1;while(fgets(l,sizeof l,f))if(sscanf(l,"VmHWM: %ld kB",&v)==1)break;fclose(f);return v;}
static void path(char*out,size_t n,const char*r,const char*x){if(snprintf(out,n,"%s/%s",r,x)>=(int)n){fprintf(stderr,"path too long\n");exit(2);}}
int main(int argc,char**argv){
 if(argc!=5){fprintf(stderr,"usage: %s MODEL_DIR OUTPUT_DIR QNN_CONFIG RUNS\n",argv[0]);return 2;}const char*root=argv[1],*outdir=argv[2];int runs=atoi(argv[4]);if(runs<1||runs>6)return 2;
 const char*text="Pocket TTS runs entirely on this Android phone using the original floating point model.";
 char flow[1024],main[1024],enc[1024],dec[1024],tc[1024],vocab[1024],scores[1024],ref[1024],provider[1200];
 path(flow,sizeof flow,root,"lm_flow.onnx");path(main,sizeof main,root,"lm_main.onnx");path(enc,sizeof enc,root,"encoder.onnx");path(dec,sizeof dec,root,"decoder.onnx");path(tc,sizeof tc,root,"text_conditioner.onnx");path(vocab,sizeof vocab,root,"vocab.json");path(scores,sizeof scores,root,"token_scores.json");path(ref,sizeof ref,root,"bria.wav");snprintf(provider,sizeof provider,"qnn:%s",argv[3]);
 SherpaOnnxOfflineTtsConfig c;memset(&c,0,sizeof c);c.model.pocket.lm_flow=flow;c.model.pocket.lm_main=main;c.model.pocket.encoder=enc;c.model.pocket.decoder=dec;c.model.pocket.text_conditioner=tc;c.model.pocket.vocab_json=vocab;c.model.pocket.token_scores_json=scores;c.model.pocket.voice_embedding_cache_capacity=50;c.model.num_threads=1;c.model.provider=provider;c.model.debug=0;
 double l0=now_s();const SherpaOnnxOfflineTts*tts=SherpaOnnxCreateOfflineTts(&c);double load=now_s()-l0;if(!tts){fprintf(stderr,"create OfflineTts failed\n");return 3;}const SherpaOnnxWave*w=SherpaOnnxReadWave(ref);if(!w){fprintf(stderr,"read reference failed\n");return 4;}
 SherpaOnnxGenerationConfig g;memset(&g,0,sizeof g);g.reference_audio=w->samples;g.reference_audio_len=w->num_samples;g.reference_sample_rate=w->sample_rate;g.num_steps=1;g.extra="{\"max_reference_audio_len\":10.0,\"seed\":0}";
 printf("{\"route\":\"mixed_qnn_htp_cpu\",\"runtime\":{\"sherpa\":\"%s\",\"git\":\"%s\",\"onnxruntime\":\"%s\",\"threads\":1,\"cpu_fallback\":true},\"load_seconds\":%.9f,\"load_vm_hwm_kb\":%ld,\"runs\":[",SherpaOnnxGetVersionStr(),SherpaOnnxGetGitSha1(),SherpaOnnxGetOnnxruntimeVersionStr(),load,vm_hwm_kb());
 for(int i=0;i<runs;i++){double t0=now_s();const SherpaOnnxGeneratedAudio*a=SherpaOnnxOfflineTtsGenerateWithConfig(tts,text,&g,NULL,NULL);double e=now_s()-t0;if(!a||!a->samples||a->n<=0){fprintf(stderr,"generation %d failed\n",i);return 5;}char wav[1024],name[80];snprintf(name,sizeof name,"pocket-hybrid-%s-%d.wav",i?"warm":"cold",i);path(wav,sizeof wav,outdir,name);if(!SherpaOnnxWriteWave(a->samples,a->n,a->sample_rate,wav))return 6;double dur=(double)a->n/a->sample_rate;printf("%s{\"index\":%d,\"state\":\"%s\",\"seconds\":%.9f,\"samples\":%d,\"sample_rate\":%d,\"audio_seconds\":%.9f,\"rtf\":%.9f,\"vm_hwm_kb\":%ld,\"inferred_ar_frames\":%d,\"inferred_flow_calls\":%d,\"wav\":\"%s\"}",i?",":"",i,i?"warm":"cold",e,a->n,a->sample_rate,dur,e/dur,vm_hwm_kb(),a->n/1920,a->n/1920,name);SherpaOnnxDestroyOfflineTtsGeneratedAudio(a);fflush(stdout);}
 printf("],\"text\":\"%s\"}\n",text);SherpaOnnxFreeWave(w);SherpaOnnxDestroyOfflineTts(tts);return 0;
}
