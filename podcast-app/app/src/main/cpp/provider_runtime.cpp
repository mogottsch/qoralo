#include <jni.h>
#include <algorithm>
#include <array>
#include <cstdlib>
#include <dlfcn.h>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <memory>
#include <sstream>
#include <sys/resource.h>
#include <string>
#include <unordered_map>
#include "onnxruntime_cxx_api.h"
#include "provider_math.h"
#include "tensor_validation.h"

namespace {
namespace fs = std::filesystem;
using namespace provider;
void error(JNIEnv* env, const char* text) { auto type=env->FindClass("java/lang/RuntimeException"); if(type) env->ThrowNew(type,text); }
std::string string(JNIEnv* env,jstring value) {
  if(!value) throw std::runtime_error("Missing provider argument");
  auto p=env->GetStringUTFChars(value,nullptr); if(!p) throw std::runtime_error("Provider string unavailable");
  std::string result(p);env->ReleaseStringUTFChars(value,p);return result;
}
std::string library_dir() {
  Dl_info info{}; if(!dladdr(reinterpret_cast<void*>(&library_dir),&info)||!info.dli_fname) throw std::runtime_error("Cannot locate provider runtime library");
  return fs::path(info.dli_fname).parent_path().string();
}
template<class T> std::vector<T> read(const fs::path& path,size_t n) {
  std::ifstream in(path,std::ios::binary|std::ios::ate);
  if(!in||in.tellg()!=std::streamoff(n*sizeof(T))) throw std::runtime_error("Invalid provider asset extent");
  in.seekg(0);std::vector<T> out(n);in.read(reinterpret_cast<char*>(out.data()),n*sizeof(T));
  if(!in) throw std::runtime_error("Provider asset read failed");return out;
}
struct Abi { const char* name; std::vector<int64_t> shape; ONNXTensorElementDataType type=ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT; };
void abi(Ort::Session& session,std::initializer_list<Abi> inputs,const Abi& output) {
  if(session.GetInputCount()!=inputs.size()||session.GetOutputCount()!=1) throw std::runtime_error("Provider context ABI count mismatch");
  Ort::AllocatorWithDefaultOptions allocator;size_t i=0;
  for(const auto& value:inputs) {
    auto name=session.GetInputNameAllocated(i,allocator);auto type=session.GetInputTypeInfo(i);auto shape=type.GetTensorTypeAndShapeInfo();
    if(std::string(name.get())!=value.name||shape.GetShape()!=value.shape||shape.GetElementType()!=value.type) throw std::runtime_error("Provider context input ABI mismatch");++i;
  }
  auto name=session.GetOutputNameAllocated(0,allocator);auto type=session.GetOutputTypeInfo(0);auto shape=type.GetTensorTypeAndShapeInfo();
  if(std::string(name.get())!=output.name||shape.GetShape()!=output.shape||shape.GetElementType()!=output.type) throw std::runtime_error("Provider context output ABI mismatch");
}
struct Engine {
  Ort::Env env{ORT_LOGGING_LEVEL_WARNING,"podcast-provider-qnn"};
  std::unique_ptr<Ort::Session> duration,text,vector,vocoder;
  std::vector<float> dp,ttl;Gaussian gaussian;bool started=false;int32_t max_id=0;
  explicit Engine(const std::string& root) {
    if(std::string(OrtGetApiBase()->GetVersionString())!="1.27.1") throw std::runtime_error("Provider ORT version mismatch");
    const auto native=library_dir();setenv("ADSP_LIBRARY_PATH",native.c_str(),1);
    const auto indexer=read<int32_t>(fs::path(root)/"assets/unicode-indexer.i32",65536);max_id=*std::max_element(indexer.begin(),indexer.end());
    const auto voice_path=fs::path(root)/"assets/voice.bin";
    std::ifstream voice(voice_path,std::ios::binary|std::ios::ate);
    if(!voice||voice.tellg()!=std::streamoff(6*sizeof(int64_t)+(12800+128)*sizeof(float))) throw std::runtime_error("Provider voice extent mismatch");
    voice.seekg(0);std::array<int64_t,6> dims{};voice.read(reinterpret_cast<char*>(dims.data()),sizeof(dims));
    if(dims!=std::array<int64_t,6>{1,50,256,1,8,16}) throw std::runtime_error("Provider voice shape mismatch");
    ttl.resize(12800);dp.resize(128);voice.read(reinterpret_cast<char*>(ttl.data()),ttl.size()*4);voice.read(reinterpret_cast<char*>(dp.data()),dp.size()*4);
    if(!voice) throw std::runtime_error("Provider voice read failed");RequireAllFinite(ttl,"provider style");RequireAllFinite(dp,"provider duration style");
    auto create=[&](const char* component) {
      const auto descriptor=(fs::path(root)/"contexts"/(std::string(component)+"-context.onnx")).string();
      Ort::SessionOptions o;o.SetIntraOpNumThreads(1);o.SetInterOpNumThreads(1);o.SetExecutionMode(ExecutionMode::ORT_SEQUENTIAL);
      o.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);o.DisableCpuMemArena();o.DisableMemPattern();
      o.AddConfigEntry("session.disable_cpu_ep_fallback","1");o.AddConfigEntry("ep.context_file_path",descriptor.c_str());
      std::unordered_map<std::string,std::string> qnn={{"backend_path",native+"/libQnnHtp.so"},{"offload_graph_io_quantization","0"},{"htp_performance_mode","burst"},{"soc_model","43"}};
      o.AppendExecutionProvider("QNN",qnn);return std::make_unique<Ort::Session>(env,descriptor.c_str(),o);
    };
    duration=create("duration");text=create("text");vector=create("vector");vocoder=create("vocoder");
    abi(*duration,{{"text_ids",{1,kText},ONNX_TENSOR_ELEMENT_DATA_TYPE_INT64},{"style_dp",{1,8,16}},{"text_mask",{1,1,kText}},
      {"native_text_edge_r2",{kText+1+4},ONNX_TENSOR_ELEMENT_DATA_TYPE_INT32}},{"duration",{1}});
    abi(*text,{{"text_ids",{1,kText},ONNX_TENSOR_ELEMENT_DATA_TYPE_INT64},{"style_ttl",{1,50,256}},{"text_mask",{1,1,kText}},
      {"native_text_edge_r2",{kText+4},ONNX_TENSOR_ELEMENT_DATA_TYPE_INT32},{"native_text_edge_r4",{kText+8},ONNX_TENSOR_ELEMENT_DATA_TYPE_INT32},
      {"native_text_edge_r8",{kText+16},ONNX_TENSOR_ELEMENT_DATA_TYPE_INT32}},{"text_emb",{1,256,kText}});
    abi(*vector,{{"noisy_latent",{1,kChannels,kLatent}},{"text_emb",{1,256,kText}},{"style_ttl",{1,50,256}},
      {"latent_mask",{1,1,kLatent}},{"text_mask",{1,1,kText}},{"current_step",{1}},{"total_step",{1}},
      {"native_edge_indices_r2",{kLatent+4},ONNX_TENSOR_ELEMENT_DATA_TYPE_INT32},{"native_edge_indices_r4",{kLatent+8},ONNX_TENSOR_ELEMENT_DATA_TYPE_INT32},
      {"native_edge_indices_r8",{kLatent+16},ONNX_TENSOR_ELEMENT_DATA_TYPE_INT32},{"native_edge_indices_r16",{kLatent+32},ONNX_TENSOR_ELEMENT_DATA_TYPE_INT32}},
      {"denoised_latent",{1,kChannels,kLatent}});
    abi(*vocoder,{{"latent",{1,kChannels,kLatent}}},{"wav_tts",{1,kLatent*kHop}});
  }
};
template<class T> Ort::Value tensor(std::vector<T>& values,std::initializer_list<int64_t> shape,Ort::MemoryInfo& memory) {
  return Ort::Value::CreateTensor<T>(memory,values.data(),values.size(),shape.begin(),shape.size());
}
std::vector<float> run(Ort::Session& session,std::initializer_list<const char*> names,std::vector<Ort::Value>& inputs,const char* output,size_t expected) {
  auto outputs=session.Run(Ort::RunOptions{nullptr},names.begin(),inputs.data(),inputs.size(),&output,1);
  if(!outputs[0].IsTensor()) throw std::runtime_error("Provider output is not a tensor");
  auto info=outputs[0].GetTensorTypeAndShapeInfo();
  if(info.GetElementType()!=ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT||info.GetElementCount()!=expected) throw std::runtime_error("Provider output extent/type mismatch");
  auto data=outputs[0].GetTensorData<float>();std::vector<float> result(data,data+expected);RequireAllFinite(result,"provider output");return result;
}
void put16(std::ofstream& out,uint16_t x) { const char b[]={char(x),char(x>>8)};out.write(b,2); }
void put32(std::ofstream& out,uint32_t x) { const char b[]={char(x),char(x>>8),char(x>>16),char(x>>24)};out.write(b,4); }
void wave(const fs::path& path,const std::vector<float>& values,size_t frames) {
  const fs::path temp=path.string()+".provider-part";
  if(frames==0||frames>values.size()||frames>(UINT32_MAX-36)/2||fs::exists(path)||fs::exists(temp)) throw std::runtime_error("Provider WAV target/extent invalid");
  { std::ofstream out(temp,std::ios::binary);out.write("RIFF",4);put32(out,36+frames*2);out.write("WAVEfmt ",8);put32(out,16);
    put16(out,1);put16(out,1);put32(out,kRate);put32(out,kRate*2);put16(out,2);put16(out,16);out.write("data",4);put32(out,frames*2);
    for(size_t i=0;i<frames;++i) put16(out,uint16_t(pcm16(values[i])));
    out.flush();if(!out) throw std::runtime_error("Provider WAV write failed"); }
  fs::rename(temp,path);
}
std::string render(Engine& e,const std::vector<int64_t>& native_ids,const fs::path& output) {
  if(!e.started||native_ids.empty()||native_ids.size()>size_t(kText)) throw std::runtime_error("Provider chapter/segment not admitted");
  for(auto id:native_ids) if(id<0||id>e.max_id) throw std::runtime_error("Invalid provider character index");
  const auto n=int64_t(native_ids.size());const auto offset=e.gaussian.count();
  std::vector<int64_t> ids(kText,0);std::copy(native_ids.begin(),native_ids.end(),ids.begin());
  std::vector<float> mask(kText,0);std::fill_n(mask.begin(),n,1.f);auto memory=Ort::MemoryInfo::CreateCpu(OrtArenaAllocator,OrtMemTypeDefault);
  auto d_edge=edges(n+1,kText+1,2);std::vector<Ort::Value> di;
  di.push_back(tensor(ids,{1,kText},memory));di.push_back(tensor(e.dp,{1,8,16},memory));di.push_back(tensor(mask,{1,1,kText},memory));di.push_back(tensor(d_edge,{kText+5},memory));
  auto predicted=run(*e.duration,{"text_ids","style_dp","text_mask","native_text_edge_r2"},di,"duration",1);const auto size=extent(predicted[0]);
  std::array<std::vector<int32_t>,3> te={edges(n,kText,2),edges(n,kText,4),edges(n,kText,8)};
  std::vector<Ort::Value> ti;ti.push_back(tensor(ids,{1,kText},memory));ti.push_back(tensor(e.ttl,{1,50,256},memory));ti.push_back(tensor(mask,{1,1,kText},memory));
  for(size_t i=0;i<te.size();++i) ti.push_back(tensor(te[i],{int64_t(te[i].size())},memory));
  auto embedding=run(*e.text,{"text_ids","style_ttl","text_mask","native_text_edge_r2","native_text_edge_r4","native_text_edge_r8"},ti,"text_emb",256*kText);
  // Discard only artificial text-bucket positions; logical native embeddings are unchanged.
  for(int64_t c=0;c<256;++c) for(int64_t t=n;t<kText;++t) embedding[c*kText+t]=0.f;
  std::vector<float> latent(kChannels*kLatent,0.f),lmask(kLatent,0.f),total{float(kSteps)};
  std::fill_n(lmask.begin(),size.native_length,1.f);
  for(int64_t c=0;c<kChannels;++c) for(int64_t l=0;l<size.native_length;++l) latent[c*kLatent+l]=e.gaussian.next();
  std::array<std::vector<int32_t>,4> ve={edges(size.native_length,kLatent,2),edges(size.native_length,kLatent,4),edges(size.native_length,kLatent,8),edges(size.native_length,kLatent,16)};
  for(int step=0;step<kSteps;++step) {
    std::vector<float> current{float(step)};std::vector<Ort::Value> vi;
    vi.push_back(tensor(latent,{1,kChannels,kLatent},memory));vi.push_back(tensor(embedding,{1,256,kText},memory));vi.push_back(tensor(e.ttl,{1,50,256},memory));
    vi.push_back(tensor(lmask,{1,1,kLatent},memory));vi.push_back(tensor(mask,{1,1,kText},memory));vi.push_back(tensor(current,{1},memory));vi.push_back(tensor(total,{1},memory));
    for(auto& edge:ve) vi.push_back(tensor(edge,{int64_t(edge.size())},memory));
    latent=run(*e.vector,{"noisy_latent","text_emb","style_ttl","latent_mask","text_mask","current_step","total_step", "native_edge_indices_r2","native_edge_indices_r4","native_edge_indices_r8","native_edge_indices_r16"},vi,"denoised_latent",kChannels*kLatent);
    for(int64_t c=0;c<kChannels;++c) for(int64_t l=size.native_length;l<kLatent;++l) if(latent[c*kLatent+l]!=0.f) throw std::runtime_error("Nonzero inactive provider latent; no repair");
  }
  std::vector<Ort::Value> vi;vi.push_back(tensor(latent,{1,kChannels,kLatent},memory));auto samples=run(*e.vocoder,{"latent"},vi,"wav_tts",kLatent*kHop);
  const auto frames=size.native_length*kHop;wave(output,samples,size_t(frames));
  rusage usage{};const long peak=getrusage(RUSAGE_SELF,&usage)==0?usage.ru_maxrss:-1;
  std::ostringstream result;result<<std::setprecision(12)<<"{\"nativeTextLength\":"<<n<<",\"nativeLatentLength\":"<<size.native_length
    <<",\"rawDuration\":"<<predicted[0]<<",\"speedAdjustedDuration\":"<<size.duration<<",\"predictedFramesNotCrop\":"<<size.predicted_frames
    <<",\"frameCount\":"<<frames<<",\"noiseOffset\":"<<offset<<",\"noiseConsumed\":"<<e.gaussian.count()-offset<<",\"processLifetimeMaxRssKiB\":"<<peak<<",\"neuralCalls\":11}";
  return result.str();
}
jlong create(JNIEnv* env,jclass,jstring root) { try { return reinterpret_cast<jlong>(new Engine(string(env,root))); } catch(const std::exception& e) {error(env,e.what());return 0;} }
void begin(JNIEnv* env,jclass,jlong handle) {auto e=reinterpret_cast<Engine*>(handle);if(!e) {error(env,"Provider engine closed");return;}e->gaussian.reset();e->started=true;}
jstring segment(JNIEnv* env,jclass,jlong handle,jlongArray ids,jstring path) {
  try {auto e=reinterpret_cast<Engine*>(handle);if(!e||!ids) throw std::runtime_error("Provider engine/input unavailable");
    const auto n=env->GetArrayLength(ids);if(n<1||n>kText) throw std::runtime_error("Provider input extent invalid");
    std::vector<jlong> incoming(n);env->GetLongArrayRegion(ids,0,n,incoming.data());if(env->ExceptionCheck()) return nullptr;
    const auto result=render(*e,std::vector<int64_t>(incoming.begin(),incoming.end()),string(env,path));return env->NewStringUTF(result.c_str());
  } catch(const std::exception& e) {error(env,e.what());return nullptr;}
}
void close(JNIEnv*,jclass,jlong handle) {delete reinterpret_cast<Engine*>(handle);}
jfloatArray gaussian_probe(JNIEnv* env,jclass,jint count) {
  if(count<1||count>2160000) {error(env,"Invalid Gaussian probe extent");return nullptr;}
  Gaussian rng;rng.reset();std::vector<float> values(static_cast<size_t>(count));for(auto& v:values) v=rng.next();
  auto output=env->NewFloatArray(count);if(!output) return nullptr;env->SetFloatArrayRegion(output,0,count,values.data());return output;
}
jstring provenance(JNIEnv* env,jclass,jlong handle) {
  if(!handle) {error(env,"Provider engine closed");return nullptr;}
  return env->NewStringUTF("{\"runtimeApiVersion\":1,\"model\":\"SUPERTONIC_3_PROVIDER_PIPELINE\",\"backend\":\"QNN_HTP\",\"runtimeVersion\":\"ONNX Runtime 1.27.1 / QAIRT 2.49.0.260730\",\"cpuFallbackEnabled\":false,\"readyComponents\":[\"duration_context\",\"text_context\",\"vector_context\",\"vocoder_context\",\"htp\",\"text_length=320\",\"latent_length=512\",\"latent_channels=144\",\"diffusion_steps=8\",\"sample_rate_hz=44100\",\"channel_count=1\",\"pcm_bits=16\",\"native_text_edges\",\"native_latent_edges\",\"numpy_legacy_rng\"]}");
}
}
bool RegisterProviderNatives(JNIEnv* env) {
  auto type=env->FindClass("dev/qoralo/podcast/runtime/ProviderNative");if(!type) return false;
  JNINativeMethod methods[]={
    {const_cast<char*>("create"),const_cast<char*>("(Ljava/lang/String;)J"),reinterpret_cast<void*>(create)},
    {const_cast<char*>("beginChapter"),const_cast<char*>("(J)V"),reinterpret_cast<void*>(begin)},
    {const_cast<char*>("renderSegment"),const_cast<char*>("(J[JLjava/lang/String;)Ljava/lang/String;"),reinterpret_cast<void*>(segment)},
    {const_cast<char*>("destroy"),const_cast<char*>("(J)V"),reinterpret_cast<void*>(close)},
    {const_cast<char*>("provenance"),const_cast<char*>("(J)Ljava/lang/String;"),reinterpret_cast<void*>(provenance)},
    {const_cast<char*>("gaussianProbe"),const_cast<char*>("(I)[F"),reinterpret_cast<void*>(gaussian_probe)}};
  return env->RegisterNatives(type,methods,6)==JNI_OK;
}
