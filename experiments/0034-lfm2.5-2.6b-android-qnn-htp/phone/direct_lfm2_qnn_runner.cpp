#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <functional>
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

#include "integrated_output.hpp"
#include "DynamicLoadUtil.hpp"
#include "Logger.hpp"
#include "PAL/DynamicLoading.hpp"
#include "QnnSampleApp.hpp"
#include "QnnTensor.h"
#include "QnnTypeMacros.hpp"

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

using qnn::tools::sample_app::QnnSampleApp;
using qnn::tools::sample_app::QnnFunctionPointers;
using qnn::tools::sample_app::StatusCode;

static void Require(StatusCode actual, const std::string& operation) {
  if (actual != StatusCode::SUCCESS) throw std::runtime_error(operation + " failed");
}

class DirectContext {
 public:
  struct GraphSlot {
    qnn_wrapper_api::GraphInfo_t* graph = nullptr;
    Qnn_Tensor_t* inputs = nullptr;
    Qnn_Tensor_t* outputs = nullptr;
  };

  DirectContext(const QnnFunctionPointers& pointers, void* backend_library,
                Qnn_BackendHandle_t backend, Qnn_DeviceHandle_t device,
                Qnn_ProfileHandle_t profile, const fs::path& binary,
                const std::vector<std::string>& aliases)
      : app_(std::make_unique<QnnSampleApp>(
            pointers, "", "", backend_library, "", false,
            qnn::tools::iotensor::OutputDataType::FLOAT_ONLY,
            qnn::tools::iotensor::InputDataType::FLOAT,
            qnn::tools::sample_app::ProfilingLevel::BASIC, false,
            binary.string(), "", 1, false, "")) {
    app_->m_backendHandle = backend;
    app_->m_deviceHandle = device;
    app_->m_profileBackendHandle = profile;
    Require(app_->createFromBinary(), "QnnContext_createFromBinary " + binary.string());
    if (app_->isFinalizeDeserializedGraphSupported() == StatusCode::SUCCESS) {
      Require(app_->finalizeGraphs(), "finalize deserialized graph " + binary.string());
    }
    if (app_->m_graphsCount != aliases.size()) {
      throw std::runtime_error("graph/alias count mismatch in " + binary.string());
    }
    slots_.resize(aliases.size());
    for (size_t index = 0; index < aliases.size(); ++index) {
      auto& slot = slots_[index];
      slot.graph = &(*app_->m_graphsInfo)[index];
      if (app_->m_ioTensor.setupInputAndOutputTensors(&slot.inputs, &slot.outputs, *slot.graph) !=
          qnn::tools::iotensor::StatusCode::SUCCESS) {
        throw std::runtime_error("setup QNN tensors failed: " + aliases[index]);
      }
      aliases_[aliases[index]] = index;
    }
  }

  ~DirectContext() {
    for (auto& slot : slots_) {
      if (slot.graph) app_->m_ioTensor.tearDownInputAndOutputTensors(
          slot.inputs, slot.outputs, slot.graph->numInputTensors, slot.graph->numOutputTensors);
    }
    if (app_ && app_->m_isContextCreated) app_->freeContext();
  }

  std::vector<std::vector<float>> Run(const std::string& alias,
                                      const std::vector<Input>& values,
                                      const std::vector<std::string>& requested_outputs) {
    const auto found_slot = aliases_.find(alias);
    if (found_slot == aliases_.end()) throw std::runtime_error("missing graph alias: " + alias);
    auto& slot = slots_[found_slot->second];
    auto* graph = slot.graph;
    auto* inputs = slot.inputs;
    auto* outputs = slot.outputs;
    if (values.size() != graph->numInputTensors) throw std::runtime_error("QNN input count mismatch");
    for (uint32_t index = 0; index < graph->numInputTensors; ++index) {
      Qnn_Tensor_t& tensor = inputs[index];
      const std::string name = QNN_TENSOR_GET_NAME(tensor) ? QNN_TENSOR_GET_NAME(tensor) : "";
      auto found = std::find_if(values.begin(), values.end(), [&](const Input& item) { return item.name == name; });
      if (found == values.end()) throw std::runtime_error("missing QNN input: " + name);
      const Qnn_DataType_t expected = found->type == Input::Type::Float
                                          ? QNN_DATATYPE_FLOAT_32
                                          : QNN_DATATYPE_INT_64;
      if (QNN_TENSOR_GET_DATA_TYPE(tensor) != expected) {
        throw std::runtime_error("QNN input datatype mismatch: " + name);
      }
      const size_t bytes = found->count * (found->type == Input::Type::Float ? sizeof(float) : sizeof(int64_t));
      if (QNN_TENSOR_GET_CLIENT_BUF(tensor).dataSize != bytes) {
        throw std::runtime_error("QNN input byte-size mismatch: " + name);
      }
      std::memcpy(QNN_TENSOR_GET_CLIENT_BUF(tensor).data, found->data, bytes);
    }
    const Qnn_ErrorHandle_t status = app_->m_qnnFunctionPointers.qnnInterface.graphExecute(
        graph->graph, inputs, graph->numInputTensors, outputs, graph->numOutputTensors,
        app_->m_profileBackendHandle, nullptr);
    if (status != QNN_GRAPH_NO_ERROR) {
      throw std::runtime_error("QnnGraph_execute failed: " + std::to_string(status));
    }
    std::vector<std::vector<float>> copied;
    copied.reserve(requested_outputs.size());
    for (const auto& requested : requested_outputs) {
      bool matched = false;
      for (uint32_t index = 0; index < graph->numOutputTensors; ++index) {
        Qnn_Tensor_t& tensor = outputs[index];
        const std::string name = QNN_TENSOR_GET_NAME(tensor) ? QNN_TENSOR_GET_NAME(tensor) : "";
        if (name != requested) continue;
        if (QNN_TENSOR_GET_DATA_TYPE(tensor) != QNN_DATATYPE_FLOAT_32) {
          throw std::runtime_error("non-float QNN output: " + name);
        }
        const size_t count = QNN_TENSOR_GET_CLIENT_BUF(tensor).dataSize / sizeof(float);
        const float* data = static_cast<const float*>(QNN_TENSOR_GET_CLIENT_BUF(tensor).data);
        for (size_t element = 0; element < count; ++element) {
          if (!std::isfinite(data[element])) throw std::runtime_error("non-finite QNN output: " + name);
        }
        copied.emplace_back(data, data + count);
        matched = true;
        break;
      }
      if (!matched) throw std::runtime_error("missing QNN output: " + requested);
    }
    std::cerr << "qnn_outputs_finite alias=" << alias << " requested=" << requested_outputs.size() << "\n";
    return copied;
  }

