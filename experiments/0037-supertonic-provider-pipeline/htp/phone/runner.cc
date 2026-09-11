// Supertonic-py v1.3.1 provider segmentation/assembly; all neural stages on HTP.
// Case-specific exactT DP/text; shared T320/L512 vector and L512 causal vocoder.
// Native EDGE Gather indices and Gaussian offsets come only from OWN HTP duration.
// CPU fallback/profile OFF. No calibration, extra generation or audio repair.
#include <algorithm>
#include <array>
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
#include <unordered_map>
#include <unistd.h>
#include <vector>
#include "onnxruntime_cxx_api.h"
namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;
constexpr int64_t SR=44100, C=144, HOP=3072, TB=320, LB=512;
constexpr std::array<int,4> RADII={2,4,8,16};
constexpr std::array<int64_t,15> TS={309,213,243,153,188,298,106,212,97,239,224,236,252,229,280};

double seconds(Clock::time_point start) { return std::chrono::duration<double>(Clock::now()-start).count(); }
long rss() { rusage r{}; return getrusage(RUSAGE_SELF,&r)==0 ? r.ru_maxrss : -1; }
std::string id(int i) { auto s=std::to_string(i); return std::string(3-s.size(),'0')+s; }
std::string escaped(const std::string& s) {
  std::string out;
  for(unsigned char c:s) {
    if(c=='"' || c=='\\') { out+='\\'; out+=char(c); }
    else if(c=='\n') out+="\\n";
    else if(c=='\r') out+="\\r";
    else if(c=='\t') out+="\\t";
    else if(c>=32) out+=char(c);
  }
  return out;
}
template<class T> std::vector<T> read(const fs::path& p,size_t n) {
  std::ifstream f(p,std::ios::binary|std::ios::ate);
  if(!f || f.tellg()!=std::streamoff(n*sizeof(T))) throw std::runtime_error("input size mismatch: "+p.filename().string());
  f.seekg(0); std::vector<T> v(n); f.read(reinterpret_cast<char*>(v.data()),n*sizeof(T));
  if(!f) throw std::runtime_error("short input");
  return v;
}
template<class T> void raw(const fs::path& p,const std::vector<T>& v) {
  std::ofstream f(p,std::ios::binary); f.write(reinterpret_cast<const char*>(v.data()),v.size()*sizeof(T));
  if(!f) throw std::runtime_error("raw output failure");
}
template<class T> Ort::Value tensor(std::vector<T>& v,std::initializer_list<int64_t> shape,Ort::MemoryInfo& m) {
  return Ort::Value::CreateTensor<T>(m,v.data(),v.size(),shape.begin(),shape.size());
}
std::vector<float> run(Ort::Session& s,std::initializer_list<const char*> names,
                      std::vector<Ort::Value>& inputs,const char* out,std::initializer_list<int64_t> shape) {
  auto values=s.Run(Ort::RunOptions{nullptr},names.begin(),inputs.data(),inputs.size(),&out,1);
  if(!values[0].IsTensor()) throw std::runtime_error("non-tensor neural output");
  auto info=values[0].GetTensorTypeAndShapeInfo();
  if(info.GetElementType()!=ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT || info.GetShape()!=std::vector<int64_t>(shape))
    throw std::runtime_error("neural output ABI mismatch");
  auto p=values[0].GetTensorData<float>(); std::vector<float> result(p,p+info.GetElementCount());
  if(!std::all_of(result.begin(),result.end(),[](float x){return std::isfinite(x);}))
    throw std::runtime_error("nonfinite neural output");
  return result;
}
void u16(std::ofstream& f,uint16_t n) { char b[]={char(n),char(n>>8)}; f.write(b,2); }
void u32(std::ofstream& f,uint32_t n) { char b[]={char(n),char(n>>8),char(n>>16),char(n>>24)}; f.write(b,4); }
void wav(const fs::path& p,const std::vector<float>& v) {
  if(v.empty() || v.size()>(UINT32_MAX-36)/2) throw std::runtime_error("invalid WAV extent");
  auto temporary=p.string()+".tmp";
  {
    std::ofstream f(temporary,std::ios::binary);
    f.write("RIFF",4); u32(f,36+v.size()*2); f.write("WAVEfmt ",8); u32(f,16);
    u16(f,1); u16(f,1); u32(f,SR); u32(f,SR*2); u16(f,2); u16(f,16);
    f.write("data",4); u32(f,v.size()*2);
    for(float x:v) {
      if(!std::isfinite(x)) throw std::runtime_error("nonfinite PCM input");
      long q=long(std::floor(std::clamp(x,-1.f,1.f)*32768.f));
      u16(f,uint16_t(int16_t(std::clamp(q,-32768L,32767L))));
    }
    f.flush(); if(!f) throw std::runtime_error("WAV write failure");
  }
  fs::rename(temporary,p); // Complete/closed file boundary, not playback.
}
struct Abi { const char* name; std::vector<int64_t> shape; ONNXTensorElementDataType type=ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT; };
void check_abi(Ort::Session& s,std::initializer_list<Abi> inputs,const Abi& output) {
  if(s.GetInputCount()!=inputs.size() || s.GetOutputCount()!=1) throw std::runtime_error("context ABI count mismatch");
  Ort::AllocatorWithDefaultOptions allocator; size_t i=0;
  for(const auto& expected:inputs) {
    auto name=s.GetInputNameAllocated(i,allocator);
    auto type=s.GetInputTypeInfo(i); auto info=type.GetTensorTypeAndShapeInfo();
    if(expected.name!=std::string(name.get()) || expected.shape!=info.GetShape() || expected.type!=info.GetElementType())
      throw std::runtime_error("context input ABI mismatch");
    ++i;
  }
  auto name=s.GetOutputNameAllocated(0,allocator);
  auto type=s.GetOutputTypeInfo(0); auto info=type.GetTensorTypeAndShapeInfo();
  if(output.name!=std::string(name.get()) || output.shape!=info.GetShape() || output.type!=info.GetElementType())
    throw std::runtime_error("context output ABI mismatch");
}
struct NativeExtent { float duration; int64_t predicted_frames, length, mask_length; };
NativeExtent native_extent(float raw_duration,float speed) {
  float d=raw_duration/speed;
  if(!std::isfinite(d) || d<=0 || d>69) throw std::runtime_error("own duration exceeds native bound; no override");
  float wf=d*float(SR); int64_t frames=int64_t(wf);
  float extent=wf+float(HOP); extent=extent-1.f; extent=extent/float(HOP);
  int64_t length=int32_t(extent),mask_length=(frames+HOP-1)/HOP;
  if(length<=0 || length>LB || length!=mask_length) throw std::runtime_error("own nativeL/mask exceeds static contract; no correction");
  return {d,frames,length,mask_length};
}
std::vector<float> channel_pad(const std::vector<float>& native,int64_t channels,int64_t length,int64_t bucket) {
  if(channels<=0 || length<=0 || bucket<length || native.size()!=size_t(channels*length))
    throw std::runtime_error("invalid channel padding contract");
  std::vector<float> padded(channels*bucket,0.f);
  for(int64_t c=0;c<channels;++c) std::copy_n(native.begin()+c*length,length,padded.begin()+c*bucket);
  return padded;
}
std::array<std::vector<int32_t>,4> native_edge_indices(int64_t length) {
  if(length<=0 || length>LB) throw std::runtime_error("invalid edge nativeL");
  std::array<std::vector<int32_t>,4> edges;
  for(size_t k=0;k<RADII.size();++k) {
    int radius=RADII[k]; edges[k].resize(LB+2*radius);
    for(int64_t j=0;j<LB+2*radius;++j) edges[k][j]=int32_t(std::clamp(j-radius,int64_t(0),length-1));
  }
  return edges;
}
struct Chunk {
  int64_t T=0,L=0,maskL=0,predicted_frames=0,emitted=0;
  size_t noise_offset=0;
  float raw_duration=0,duration=0;
  std::array<double,4> stage{};
  std::array<double,2> setup{};
  double teardown=0,wall=0,wave_ready_entry=0,playable_entry=0,playable_generation=0;
  long peak=0;
};
int main(int argc,char** argv) {
  const auto entry=Clock::now(); fs::path out; bool output_created=false;
  std::string phase="arguments";
  try {
    if(argc!=5) throw std::runtime_error("usage: runner CONTEXTS BUNDLE OUTPUT BACKEND");
    fs::path models=argv[1],bundle=argv[2]; out=argv[3]; std::string backend=argv[4];
    if(!fs::is_regular_file(backend)) throw std::runtime_error("backend missing");
    rlimit limit{5ULL*1024*1024*1024,5ULL*1024*1024*1024};
    if(setrlimit(RLIMIT_AS,&limit)) throw std::runtime_error("cannot apply5GiB AS bound");
    alarm(1800);
    if(!fs::create_directory(out)) throw std::runtime_error("fresh output required");
    output_created=true;
    std::ofstream events(out/"events.jsonl"); events<<std::setprecision(12);
    phase="frozen_inputs";
    std::ifstream config(bundle/"runner-config.txt"); int count=0,steps=0; float speed=0; int64_t gap=0; size_t draws=0;
    config>>count>>steps>>speed>>gap>>draws;
    if(!config || count!=15 || steps!=8 || speed!=1.05f || gap!=13230 || draws!=size_t(count)*C*1000)
      throw std::runtime_error("frozen provider recipe mismatch");
    for(auto expected:TS) { int64_t value=0; config>>value; if(!config || value!=expected) throw std::runtime_error("nativeT freeze mismatch"); }
    auto dp=read<float>(bundle/"style_dp.f32",128),ttl=read<float>(bundle/"style_ttl.f32",12800);
    auto stream=read<float>(bundle/"noise_stream.f32",draws),schedule=read<float>(bundle/"current_steps.f32",steps);
    auto total=read<float>(bundle/"total_steps.f32",1);
    if(total[0]!=float(steps)) throw std::runtime_error("total step drift");
    for(int i=0;i<steps;++i) if(schedule[i]!=float(i)) throw std::runtime_error("schedule drift");
    Ort::Env env(ORT_LOGGING_LEVEL_WARNING,"provider-htp");
    auto memory=Ort::MemoryInfo::CreateCpu(OrtArenaAllocator,OrtMemTypeDefault);
    size_t constructors=0;
    auto create=[&](const std::string& directory,const std::string& component,double& elapsed) {
      phase="create_"+directory;
      auto descriptor=models/directory/(component+"-context.onnx");
      Ort::SessionOptions o; o.SetIntraOpNumThreads(1); o.SetInterOpNumThreads(1);
      o.SetExecutionMode(ExecutionMode::ORT_SEQUENTIAL); o.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
      o.DisableCpuMemArena(); o.DisableMemPattern();
      o.AddConfigEntry("session.disable_cpu_ep_fallback","1");
      o.AddConfigEntry("ep.context_file_path",descriptor.c_str());
      std::unordered_map<std::string,std::string> provider={{"backend_path",backend},
        {"offload_graph_io_quantization","0"},{"htp_performance_mode","burst"},{"soc_model","43"}};
      o.AppendExecutionProvider("QNN",provider);
      const auto started=Clock::now(); ++constructors;
      auto s=std::make_unique<Ort::Session>(env,descriptor.c_str(),o); elapsed=seconds(started);
      events<<"{\"event\":\"session_ready\",\"context\":\""<<directory<<"\",\"seconds\":"<<elapsed
        <<",\"entry_seconds\":"<<seconds(entry)<<",\"maxrss_kib\":"<<rss()<<"}"<<std::endl;
      return s;
    };
    const auto shared_setup_start=Clock::now(); std::array<double,2> shared_setup{};
    auto vector=create("vector","vector",shared_setup[0]);
    check_abi(*vector,{{"noisy_latent",{1,C,LB}},{"text_emb",{1,256,TB}},{"style_ttl",{1,50,256}},
      {"latent_mask",{1,1,LB}},{"text_mask",{1,1,TB}},{"current_step",{1}},{"total_step",{1}},
      {"native_edge_indices_r2",{LB+4},ONNX_TENSOR_ELEMENT_DATA_TYPE_INT32},
      {"native_edge_indices_r4",{LB+8},ONNX_TENSOR_ELEMENT_DATA_TYPE_INT32},
      {"native_edge_indices_r8",{LB+16},ONNX_TENSOR_ELEMENT_DATA_TYPE_INT32},
      {"native_edge_indices_r16",{LB+32},ONNX_TENSOR_ELEMENT_DATA_TYPE_INT32}}, {"denoised_latent",{1,C,LB}});
    auto vocoder=create("vocoder","vocoder",shared_setup[1]);
    check_abi(*vocoder,{{"latent",{1,C,LB}}},{"wav_tts",{1,LB*HOP}});
    const double shared_setup_wall=seconds(shared_setup_start),ready_entry=seconds(entry); const long ready_rss=rss();
    events<<"{\"event\":\"shared_sessions_ready\",\"entry_seconds\":"<<ready_entry<<",\"exactT_sessions_not_yet_created\":true}"<<std::endl;
    std::unique_ptr<Ort::Session> duration,text; int64_t cached_t=-1;
    std::vector<float> assembly; assembly.reserve(count*LB*HOP+(count-1)*gap);
    std::vector<Chunk> records; size_t offset=0;
    const auto generation=Clock::now();
    for(int index=0;index<count;++index) {
      const auto chunk_start=Clock::now(); Chunk r; r.T=TS[index]; r.noise_offset=offset;
      auto folder=bundle/id(index); auto ids=read<int64_t>(folder/"text_ids.i64",r.T);
      auto mask=read<float>(folder/"text_mask.f32",r.T);
      if(!std::all_of(mask.begin(),mask.end(),[](float x){return x==1.f;})) throw std::runtime_error("native text mask must be all ones");
      // Bounded cache: retain only the current exactT pair. All15 T values are
      // unique here, so retaining earlier pairs would consume RAM without reuse.
      if(cached_t!=r.T) {
        auto t=Clock::now(); text.reset(); duration.reset(); r.teardown=seconds(t);
        duration=create("duration-t"+std::to_string(r.T),"duration",r.setup[0]);
        check_abi(*duration,{{"text_ids",{1,r.T},ONNX_TENSOR_ELEMENT_DATA_TYPE_INT64},
          {"style_dp",{1,8,16}},{"text_mask",{1,1,r.T}}},{"duration",{1}});
        text=create("text-t"+std::to_string(r.T),"text",r.setup[1]);
        check_abi(*text,{{"text_ids",{1,r.T},ONNX_TENSOR_ELEMENT_DATA_TYPE_INT64},
          {"style_ttl",{1,50,256}},{"text_mask",{1,1,r.T}}},{"text_emb",{1,256,r.T}});
        cached_t=r.T;
      }
      phase="duration_chunk_"+id(index); auto t=Clock::now(); std::vector<Ort::Value> din;
      din.push_back(tensor(ids,{1,r.T},memory)); din.push_back(tensor(dp,{1,8,16},memory)); din.push_back(tensor(mask,{1,1,r.T},memory));
      auto d=run(*duration,{"text_ids","style_dp","text_mask"},din,"duration",{1}); r.stage[0]=seconds(t);
      // NumPy2.3.5 FP32 operation order; compiler FMA off. Own prediction only.
      r.raw_duration=d[0]; const auto extent=native_extent(d[0],speed);
      r.duration=extent.duration; r.predicted_frames=extent.predicted_frames;
      r.L=extent.length; r.maskL=extent.mask_length;
      if(offset+C*r.L>stream.size()) throw std::runtime_error("own noise stream exhausted; no replacement");
      phase="text_chunk_"+id(index); t=Clock::now(); std::vector<Ort::Value> tin;
      tin.push_back(tensor(ids,{1,r.T},memory)); tin.push_back(tensor(ttl,{1,50,256},memory)); tin.push_back(tensor(mask,{1,1,r.T},memory));
      auto native_emb=run(*text,{"text_ids","style_ttl","text_mask"},tin,"text_emb",{1,256,r.T}); r.stage[1]=seconds(t);
      auto emb=channel_pad(native_emb,256,r.T,TB);
      std::vector<float> tmask(TB,0.f),lmask(LB,0.f);
      std::fill_n(tmask.begin(),r.T,1.f); std::fill_n(lmask.begin(),r.L,1.f);
      std::vector<float> native_noise(stream.begin()+offset,stream.begin()+offset+C*r.L); offset+=C*r.L;
      auto latent=channel_pad(native_noise,C,r.L,LB);
      raw(out/("chunk-"+id(index)+"-initial.f32"),native_noise);
      auto edges=native_edge_indices(r.L);
      for(size_t k=0;k<RADII.size();++k)
        raw(out/("chunk-"+id(index)+"-edge-r"+std::to_string(RADII[k])+".i32"),edges[k]);
      phase="vector_chunk_"+id(index); t=Clock::now();
      for(int step=0;step<steps;++step) {
        std::vector<float> current{schedule[step]}; std::vector<Ort::Value> vin;
        vin.push_back(tensor(latent,{1,C,LB},memory)); vin.push_back(tensor(emb,{1,256,TB},memory));
        vin.push_back(tensor(ttl,{1,50,256},memory)); vin.push_back(tensor(lmask,{1,1,LB},memory));
        vin.push_back(tensor(tmask,{1,1,TB},memory)); vin.push_back(tensor(current,{1},memory)); vin.push_back(tensor(total,{1},memory));
        for(size_t k=0;k<RADII.size();++k) vin.push_back(tensor(edges[k],{LB+2*RADII[k]},memory));
        latent=run(*vector,{"noisy_latent","text_emb","style_ttl","latent_mask","text_mask","current_step","total_step",
          "native_edge_indices_r2","native_edge_indices_r4","native_edge_indices_r8","native_edge_indices_r16"},vin,"denoised_latent",{1,C,LB});
        for(int64_t c=0;c<C;++c) for(int64_t j=r.L;j<LB;++j)
          if(latent[c*LB+j]!=0.f) throw std::runtime_error("nonzero inactive latent; reject rather than repair");
      }
      r.stage[2]=seconds(t);
      phase="vocoder_chunk_"+id(index); t=Clock::now(); std::vector<Ort::Value> vin;
      vin.push_back(tensor(latent,{1,C,LB},memory)); auto wave=run(*vocoder,{"latent"},vin,"wav_tts",{1,LB*HOP}); r.stage[3]=seconds(t);
      wave.resize(r.L*HOP); // Remove ONLY artificial bucket extension, never floor(duration*SR).
      r.emitted=wave.size(); r.wave_ready_entry=seconds(entry);
      wav(out/("chunk-"+id(index)+".wav"),wave);
      r.playable_generation=seconds(generation); r.playable_entry=seconds(entry); r.peak=rss();
      events<<"{\"event\":\"chunk_playable\",\"index\":"<<index<<",\"entry_seconds\":"<<r.playable_entry
        <<",\"generation_seconds\":"<<r.playable_generation<<",\"native_wave_ready_entry_seconds\":"<<r.wave_ready_entry
        <<",\"native_L\":"<<r.L<<",\"frames\":"<<r.emitted<<",\"noise_offset\":"<<r.noise_offset<<",\"maxrss_kib\":"<<r.peak<<"}"<<std::endl;
      if(index) assembly.insert(assembly.end(),gap,0.f);
      assembly.insert(assembly.end(),wave.begin(),wave.end()); r.wall=seconds(chunk_start); records.push_back(r);
    }
    phase="chapter_assembly"; wav(out/"chapter.wav",assembly);
    const double generation_wall=seconds(generation),entry_to_complete=seconds(entry);
    events<<"{\"event\":\"chapter_playable\",\"entry_seconds\":"<<entry_to_complete<<",\"frames\":"<<assembly.size()<<"}"<<std::endl;
    double interleaved_setup=0,interleaved_teardown=0,neural_sum=0;
    for(const auto& r:records) { interleaved_setup+=r.setup[0]+r.setup[1]; interleaved_teardown+=r.teardown; for(double s:r.stage) neural_sum+=s; }
    phase="final_session_teardown"; const auto teardown_start=Clock::now();
    duration.reset(); text.reset(); vector.reset(); vocoder.reset(); const double final_teardown=seconds(teardown_start);
    const long final_rss=rss();
    const double audio=double(assembly.size())/SR,speech=double(assembly.size()-(count-1)*gap)/SR;
    const double excluding_setup=generation_wall-interleaved_setup-interleaved_teardown;
    std::ofstream result(out/"result.json"); result<<std::setprecision(12)
      <<"{\"result\":\"passed\",\"runtime\":\""<<OrtGetApiBase()->GetVersionString()<<"\",\"provider\":\"QNNExecutionProvider\","
      <<"\"cpu_fallback_disabled\":true,\"profiling_enabled\":false,\"intra_threads\":1,\"inter_threads\":1,"
      <<"\"session_lifecycle\":\"shared_vector_vocoder_reused_current_exactT_pair_cache_capacity1\",\"max_resident_sessions\":4,"
      <<"\"session_constructor_count\":"<<constructors<<",\"neural_Run_calls\":"<<count*(steps+3)<<",\"chunk_count\":"<<count
      <<",\"steps\":"<<steps<<",\"speed\":"<<speed<<",\"text_bucket\":"<<TB<<",\"latent_bucket\":"<<LB
      <<",\"native_edge_radii\":[2,4,8,16],\"gap_frames_each\":"<<gap<<",\"total_gap_frames\":"<<(count-1)*gap
      <<",\"emitted_frames\":"<<assembly.size()<<",\"speech_vocoder_frames\":"<<assembly.size()-(count-1)*gap
      <<",\"emitted_audio_seconds\":"<<audio<<",\"shared_setup_seconds\":"<<shared_setup_wall
      <<",\"interleaved_constructor_seconds\":"<<interleaved_setup<<",\"interleaved_teardown_seconds\":"<<interleaved_teardown
      <<",\"all_constructor_seconds\":"<<shared_setup[0]+shared_setup[1]+interleaved_setup
      <<",\"entry_to_shared_ready_seconds\":"<<ready_entry<<",\"first_chunk_playable_from_entry_seconds\":"<<records[0].playable_entry
      <<",\"first_chunk_playable_from_generation_seconds\":"<<records[0].playable_generation
      <<",\"first_native_wave_ready_from_entry_seconds\":"<<records[0].wave_ready_entry
      <<",\"generation_wall_including_interleaved_setup_seconds\":"<<generation_wall
      <<",\"generation_wall_excluding_interleaved_lifecycle_seconds\":"<<excluding_setup
      <<",\"neural_stage_sum_seconds\":"<<neural_sum<<",\"entry_to_complete_seconds\":"<<entry_to_complete
      <<",\"final_session_teardown_seconds\":"<<final_teardown
      <<",\"rtf_generation_including_gaps_and_interleaved_setup\":"<<generation_wall/audio
      <<",\"rtf_generation_speech_only_including_interleaved_setup\":"<<generation_wall/speech
      <<",\"rtf_excluding_session_lifecycle_including_gaps\":"<<excluding_setup/audio
      <<",\"maxrss_at_shared_ready_kib\":"<<ready_rss<<",\"maxrss_kib\":"<<final_rss
      <<",\"noise_stream_draws_consumed\":"<<offset<<",\"chunks\":[";
    for(size_t i=0;i<records.size();++i) {
      const auto& r=records[i]; result<<(i?",":"")<<"{\"index\":"<<i<<",\"text_extent\":"<<r.T<<",\"native_latent\":"<<r.L
        <<",\"raw_predicted_seconds\":"<<r.raw_duration<<",\"speed_adjusted_seconds\":"<<r.duration
        <<",\"predicted_frames_floor_not_audio_crop\":"<<r.predicted_frames<<",\"emitted_frames\":"<<r.emitted
        <<",\"noise_offset\":"<<r.noise_offset<<",\"wall_seconds\":"<<r.wall
        <<",\"native_wave_ready_entry_seconds\":"<<r.wave_ready_entry<<",\"playable_entry_seconds\":"<<r.playable_entry
        <<",\"playable_generation_seconds\":"<<r.playable_generation<<",\"maxrss_kib\":"<<r.peak
        <<",\"pair_teardown_seconds\":"<<r.teardown<<",\"pair_setup_seconds\":["<<r.setup[0]<<","<<r.setup[1]<<"],\"stage_seconds\":[";
      for(int j=0;j<4;++j) result<<(j?",":"")<<r.stage[j];
      result<<"]}";
    }
    result<<"]}"<<std::endl; if(!result) throw std::runtime_error("result write failure");
    std::cout<<"complete chunks="<<count<<" frames="<<assembly.size()<<" generation_seconds="<<generation_wall<<std::endl;
    return 0;
  } catch(const std::exception& e) {
    if(output_created) {
      std::ofstream failure(out/"failure.json");
      failure<<"{\"phase\":\""<<escaped(phase)<<"\",\"error\":\""<<escaped(e.what())<<"\",\"maxrss_kib\":"<<rss()<<"}"<<std::endl;
    }
    std::cerr<<"failed phase="<<phase<<": "<<e.what()<<std::endl; return 2;
  }
}
