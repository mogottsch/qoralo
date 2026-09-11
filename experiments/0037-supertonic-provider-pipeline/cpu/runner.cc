// Official Supertonic-py v1.3.1 segmented pipeline, neural stages on Android CPU.
// Prepared frontend tensors are exact official chunk_text -> UnicodeProcessor.
// Four original dynamic sessions created once and reused; all content stays private.
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
#include <unistd.h>
#include <vector>
#include "onnxruntime_cxx_api.h"
namespace fs=std::filesystem;
using Clock=std::chrono::steady_clock;
constexpr int64_t SR=44100,C=144,HOP=3072;
double seconds(Clock::time_point start){return std::chrono::duration<double>(Clock::now()-start).count();}
long rss(){rusage r{};return getrusage(RUSAGE_SELF,&r)==0?r.ru_maxrss:-1;}
template<class T>std::vector<T>read(const fs::path&p,size_t count){
 std::ifstream f(p,std::ios::binary|std::ios::ate);if(!f||f.tellg()!=std::streamoff(count*sizeof(T)))throw std::runtime_error("input size mismatch "+p.filename().string());f.seekg(0);std::vector<T>v(count);f.read(reinterpret_cast<char*>(v.data()),count*sizeof(T));if(!f)throw std::runtime_error("short read");return v;
}
template<class T>void raw(const fs::path&p,const std::vector<T>&v){std::ofstream f(p,std::ios::binary);f.write(reinterpret_cast<const char*>(v.data()),v.size()*sizeof(T));if(!f)throw std::runtime_error("raw output failed");}
template<class T>Ort::Value tensor(std::vector<T>&v,std::initializer_list<int64_t>shape,Ort::MemoryInfo&m){return Ort::Value::CreateTensor<T>(m,v.data(),v.size(),shape.begin(),shape.size());}
std::vector<float>run(Ort::Session&s,std::initializer_list<const char*>names,std::vector<Ort::Value>&inputs,const char*out,size_t expected){auto values=s.Run(Ort::RunOptions{nullptr},names.begin(),inputs.data(),inputs.size(),&out,1);if(!values[0].IsTensor()||values[0].GetTensorTypeAndShapeInfo().GetElementCount()!=expected)throw std::runtime_error("output shape mismatch");auto p=values[0].GetTensorData<float>();std::vector<float>v(p,p+expected);if(!std::all_of(v.begin(),v.end(),[](float x){return std::isfinite(x);}))throw std::runtime_error("nonfinite neural output");return v;}
void u16(std::ofstream&f,uint16_t n){char b[]={char(n),char(n>>8)};f.write(b,2);}void u32(std::ofstream&f,uint32_t n){char b[]={char(n),char(n>>8),char(n>>16),char(n>>24)};f.write(b,4);}
void wav(const fs::path&path,const std::vector<float>&v){
 if(v.empty()||v.size()>(UINT32_MAX-36)/2)throw std::runtime_error("invalid WAV extent");auto tmp=path.string()+".tmp";
 {std::ofstream f(tmp,std::ios::binary);f.write("RIFF",4);u32(f,36+v.size()*2);f.write("WAVEfmt ",8);u32(f,16);u16(f,1);u16(f,1);u32(f,SR);u32(f,SR*2);u16(f,2);u16(f,16);f.write("data",4);u32(f,v.size()*2);
 for(float x:v){if(!std::isfinite(x))throw std::runtime_error("nonfinite WAV sample");long q=long(std::floor(std::clamp(x,-1.f,1.f)*32768.f));u16(f,uint16_t(int16_t(std::clamp(q,-32768L,32767L))));}f.flush();if(!f)throw std::runtime_error("WAV write failure");}
 fs::rename(tmp,path); // Host sees a complete playable WAV, never partial header/payload.
}
std::string id(int i){auto x=std::to_string(i);return std::string(3-x.size(),'0')+x;}
struct Chunk{int64_t T=0,L=0,maskL=0,predicted_frames=0,emitted=0;size_t noise_offset=0;float raw_duration=0,duration=0;std::array<double,4>stage{};double wall=0,completed_from_generation=0,completed_from_entry=0;long peak=0;};
int main(int argc,char**argv){
 const auto entry=Clock::now();try{
 if(argc!=4)throw std::runtime_error("usage: runner MODELS BUNDLE OUTPUT");fs::path models=argv[1],bundle=argv[2],out=argv[3];
 rlimit limit{5ULL*1024*1024*1024,5ULL*1024*1024*1024};if(setrlimit(RLIMIT_AS,&limit))throw std::runtime_error("cannot apply5GiB AS bound");alarm(1800);
 if(!fs::create_directory(out))throw std::runtime_error("fresh output required");
 std::ifstream config(bundle/"runner-config.txt");int count=0,steps=0;float speed=0;int64_t gap=0;size_t draws=0;config>>count>>steps>>speed>>gap>>draws;
 if(!config||count!=15||steps!=8||speed!=1.05f||gap!=13230||draws!=size_t(count)*C*1000)throw std::runtime_error("frozen provider recipe mismatch");
 std::vector<int64_t>ts(count);for(auto&t:ts){config>>t;if(!config||t<=9||t>1000)throw std::runtime_error("invalid nativeT");}
 auto dp=read<float>(bundle/"style_dp.f32",128),ttl=read<float>(bundle/"style_ttl.f32",12800),stream=read<float>(bundle/"noise_stream.f32",draws),schedule=read<float>(bundle/"current_steps.f32",steps),total=read<float>(bundle/"total_steps.f32",1);
 if(total[0]!=float(steps))throw std::runtime_error("total step drift");for(int i=0;i<steps;++i)if(schedule[i]!=float(i))throw std::runtime_error("schedule drift");
 Ort::Env env(ORT_LOGGING_LEVEL_WARNING,"provider-cpu");auto mem=Ort::MemoryInfo::CreateCpu(OrtArenaAllocator,OrtMemTypeDefault);
 std::array<const char*,4>names={"duration","text","vector","vocoder"};std::array<std::unique_ptr<Ort::Session>,4>sessions;std::array<double,4>setup{};
 std::ofstream events(out/"events.jsonl");events<<std::setprecision(12);
 const auto setup_start=Clock::now();
 for(int i=0;i<4;++i){Ort::SessionOptions options;options.SetIntraOpNumThreads(4);options.SetInterOpNumThreads(1);options.SetExecutionMode(ExecutionMode::ORT_SEQUENTIAL);options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);options.EnableProfiling((out/names[i]).c_str());auto t=Clock::now();sessions[i]=std::make_unique<Ort::Session>(env,(models/(std::string(names[i])+".onnx")).c_str(),options);setup[i]=seconds(t);}
 const double setup_wall=seconds(setup_start),ready_entry=seconds(entry);const long ready_rss=rss();events<<"{\"event\":\"ready\",\"entry_seconds\":"<<ready_entry<<",\"maxrss_kib\":"<<ready_rss<<"}"<<std::endl;
 const auto generation=Clock::now();std::vector<float>assembly;std::vector<Chunk>records;size_t offset=0;
 for(int index=0;index<count;++index){const auto chunk_start=Clock::now();Chunk r;r.T=ts[index];r.noise_offset=offset;auto folder=bundle/id(index);
 auto ids=read<int64_t>(folder/"text_ids.i64",r.T);auto mask=read<float>(folder/"text_mask.f32",r.T);if(!std::all_of(mask.begin(),mask.end(),[](float x){return x==1.f;}))throw std::runtime_error("CPU native text mask must be all ones");
 auto t=Clock::now();std::vector<Ort::Value>din;din.push_back(tensor(ids,{1,r.T},mem));din.push_back(tensor(dp,{1,8,16},mem));din.push_back(tensor(mask,{1,1,r.T},mem));auto d=run(*sessions[0],{"text_ids","style_dp","text_mask"},din,"duration",1);r.stage[0]=seconds(t);r.raw_duration=d[0];r.duration=d[0]/speed;
 if(r.duration<=0||r.duration>69)throw std::runtime_error("duration exceeds original1000-position safe bound; no override");
 // Preserve NumPy2.3.5 FP32 scalar/array operation order, including +hop then -1.
 float wf=r.duration*float(SR);r.predicted_frames=int64_t(wf);float extent=wf+float(HOP);extent=extent-1.f;extent=extent/float(HOP);r.L=int32_t(extent);r.maskL=(r.predicted_frames+HOP-1)/HOP;
 if(r.L<=0||r.L>1000||r.maskL!=r.L||offset+C*r.L>stream.size())throw std::runtime_error("native latent extent/mask/stream mismatch; no repair");
 t=Clock::now();std::vector<Ort::Value>tin;tin.push_back(tensor(ids,{1,r.T},mem));tin.push_back(tensor(ttl,{1,50,256},mem));tin.push_back(tensor(mask,{1,1,r.T},mem));auto emb=run(*sessions[1],{"text_ids","style_ttl","text_mask"},tin,"text_emb",256*r.T);r.stage[1]=seconds(t);
 std::vector<float>latent(stream.begin()+offset,stream.begin()+offset+C*r.L);offset+=C*r.L;std::vector<float>lmask(r.L,1.f);raw(out/("chunk-"+id(index)+"-initial.f32"),latent);
 t=Clock::now();for(int step=0;step<steps;++step){std::vector<float>current{schedule[step]};std::vector<Ort::Value>vin;vin.push_back(tensor(latent,{1,C,r.L},mem));vin.push_back(tensor(emb,{1,256,r.T},mem));vin.push_back(tensor(ttl,{1,50,256},mem));vin.push_back(tensor(mask,{1,1,r.T},mem));vin.push_back(tensor(lmask,{1,1,r.L},mem));vin.push_back(tensor(current,{1},mem));vin.push_back(tensor(total,{1},mem));latent=run(*sessions[2],{"noisy_latent","text_emb","style_ttl","text_mask","latent_mask","current_step","total_step"},vin,"denoised_latent",C*r.L);}r.stage[2]=seconds(t);
 t=Clock::now();std::vector<Ort::Value>vin;vin.push_back(tensor(latent,{1,C,r.L},mem));auto wave=run(*sessions[3],{"latent"},vin,"wav_tts",r.L*HOP);r.stage[3]=seconds(t);r.emitted=wave.size();
 wav(out/("chunk-"+id(index)+".wav"),wave);r.completed_from_generation=seconds(generation);r.completed_from_entry=seconds(entry);r.peak=rss();
 events<<"{\"event\":\"chunk_playable\",\"index\":"<<index<<",\"entry_seconds\":"<<r.completed_from_entry<<",\"generation_seconds\":"<<r.completed_from_generation<<",\"frames\":"<<r.emitted<<",\"raw_duration\":"<<r.raw_duration<<",\"speed_adjusted_duration\":"<<r.duration<<",\"native_L\":"<<r.L<<",\"maxrss_kib\":"<<r.peak<<"}"<<std::endl;
 if(index)assembly.insert(assembly.end(),gap,0.f);assembly.insert(assembly.end(),wave.begin(),wave.end());r.wall=seconds(chunk_start);records.push_back(r);
 }
 wav(out/"chapter.wav",assembly);const double generation_wall=seconds(generation),entry_to_complete=seconds(entry);const long final_rss=rss();
 Ort::AllocatorWithDefaultOptions allocator;std::vector<std::string>profiles;for(auto&s:sessions){auto p=s->EndProfilingAllocated(allocator);profiles.emplace_back(p.get());}
 std::ofstream result(out/"result.json");result<<std::setprecision(12)<<"{\"result\":\"passed\",\"runtime\":\""<<OrtGetApiBase()->GetVersionString()<<"\",\"provider\":\"CPUExecutionProvider\",\"profiling_enabled\":true,\"intra_threads\":4,\"inter_threads\":1,\"session_count\":4,\"session_lifecycle\":\"all4resident_reused\",\"chunk_count\":"<<count<<",\"steps\":"<<steps<<",\"speed\":"<<speed<<",\"gap_frames_each\":"<<gap<<",\"total_gap_frames\":"<<(count-1)*gap<<",\"emitted_frames\":"<<assembly.size()<<",\"speech_vocoder_frames\":"<<assembly.size()-(count-1)*gap<<",\"emitted_audio_seconds\":"<<double(assembly.size())/SR<<",\"setup_seconds\":"<<setup_wall<<",\"entry_to_ready_seconds\":"<<ready_entry<<",\"first_chunk_playable_from_entry_seconds\":"<<records[0].completed_from_entry<<",\"first_chunk_playable_from_generation_seconds\":"<<records[0].completed_from_generation<<",\"generation_wall_seconds\":"<<generation_wall<<",\"entry_to_complete_seconds\":"<<entry_to_complete<<",\"rtf_including_prescribed_gaps\":"<<generation_wall/(double(assembly.size())/SR)<<",\"rtf_speech_only\":"<<generation_wall/(double(assembly.size()-(count-1)*gap)/SR)<<",\"maxrss_at_ready_kib\":"<<ready_rss<<",\"maxrss_kib\":"<<final_rss<<",\"noise_stream_draws_consumed\":"<<offset<<",\"chunks\":[";
 for(size_t i=0;i<records.size();++i){auto&r=records[i];result<<(i?",":"")<<"{\"index\":"<<i<<",\"text_extent\":"<<r.T<<",\"native_latent\":"<<r.L<<",\"raw_predicted_seconds\":"<<r.raw_duration<<",\"speed_adjusted_seconds\":"<<r.duration<<",\"predicted_frames_floor\":"<<r.predicted_frames<<",\"emitted_frames\":"<<r.emitted<<",\"noise_offset\":"<<r.noise_offset<<",\"wall_seconds\":"<<r.wall<<",\"playable_entry_seconds\":"<<r.completed_from_entry<<",\"maxrss_kib\":"<<r.peak<<",\"stage_seconds\":[";for(int j=0;j<4;++j)result<<(j?",":"")<<r.stage[j];result<<"]}";}
 result<<"],\"profiles\":[";for(size_t i=0;i<profiles.size();++i)result<<(i?",":"")<<"\""<<profiles[i]<<"\"";result<<"]}"<<std::endl;if(!result)throw std::runtime_error("result write failed");std::cout<<"complete chunks="<<count<<" frames="<<assembly.size()<<" generation_seconds="<<generation_wall<<std::endl;return 0;
 }catch(const std::exception&e){std::cerr<<"failed: "<<e.what()<<std::endl;return 2;}
}
