// Component-only ORT QNN runner for the fixed Supertonic vocoder probe.
// No Qualcomm headers or implementation code are included.

#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

#include "onnxruntime_cxx_api.h"

namespace {

struct Args {
  std::string model;
  std::string input;
  std::string output;
  std::string backend;
  std::string profile_prefix;
  int32_t latent_length = 0;
  int32_t runs = 1;
};

Args ParseArgs(int argc, char **argv) {
  Args result;
  auto take = [&](int *index) -> std::string {
    if (*index + 1 >= argc)
      throw std::runtime_error("missing argument value");
    return argv[++(*index)];
  };
  for (int index = 1; index < argc; ++index) {
    std::string key = argv[index];
    if (key == "--model")
      result.model = take(&index);
    else if (key == "--input")
      result.input = take(&index);
    else if (key == "--output")
      result.output = take(&index);
    else if (key == "--backend")
      result.backend = take(&index);
    else if (key == "--profile-prefix")
      result.profile_prefix = take(&index);
    else if (key == "--latent-length")
      result.latent_length = std::stoi(take(&index));
    else if (key == "--runs")
      result.runs = std::stoi(take(&index));
    else
      throw std::runtime_error("unknown argument: " + key);
  }
  if (result.model.empty() || result.input.empty() || result.output.empty() ||
      result.backend.empty() || result.profile_prefix.empty() ||
      result.latent_length <= 0 || result.runs <= 0) {
    throw std::runtime_error("missing or invalid required arguments");
  }
  return result;
}

std::vector<float> ReadFloats(const std::string &path, size_t expected) {
  std::ifstream input(path, std::ios::binary | std::ios::ate);
  if (!input)
    throw std::runtime_error("cannot open input: " + path);
  const auto bytes = input.tellg();
  if (bytes < 0 || static_cast<size_t>(bytes) != expected * sizeof(float)) {
    throw std::runtime_error("input byte count does not match expected shape");
  }
  input.seekg(0);
  std::vector<float> values(expected);
  if (!input.read(reinterpret_cast<char *>(values.data()), bytes)) {
    throw std::runtime_error("short input read");
  }
  return values;
}

void WriteFloats(const std::string &path, const float *values, size_t count) {
  std::filesystem::create_directories(
      std::filesystem::path(path).parent_path());
  std::ofstream output(path, std::ios::binary | std::ios::trunc);
  if (!output.write(reinterpret_cast<const char *>(values),
                    static_cast<std::streamsize>(count * sizeof(float)))) {
    throw std::runtime_error("output write failed");
  }
}

double SecondsSince(const std::chrono::steady_clock::time_point &start) {
  return std::chrono::duration<double>(std::chrono::steady_clock::now() - start)
      .count();
}

} // namespace

int main(int argc, char **argv) {
  try {
    const Args args = ParseArgs(argc, argv);
    constexpr int64_t kBatch = 1;
    constexpr int64_t kChannels = 144;
    const std::vector<int64_t> input_shape = {kBatch, kChannels,
                                              args.latent_length};
    const size_t input_count = static_cast<size_t>(kBatch * kChannels) *
                               static_cast<size_t>(args.latent_length);
    auto input_values = ReadFloats(args.input, input_count);

    Ort::Env environment(ORT_LOGGING_LEVEL_INFO, "supertonic-qnn-probe");
    Ort::SessionOptions options;
    options.SetIntraOpNumThreads(1);
    options.SetInterOpNumThreads(1);
    options.SetExecutionMode(ExecutionMode::ORT_SEQUENTIAL);
    options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
    options.AddConfigEntry("session.disable_cpu_ep_fallback", "1");
    options.EnableProfiling(args.profile_prefix.c_str());
    const std::unordered_map<std::string, std::string> provider_options = {
        {"backend_path", args.backend},
        {"profiling_level", "detailed"},
        {"profiling_file_path", args.profile_prefix + ".qnn.csv"},
        {"offload_graph_io_quantization", "0"},
        {"htp_performance_mode", "burst"},
        {"soc_model", "43"},
    };
    options.AppendExecutionProvider("QNN", provider_options);

    const auto create_start = std::chrono::steady_clock::now();
    Ort::Session session(environment, args.model.c_str(), options);
    const double session_create_seconds = SecondsSince(create_start);

    if (session.GetInputCount() != 1 || session.GetOutputCount() != 1) {
      throw std::runtime_error(
          "vocoder runner requires exactly one input/output");
    }
    Ort::AllocatorWithDefaultOptions allocator;
    auto input_name = session.GetInputNameAllocated(0, allocator);
    auto output_name = session.GetOutputNameAllocated(0, allocator);
    if (std::string(input_name.get()) != "latent" ||
        std::string(output_name.get()) != "wav_tts") {
      throw std::runtime_error("unexpected vocoder input/output names");
    }
    const auto model_input_shape =
        session.GetInputTypeInfo(0).GetTensorTypeAndShapeInfo().GetShape();
    if (model_input_shape != input_shape) {
      throw std::runtime_error("model input shape does not match runner shape");
    }

    auto memory =
        Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    Ort::Value input_tensor = Ort::Value::CreateTensor<float>(
        memory, input_values.data(), input_values.size(), input_shape.data(),
        input_shape.size());
    const char *input_names[] = {input_name.get()};
    const char *output_names[] = {output_name.get()};
    double first_run_seconds = 0.0;
    double warm_total_seconds = 0.0;
    std::vector<Ort::Value> outputs;
    for (int32_t run = 0; run < args.runs; ++run) {
      const auto run_start = std::chrono::steady_clock::now();
      outputs = session.Run(Ort::RunOptions{nullptr}, input_names,
                            &input_tensor, 1, output_names, 1);
      const double elapsed = SecondsSince(run_start);
      if (run == 0)
        first_run_seconds = elapsed;
      else
        warm_total_seconds += elapsed;
    }
    if (outputs.size() != 1 || !outputs[0].IsTensor()) {
      throw std::runtime_error("invalid vocoder output");
    }
    const auto output_info = outputs[0].GetTensorTypeAndShapeInfo();
    const auto output_shape = output_info.GetShape();
    const std::vector<int64_t> expected_output_shape = {
        1, static_cast<int64_t>(3072) * args.latent_length};
    if (output_shape != expected_output_shape) {
      throw std::runtime_error("unexpected vocoder output shape");
    }
    const size_t output_count = output_info.GetElementCount();
    WriteFloats(args.output, outputs[0].GetTensorData<float>(), output_count);
    auto profile_path = session.EndProfilingAllocated(allocator);

    std::cout << "{\n"
              << "  \"result\": \"passed\",\n"
              << "  \"session_create_seconds\": " << session_create_seconds
              << ",\n"
              << "  \"first_run_seconds\": " << first_run_seconds << ",\n"
              << "  \"warm_mean_seconds\": "
              << (args.runs > 1 ? warm_total_seconds / (args.runs - 1) : 0.0)
              << ",\n"
              << "  \"runs\": " << args.runs << ",\n"
              << "  \"output_elements\": " << output_count << ",\n"
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
