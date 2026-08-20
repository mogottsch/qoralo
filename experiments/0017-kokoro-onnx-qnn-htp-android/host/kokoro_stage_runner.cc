// Generic fixed-shape stage runner for experiment 0017 Kokoro decomposition.
// Qualcomm headers or implementation code are not included.

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

#if !defined(_WIN32)
#include <sys/resource.h>
#endif

#include "onnxruntime_cxx_api.h"

namespace {

struct TensorSpec {
  std::string name;
  std::string dtype;
  std::vector<int64_t> shape;
  std::string path;
};

struct Args {
  std::string model;
  std::string stage;
  std::vector<TensorSpec> inputs;
  std::vector<TensorSpec> outputs;
  std::string provider = "cpu";
  std::string backend;
  std::string profile_prefix;
  std::string optimization = "disabled";
  int runs = 1;
};

std::vector<std::string> Split(const std::string &value, char delimiter) {
  std::vector<std::string> result;
  std::string item;
  std::istringstream stream(value);
  while (std::getline(stream, item, delimiter)) result.push_back(item);
  return result;
}

std::vector<int64_t> ParseShape(const std::string &value) {
  if (value.empty()) throw std::runtime_error("empty shape");
  std::vector<int64_t> shape;
  for (const auto &item : Split(value, ',')) {
    const int64_t dim = std::stoll(item);
    if (dim <= 0) throw std::runtime_error("shape dimensions must be positive");
    shape.push_back(dim);
  }
  return shape;
}

size_t ElementCount(const std::vector<int64_t> &shape) {
  size_t count = 1;
  for (int64_t dim : shape) {
    if (static_cast<uint64_t>(dim) >
        std::numeric_limits<size_t>::max() / count) {
      throw std::runtime_error("tensor element count overflow");
    }
    count *= static_cast<size_t>(dim);
  }
  return count;
}

TensorSpec ParseTensorSpec(const std::string &value) {
  const auto fields = Split(value, '|');
  if (fields.size() != 4 || fields[0].empty() || fields[3].empty()) {
    throw std::runtime_error(
        "tensor spec must be name|dtype|comma-shape|path: " + value);
  }
  if (fields[1] != "float32" && fields[1] != "int64") {
    throw std::runtime_error("tensor dtype must be float32 or int64");
  }
  return TensorSpec{fields[0], fields[1], ParseShape(fields[2]), fields[3]};
}

Args ParseArgs(int argc, char **argv) {
  Args args;
  auto value = [&](int *index) {
    if (++(*index) >= argc) throw std::runtime_error("missing argument value");
    return std::string(argv[*index]);
  };
  for (int index = 1; index < argc; ++index) {
    const std::string key = argv[index];
    if (key == "--model") args.model = value(&index);
    else if (key == "--stage") args.stage = value(&index);
    else if (key == "--input-spec")
      args.inputs.push_back(ParseTensorSpec(value(&index)));
    else if (key == "--output-spec")
      args.outputs.push_back(ParseTensorSpec(value(&index)));
    else if (key == "--provider") args.provider = value(&index);
    else if (key == "--backend") args.backend = value(&index);
    else if (key == "--profile-prefix") args.profile_prefix = value(&index);
    else if (key == "--optimization") args.optimization = value(&index);
    else if (key == "--runs") args.runs = std::stoi(value(&index));
    else throw std::runtime_error("unknown argument: " + key);
  }
  if (args.model.empty() || args.stage.empty() || args.inputs.empty() ||
      args.outputs.empty() || args.profile_prefix.empty() || args.runs <= 0) {
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

std::string JsonEscape(const std::string &value) {
  std::ostringstream out;
  for (unsigned char ch : value) {
    switch (ch) {
      case '\\': out << "\\\\"; break;
      case '"': out << "\\\""; break;
      case '\n': out << "\\n"; break;
      case '\r': out << "\\r"; break;
      case '\t': out << "\\t"; break;
      default:
        if (ch < 0x20) {
          const char *hex = "0123456789abcdef";
          out << "\\u00" << hex[ch >> 4] << hex[ch & 0x0f];
        } else {
          out << static_cast<char>(ch);
        }
    }
  }
  return out.str();
}

ONNXTensorElementDataType ElementType(const TensorSpec &spec) {
  return spec.dtype == "float32" ? ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT
                                 : ONNX_TENSOR_ELEMENT_DATA_TYPE_INT64;
}

size_t ElementBytes(const TensorSpec &spec) {
  return spec.dtype == "float32" ? sizeof(float) : sizeof(int64_t);
}

std::vector<char> ReadBytes(const TensorSpec &spec) {
  std::ifstream stream(spec.path, std::ios::binary | std::ios::ate);
  if (!stream) throw std::runtime_error("cannot open input: " + spec.path);
  const auto bytes = stream.tellg();
  const size_t expected = ElementCount(spec.shape) * ElementBytes(spec);
  if (bytes < 0 || static_cast<size_t>(bytes) != expected) {
    throw std::runtime_error("input byte count mismatch: " + spec.path);
  }
  stream.seekg(0);
  std::vector<char> result(expected);
  if (!stream.read(result.data(), static_cast<std::streamsize>(expected))) {
    throw std::runtime_error("short input read: " + spec.path);
  }
  return result;
}

void WriteBytes(const std::string &path, const void *values, size_t bytes) {
  const auto parent = std::filesystem::path(path).parent_path();
  if (!parent.empty()) std::filesystem::create_directories(parent);
  std::ofstream stream(path, std::ios::binary | std::ios::trunc);
  if (!stream.write(reinterpret_cast<const char *>(values),
                    static_cast<std::streamsize>(bytes))) {
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

std::string ShapeJson(const std::vector<int64_t> &shape) {
  std::ostringstream out;
  out << "[";
  for (size_t index = 0; index < shape.size(); ++index) {
    if (index) out << ",";
    out << shape[index];
  }
  out << "]";
  return out.str();
}

void ValidateInterface(Ort::Session &session, const Args &args) {
  if (session.GetInputCount() != args.inputs.size() ||
      session.GetOutputCount() != args.outputs.size()) {
    throw std::runtime_error("session input/output count differs from contract");
  }
  Ort::AllocatorWithDefaultOptions allocator;
  for (size_t index = 0; index < args.inputs.size(); ++index) {
    auto name = session.GetInputNameAllocated(index, allocator);
    auto type_info = session.GetInputTypeInfo(index);
    auto info = type_info.GetTensorTypeAndShapeInfo();
    const auto actual_shape = info.GetShape();
    const auto actual_type = info.GetElementType();
    if (args.inputs[index].name != name.get() ||
        args.inputs[index].shape != actual_shape ||
        ElementType(args.inputs[index]) != actual_type) {
      throw std::runtime_error(
          "session input contract mismatch at index " + std::to_string(index) +
          ": expected name=" + args.inputs[index].name +
          " shape=" + ShapeJson(args.inputs[index].shape) +
          " type=" + std::to_string(ElementType(args.inputs[index])) +
          "; actual name=" + name.get() + " shape=" + ShapeJson(actual_shape) +
          " type=" + std::to_string(actual_type));
    }
  }
  for (size_t index = 0; index < args.outputs.size(); ++index) {
    auto name = session.GetOutputNameAllocated(index, allocator);
    auto type_info = session.GetOutputTypeInfo(index);
    auto info = type_info.GetTensorTypeAndShapeInfo();
    const auto actual_shape = info.GetShape();
    const auto actual_type = info.GetElementType();
    if (args.outputs[index].name != name.get() ||
        args.outputs[index].shape != actual_shape ||
        ElementType(args.outputs[index]) != actual_type) {
      throw std::runtime_error(
          "session output contract mismatch at index " + std::to_string(index) +
          ": expected name=" + args.outputs[index].name +
          " shape=" + ShapeJson(args.outputs[index].shape) +
          " type=" + std::to_string(ElementType(args.outputs[index])) +
          "; actual name=" + name.get() + " shape=" + ShapeJson(actual_shape) +
          " type=" + std::to_string(actual_type));
    }
  }
}

}  // namespace

int main(int argc, char **argv) {
  try {
    const Args args = ParseArgs(argc, argv);
    std::vector<std::vector<char>> input_buffers;
    input_buffers.reserve(args.inputs.size());
    for (const auto &spec : args.inputs) input_buffers.push_back(ReadBytes(spec));

    Ort::Env environment(ORT_LOGGING_LEVEL_WARNING, "kokoro-qnn-0017-stage");
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
    ValidateInterface(session, args);

    auto memory = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    std::vector<Ort::Value> input_values;
    std::vector<const char *> input_names;
    input_values.reserve(args.inputs.size());
    input_names.reserve(args.inputs.size());
    for (size_t index = 0; index < args.inputs.size(); ++index) {
      const auto &spec = args.inputs[index];
      auto &bytes = input_buffers[index];
      input_names.push_back(spec.name.c_str());
      if (spec.dtype == "float32") {
        input_values.push_back(Ort::Value::CreateTensor<float>(
            memory, reinterpret_cast<float *>(bytes.data()), ElementCount(spec.shape),
            spec.shape.data(), spec.shape.size()));
      } else {
        input_values.push_back(Ort::Value::CreateTensor<int64_t>(
            memory, reinterpret_cast<int64_t *>(bytes.data()),
            ElementCount(spec.shape), spec.shape.data(), spec.shape.size()));
      }
    }
    std::vector<const char *> output_names;
    output_names.reserve(args.outputs.size());
    for (const auto &spec : args.outputs) output_names.push_back(spec.name.c_str());

    std::vector<double> run_seconds;
    std::vector<Ort::Value> output_values;
    for (int run = 0; run < args.runs; ++run) {
      const auto start = std::chrono::steady_clock::now();
      output_values = session.Run(
          Ort::RunOptions{nullptr}, input_names.data(), input_values.data(),
          input_values.size(), output_names.data(), output_names.size());
      run_seconds.push_back(Elapsed(start));
    }
    if (output_values.size() != args.outputs.size()) {
      throw std::runtime_error("runtime output count mismatch");
    }

    std::ostringstream output_json;
    output_json << "[";
    for (size_t index = 0; index < args.outputs.size(); ++index) {
      const auto &spec = args.outputs[index];
      auto &value = output_values[index];
      if (!value.IsTensor()) throw std::runtime_error("non-tensor output");
      const auto info = value.GetTensorTypeAndShapeInfo();
      if (info.GetShape() != spec.shape || info.GetElementType() != ElementType(spec)) {
        throw std::runtime_error("runtime output contract mismatch: " + spec.name);
      }
      const size_t count = ElementCount(spec.shape);
      if (index) output_json << ",";
      output_json << "{\"name\":\"" << JsonEscape(spec.name)
                  << "\",\"dtype\":\"" << spec.dtype << "\",\"shape\":"
                  << ShapeJson(spec.shape) << ",\"elements\":" << count;
      if (spec.dtype == "float32") {
        const float *data = value.GetTensorData<float>();
        size_t non_finite = 0;
        double sum_squares = 0.0;
        float peak = 0.0f;
        for (size_t item = 0; item < count; ++item) {
          const float sample = data[item];
          if (!std::isfinite(sample)) ++non_finite;
          peak = std::max(peak, std::abs(sample));
          sum_squares += static_cast<double>(sample) * sample;
        }
        if (non_finite != 0) {
          throw std::runtime_error("non-finite float output: " + spec.name);
        }
        WriteBytes(spec.path, data, count * sizeof(float));
        output_json << ",\"non_finite\":0,\"absolute_peak\":" << peak
                    << ",\"rms\":" << std::sqrt(sum_squares / count);
      } else {
        const int64_t *data = value.GetTensorData<int64_t>();
        int64_t sum = 0;
        for (size_t item = 0; item < count; ++item) sum += data[item];
        WriteBytes(spec.path, data, count * sizeof(int64_t));
        output_json << ",\"sum\":" << sum;
      }
      output_json << ",\"path\":\"" << JsonEscape(spec.path) << "\"}";
    }
    output_json << "]";

    Ort::AllocatorWithDefaultOptions allocator;
    auto profile_path = session.EndProfilingAllocated(allocator);
    std::cout << "{\n"
              << "  \"status\": \"passed\",\n"
              << "  \"stage\": \"" << JsonEscape(args.stage) << "\",\n"
              << "  \"provider\": \"" << args.provider << "\",\n"
              << "  \"optimization\": \"" << args.optimization << "\",\n"
              << "  \"session_creation_seconds\": " << session_seconds << ",\n"
              << "  \"run_seconds\": [";
    for (size_t index = 0; index < run_seconds.size(); ++index) {
      if (index) std::cout << ",";
      std::cout << run_seconds[index];
    }
    std::cout << "],\n"
              << "  \"outputs\": " << output_json.str() << ",\n"
              << "  \"max_rss_kib\": " << MaxRssKiB() << ",\n"
              << "  \"profile_path\": \"" << JsonEscape(profile_path.get())
              << "\"\n}\n";
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
