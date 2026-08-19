// Fixed-contract Kokoro ONNX Runtime CPU/QNN runner.
// Qualcomm headers or implementation code are not included.

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

#if !defined(_WIN32)
#include <sys/resource.h>
#endif

#include "onnxruntime_cxx_api.h"

namespace {

struct Args {
  std::string model;
  std::string tokens;
  std::string style;
  std::string speed;
  std::string audio_output;
  std::string duration_output;
  std::string provider = "cpu";
  std::string backend;
  std::string profile_prefix;
  std::string optimization = "disabled";
  int runs = 1;
};

Args ParseArgs(int argc, char **argv) {
  Args args;
  auto value = [&](int *index) {
    if (++(*index) >= argc) throw std::runtime_error("missing argument value");
    return std::string(argv[*index]);
  };
  for (int index = 1; index < argc; ++index) {
    const std::string key = argv[index];
    if (key == "--model") args.model = value(&index);
    else if (key == "--tokens") args.tokens = value(&index);
    else if (key == "--style") args.style = value(&index);
    else if (key == "--speed") args.speed = value(&index);
    else if (key == "--audio-output") args.audio_output = value(&index);
    else if (key == "--duration-output") args.duration_output = value(&index);
    else if (key == "--provider") args.provider = value(&index);
    else if (key == "--backend") args.backend = value(&index);
    else if (key == "--profile-prefix") args.profile_prefix = value(&index);
    else if (key == "--optimization") args.optimization = value(&index);
    else if (key == "--runs") args.runs = std::stoi(value(&index));
    else throw std::runtime_error("unknown argument: " + key);
  }
  if (args.model.empty() || args.tokens.empty() || args.style.empty() ||
      args.speed.empty() || args.audio_output.empty() ||
      args.duration_output.empty() || args.profile_prefix.empty() ||
      args.runs <= 0) {
    throw std::runtime_error("missing or invalid required argument");
  }
  if (args.provider != "cpu" && args.provider != "qnn") {
    throw std::runtime_error("provider must be cpu or qnn");
  }
  if (args.provider == "qnn" && args.backend.empty()) {
    throw std::runtime_error("QNN requires --backend");
  }
  if (args.optimization != "disabled" && args.optimization != "basic" &&
      args.optimization != "all") {
    throw std::runtime_error("optimization must be disabled, basic, or all");
  }
  return args;
}

template <typename T>
std::vector<T> Read(const std::string &path, size_t count) {
  std::ifstream stream(path, std::ios::binary | std::ios::ate);
  if (!stream) throw std::runtime_error("cannot open input: " + path);
  const auto bytes = stream.tellg();
  if (bytes < 0 || static_cast<size_t>(bytes) != count * sizeof(T)) {
    throw std::runtime_error("input byte count mismatch: " + path);
  }
  stream.seekg(0);
  std::vector<T> result(count);
  if (!stream.read(reinterpret_cast<char *>(result.data()), bytes)) {
    throw std::runtime_error("short input read: " + path);
  }
  return result;
}

template <typename T>
void Write(const std::string &path, const T *values, size_t count) {
  const auto parent = std::filesystem::path(path).parent_path();
  if (!parent.empty()) std::filesystem::create_directories(parent);
  std::ofstream stream(path, std::ios::binary | std::ios::trunc);
  if (!stream.write(reinterpret_cast<const char *>(values),
                    static_cast<std::streamsize>(count * sizeof(T)))) {
    throw std::runtime_error("output write failed: " + path);
  }
}

double Elapsed(const std::chrono::steady_clock::time_point &start) {
  return std::chrono::duration<double>(std::chrono::steady_clock::now() - start)
      .count();
}

long MaxRssKiB() {
#if defined(_WIN32)
  return -1;
#else
  struct rusage usage {};
  return getrusage(RUSAGE_SELF, &usage) == 0 ? usage.ru_maxrss : -1;
#endif
}

}  // namespace

