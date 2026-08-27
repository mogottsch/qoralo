#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#include "onnxruntime_cxx_api.h"

namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;

static constexpr int kLayers = 30;
static constexpr int kCapacity = 4096;
static constexpr int kCacheLength = 4095;
static constexpr int kHidden = 2048;
static constexpr int kVocab = 128000;
static constexpr int kEos = 124900;
static const std::array<int, 8> kAttention = {2, 5, 9, 13, 17, 21, 24, 27};

struct MappedFile {
  int fd = -1;
  size_t size = 0;
  const uint8_t* data = nullptr;
  explicit MappedFile(const fs::path& path) {
    fd = open(path.c_str(), O_RDONLY | O_CLOEXEC);
    if (fd < 0) throw std::runtime_error("open failed: " + path.string());
    struct stat st {};
    if (fstat(fd, &st) != 0) throw std::runtime_error("fstat failed: " + path.string());
    size = static_cast<size_t>(st.st_size);
    void* mapped = mmap(nullptr, size, PROT_READ, MAP_PRIVATE, fd, 0);
    if (mapped == MAP_FAILED) throw std::runtime_error("mmap failed: " + path.string());
    data = static_cast<const uint8_t*>(mapped);
  }
  ~MappedFile() {
    if (data) munmap(const_cast<uint8_t*>(data), size);
    if (fd >= 0) close(fd);
  }
};

struct Input {
  std::string name;
  enum class Type { Float, Int64 } type;
  const void* data;
  size_t count;
  std::vector<int64_t> shape;
};

static bool IsAttention(int layer) {
  return std::find(kAttention.begin(), kAttention.end(), layer) != kAttention.end();
}

static std::string Layer(int layer, const std::string& suffix) {
  char number[3];
  std::snprintf(number, sizeof(number), "%02d", layer);
  return "layer-" + std::string(number) + "-" + suffix;
}

class Runner {
 public:
  explicit Runner(fs::path root)
      : root_(std::move(root)),
        quant_(root_ / "embedding-quant.u8"),
        scales_(root_ / "embedding-scales.f32le"),
        zero_points_(root_ / "embedding-zp.u8"),
        env_(ORT_LOGGING_LEVEL_WARNING, "lfm2-0034") {
    if (quant_.size != static_cast<size_t>(kVocab) * 1024 ||
        scales_.size != static_cast<size_t>(kVocab) * 64 * sizeof(float) ||
        zero_points_.size != static_cast<size_t>(kVocab) * 32) {
      throw std::runtime_error("embedding asset size mismatch");
    }
    env_.RegisterExecutionProviderLibrary("QNNExecutionProvider", root_ / "libonnxruntime_providers_qnn.so");
    for (auto device : env_.GetEpDevices()) {
      if (std::string(device.EpName()) == "QNNExecutionProvider") devices_.push_back(device);
    }
    if (devices_.empty()) throw std::runtime_error("QNNExecutionProvider device not found");
    fs::create_directories(root_ / "profiles");
    LoadSessions();
    Reset();
  }

  ~Runner() {
    sessions_.clear();
    try {
      env_.UnregisterExecutionProviderLibrary("QNNExecutionProvider");
    } catch (...) {
    }
  }

  void Reset() {
    conv_.clear();
    key_.clear();
    value_.clear();
    for (int layer = 0; layer < kLayers; ++layer) {
      if (IsAttention(layer)) {
        key_[layer] = std::vector<float>(8 * 64 * kCacheLength, 0.0f);
        value_[layer] = std::vector<float>(8 * kCacheLength * 64, 0.0f);
      } else {
        conv_[layer] = std::vector<float>(kHidden * 3, 0.0f);
      }
    }
  }

