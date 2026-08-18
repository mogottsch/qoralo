// Single-fixture Supertonic vector-estimator runner for CPU or mixed QNN+CPU.
// No Qualcomm headers or implementation code are included.

#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <sys/resource.h>
#include <unordered_map>
#include <vector>

#include "onnxruntime_cxx_api.h"

namespace {

struct Args {
  std::string provider;
  std::string model;
  std::string fixture;
  std::string output;
  std::string backend;
  std::string profile_prefix;
  int32_t runs = 1;
};

Args ParseArgs(int argc, char **argv) {
  Args result;
  auto take = [&](int *index) {
    if (*index + 1 >= argc)
      throw std::runtime_error("missing argument value");
    return std::string(argv[++*index]);
  };
  for (int index = 1; index < argc; ++index) {
    const std::string key = argv[index];
    if (key == "--provider") result.provider = take(&index);
    else if (key == "--model") result.model = take(&index);
    else if (key == "--fixture") result.fixture = take(&index);
    else if (key == "--output") result.output = take(&index);
    else if (key == "--backend") result.backend = take(&index);
    else if (key == "--profile-prefix") result.profile_prefix = take(&index);
    else if (key == "--runs") result.runs = std::stoi(take(&index));
    else throw std::runtime_error("unknown argument: " + key);
  }
  if ((result.provider != "cpu" && result.provider != "qnn-fallback") ||
      result.model.empty() || result.fixture.empty() || result.output.empty() ||
      result.profile_prefix.empty() || result.runs <= 0 ||
      (result.provider == "qnn-fallback" && result.backend.empty()))
    throw std::runtime_error("missing or invalid required arguments");
  return result;
}

std::vector<float> ReadFloats(const std::filesystem::path &path, size_t count) {
  std::ifstream stream(path, std::ios::binary | std::ios::ate);
  if (!stream) throw std::runtime_error("cannot open input: " + path.string());
  const auto bytes = stream.tellg();
  if (bytes < 0 || static_cast<size_t>(bytes) != count * sizeof(float))
    throw std::runtime_error("input byte count mismatch: " + path.string());
  stream.seekg(0);
  std::vector<float> values(count);
  if (!stream.read(reinterpret_cast<char *>(values.data()), bytes))
    throw std::runtime_error("short input read: " + path.string());
  return values;
}

void WriteFloats(const std::string &path, const float *values, size_t count) {
  const std::filesystem::path output(path);
  if (!output.parent_path().empty())
    std::filesystem::create_directories(output.parent_path());
  std::ofstream stream(output, std::ios::binary | std::ios::trunc);
  if (!stream.write(reinterpret_cast<const char *>(values),
                    static_cast<std::streamsize>(count * sizeof(float))))
    throw std::runtime_error("output write failed");
}

double SecondsSince(const std::chrono::steady_clock::time_point &start) {
  return std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
}

long MaxRssKb() {
  struct rusage usage {};
  if (getrusage(RUSAGE_SELF, &usage) != 0) return -1;
  return usage.ru_maxrss;
}

struct Input {
  const char *name;
  std::vector<int64_t> shape;
  std::vector<float> values;
};

}  // namespace

