// Fresh TEXT-only external-context constructor/close; zero neural Run APIs.
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <string>
#include <sys/resource.h>
#include <unistd.h>
#include <unordered_map>
#include "onnxruntime_cxx_api.h"
namespace fs=std::filesystem;
using Clock=std::chrono::steady_clock;
void memory(const char* label) {
  std::ifstream stream("/proc/self/status");std::string line;
  std::cerr<<"DIAGNOSTIC_MEMORY "<<label<<"\n";
  while(std::getline(stream,line))
    if(line.rfind("Vm",0)==0||line.rfind("Rss",0)==0)std::cerr<<line<<"\n";
  std::cerr<<std::flush;
}
int main(int argc,char**argv) {
  if(argc!=3)return 90;
  rlimit limit{5ULL*1024*1024*1024,5ULL*1024*1024*1024};
  if(setrlimit(RLIMIT_AS,&limit))return 91;
  alarm(180);
  const fs::path descriptor=argv[1],backend=argv[2];
  if(descriptor.filename()!="text-context.onnx"||fs::exists(descriptor.parent_path()/"duration-context.onnx"))return 92;
  memory("before_environment");
  auto before=Clock::now();bool constructed=false;
  try {
    Ort::Env env(ORT_LOGGING_LEVEL_VERBOSE,"text-load-only");
    Ort::SessionOptions options;
    options.SetLogSeverityLevel(0);
    Ort::ThrowOnError(Ort::GetApi().SetSessionLogVerbosityLevel(options,1));
    options.SetIntraOpNumThreads(1);options.SetInterOpNumThreads(1);
    options.SetExecutionMode(ExecutionMode::ORT_SEQUENTIAL);
    options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
    options.DisableCpuMemArena();options.DisableMemPattern();
    options.AddConfigEntry("session.disable_cpu_ep_fallback","1");
    options.AddConfigEntry("ep.context_file_path",descriptor.c_str());
    std::unordered_map<std::string,std::string> provider={{"backend_path",backend.string()},
      {"offload_graph_io_quantization","0"},{"htp_performance_mode","burst"},{"soc_model","43"}};
    options.AppendExecutionProvider("QNN",provider);
    memory("before_text_constructor");
    before=Clock::now();
    auto session=std::make_unique<Ort::Session>(env,descriptor.c_str(),options);
    const auto seconds=std::chrono::duration<double>(Clock::now()-before).count();constructed=true;
    memory("after_text_constructor");
    if(session->GetInputCount()!=3||session->GetOutputCount()!=1)throw std::runtime_error("wrong text ABI count");
    const auto shape=session->GetOutputTypeInfo(0).GetTensorTypeAndShapeInfo().GetShape();
    if(shape!=std::vector<int64_t>{1,256,3200})throw std::runtime_error("wrong text output ABI");
    session.reset();memory("after_text_close");
    std::cout<<"{\"status\":\"text_context_loaded_and_closed\",\"constructor_seconds\":"<<seconds
      <<",\"constructor_calls\":1,\"Run_calls\":0,\"profiling\":false,\"fallback_disabled\":true,\"DP_context_present\":false}"<<std::endl;
    return 0;
  } catch(const std::exception& error) {
    memory("constructor_error");
    std::cerr<<"DIAGNOSTIC_ERROR "<<error.what()<<std::endl;
    std::cout<<"{\"status\":\"text_context_load_failed\",\"constructor_completed\":"<<(constructed?"true":"false")
      <<",\"elapsed_seconds\":"<<std::chrono::duration<double>(Clock::now()-before).count()
      <<",\"constructor_calls\":1,\"Run_calls\":0,\"profiling\":false,\"fallback_disabled\":true,\"DP_context_present\":false}"<<std::endl;
    return 2;
  }
}