  int RunToken(int token, int position, bool sample) {
    if (position < 0 || position >= kCacheLength) throw std::runtime_error("position out of range");
    std::vector<float> hidden = Embedding(token);
    std::string hidden_name = "/model/embed_tokens/GatherBlockQuantized/output_0";
    std::vector<float> mask(kCapacity, -65504.0f);
    std::fill(mask.begin(), mask.begin() + position, 0.0f);
    mask.back() = 0.0f;
    int64_t position_value = position;

    for (int layer = 0; layer < kLayers; ++layer) {
      const std::string residual_name = "/model/layers." + std::to_string(layer) + "/Add_1/output_0";
      const std::string norm_name = "/model/layers." + std::to_string(layer) + "/ffn_layernorm/LayerNorm/output_0";
      std::vector<std::string> core_outputs = {residual_name, norm_name};
      std::vector<Input> core_inputs = {
          {hidden_name, Input::Type::Float, hidden.data(), hidden.size(), {1, 1, kHidden}}};
      if (IsAttention(layer)) {
        const std::string key_input = "past_key_values." + std::to_string(layer) + ".key";
        const std::string value_input = "past_key_values." + std::to_string(layer) + ".value";
        core_inputs.push_back({"position_ids", Input::Type::Int64, &position_value, 1, {1, 1}});
        core_inputs.push_back({"attention_mask", Input::Type::Float, mask.data(), mask.size(), {1, 1, 1, kCapacity}});
        core_inputs.push_back({key_input, Input::Type::Float, key_[layer].data(), key_[layer].size(), {1, 8, 64, kCacheLength}});
        core_inputs.push_back({value_input, Input::Type::Float, value_[layer].data(), value_[layer].size(), {1, 8, kCacheLength, 64}});
        core_outputs.push_back("present." + std::to_string(layer) + ".key");
        core_outputs.push_back("present." + std::to_string(layer) + ".value");
      } else {
        const std::string state = "past_conv." + std::to_string(layer);
        core_inputs.push_back({state, Input::Type::Float, conv_[layer].data(), conv_[layer].size(), {1, kHidden, 3}});
        core_outputs.push_back("present_conv." + std::to_string(layer));
      }
      auto core = Run(Layer(layer, "core-norm"), core_inputs, core_outputs);
      auto residual = std::move(core[0]);
      auto norm = std::move(core[1]);
      if (IsAttention(layer)) {
        const auto& new_key = core[2];
        const auto& new_value = core[3];
        for (int head = 0; head < 8; ++head) {
          for (int dim = 0; dim < 64; ++dim) {
            key_[layer][(head * 64 + dim) * kCacheLength + position] = new_key[head * 64 + dim];
            value_[layer][(head * kCacheLength + position) * 64 + dim] = new_value[head * 64 + dim];
          }
        }
      } else {
        conv_[layer] = std::move(core[2]);
      }

      std::array<std::vector<float>, 2> down;
      for (int part = 0; part < 2; ++part) {
        const int width = part == 0 ? 6144 : 4608;
        const std::string norm_input = norm_name;
        const std::string up_output = "/model/layers." + std::to_string(layer) + "/mlp/up_proj/MatMul_Q4/htp_shard/part" + std::to_string(part);
        auto up = Run(Layer(layer, "up-" + std::to_string(part)),
                      {{norm_input, Input::Type::Float, norm.data(), norm.size(), {1, 1, kHidden}}},
                      {up_output})[0];
        const std::string product_output = "/model/layers." + std::to_string(layer) + "/mlp/pipeline_product_part" + std::to_string(part);
        auto product = Run(
            Layer(layer, "gate-activate-" + std::to_string(part)),
            {{norm_input, Input::Type::Float, norm.data(), norm.size(), {1, 1, kHidden}},
             {up_output, Input::Type::Float, up.data(), up.size(), {1, 1, width}}},
            {product_output})[0];
        const std::string down_output = "/model/layers." + std::to_string(layer) + "/mlp/down_proj/MatMul_Q4/htp_shard/part" + std::to_string(part);
        down[part] = Run(
            Layer(layer, "down-" + std::to_string(part)),
            {{product_output, Input::Type::Float, product.data(), product.size(), {1, 1, width}}},
            {down_output})[0];
      }
      const std::string down0_name = "/model/layers." + std::to_string(layer) + "/mlp/down_proj/MatMul_Q4/htp_shard/part0";
      const std::string down1_name = "/model/layers." + std::to_string(layer) + "/mlp/down_proj/MatMul_Q4/htp_shard/part1";
      const std::string next_hidden = "/model/layers." + std::to_string(layer) + "/Add_2/output_0";
      hidden = Run(
          Layer(layer, "residual"),
          {{down0_name, Input::Type::Float, down[0].data(), down[0].size(), {1, 1, kHidden}},
           {down1_name, Input::Type::Float, down[1].data(), down[1].size(), {1, 1, kHidden}},
           {residual_name, Input::Type::Float, residual.data(), residual.size(), {1, 1, kHidden}}},
          {next_hidden})[0];
      hidden_name = next_hidden;
    }

    if (!sample) return -1;
    const std::string normalized_name = "/model/layers.30/final_norm_layernorm/output_0";
    auto normalized = Run("final-norm",
                          {{hidden_name, Input::Type::Float, hidden.data(), hidden.size(), {1, 1, kHidden}}},
                          {normalized_name})[0];
    float best = -std::numeric_limits<float>::infinity();
    int best_token = -1;
    int offset = 0;
    int chunk = 0;
    while (offset < kVocab) {
      int remaining = kVocab - offset;
      int width = remaining == 5120 ? 4096 : std::min(6144, remaining);
      char chunk_name[3];
      std::snprintf(chunk_name, sizeof(chunk_name), "%02d", chunk);
      const std::string output = "logits_vocab_" + std::to_string(offset) + "_" + std::to_string(offset + width);
      auto logits = Run("head-" + std::string(chunk_name),
                        {{normalized_name, Input::Type::Float, normalized.data(), normalized.size(), {1, 1, kHidden}}},
                        {output})[0];
      for (int index = 0; index < width; ++index) {
        if (logits[index] > best) {
          best = logits[index];
          best_token = offset + index;
        }
      }
      offset += width;
      ++chunk;
    }
    return best_token;
  }