int main(int argc, char **argv) {
  try {
    const Args args = ParseArgs(argc, argv);
    auto tokens = Read<int64_t>(args.tokens, 125);
    auto style = Read<float>(args.style, 256);
    auto speed = Read<float>(args.speed, 1);
    if (speed[0] != 1.0f) throw std::runtime_error("speed contract drift");

    Ort::Env environment(ORT_LOGGING_LEVEL_WARNING, "kokoro-qnn-0017");
    Ort::SessionOptions options;
    options.SetIntraOpNumThreads(1);
    options.SetInterOpNumThreads(1);
    options.SetExecutionMode(ExecutionMode::ORT_SEQUENTIAL);
    if (args.optimization == "disabled")
      options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_DISABLE_ALL);
    else if (args.optimization == "basic")
      options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_BASIC);
    else
      options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
    options.EnableProfiling(args.profile_prefix.c_str());
    if (args.provider == "qnn") {
      options.AddConfigEntry("session.disable_cpu_ep_fallback", "1");
      const std::unordered_map<std::string, std::string> provider_options = {
          {"backend_path", args.backend},
          {"profiling_level", "detailed"},
          {"profiling_file_path", args.profile_prefix + ".qnn.csv"},
          {"offload_graph_io_quantization", "0"},
          {"htp_performance_mode", "burst"},
          {"soc_model", "43"},
      };
      options.AppendExecutionProvider("QNN", provider_options);
    }

    const auto create_start = std::chrono::steady_clock::now();
    Ort::Session session(environment, args.model.c_str(), options);
    const double session_seconds = Elapsed(create_start);
    if (session.GetInputCount() != 3 || session.GetOutputCount() != 2) {
      throw std::runtime_error("expected exactly three inputs and two outputs");
    }
    Ort::AllocatorWithDefaultOptions allocator;
    std::vector<Ort::AllocatedStringPtr> input_names_owned;
    std::vector<const char *> input_names;
    for (size_t index = 0; index < session.GetInputCount(); ++index) {
      input_names_owned.push_back(session.GetInputNameAllocated(index, allocator));
      input_names.push_back(input_names_owned.back().get());
    }
    std::vector<Ort::AllocatedStringPtr> output_names_owned;
    std::vector<const char *> output_names;
    for (size_t index = 0; index < session.GetOutputCount(); ++index) {
      output_names_owned.push_back(session.GetOutputNameAllocated(index, allocator));
      output_names.push_back(output_names_owned.back().get());
    }
    if (std::vector<std::string>{input_names[0], input_names[1], input_names[2]} !=
            std::vector<std::string>{"tokens", "style", "speed"} ||
        std::vector<std::string>{output_names[0], output_names[1]} !=
            std::vector<std::string>{"audio", "pred_dur"}) {
      throw std::runtime_error("input/output names drifted");
    }

    const std::vector<int64_t> token_shape{1, 125};
    const std::vector<int64_t> style_shape{1, 256};
    const std::vector<int64_t> speed_shape{1};
    auto memory = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    std::vector<Ort::Value> inputs;
    inputs.push_back(Ort::Value::CreateTensor<int64_t>(
        memory, tokens.data(), tokens.size(), token_shape.data(), token_shape.size()));
    inputs.push_back(Ort::Value::CreateTensor<float>(
        memory, style.data(), style.size(), style_shape.data(), style_shape.size()));
    inputs.push_back(Ort::Value::CreateTensor<float>(
        memory, speed.data(), speed.size(), speed_shape.data(), speed_shape.size()));

    std::vector<double> run_seconds;
    std::vector<Ort::Value> outputs;
    for (int run = 0; run < args.runs; ++run) {
      const auto start = std::chrono::steady_clock::now();
      outputs = session.Run(Ort::RunOptions{nullptr}, input_names.data(),
                            inputs.data(), inputs.size(), output_names.data(),
                            output_names.size());
      run_seconds.push_back(Elapsed(start));
    }
    if (outputs.size() != 2 || !outputs[0].IsTensor() || !outputs[1].IsTensor()) {
      throw std::runtime_error("invalid output values");
    }
    const auto audio_info = outputs[0].GetTensorTypeAndShapeInfo();
    const auto duration_info = outputs[1].GetTensorTypeAndShapeInfo();
    if (audio_info.GetElementType() != ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT ||
        duration_info.GetElementType() != ONNX_TENSOR_ELEMENT_DATA_TYPE_INT64 ||
        audio_info.GetShape() != std::vector<int64_t>{182400} ||
        duration_info.GetShape() != std::vector<int64_t>{125}) {
      throw std::runtime_error("output dtype/shape contract drift");
    }
    const float *audio = outputs[0].GetTensorData<float>();
    const int64_t *duration = outputs[1].GetTensorData<int64_t>();
    double sum_squares = 0.0;
    float peak = 0.0f;
    size_t non_finite = 0;
    size_t clipped = 0;
    for (size_t index = 0; index < 182400; ++index) {
      const float value = audio[index];
      if (!std::isfinite(value)) ++non_finite;
      peak = std::max(peak, std::abs(value));
      sum_squares += static_cast<double>(value) * value;
      if (std::abs(value) >= 1.0f) ++clipped;
    }
    int64_t duration_sum = 0;
    for (size_t index = 0; index < 125; ++index) duration_sum += duration[index];
    if (non_finite != 0 || duration_sum != 304) {
      throw std::runtime_error("output validity/duration contract failed");
    }
    Write(args.audio_output, audio, 182400);
    Write(args.duration_output, duration, 125);
    auto profile_path = session.EndProfilingAllocated(allocator);

    std::cout << "{\n"
              << "  \"status\": \"passed\",\n"
              << "  \"provider\": \"" << args.provider << "\",\n"
              << "  \"optimization\": \"" << args.optimization << "\",\n"
              << "  \"session_creation_seconds\": " << session_seconds << ",\n"
              << "  \"run_seconds\": [";
    for (size_t index = 0; index < run_seconds.size(); ++index) {
      if (index) std::cout << ", ";
      std::cout << run_seconds[index];
    }
    std::cout << "],\n"
              << "  \"audio_elements\": 182400,\n"
              << "  \"duration_elements\": 125,\n"
              << "  \"duration_sum\": " << duration_sum << ",\n"
              << "  \"absolute_peak\": " << peak << ",\n"
              << "  \"rms\": " << std::sqrt(sum_squares / 182400.0) << ",\n"
              << "  \"non_finite_samples\": " << non_finite << ",\n"
              << "  \"clipped_samples\": " << clipped << ",\n"
              << "  \"max_rss_kib\": " << MaxRssKiB() << ",\n"
              << "  \"profile_path\": \"" << profile_path.get() << "\"\n"
              << "}\n";
    return 0;
  } catch (const Ort::Exception &error) {
    std::cerr << "ORT error " << error.GetOrtErrorCode() << ": " << error.what()
              << "\n";
    return 2;
  } catch (const std::exception &error) {
    std::cerr << "error: " << error.what() << "\n";
    return 3;
  }
}
