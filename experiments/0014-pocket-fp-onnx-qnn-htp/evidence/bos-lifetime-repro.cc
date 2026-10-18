// Host-only ownership repro. No model, Ort::Session, inference, or phone access.
// Mirrors TV() and the step-zero buffer scope in the retained original runner.
// Uses the installed host ORT 1.22.1 API only to create/read a non-owning tensor.
#define ORT_API_MANUAL_INIT
#include "onnxruntime_cxx_api.h"
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

// Same user-buffer overload as the historical runner's TV helper.
template<class T>
static Ort::Value TV(Ort::MemoryInfo& mi, std::vector<T>& v,
                     std::initializer_list<int64_t> shape) {
  std::vector<int64_t> s(shape);
  return Ort::Value::CreateTensor<T>(mi, v.data(), v.size(), s.data(), s.size());
}

int main(int argc, char** argv) {
  Ort::InitApi(OrtGetApiBase()->GetApi(22));
  std::cerr << "host_ort=" << OrtGetApiBase()->GetVersionString() << '\n';
  auto mi = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
  const bool keep_alive = argc > 1 && std::string(argv[1]) == "keep-alive";
  std::vector<float> persistent_bos;
  std::vector<Ort::Value> inputs;
  if (keep_alive) {
    persistent_bos.assign(32, std::numeric_limits<float>::quiet_NaN());
    inputs.push_back(TV(mi, persistent_bos, {1, 1, 32}));
  } else {
    std::vector<float> bos(32, std::numeric_limits<float>::quiet_NaN());
    inputs.push_back(TV(mi, bos, {1, 1, 32}));
  } // Historical bug: bos is destroyed here, before inference would consume it.
  const float* data = inputs.front().GetTensorMutableData<float>();
  // ASan diagnoses the same dangling buffer without running any neural graph.
  volatile float first = data[0];
  if (!std::isnan(first)) return 2;
  for (int i = 0; i < 32; ++i) if (!std::isnan(data[i])) return 3;
  std::cout << "PASS: all 32 BOS markers remain alive through tensor consumption\n";
}