  size_t SessionCount() const { return sessions_.size(); }

 private:
  fs::path root_;
  MappedFile quant_;
  MappedFile scales_;
  MappedFile zero_points_;
  Ort::Env env_;
  std::vector<Ort::ConstEpDevice> devices_;
  std::unordered_map<std::string, std::unique_ptr<Ort::Session>> sessions_;
  std::unordered_map<int, std::vector<float>> conv_;
  std::unordered_map<int, std::vector<float>> key_;
  std::unordered_map<int, std::vector<float>> value_;
  Ort::MemoryInfo memory_{Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault)};

  std::vector<float> Embedding(int token) const {
    if (token < 0 || token >= kVocab) throw std::runtime_error("token out of range");
    const uint8_t* packed = quant_.data + static_cast<size_t>(token) * 1024;
    const float* scales = reinterpret_cast<const float*>(scales_.data + static_cast<size_t>(token) * 64 * sizeof(float));
    const uint8_t* packed_zp = zero_points_.data + static_cast<size_t>(token) * 32;
    std::vector<float> output(kHidden);
    for (int block = 0; block < 64; ++block) {
      const uint8_t zp_byte = packed_zp[block / 2];
      const float zp = static_cast<float>((block & 1) ? (zp_byte >> 4) : (zp_byte & 15));
      for (int index = 0; index < 32; ++index) {
        const int value_index = block * 32 + index;
        const uint8_t byte = packed[value_index / 2];
        const float q = static_cast<float>((value_index & 1) ? (byte >> 4) : (byte & 15));
        output[value_index] = (q - zp) * scales[block];
      }
    }
    return output;
  }

  void LoadSessions() {
    std::vector<std::string> names;
    for (int layer = 0; layer < kLayers; ++layer) {
      names.push_back(Layer(layer, "core-norm"));
      names.push_back(Layer(layer, "up-0"));
      names.push_back(Layer(layer, "gate-activate-0"));
      names.push_back(Layer(layer, "up-1"));
      names.push_back(Layer(layer, "gate-activate-1"));
      names.push_back(Layer(layer, "down-0"));
      names.push_back(Layer(layer, "down-1"));
      names.push_back(Layer(layer, "residual"));
    }
    names.push_back("final-norm");
    for (int chunk = 0; chunk < 22; ++chunk) {
      char value[3];
      std::snprintf(value, sizeof(value), "%02d", chunk);
      names.push_back("head-" + std::string(value));
    }
    for (size_t index = 0; index < names.size(); ++index) {
      const auto& name = names[index];
      Ort::KeyValuePairs provider_options;
      provider_options.Add("backend_path", (root_ / "libQnnHtp.so").c_str());
      provider_options.Add("htp_performance_mode", "burst");
      provider_options.Add("rpc_control_latency", "100");
      provider_options.Add("soc_model", "43");
      provider_options.Add("htp_share_resource_optimization", "1");
      provider_options.Add("profiling_level", "basic");
      provider_options.Add("profiling_file_path", (root_ / "profiles" / (name + ".csv")).c_str());
      Ort::SessionOptions options;
      options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_BASIC);
      options.AddConfigEntry("session.disable_cpu_ep_fallback", "1");
      options.AppendExecutionProvider_V2(env_, devices_, provider_options);
      sessions_[name] = std::make_unique<Ort::Session>(
          env_, (root_ / "contexts" / name / "context.onnx").c_str(), options);
      if ((index + 1) % 20 == 0 || index + 1 == names.size()) {
        std::cerr << "loaded_sessions=" << (index + 1) << "/" << names.size() << "\n";
      }
    }
  }

  std::vector<std::vector<float>> Run(const std::string& session_name,
                                      const std::vector<Input>& inputs,
                                      const std::vector<std::string>& output_names) {
    auto found = sessions_.find(session_name);
    if (found == sessions_.end()) throw std::runtime_error("missing session: " + session_name);
    std::vector<const char*> input_names;
    std::vector<Ort::Value> values;
    input_names.reserve(inputs.size());
    values.reserve(inputs.size());
    for (const auto& input : inputs) {
      input_names.push_back(input.name.c_str());
      if (input.type == Input::Type::Float) {
        values.emplace_back(Ort::Value::CreateTensor<float>(
            memory_, const_cast<float*>(static_cast<const float*>(input.data)), input.count,
            input.shape.data(), input.shape.size()));
      } else {
        values.emplace_back(Ort::Value::CreateTensor<int64_t>(
            memory_, const_cast<int64_t*>(static_cast<const int64_t*>(input.data)), input.count,
            input.shape.data(), input.shape.size()));
      }
    }
    std::vector<const char*> outputs;
    outputs.reserve(output_names.size());
    for (const auto& name : output_names) outputs.push_back(name.c_str());
    auto result = found->second->Run(Ort::RunOptions{nullptr}, input_names.data(), values.data(), values.size(),
                                     outputs.data(), outputs.size());
    std::vector<std::vector<float>> copied;
    copied.reserve(result.size());
    for (auto& tensor : result) {
      auto info = tensor.GetTensorTypeAndShapeInfo();
      size_t count = info.GetElementCount();
      const float* data = tensor.GetTensorData<float>();
      copied.emplace_back(data, data + count);
    }
    return copied;
  }
};

