// Single whole-chapter Android QNN/HTP render, all four logical stages fail-closed.
// TEXT is partitioned by network depth into three fullT3200 contexts, not text chunks.
// Original operators/weights preserved; original-vs-composed CPU output bitwise equal.
// Forked0036 CPU runner237bb31dfe92be49a8336e8e3abfdad2a9a90024848cd03f4e2afde22458aa53
// to share exact tensor layout, natural duration/mask, step and PCM semantics.
// External QNN EPContexts only; profiling deliberately OFF (old6006 failure).
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <sys/resource.h>
#include <vector>
#include <unordered_map>
#include <unistd.h>
#include "onnxruntime_cxx_api.h"
namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;
constexpr int64_t T = 3200, C = 144, SR = 44100, HOP = 3072;
double elapsed(Clock::time_point t) { return std::chrono::duration<double>(Clock::now()-t).count(); }
long rss() { rusage r{}; return getrusage(RUSAGE_SELF,&r)==0?r.ru_maxrss:-1; }
template<class V> std::vector<V> read(const fs::path &p, size_t n) {
  std::ifstream f(p,std::ios::binary|std::ios::ate);
  if (!f || f.tellg()!=std::streamoff(n*sizeof(V))) throw std::runtime_error("input size mismatch: "+p.filename().string());
  f.seekg(0); std::vector<V> v(n); f.read(reinterpret_cast<char*>(v.data()),n*sizeof(V));
  if(!f) throw std::runtime_error("short input"); return v;
}
template<class V> void raw(const fs::path &p,const std::vector<V>&v) {
  std::ofstream f(p,std::ios::binary); f.write(reinterpret_cast<const char*>(v.data()),v.size()*sizeof(V));
  if(!f) throw std::runtime_error("output failure");
}
template<class V> Ort::Value tensor(std::vector<V>&v,std::initializer_list<int64_t> shape,Ort::MemoryInfo&m) {
  return Ort::Value::CreateTensor<V>(m,v.data(),v.size(),shape.begin(),shape.size());
}
std::vector<float> run(Ort::Session&s,std::initializer_list<const char*> names,std::vector<Ort::Value>&in,const char*out,size_t n) {
  auto v=s.Run(Ort::RunOptions{nullptr},names.begin(),in.data(),in.size(),&out,1);
  if(!v[0].IsTensor()||v[0].GetTensorTypeAndShapeInfo().GetElementCount()!=n) throw std::runtime_error("output shape mismatch");
  auto p=v[0].GetTensorData<float>(); std::vector<float> r(p,p+n);
  if(!std::all_of(r.begin(),r.end(),[](float x){return std::isfinite(x);})) throw std::runtime_error("nonfinite output");
  return r;
}
void u16(std::ofstream&f,uint16_t v){char b[]={char(v),char(v>>8)};f.write(b,2);}
void u32(std::ofstream&f,uint32_t v){char b[]={char(v),char(v>>8),char(v>>16),char(v>>24)};f.write(b,4);}
void wav(const fs::path&p,const std::vector<float>&v,size_t frames){
  if(frames==0||frames>v.size()||frames>(UINT32_MAX-36)/2) throw std::runtime_error("invalid natural wave frames");
  std::ofstream f(p,std::ios::binary);f.write("RIFF",4);u32(f,36+frames*2);f.write("WAVEfmt ",8);u32(f,16);u16(f,1);u16(f,1);u32(f,SR);u32(f,SR*2);u16(f,2);u16(f,16);f.write("data",4);u32(f,frames*2);
  for(size_t i=0;i<frames;++i)u16(f,uint16_t(int16_t(std::lround(std::clamp(v[i],-1.f,1.f)*32767.f))));
  if(!f)throw std::runtime_error("wav write failure");
}
int main(int argc,char**argv){
  try{
    // Only one full render. Each stage uses its own HTP prediction/features.
    if(argc!=6)throw std::runtime_error("usage: runner CONTEXTS BUNDLE OUTPUT L BACKEND");
    fs::path models=argv[1],bundle=argv[2],out=argv[3];std::string action="full",backend=argv[5];int64_t L=std::stoll(argv[4]);int threads=1;
    if(L<1||L>10000||!fs::is_regular_file(backend))throw std::runtime_error("invalid run contract");
    // Preserve user phone memory: fail rather than grow without limit. Host guard also samples RSS.
    rlimit limit{5ULL*1024*1024*1024,5ULL*1024*1024*1024};
    if(setrlimit(RLIMIT_AS,&limit))throw std::runtime_error("cannot apply 5GiB AS bound");
    alarm(1800);
    if(!fs::create_directory(out))throw std::runtime_error("output directory must be fresh");
    std::cout<<std::setprecision(10);
    auto ids=read<int64_t>(bundle/"text_ids.i64",T);
    auto mask=read<float>(bundle/"text_mask.f32",T),dp=read<float>(bundle/"style_dp.f32",128),ttl=read<float>(bundle/"style_ttl.f32",12800);
    for(int i=0;i<T;++i) if(mask[i]!=(i<3167?1.f:0.f)||(i>=3167&&ids[i]!=0))throw std::runtime_error("text padding contract mismatch");
    Ort::Env env(ORT_LOGGING_LEVEL_WARNING,"chapter-htp");
    auto memory=Ort::MemoryInfo::CreateCpu(OrtArenaAllocator,OrtMemTypeDefault);
    std::vector<double> setups(6,0),times(6,0);std::vector<std::string> profiles;
    auto create=[&](int index,const std::string&name){
      Ort::SessionOptions o;o.SetIntraOpNumThreads(threads);o.SetInterOpNumThreads(1);o.SetExecutionMode(ExecutionMode::ORT_SEQUENTIAL);o.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
      o.DisableCpuMemArena();o.DisableMemPattern();
      o.AddConfigEntry("session.disable_cpu_ep_fallback","1");
      const auto descriptor=models/(name+"-context.onnx");
      o.AddConfigEntry("ep.context_file_path",descriptor.c_str());
      std::unordered_map<std::string,std::string> provider={{"backend_path",backend},{"offload_graph_io_quantization","0"},{"htp_performance_mode","burst"},{"soc_model","43"}};
      o.AppendExecutionProvider("QNN",provider);
      auto start=Clock::now();auto s=std::make_unique<Ort::Session>(env,descriptor.c_str(),o);setups[index]=elapsed(start);
      if(s->GetInputCount()==0||s->GetOutputCount()!=(name=="text3_a"?2u:1u))throw std::runtime_error("context ABI differs");
      std::cerr<<"session_ready "<<name<<" seconds="<<setups[index]<<" maxrss_kib="<<rss()<<std::endl;return s;
    };
    auto close=[&](std::unique_ptr<Ort::Session>&s){s.reset();};
    auto pipeline_start=Clock::now();
    auto duration=create(0,"duration");auto start=Clock::now();std::vector<Ort::Value> din;
    din.push_back(tensor(ids,{1,T},memory));din.push_back(tensor(dp,{1,8,16},memory));din.push_back(tensor(mask,{1,1,T},memory));
    auto predicted=run(*duration,{"text_ids","style_dp","text_mask"},din,"duration",1);times[0]=elapsed(start);
    if(predicted[0]<=0||predicted[0]>600)throw std::runtime_error("duration outside bounded 0..600s");
    int64_t frames=int64_t(std::floor(predicted[0]*float(SR)));int64_t active=(frames+HOP-1)/HOP;
    raw(out/"duration.f32",predicted);close(duration);
    std::cerr<<"duration_complete predicted_seconds="<<predicted[0]<<" frames="<<frames<<" active_L="<<active<<" seconds="<<times[0]<<std::endl;
    if(action=="full"){
      if(active<=0||active>L)throw std::runtime_error("natural duration exceeds common L; no crop/override");
      constexpr const char* cut="/text_encoder/attn_encoder/norm_layers_2.0/Transpose_1_output_0";
      constexpr const char* middle_cut="/text_encoder/attn_encoder/norm_layers_2.2/Transpose_1_output_0";
      constexpr const char* residual_name="/text_encoder/convnext/convnext.5/Mul_3_output_0";
      auto text_a=create(1,"text3_a");start=Clock::now();std::vector<Ort::Value> ain;
      ain.push_back(tensor(ids,{1,T},memory));ain.push_back(tensor(mask,{1,1,T},memory));
      const char* anames[]={"text_ids","text_mask"};const char* aoutputs[]={cut,residual_name};
      auto av=text_a->Run(Ort::RunOptions{nullptr},anames,ain.data(),2,aoutputs,2);
      std::vector<float> middle,residual;
      for(size_t index=0;index<2;++index){
        if(!av[index].IsTensor()||av[index].GetTensorTypeAndShapeInfo().GetShape()!=std::vector<int64_t>{1,256,T})throw std::runtime_error("text boundary shape differs");
        const float* data=av[index].GetTensorData<float>();auto& target=index==0?middle:residual;target.assign(data,data+256*T);
        if(!std::all_of(target.begin(),target.end(),[](float value){return std::isfinite(value);}))throw std::runtime_error("nonfinite text boundary");
      }
      times[1]=elapsed(start);av.clear();close(text_a);
      auto text_b=create(2,"text3_b");start=Clock::now();std::vector<Ort::Value> bin;
      bin.push_back(tensor(middle,{1,256,T},memory));bin.push_back(tensor(mask,{1,1,T},memory));
      auto next_middle=run(*text_b,{cut,"text_mask"},bin,middle_cut,256*T);times[2]=elapsed(start);close(text_b);bin.clear();middle=std::move(next_middle);
      auto text_c=create(3,"text3_c");start=Clock::now();std::vector<Ort::Value> cin;
      cin.push_back(tensor(middle,{1,256,T},memory));cin.push_back(tensor(residual,{1,256,T},memory));
      cin.push_back(tensor(ttl,{1,50,256},memory));cin.push_back(tensor(mask,{1,1,T},memory));
      auto emb=run(*text_c,{middle_cut,residual_name,"style_ttl","text_mask"},cin,"text_emb",256*T);times[3]=elapsed(start);close(text_c);
      cin.clear();std::vector<float>().swap(middle);std::vector<float>().swap(residual);
      auto latent=read<float>(bundle/"noise.f32",C*L);auto current=read<float>(bundle/"current_step.f32",5),total=read<float>(bundle/"total_step.f32",1);std::vector<float> lmask(L,0);
      for(int64_t pos=0;pos<L;++pos){if(pos<active)lmask[pos]=1;else for(int64_t c=0;c<C;++c)latent[c*L+pos]=0;}
      if(total[0]!=5)throw std::runtime_error("step contract mismatch");raw(out/"latent_mask.f32",lmask);raw(out/"initial_latent.f32",latent);
      auto vector=create(4,"vector");start=Clock::now();
      for(int step=0;step<5;++step){
        if(current[step]!=float(step))throw std::runtime_error("timestep mismatch");std::vector<float> now{current[step]};std::vector<Ort::Value> vin;
        vin.push_back(tensor(latent,{1,C,L},memory));vin.push_back(tensor(emb,{1,256,T},memory));vin.push_back(tensor(ttl,{1,50,256},memory));vin.push_back(tensor(lmask,{1,1,L},memory));vin.push_back(tensor(mask,{1,1,T},memory));vin.push_back(tensor(now,{1},memory));vin.push_back(tensor(total,{1},memory));
        latent=run(*vector,{"noisy_latent","text_emb","style_ttl","latent_mask","text_mask","current_step","total_step"},vin,"denoised_latent",C*L);
        std::cerr<<"vector_step_complete "<<step<<" elapsed_seconds="<<elapsed(start)<<" maxrss_kib="<<rss()<<std::endl;
      }times[4]=elapsed(start);close(vector);raw(out/"final_latent.f32",latent);
      auto vocoder=create(5,"vocoder");start=Clock::now();std::vector<Ort::Value> vin;vin.push_back(tensor(latent,{1,C,L},memory));
      auto wave=run(*vocoder,{"latent"},vin,"wav_tts",L*HOP);times[5]=elapsed(start);close(vocoder);wav(out/"htp.wav",wave,frames);
    }
    double process=elapsed(pipeline_start),setup=0,render=0;for(double x:setups)setup+=x;for(double x:times)render+=x;
    std::cout<<"{\"result\":\"passed\",\"action\":\""<<action<<"\",\"runtime\":\""<<OrtGetApiBase()->GetVersionString()<<"\",\"provider\":\"QNNExecutionProvider\",\"cpu_fallback_disabled\":true,\"profiling_enabled\":false,\"threads\":"<<threads<<",\"text_extent\":"<<T<<",\"active_text_positions\":3167,\"latent_extent\":"<<L<<",\"natural_active_latent\":"<<active<<",\"predicted_duration_seconds\":"<<predicted[0]<<",\"natural_wave_frames\":"<<frames<<",\"emitted_frames\":"<<(action=="full"?frames:0)<<",\"vocoder_output_frames\":"<<(action=="full"?L*HOP:0)<<",\"setup_seconds\":"<<setup<<",\"render_stage_seconds\":"<<render<<",\"pipeline_wall_seconds\":"<<process<<",\"audio_seconds\":"<<double(frames)/SR<<",\"rtf_stage_sum\":"<<(action=="full"?render/(double(frames)/SR):0)<<",\"maxrss_kib\":"<<rss()<<",\"stage_setup_seconds\":[";
    for(int i=0;i<6;++i)std::cout<<(i?",":"")<<setups[i];std::cout<<"],\"stage_run_seconds\":[";for(int i=0;i<6;++i)std::cout<<(i?",":"")<<times[i];std::cout<<"],\"stage_names\":[\"duration\",\"text3_a\",\"text3_b\",\"text3_c\",\"vector\",\"vocoder\"],\"text_depth_partitioned\":true,\"profiles\":[";for(size_t i=0;i<profiles.size();++i)std::cout<<(i?",":"")<<"\""<<profiles[i]<<"\"";std::cout<<"]}"<<std::endl;
    return 0;
  }catch(const std::exception&e){std::cerr<<"failed: "<<e.what()<<std::endl;return 2;}
}