  void DumpProfile(const std::string& phase) const {
    const auto& qnn = app_->m_qnnFunctionPointers.qnnInterface;
    const Qnn_ProfileHandle_t profile = app_->m_profileBackendHandle;
    const QnnProfile_EventId_t* events = nullptr; uint32_t count = 0;
    if (!profile || qnn.profileGetEvents(profile, &events, &count) != QNN_PROFILE_NO_ERROR) {
      throw std::runtime_error("profileGetEvents failed: " + phase);
    }
    std::function<void(QnnProfile_EventId_t, int)> emit = [&](QnnProfile_EventId_t id, int depth) {
      QnnProfile_EventData_t data{};
      if (qnn.profileGetEventData(id, &data) != QNN_PROFILE_NO_ERROR) throw std::runtime_error("profileGetEventData failed");
      std::cerr << "qnn_profile phase=" << phase << " depth=" << depth << " type=" << data.type
                << " value=" << data.value << " unit=" << data.unit << " identifier="
                << (data.identifier ? data.identifier : "") << "\n";
      const QnnProfile_EventId_t* children = nullptr; uint32_t children_count = 0;
      if (qnn.profileGetSubEvents(id, &children, &children_count) != QNN_PROFILE_NO_ERROR) throw std::runtime_error("profileGetSubEvents failed");
      for (uint32_t index = 0; index < children_count; ++index) emit(children[index], depth + 1);
    };
    for (uint32_t index = 0; index < count; ++index) emit(events[index], 0);
  }

 private:
  std::unique_ptr<QnnSampleApp> app_;
  std::vector<GraphSlot> slots_;
  std::unordered_map<std::string, size_t> aliases_;
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
  explicit Runner(fs::path root, bool defer_context_load = false)
      : root_(std::move(root)),
        quant_(root_ / "embedding-quant.u8"),
        scales_(root_ / "embedding-scales.f32le"),
        zero_points_(root_ / "embedding-zp.u8") {
    if (quant_.size != static_cast<size_t>(kVocab) * 1024 ||
        scales_.size != static_cast<size_t>(kVocab) * 64 * sizeof(float) ||
        zero_points_.size != static_cast<size_t>(kVocab) * 32) {
      throw std::runtime_error("embedding asset size mismatch");
    }
    if (!qnn::log::initializeLogging()) throw std::runtime_error("QNN logging initialization failed");
    if (qnn::tools::dynamicloadutil::getQnnFunctionPointers(
            (root_ / "libQnnHtp.so").string(), "", &pointers_, &backend_library_, false,
            &model_library_) != qnn::tools::dynamicloadutil::StatusCode::SUCCESS) {
      throw std::runtime_error("load QNN HTP interface failed");
    }
    if (qnn::tools::dynamicloadutil::getQnnSystemFunctionPointers(
            (root_ / "libQnnSystem.so").string(), &pointers_) !=
        qnn::tools::dynamicloadutil::StatusCode::SUCCESS) {
      throw std::runtime_error("load QNN System interface failed");
    }
    owner_ = std::make_unique<QnnSampleApp>(
        pointers_, "", "", backend_library_, "", false,
        qnn::tools::iotensor::OutputDataType::FLOAT_ONLY,
        qnn::tools::iotensor::InputDataType::FLOAT,
        qnn::tools::sample_app::ProfilingLevel::DETAILED, false, "", "", 1, false, "");
    Require(owner_->initializeBackend(), "QNN backend initialization");
    Require(owner_->createDevice(), "QNN HTP device creation");
    Require(owner_->initializeProfiling(), "QNN profiling initialization");
    std::cerr << "qnn_backend_build_id=" << owner_->getBackendBuildId() << "\n";
    if (!defer_context_load) LoadSessions();
    Reset();
  }