static std::vector<int32_t> ReadTokens(const fs::path& path) {
  std::ifstream stream(path, std::ios::binary | std::ios::ate);
  if (!stream) throw std::runtime_error("cannot open tokens: " + path.string());
  auto bytes = stream.tellg();
  if (bytes <= 0 || bytes % 4 != 0) throw std::runtime_error("invalid token file");
  stream.seekg(0);
  std::vector<int32_t> result(static_cast<size_t>(bytes) / 4);
  stream.read(reinterpret_cast<char*>(result.data()), bytes);
  return result;
}

int main(int argc, char** argv) {
  try {
    if (argc != 5) {
      std::cerr << "usage: lfm2_qnn_runner ROOT PROMPT.int32le MAX_NEW OUTPUT.int32le\n";
      return 2;
    }
    const fs::path root = argv[1];
    const auto prompt = ReadTokens(argv[2]);
    const int max_new = std::stoi(argv[3]);
    if (max_new < 1) throw std::runtime_error("MAX_NEW must be positive");
    if (prompt.size() + static_cast<size_t>(max_new) > kCacheLength) {
      throw std::runtime_error("prompt plus output exceeds route capacity");
    }
    const auto setup_start = Clock::now();
    Runner runner(root);
    const auto setup_end = Clock::now();
    std::vector<int32_t> generated;
    generated.reserve(max_new);
    const auto request_start = Clock::now();
    int token = -1;
    for (size_t position = 0; position < prompt.size(); ++position) {
      token = runner.RunToken(prompt[position], static_cast<int>(position), position + 1 == prompt.size());
    }
    const auto first_token = Clock::now();
    if (max_new > 0) generated.push_back(token);
    for (int index = 1; index < max_new && generated.back() != kEos; ++index) {
      const int position = static_cast<int>(prompt.size()) + index - 1;
      token = runner.RunToken(generated.back(), position, true);
      generated.push_back(token);
    }
    const auto request_end = Clock::now();
    std::ofstream output(argv[4], std::ios::binary);
    if (!output) throw std::runtime_error("cannot open output token file");
    output.write(reinterpret_cast<const char*>(generated.data()),
                 static_cast<std::streamsize>(generated.size() * sizeof(int32_t)));
    output.close();
    const auto seconds = [](auto duration) {
      return std::chrono::duration<double>(duration).count();
    };
    std::cout << "{\n"
              << "  \"result\": \"passed\",\n"
              << "  \"sessions_loaded\": " << runner.SessionCount() << ",\n"
              << "  \"prompt_tokens\": " << prompt.size() << ",\n"
              << "  \"generated_tokens\": " << generated.size() << ",\n"
              << "  \"stop_reason\": \"" << ((!generated.empty() && generated.back() == kEos) ? "eos" : "max_tokens") << "\",\n"
              << "  \"setup_seconds\": " << seconds(setup_end - setup_start) << ",\n"
              << "  \"request_to_first_token_seconds\": " << seconds(first_token - request_start) << ",\n"
              << "  \"total_request_seconds\": " << seconds(request_end - request_start) << "\n"
              << "}\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "fatal=" << error.what() << "\n";
    return 1;
  }
}