int main(int argc, char **argv) {
  try {
    const Args args = ParseArgs(argc, argv);
    const std::filesystem::path root(args.fixture);
    std::vector<Input> inputs;
    inputs.push_back({"noisy_latent", {1, 144, 238}, ReadFloats(root / "input-noisy_latent.raw", 1 * 144 * 238)});
    inputs.push_back({"text_emb", {1, 256, 239}, ReadFloats(root / "text_emb.raw", 1 * 256 * 239)});
    inputs.push_back({"style_ttl", {1, 50, 256}, ReadFloats(root / "style_ttl.raw", 1 * 50 * 256)});
    inputs.push_back({"latent_mask", {1, 1, 238}, ReadFloats(root / "latent_mask.raw", 238)});
    inputs.push_back({"text_mask", {1, 1, 239}, ReadFloats(root / "text_mask.raw", 239)});
    inputs.push_back({"current_step", {1}, ReadFloats(root / "input-current_step.raw", 1)});
    inputs.push_back({"total_step", {1}, ReadFloats(root / "total_step.raw", 1)});

    Ort::Env environment(ORT_LOGGING_LEVEL_INFO, "supertonic-vector-fallback");
    Ort::SessionOptions options;
    options.SetIntraOpNumThreads(1);
    options.SetInterOpNumThreads(1);
    options.SetExecutionMode(ExecutionMode::ORT_SEQUENTIAL);
    options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
    options.EnableProfiling(args.profile_prefix.c_str());
    if (args.provider == "qnn-fallback") {
      options.AddConfigEntry("session.disable_cpu_ep_fallback", "0");
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
    const double create_seconds = SecondsSince(create_start);
    const long rss_after_session_kb = MaxRssKb();
    if (session.GetInputCount() != inputs.size() || session.GetOutputCount() != 1)
      throw std::runtime_error("unexpected model input/output count");

    Ort::AllocatorWithDefaultOptions allocator;
    std::vector<Ort::AllocatedStringPtr> allocated_names;
    std::vector<const char *> input_names;
    std::vector<Ort::Value> tensors;
    auto memory = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    for (size_t index = 0; index < inputs.size(); ++index) {
      allocated_names.push_back(session.GetInputNameAllocated(index, allocator));
      if (allocated_names.back().get() != std::string(inputs[index].name))
        throw std::runtime_error("unexpected input order/name");
      const auto model_shape = session.GetInputTypeInfo(index).GetTensorTypeAndShapeInfo().GetShape();
      if (model_shape != inputs[index].shape)
        throw std::runtime_error("unexpected model input shape");
      input_names.push_back(allocated_names.back().get());
      tensors.push_back(Ort::Value::CreateTensor<float>(
          memory, inputs[index].values.data(), inputs[index].values.size(),
          inputs[index].shape.data(), inputs[index].shape.size()));
    }
    auto output_name = session.GetOutputNameAllocated(0, allocator);
    if (std::string(output_name.get()) != "denoised_latent")
      throw std::runtime_error("unexpected output name");
    const char *output_names[] = {output_name.get()};

    double first_seconds = 0.0;
    double warm_seconds = 0.0;
    std::vector<Ort::Value> outputs;
    for (int32_t run = 0; run < args.runs; ++run) {
      const auto start = std::chrono::steady_clock::now();
      outputs = session.Run(Ort::RunOptions{nullptr}, input_names.data(),
                            tensors.data(), tensors.size(), output_names, 1);
      const double elapsed = SecondsSince(start);
      if (run == 0) first_seconds = elapsed;
      else warm_seconds += elapsed;
    }
    if (outputs.size() != 1 || !outputs[0].IsTensor())
      throw std::runtime_error("invalid output");
    const auto info = outputs[0].GetTensorTypeAndShapeInfo();
    if (info.GetShape() != std::vector<int64_t>({1, 144, 238}))
      throw std::runtime_error("unexpected output shape");
    const size_t count = info.GetElementCount();
    WriteFloats(args.output, outputs[0].GetTensorData<float>(), count);
    const long rss_after_run_kb = MaxRssKb();
    auto profile_path = session.EndProfilingAllocated(allocator);

    std::cout << "{\n"
              << "  \"result\": \"passed\",\n"
              << "  \"provider_mode\": \"" << args.provider << "\",\n"
              << "  \"cpu_ep_fallback_disabled\": false,\n"
              << "  \"session_create_seconds\": " << create_seconds << ",\n"
              << "  \"first_run_seconds\": " << first_seconds << ",\n"
              << "  \"warm_mean_seconds\": " << (args.runs > 1 ? warm_seconds / (args.runs - 1) : 0.0) << ",\n"
              << "  \"runs\": " << args.runs << ",\n"
              << "  \"output_elements\": " << count << ",\n"
              << "  \"max_rss_after_session_kb\": " << rss_after_session_kb << ",\n"
              << "  \"max_rss_after_run_kb\": " << rss_after_run_kb << ",\n"
              << "  \"profile_path\": \"" << profile_path.get() << "\"\n"
              << "}\n";
    return 0;
  } catch (const Ort::Exception &error) {
    std::cerr << "ORT error " << error.GetOrtErrorCode() << ": " << error.what() << "\n";
    return 2;
  } catch (const std::exception &error) {
    std::cerr << "error: " << error.what() << "\n";
    return 3;
  }
}