  ~Runner() {
    sessions_.clear();
    contexts_.clear();
    if (owner_) {
      owner_->freeDevice();
      owner_->terminateBackend();
      owner_.reset();
    }
    if (backend_library_) pal::dynamicloading::dlClose(backend_library_);
    if (model_library_) pal::dynamicloading::dlClose(model_library_);
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

  void LoadState(const fs::path& input_list, int expected_position) {
    std::ifstream stream(input_list);
    if (!stream) throw std::runtime_error("cannot open resume input list");
    std::unordered_map<std::string, fs::path> files;
    std::string field;
    while (stream >> field) {
      const size_t split = field.find(":=");
      if (split == std::string::npos) throw std::runtime_error("invalid resume input field");
      fs::path path = field.substr(split + 2);
      if (path.is_relative()) path = root_ / path;
      files[field.substr(0, split)] = path;
    }
    auto floats = [&](const std::string& name, size_t count) {
      auto found = files.find(name);
      if (found == files.end()) throw std::runtime_error("missing resume state: " + name);
      std::ifstream input(found->second, std::ios::binary | std::ios::ate);
      if (!input || static_cast<size_t>(input.tellg()) != count * sizeof(float)) {
        throw std::runtime_error("resume state size mismatch: " + name);
      }
      input.seekg(0); std::vector<float> result(count);
      input.read(reinterpret_cast<char*>(result.data()), count * sizeof(float));
      return result;
    };
    for (int layer = 0; layer < kLayers; ++layer) {
      if (IsAttention(layer)) {
        key_[layer] = floats("past_key_values." + std::to_string(layer) + ".key", 8 * 64 * kCacheLength);
        value_[layer] = floats("past_key_values." + std::to_string(layer) + ".value", 8 * kCacheLength * 64);
      } else {
        conv_[layer] = floats("past_conv." + std::to_string(layer), kHidden * 3);
      }
    }
    auto position_file = files.find("position_ids");
    if (position_file == files.end()) throw std::runtime_error("missing resume position_ids");
    std::ifstream position_stream(position_file->second, std::ios::binary | std::ios::ate);
    if (!position_stream || position_stream.tellg() != static_cast<std::streampos>(sizeof(int32_t))) {
      throw std::runtime_error("resume position size mismatch");
    }
    position_stream.seekg(0); int32_t position = -1;
    position_stream.read(reinterpret_cast<char*>(&position), sizeof(position));
    if (position != expected_position) throw std::runtime_error("resume position value mismatch");
    auto mask = floats("attention_mask", kCapacity);
    for (int index = 0; index < kCapacity; ++index) {
      const float expected = index < expected_position || index == kCapacity - 1 ? 0.0f : -65504.0f;
      if (mask[index] != expected) throw std::runtime_error("resume mask mismatch");
    }
  }

  void LoadOnly(const fs::path& binary, const std::string& alias) {
    sessions_.clear(); contexts_.clear();
    consolidated_ = false;
    monolithic_ = lfm2::UsesMonolithicDispatch(alias);
    std::cerr << "loading_phase_context=" << binary.string() << " alias=" << alias << "\n";
    auto context = std::make_unique<DirectContext>(
        pointers_, backend_library_, owner_->m_backendHandle, owner_->m_deviceHandle,
        owner_->m_profileBackendHandle, binary, std::vector<std::string>{alias});
    sessions_[alias] = context.get(); contexts_.push_back(std::move(context));
    std::cerr << "loaded_contexts=1 loaded_graphs=1\n";
  }

  void FreeContexts() { sessions_.clear(); contexts_.clear(); }

  void DumpProfile(const std::string& phase) const {
    if (contexts_.size() != 1) throw std::runtime_error("profile requires one context");
    contexts_[0]->DumpProfile(phase);
  }

  void ResetDetailedProfile() {
    if (!contexts_.empty()) throw std::runtime_error("free contexts before profile reset");
    if (owner_->m_profileBackendHandle) {
      if (pointers_.qnnInterface.profileFree(owner_->m_profileBackendHandle) != QNN_PROFILE_NO_ERROR) {
        throw std::runtime_error("profileFree failed");
      }
      owner_->m_profileBackendHandle = nullptr;
    }
    if (pointers_.qnnInterface.profileCreate(owner_->m_backendHandle, QNN_PROFILE_LEVEL_DETAILED,
                                             &owner_->m_profileBackendHandle) != QNN_PROFILE_NO_ERROR) {
      throw std::runtime_error("detailed profileCreate failed");
    }
  }

  int RunPrefill171(const std::vector<int32_t>& tokens,
                    const std::function<void(int)>& emit_endpoint) {
    if (tokens.size() != 171) throw std::runtime_error("integrated prefill requires 171 tokens");
    constexpr int sequence = 171, past = kCapacity - sequence;
    const auto cpu_start = Clock::now();
    std::vector<float> hidden(sequence * kHidden);
    for (int row = 0; row < sequence; ++row) {
      auto value = Embedding(tokens[row]);
      std::copy(value.begin(), value.end(), hidden.begin() + row * kHidden);
    }
    std::vector<int64_t> positions = lfm2::MakePositionIds(0, sequence);
    std::vector<float> mask = lfm2::MakePrefillMask(sequence, kCapacity);
    std::vector<Input> inputs;
    inputs.reserve(41);
    inputs.push_back({"/model/embed_tokens/GatherBlockQuantized/output_0", Input::Type::Float,
                      hidden.data(), hidden.size(), {1, sequence, kHidden}});
    inputs.push_back({"position_ids", Input::Type::Int64, positions.data(), positions.size(), {1, sequence}});
    inputs.push_back({"attention_mask", Input::Type::Float, mask.data(), mask.size(), {1, 1, sequence, kCapacity}});
    std::unordered_map<int, std::vector<float>> prefill_key, prefill_value;
    for (int layer = 0; layer < kLayers; ++layer) {
      if (IsAttention(layer)) {
        prefill_key[layer] = std::vector<float>(8 * 64 * past, 0.0f);
        prefill_value[layer] = std::vector<float>(8 * past * 64, 0.0f);
        inputs.push_back({"past_key_values." + std::to_string(layer) + ".key", Input::Type::Float,
                          prefill_key[layer].data(), prefill_key[layer].size(), {1, 8, 64, past}});
        inputs.push_back({"past_key_values." + std::to_string(layer) + ".value", Input::Type::Float,
                          prefill_value[layer].data(), prefill_value[layer].size(), {1, 8, past, 64}});
      } else {
        inputs.push_back({"past_conv." + std::to_string(layer), Input::Type::Float,
                          conv_[layer].data(), conv_[layer].size(), {1, kHidden, 3}});
      }
    }
    std::vector<std::string> outputs;
    for (int layer = 0; layer < kLayers; ++layer) {
      if (IsAttention(layer)) {
        outputs.push_back("present." + std::to_string(layer) + ".key");
        outputs.push_back("present." + std::to_string(layer) + ".value");
      } else outputs.push_back("present_conv." + std::to_string(layer));
    }
    int offset = 0;
    while (offset < kVocab) {
      int remaining = kVocab - offset;
      int width = remaining == 5120 ? 4096 : std::min(6144, remaining);
      outputs.push_back("logits_vocab_" + std::to_string(offset) + "_" + std::to_string(offset + width));
      offset += width;
    }
    const auto cpu_end = Clock::now(); const auto execute_start = Clock::now();
    auto values = Run("prefill", inputs, outputs);
    const auto execute_end = Clock::now();
    last_prefill_cpu_seconds_ = std::chrono::duration<double>(cpu_end - cpu_start).count();
    last_prefill_execute_seconds_ = std::chrono::duration<double>(execute_end - execute_start).count();
    const auto argmax_start = Clock::now();
    float best = -std::numeric_limits<float>::infinity(); int best_token = -1; offset = 0;
    for (size_t chunk = 38; chunk < values.size(); ++chunk) {
      for (size_t element = 0; element < values[chunk].size(); ++element) if (values[chunk][element] > best) {
        best = values[chunk][element]; best_token = offset + static_cast<int>(element);
      }
      offset += static_cast<int>(values[chunk].size());
    }
    const auto argmax_end = Clock::now();
    emit_endpoint(best_token);
    const auto bridge_start = Clock::now();
    size_t index = 0;
    for (int layer = 0; layer < kLayers; ++layer) {
      if (IsAttention(layer)) {
        auto& new_key = values[index++]; auto& new_value = values[index++];
        lfm2::BridgeKeyPrefix(new_key, key_[layer], sequence, kCacheLength);
        lfm2::BridgeValuePrefix(new_value, value_[layer], sequence, kCacheLength);
      } else conv_[layer] = std::move(values[index++]);
    }
    const auto bridge_end = Clock::now();
    last_prefill_argmax_seconds_ = std::chrono::duration<double>(argmax_end - argmax_start).count();
    last_prefill_bridge_seconds_ = std::chrono::duration<double>(bridge_end - bridge_start).count();
    return best_token;
  }

  double LastPrefillCpuSeconds() const { return last_prefill_cpu_seconds_; }
  double LastPrefillExecuteSeconds() const { return last_prefill_execute_seconds_; }
  double LastPrefillArgmaxSeconds() const { return last_prefill_argmax_seconds_; }
  double LastPrefillBridgeSeconds() const { return last_prefill_bridge_seconds_; }

  int RunToken(int token, int position, bool sample) {
    if (monolithic_) return RunTokenMonolithic(token, position, sample);
    if (consolidated_) return RunTokenConsolidated(token, position, sample);
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

  size_t SessionCount() const { return contexts_.size(); }

 private:
  int RunTokenMonolithic(int token, int position, bool sample) {
    if (position < 0 || position >= kCacheLength) throw std::runtime_error("position out of range");
    std::vector<float> hidden = Embedding(token);
    std::vector<float> mask = lfm2::MakeAr1Mask(position, kCapacity);
    int64_t position_value = position;
    std::vector<Input> inputs;
    inputs.reserve(41);
    inputs.push_back({"/model/embed_tokens/GatherBlockQuantized/output_0", Input::Type::Float, hidden.data(), hidden.size(), {1, 1, kHidden}});
    inputs.push_back({"position_ids", Input::Type::Int64, &position_value, 1, {1, 1}});
    inputs.push_back({"attention_mask", Input::Type::Float, mask.data(), mask.size(), {1, 1, 1, kCapacity}});
    std::vector<std::string> outputs;
    outputs.reserve(60);
    for (int layer = 0; layer < kLayers; ++layer) {
      if (IsAttention(layer)) {
        inputs.push_back({"past_key_values." + std::to_string(layer) + ".key", Input::Type::Float, key_[layer].data(), key_[layer].size(), {1, 8, 64, kCacheLength}});
        inputs.push_back({"past_key_values." + std::to_string(layer) + ".value", Input::Type::Float, value_[layer].data(), value_[layer].size(), {1, 8, kCacheLength, 64}});
        outputs.push_back("present." + std::to_string(layer) + ".key");
        outputs.push_back("present." + std::to_string(layer) + ".value");
      } else {
        inputs.push_back({"past_conv." + std::to_string(layer), Input::Type::Float, conv_[layer].data(), conv_[layer].size(), {1, kHidden, 3}});
        outputs.push_back("present_conv." + std::to_string(layer));
      }
    }
    const size_t state_outputs = outputs.size();
    if (sample) {
      int offset = 0;
      while (offset < kVocab) {
        int remaining = kVocab - offset;
        int width = remaining == 5120 ? 4096 : std::min(6144, remaining);
        outputs.push_back("logits_vocab_" + std::to_string(offset) + "_" + std::to_string(offset + width));
        offset += width;
      }
    }
    auto values = Run("monolith", inputs, outputs);
    size_t index = 0;
    for (int layer = 0; layer < kLayers; ++layer) {
      if (IsAttention(layer)) {
        const auto& new_key = values[index++];
        const auto& new_value = values[index++];
        for (int head = 0; head < 8; ++head) for (int dim = 0; dim < 64; ++dim) {
          key_[layer][(head * 64 + dim) * kCacheLength + position] = new_key[head * 64 + dim];
          value_[layer][(head * kCacheLength + position) * 64 + dim] = new_value[head * 64 + dim];
        }
      } else {
        conv_[layer] = std::move(values[index++]);
      }
    }
    if (!sample) return -1;
    float best = -std::numeric_limits<float>::infinity();
    int best_token = -1;
    int offset = 0;
    for (size_t chunk = state_outputs; chunk < values.size(); ++chunk) {
      const auto& logits = values[chunk];
      for (size_t i = 0; i < logits.size(); ++i) if (logits[i] > best) {
        best = logits[i]; best_token = offset + static_cast<int>(i);
      }
      offset += static_cast<int>(logits.size());
    }
    return best_token;
  }

  int RunTokenConsolidated(int token, int position, bool sample) {
    if (position < 0 || position >= kCacheLength) throw std::runtime_error("position out of range");
    std::vector<float> hidden = Embedding(token);
    std::string hidden_name = "/model/embed_tokens/GatherBlockQuantized/output_0";
    std::vector<float> mask(kCapacity, -65504.0f);
    std::fill(mask.begin(), mask.begin() + position, 0.0f);
    mask.back() = 0.0f;
    int64_t position_value = position;
    for (int layer = 0; layer < kLayers; ++layer) {
      std::vector<Input> inputs = {{hidden_name, Input::Type::Float, hidden.data(), hidden.size(), {1, 1, kHidden}}};
      const std::string next_hidden = "/model/layers." + std::to_string(layer) + "/Add_2/output_0";
      std::vector<std::string> outputs = {next_hidden};
      if (IsAttention(layer)) {
        inputs.push_back({"position_ids", Input::Type::Int64, &position_value, 1, {1, 1}});
        inputs.push_back({"attention_mask", Input::Type::Float, mask.data(), mask.size(), {1, 1, 1, kCapacity}});
        inputs.push_back({"past_key_values." + std::to_string(layer) + ".key", Input::Type::Float, key_[layer].data(), key_[layer].size(), {1, 8, 64, kCacheLength}});
        inputs.push_back({"past_key_values." + std::to_string(layer) + ".value", Input::Type::Float, value_[layer].data(), value_[layer].size(), {1, 8, kCacheLength, 64}});
        outputs.push_back("present." + std::to_string(layer) + ".key");
        outputs.push_back("present." + std::to_string(layer) + ".value");
      } else {
        inputs.push_back({"past_conv." + std::to_string(layer), Input::Type::Float, conv_[layer].data(), conv_[layer].size(), {1, kHidden, 3}});
        outputs.push_back("present_conv." + std::to_string(layer));
      }
      auto values = Run("layer-" + (layer < 10 ? std::string("0") : std::string()) + std::to_string(layer), inputs, outputs);
      hidden = std::move(values[0]);
      hidden_name = next_hidden;
      if (IsAttention(layer)) {
        for (int head = 0; head < 8; ++head) for (int dim = 0; dim < 64; ++dim) {
          key_[layer][(head * 64 + dim) * kCacheLength + position] = values[1][head * 64 + dim];
          value_[layer][(head * kCacheLength + position) * 64 + dim] = values[2][head * 64 + dim];
        }
      } else {
        conv_[layer] = std::move(values[1]);
      }
    }
    if (!sample) return -1;
    const std::string normalized_name = "/model/layers.30/final_norm_layernorm/output_0";
    auto normalized = Run("final-norm", {{hidden_name, Input::Type::Float, hidden.data(), hidden.size(), {1, 1, kHidden}}}, {normalized_name})[0];
    float best = -std::numeric_limits<float>::infinity();
    int best_token = -1;
    int offset = 0;
    for (int group = 0; group < 6; ++group) {
      std::vector<std::string> output_names;
      int group_width = 0;
      for (int chunk = group * 4; chunk < std::min(22, group * 4 + 4); ++chunk) {
        int remaining = kVocab - offset - group_width;
        int width = remaining == 5120 ? 4096 : std::min(6144, remaining);
        output_names.push_back("logits_vocab_" + std::to_string(offset + group_width) + "_" + std::to_string(offset + group_width + width));
        group_width += width;
      }
      auto chunks = Run("heads-0" + std::to_string(group), {{normalized_name, Input::Type::Float, normalized.data(), normalized.size(), {1, 1, kHidden}}}, output_names);
      for (const auto& logits : chunks) {
        for (size_t index = 0; index < logits.size(); ++index) if (logits[index] > best) {
          best = logits[index]; best_token = offset + static_cast<int>(index);
        }
        offset += static_cast<int>(logits.size());
      }
    }
    return best_token;
  }

  fs::path root_;
  MappedFile quant_;
  MappedFile scales_;
  MappedFile zero_points_;
  QnnFunctionPointers pointers_{};
  void* backend_library_ = nullptr;
  void* model_library_ = nullptr;
  std::unique_ptr<QnnSampleApp> owner_;
  bool consolidated_ = false;
  bool monolithic_ = false;
  std::vector<std::unique_ptr<DirectContext>> contexts_;
  std::unordered_map<std::string, DirectContext*> sessions_;
  std::unordered_map<int, std::vector<float>> conv_;
  std::unordered_map<int, std::vector<float>> key_;
  std::unordered_map<int, std::vector<float>> value_;
  double last_prefill_cpu_seconds_ = 0.0;
  double last_prefill_execute_seconds_ = 0.0;
  double last_prefill_argmax_seconds_ = 0.0;
  double last_prefill_bridge_seconds_ = 0.0;

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
    fs::path shared_manifest = root_ / "shared-contexts.tsv";
    if (fs::exists(root_ / "monolithic-contexts.tsv")) {
      shared_manifest = root_ / "monolithic-contexts.tsv";
      monolithic_ = true;
    } else if (fs::exists(root_ / "consolidated-contexts.tsv")) {
      shared_manifest = root_ / "consolidated-contexts.tsv";
      consolidated_ = true;
    }
    if (fs::exists(shared_manifest)) {
      std::ifstream stream(shared_manifest);
      if (!stream) throw std::runtime_error("cannot open shared context manifest");
      std::string line;
      size_t loaded_graphs = 0;
      while (std::getline(stream, line)) {
        if (line.empty()) continue;
        std::vector<std::string> fields;
        size_t begin = 0;
        while (true) {
          size_t end = line.find('\t', begin);
          fields.push_back(line.substr(begin, end - begin));
          if (end == std::string::npos) break;
          begin = end + 1;
        }
        if (fields.size() < 2) throw std::runtime_error("invalid shared context manifest line");
        std::vector<std::string> aliases(fields.begin() + 1, fields.end());
        std::cerr << "loading_shared_context=" << fields[0] << " graphs=" << aliases.size() << "\n";
        auto context = std::make_unique<DirectContext>(
            pointers_, backend_library_, owner_->m_backendHandle, owner_->m_deviceHandle,
            owner_->m_profileBackendHandle, root_ / fields[0], aliases);
        for (const auto& alias : aliases) {
          if (!sessions_.emplace(alias, context.get()).second) throw std::runtime_error("duplicate graph alias: " + alias);
        }
        loaded_graphs += aliases.size();
        contexts_.push_back(std::move(context));
      }
      const size_t expected = monolithic_ ? 1 : (consolidated_ ? 37 : names.size());
      if (loaded_graphs != expected || sessions_.size() != expected) {
        throw std::runtime_error("context manifest does not cover exact pipeline");
      }
      std::cerr << "loaded_contexts=" << contexts_.size() << " loaded_graphs=" << loaded_graphs << "\n";
      return;
    }
    for (size_t index = 0; index < names.size(); ++index) {
      const auto& name = names[index];
      std::cerr << "loading_context=" << name << "\n";
      auto context = std::make_unique<DirectContext>(
          pointers_, backend_library_, owner_->m_backendHandle, owner_->m_deviceHandle,
          owner_->m_profileBackendHandle, root_ / "contexts" / name / "context_qnn.bin",
          std::vector<std::string>{name});
      sessions_[name] = context.get();
      contexts_.push_back(std::move(context));
      if ((index + 1) % 20 == 0 || index + 1 == names.size()) {
        std::cerr << "loaded_contexts=" << (index + 1) << "/" << names.size() << "\n";
      }
    }
  }

  std::vector<std::vector<float>> Run(const std::string& session_name,
                                      const std::vector<Input>& inputs,
                                      const std::vector<std::string>& output_names) {
    auto found = sessions_.find(session_name);
    if (found == sessions_.end()) throw std::runtime_error("missing context: " + session_name);
    return found->second->Run(session_name, inputs, output_names);
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
    const bool integrated = argc == 6 && std::string(argv[2]) == "--integrated";
    if (integrated) {
      const fs::path root = argv[1]; const auto prompt = ReadTokens(argv[3]);
      const int max_new = std::stoi(argv[4]);
      if (prompt.size() != 171 || max_new < 1 || prompt.size() + static_cast<size_t>(max_new) > kCacheLength) {
        throw std::runtime_error("integrated route requires 171 prompt tokens and bounded total output");
      }
      // MAX_NEW is the total output cap, including the AR171 endpoint token.
      // O_EXCL prevents a retry from overwriting evidence from an earlier attempt.
      lfm2::ExclusiveTokenOutput token_output(argv[5]);
      lfm2::BoundedTokenEmitter emitter(token_output, static_cast<size_t>(max_new), kEos);
      const auto process_setup_start = Clock::now(); Runner runner(root, true);
      const auto process_setup_end = Clock::now(); const auto request_start = Clock::now();
      auto first_token_emitted = request_start; auto final_token_emitted = request_start; bool emitted = false;
      const auto prefill_load_start = Clock::now(); runner.LoadOnly(root / "contexts/ar171.bin", "prefill");
      const auto prefill_load_end = Clock::now();
      const int endpoint = runner.RunPrefill171(prompt, [&](int token) {
        emitter.Emit(token);
        first_token_emitted = final_token_emitted = Clock::now(); emitted = true;
      });
      if (!emitted) throw std::runtime_error("prefill endpoint was not emitted");
      const auto bridge_complete = Clock::now();
      const double prefill_compute_phase_sum_seconds =
          std::chrono::duration<double>(prefill_load_end - prefill_load_start).count() +
          runner.LastPrefillCpuSeconds() + runner.LastPrefillExecuteSeconds() + runner.LastPrefillArgmaxSeconds();
      const auto prefill_profile_start = Clock::now();
      const bool prefill_profile_complete = lfm2::CaptureOptionalTelemetry(
          "prefill", [&] { runner.DumpProfile("prefill"); }, std::cerr);
      const auto prefill_profile_end = Clock::now(); const auto prefill_free_start = Clock::now();
      runner.FreeContexts(); const auto prefill_free_end = Clock::now(); const auto profile_reset_start = Clock::now();
      const bool profile_reset_complete = lfm2::CaptureOptionalTelemetry(
          "profile_reset", [&] { runner.ResetDetailedProfile(); }, std::cerr);
      const auto profile_reset_end = Clock::now();
      const auto ar1_load_start = Clock::now(); runner.LoadOnly(root / "contexts/ar1.bin", "monolith");
      const auto ar1_load_end = Clock::now();
      auto resume_first_emitted = ar1_load_end;
      while (emitter.CanDecode()) {
        const size_t output_index = emitter.Tokens().size();
        const int current = runner.RunToken(emitter.Tokens().back(), 171 + static_cast<int>(output_index) - 1, true);
        emitter.Emit(current); final_token_emitted = Clock::now();
        if (output_index == 1) resume_first_emitted = final_token_emitted;
      }
      const auto& generated = emitter.Tokens();
      const auto decode_end = Clock::now(); const auto ar1_profile_start = Clock::now();
      const bool ar1_profile_complete = lfm2::CaptureOptionalTelemetry(
          "ar1_decode", [&] { runner.DumpProfile("ar1_decode"); }, std::cerr);
      const auto ar1_profile_end = Clock::now(); const auto ar1_free_start = Clock::now();
      runner.FreeContexts(); const auto ar1_free_end = Clock::now(); const auto diagnostic_end = Clock::now();
      const auto sec = [](auto d) { return std::chrono::duration<double>(d).count(); };
      const auto timing = lfm2::SummarizeTiming({request_start, first_token_emitted, final_token_emitted,
          prefill_profile_start, prefill_profile_end, ar1_profile_start, ar1_profile_end, diagnostic_end});
      std::cout << "{\n  \"result\": \"passed\",\n  \"route\": \"integrated_ar171_phase_switch_ar1\",\n"
                << "  \"prompt_tokens\": " << prompt.size() << ",\n  \"prefill_endpoint_token\": " << endpoint << ",\n"
                << "  \"output_cap_semantics\": \"MAX_NEW is total emitted tokens including the AR171 endpoint\",\n"
                << "  \"max_new_tokens\": " << max_new << ",\n  \"emitted_tokens\": " << generated.size() << ",\n"
                << "  \"resume_graph_executions\": " << generated.size() - 1 << ",\n  \"contexts_loaded_sequentially\": 2,\n"
                << "  \"simultaneous_contexts\": 1,\n  \"context_reloads_per_phase\": 0,\n"
                << "  \"process_backend_setup_seconds\": " << sec(process_setup_end - process_setup_start) << ",\n"
                << "  \"prefill_context_load_seconds\": " << sec(prefill_load_end - prefill_load_start) << ",\n"
                << "  \"prefill_cpu_input_seconds\": " << runner.LastPrefillCpuSeconds() << ",\n"
                << "  \"prefill_graph_seconds\": " << runner.LastPrefillExecuteSeconds() << ",\n"
                << "  \"prefill_argmax_seconds\": " << runner.LastPrefillArgmaxSeconds() << ",\n"
                << "  \"prefill_compute_phase_sum_seconds\": " << prefill_compute_phase_sum_seconds << ",\n"
                << "  \"request_to_first_emitted_token_seconds\": " << timing.request_to_first_emitted_seconds << ",\n"
                << "  \"prefill_phase_through_state_bridge_seconds\": " << sec(bridge_complete - request_start) << ",\n"
                << "  \"prefill_state_bridge_seconds\": " << runner.LastPrefillBridgeSeconds() << ",\n"
                << "  \"prefill_profile_complete\": " << (prefill_profile_complete ? "true" : "false") << ",\n"
                << "  \"prefill_profile_dump_seconds\": " << timing.prefill_profile_seconds << ",\n"
                << "  \"prefill_context_free_seconds\": " << sec(prefill_free_end - prefill_free_start) << ",\n"
                << "  \"profile_reset_complete\": " << (profile_reset_complete ? "true" : "false") << ",\n"
                << "  \"profile_reset_seconds\": " << sec(profile_reset_end - profile_reset_start) << ",\n"
                << "  \"ar1_context_load_seconds\": " << sec(ar1_load_end - ar1_load_start) << ",\n"
                << "  \"ar1_request_to_first_emitted_token_seconds\": " << sec(resume_first_emitted - ar1_load_end) << ",\n"
                << "  \"ar1_total_decode_seconds\": " << sec(decode_end - ar1_load_end) << ",\n"
                << "  \"request_to_final_emitted_token_seconds\": " << timing.request_to_final_emitted_seconds << ",\n"
                << "  \"decode_compute_complete_seconds\": " << sec(decode_end - request_start) << ",\n"
                << "  \"ar1_profile_complete\": " << (ar1_profile_complete ? "true" : "false") << ",\n"
                << "  \"ar1_profile_dump_seconds\": " << timing.ar1_profile_seconds << ",\n"
                << "  \"ar1_context_free_seconds\": " << sec(ar1_free_end - ar1_free_start) << ",\n"
                << "  \"diagnostic_total_with_profile_and_free_seconds\": " << timing.diagnostic_total_seconds << "\n}\n";
      return 0;
    }
    const bool resume = argc == 7;
    if (argc != 5 && !resume) {
      std::cerr << "usage: lfm2_qnn_runner ROOT PROMPT.int32le MAX_NEW OUTPUT.int32le\n"
                   "   or: lfm2_qnn_runner ROOT RESUME_INPUT_LIST START_TOKEN START_POSITION MAX_NEW OUTPUT.int32le\n"
                   "   or: lfm2_qnn_runner ROOT --integrated PROMPT.int32le MAX_NEW OUTPUT.int32le\n";
      return 2;
    }
    const fs::path root = argv[1];
    const auto prompt = resume ? std::vector<int32_t>{} : ReadTokens(argv[2]);
    const int start_token = resume ? std::stoi(argv[3]) : -1;
    const int start_position = resume ? std::stoi(argv[4]) : 0;
    const int max_new = std::stoi(argv[resume ? 5 : 3]);
    if (max_new < 1) throw std::runtime_error("MAX_NEW must be positive");
    if ((resume ? static_cast<size_t>(start_position) : prompt.size()) + static_cast<size_t>(max_new) > kCacheLength) {
      throw std::runtime_error("prompt plus output exceeds route capacity");
    }
    const auto setup_start = Clock::now();
    Runner runner(root);
    if (resume) runner.LoadState(argv[2], start_position);
    const auto setup_end = Clock::now();
    std::vector<int32_t> generated;
    generated.reserve(max_new);
    const auto request_start = Clock::now();
    auto first_token = request_start;
    int token = -1;
    if (resume) {
      int current = start_token;
      for (int index = 0; index < max_new && (index == 0 || generated.back() != kEos); ++index) {
        token = runner.RunToken(current, start_position + index, true);
        generated.push_back(token); current = token;
        if (index == 0) first_token = Clock::now();
      }
    } else {
      for (size_t position = 0; position < prompt.size(); ++position) {
        token = runner.RunToken(prompt[position], static_cast<int>(position), position + 1 == prompt.size());
      }
      if (max_new > 0) generated.push_back(token);
      first_token = Clock::now();
      for (int index = 1; index < max_new && generated.back() != kEos; ++index) {
        const int position = static_cast<int>(prompt.size()) + index - 1;
        token = runner.RunToken(generated.back(), position, true);
        generated.push_back(token);
      }
    }
    const auto request_end = Clock::now();
    std::ofstream output(argv[resume ? 6 : 4], std::ios::binary);
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
      << "  \"resume_start_position\": " << (resume ? start_position : -1) << ",\n"
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
