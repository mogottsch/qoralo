#include <chrono>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include "onnxruntime_cxx_api.h"
int main(int argc,char**argv){try{
 std::string model,backend,profile,context,soc="43";bool quiet=false;for(int i=1;i<argc;++i){std::string k=argv[i];auto take=[&](){if(++i>=argc)throw std::runtime_error("missing arg");return std::string(argv[i]);};if(k=="--model")model=take();else if(k=="--backend")backend=take();else if(k=="--profile")profile=take();else if(k=="--context-file")context=take();else if(k=="--soc-model")soc=take();else if(k=="--quiet")quiet=true;else throw std::runtime_error("unknown "+k);}if(model.empty()||backend.empty()||profile.empty()||soc.empty())throw std::runtime_error("required args");
 Ort::Env env(quiet?ORT_LOGGING_LEVEL_WARNING:ORT_LOGGING_LEVEL_INFO,"0019-host-gate");Ort::SessionOptions o;o.SetIntraOpNumThreads(1);o.SetInterOpNumThreads(1);o.SetExecutionMode(ExecutionMode::ORT_SEQUENTIAL);o.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);o.AddConfigEntry("session.disable_cpu_ep_fallback","1");if(!context.empty()){o.AddConfigEntry("ep.context_enable","1");o.AddConfigEntry("ep.context_embed_mode","0");o.AddConfigEntry("ep.context_file_path",context.c_str());}o.EnableProfiling(profile.c_str());
 const std::unordered_map<std::string,std::string> po={{"backend_path",backend},{"profiling_level","detailed"},{"profiling_file_path",profile+".qnn.csv"},{"offload_graph_io_quantization","0"},{"htp_performance_mode","burst"},{"soc_model",soc}};o.AppendExecutionProvider("QNN",po);
 auto t=std::chrono::steady_clock::now();Ort::Session s(env,model.c_str(),o);double sec=std::chrono::duration<double>(std::chrono::steady_clock::now()-t).count();Ort::AllocatorWithDefaultOptions alloc;auto path=s.EndProfilingAllocated(alloc);std::cout<<"{\"result\":\"session_created\",\"seconds\":"<<sec<<",\"profile\":\""<<path.get()<<"\"}\n";return 0;
}catch(const Ort::Exception&e){std::cerr<<"ORT error "<<e.GetOrtErrorCode()<<": "<<e.what()<<"\n";return 2;}catch(const std::exception&e){std::cerr<<"error: "<<e.what()<<"\n";return 3;}}
