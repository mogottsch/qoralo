// Matched source-ONNX versus external-QNN-context Android benchmark for the
// canonical-v2 fixed-Alba Pocket route. Sessions are created once per fresh
// process. Every generation rebuilds all FlowLM and Mimi state from immutable
// fixtures, reruns text/prefill/AR/flow/decode, and writes its own WAV.
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
#include <sys/resource.h>
#include <unordered_map>
#include <vector>
#include "onnxruntime_cxx_api.h"

namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;

static double Now() {
  return std::chrono::duration<double>(Clock::now().time_since_epoch()).count();
}
static long Hwm() {
  struct rusage value {};
  return getrusage(RUSAGE_SELF, &value) ? -1 : value.ru_maxrss;
}
static void Put16(std::ostream &stream, uint16_t value) {
  char bytes[2] = {char(value), char(value >> 8)};
  stream.write(bytes, 2);
}
static void Put32(std::ostream &stream, uint32_t value) {
  char bytes[4] = {char(value), char(value >> 8), char(value >> 16), char(value >> 24)};
  stream.write(bytes, 4);
}
static std::vector<float> ReadFloats(const fs::path &path, size_t count) {
  std::ifstream stream(path, std::ios::binary | std::ios::ate);
  if (!stream || size_t(stream.tellg()) != count * sizeof(float)) {
    throw std::runtime_error("float fixture size: " + path.string());
  }
  stream.seekg(0);
  std::vector<float> values(count);
  stream.read(reinterpret_cast<char *>(values.data()), values.size() * sizeof(float));
  if (!stream) throw std::runtime_error("float fixture read");
  return values;
}
static std::vector<int64_t> ReadInt64(const fs::path &path, size_t count) {
  std::ifstream stream(path, std::ios::binary | std::ios::ate);
  if (!stream || size_t(stream.tellg()) != count * sizeof(int64_t)) {
    throw std::runtime_error("int64 fixture size: " + path.string());
  }
  stream.seekg(0);
  std::vector<int64_t> values(count);
  stream.read(reinterpret_cast<char *>(values.data()), values.size() * sizeof(int64_t));
  if (!stream) throw std::runtime_error("int64 fixture read");
  return values;
}
static void WriteWav(const fs::path &path, const std::vector<float> &audio) {
  std::ofstream stream(path, std::ios::binary | std::ios::trunc);
  uint32_t payload_bytes = audio.size() * 2;
  stream.write("RIFF", 4); Put32(stream, 36 + payload_bytes);
  stream.write("WAVEfmt ", 8); Put32(stream, 16); Put16(stream, 1); Put16(stream, 1);
  Put32(stream, 24000); Put32(stream, 48000); Put16(stream, 2); Put16(stream, 16);
  stream.write("data", 4); Put32(stream, payload_bytes);
  for (float sample : audio) {
    long quantized = long(std::nearbyint(std::clamp(sample, -1.f, 1.f) * 32767.f));
    Put16(stream, uint16_t(int16_t(std::clamp(quantized, -32768L, 32767L))));
  }
  if (!stream) throw std::runtime_error("wav write");
}

struct Model {
  std::string name;
  std::unique_ptr<Ort::Session> session;
  std::vector<std::string> input_names, output_names;
  std::vector<const char *> input_ptrs, output_ptrs;
  double create_seconds = 0;
};

static Ort::SessionOptions Options(const std::string &backend, const std::string &prefix,
                                   bool profile, bool context_arm,
                                   const fs::path &model_path) {
  Ort::SessionOptions options;
  options.SetIntraOpNumThreads(1);
  options.SetInterOpNumThreads(1);
  options.SetExecutionMode(ExecutionMode::ORT_SEQUENTIAL);
  options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_BASIC);
  if (profile) options.EnableProfiling(prefix.c_str());
  options.AddConfigEntry("session.disable_cpu_ep_fallback", "1");
  if (context_arm) {
    options.AddConfigEntry("ep.context_file_path", model_path.c_str());
  }
  std::unordered_map<std::string, std::string> qnn = {
    {"backend_path", backend},
    {"offload_graph_io_quantization", "0"},
    {"htp_performance_mode", "burst"},
    {"soc_model", "43"},
    {"enable_htp_fp16_precision", "0"},
  };
  if (profile) {
    qnn["profiling_level"] = "detailed";
    qnn["profiling_file_path"] = prefix + ".qnn.csv";
  }
  options.AppendExecutionProvider("QNN", qnn);
  return options;
}
static Model Load(Ort::Env &env, const fs::path &path, const std::string &name,
                  const std::string &backend, const fs::path &profile_dir,
                  bool profile, bool context_arm) {
  Model model;
  model.name = name;
  auto options = Options(backend, (profile_dir / name).string(), profile,
                         context_arm, path);
  double start = Now();
  model.session = std::make_unique<Ort::Session>(env, path.c_str(), options);
  model.create_seconds = Now() - start;
  Ort::AllocatorWithDefaultOptions allocator;
  for (size_t i = 0; i < model.session->GetInputCount(); ++i) {
    auto value = model.session->GetInputNameAllocated(i, allocator);
    model.input_names.emplace_back(value.get());
  }
  for (size_t i = 0; i < model.session->GetOutputCount(); ++i) {
    auto value = model.session->GetOutputNameAllocated(i, allocator);
    model.output_names.emplace_back(value.get());
  }
  for (auto &value : model.input_names) model.input_ptrs.push_back(value.c_str());
  for (auto &value : model.output_names) model.output_ptrs.push_back(value.c_str());
  return model;
}
static std::vector<Ort::Value> Run(Model &model, std::vector<Ort::Value> &inputs) {
  if (inputs.size() != model.input_ptrs.size()) {
    throw std::runtime_error(model.name + " input count");
  }
  return model.session->Run(Ort::RunOptions{nullptr}, model.input_ptrs.data(),
                            inputs.data(), inputs.size(), model.output_ptrs.data(),
                            model.output_ptrs.size());
}
template <class T>
static Ort::Value Tensor(Ort::MemoryInfo &memory, std::vector<T> &values,
                         std::initializer_list<int64_t> shape) {
  std::vector<int64_t> dimensions(shape);
  return Ort::Value::CreateTensor<T>(memory, values.data(), values.size(),
                                     dimensions.data(), dimensions.size());
}
static std::vector<float> CopyFloat(Ort::Value &value) {
  auto info = value.GetTensorTypeAndShapeInfo();
  const float *data = value.GetTensorData<float>();
  return {data, data + info.GetElementCount()};
}

static std::vector<Ort::Value> InitFixedState(
    const std::vector<float> &packed, Ort::AllocatorWithDefaultOptions &allocator) {
  constexpr size_t kHeads = 16, kDim = 64, kSource = 126, kCapacity = 512;
  constexpr size_t kPerLayer = 2 * kSource * kHeads * kDim;
  if (packed.size() != 6 * kPerLayer) throw std::runtime_error("Alba cache pack");
  std::vector<Ort::Value> state;
  state.reserve(13);
  std::array<int64_t, 4> shape{1, kHeads, kCapacity, kDim};
  for (size_t layer = 0; layer < 6; ++layer) {
    for (size_t kv = 0; kv < 2; ++kv) {
      auto value = Ort::Value::CreateTensor<float>(allocator, shape.data(), shape.size());
      float *destination = value.GetTensorMutableData<float>();
      std::fill(destination, destination + kHeads * kCapacity * kDim, 0.f);
      const float *source = packed.data() + layer * kPerLayer + kv * kSource * kHeads * kDim;
      for (size_t position = 0; position < kSource; ++position) {
        for (size_t head = 0; head < kHeads; ++head) {
          std::copy(source + (position * kHeads + head) * kDim,
                    source + (position * kHeads + head + 1) * kDim,
                    destination + (head * kCapacity + (kCapacity - kSource + position)) * kDim);
        }
      }
      state.push_back(std::move(value));
    }
  }
  std::array<int64_t, 4> mask_shape{1, 1, 1, kCapacity};
  auto mask = Ort::Value::CreateTensor<float>(allocator, mask_shape.data(), mask_shape.size());
  float *mask_data = mask.GetTensorMutableData<float>();
  std::fill(mask_data, mask_data + kCapacity, -10000.f);
  std::fill(mask_data + kCapacity - kSource, mask_data + kCapacity, 0.f);
  state.push_back(std::move(mask));
  return state;
}
static std::vector<Ort::Value> StaticCall(
    Model &model, Ort::Value *leading, std::vector<int64_t> &positions,
    std::vector<Ort::Value> &state, Ort::MemoryInfo &memory) {
  std::vector<Ort::Value> inputs;
  if (leading) inputs.push_back(std::move(*leading));
  inputs.push_back(Tensor(memory, positions, {int64_t(positions.size())}));
  inputs.push_back(std::move(state[12]));
  for (int i = 0; i < 12; ++i) inputs.push_back(std::move(state[i]));
  auto result = Run(model, inputs);
  size_t offset = model.name == "prefill_text" ? 0 : 2;
  state.clear();
  for (size_t i = 0; i < 13; ++i) state.push_back(std::move(result[offset + i]));
  return result;
}
static std::vector<Ort::Value> InitDecoder(
    Model &model, Ort::AllocatorWithDefaultOptions &allocator) {
  std::vector<Ort::Value> state;
  for (size_t i = 1; i < model.input_names.size(); ++i) {
    auto info = model.session->GetInputTypeInfo(i).GetTensorTypeAndShapeInfo();
    auto shape = info.GetShape();
    auto type = info.GetElementType();
    auto value = Ort::Value::CreateTensor(allocator, shape.data(), shape.size(), type);
    size_t count = info.GetElementCount();
    if (type == ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT) {
      std::fill(value.GetTensorMutableData<float>(), value.GetTensorMutableData<float>() + count, 0.f);
    } else if (type == ONNX_TENSOR_ELEMENT_DATA_TYPE_INT64) {
      std::fill(value.GetTensorMutableData<int64_t>(), value.GetTensorMutableData<int64_t>() + count, 0);
    } else if (type == ONNX_TENSOR_ELEMENT_DATA_TYPE_BOOL) {
      std::memset(value.GetTensorMutableRawData(), 1, count);
    } else {
      throw std::runtime_error("decoder state dtype");
    }
    state.push_back(std::move(value));
  }
  if (state.size() != 56) throw std::runtime_error("decoder state ABI");
  return state;
}

struct Iteration {
  std::string kind, wav_name;
  double generation_seconds = 0, text_seconds = 0, prefill_seconds = 0;
  double ar_seconds = 0, flow_seconds = 0, decoder_seconds = 0;
  int eos_step = -1, latent_frames = 0;
  size_t samples = 0;
  long vm_hwm_kb = -1;
  float peak = 0;
};

int main(int argc, char **argv) {
  try {
    if (argc != 15) {
      throw std::runtime_error(
          "usage: runner MODEL_DIR ALBA_CACHE TOKEN_IDS_I64 NOISE_F32 OUTPUT_DIR "
          "PROFILE_DIR|- QNN_BACKEND TEMPERATURE MAX_FRAMES VARIANT WARM_RUNS "
          "EXPECTED_EOS EXPECTED_FRAMES SOURCE|CONTEXT");
    }
    fs::path root = argv[1], cache_path = argv[2], token_path = argv[3],
             noise_path = argv[4], output_dir = argv[5], profile_dir = argv[6];
    std::string backend = argv[7], variant = argv[10], arm = argv[14];
    float temperature = std::stof(argv[8]);
    int max_frames = std::stoi(argv[9]), warm_runs = std::stoi(argv[11]);
    int expected_eos = std::stoi(argv[12]), expected_frames = std::stoi(argv[13]);
    bool profile = profile_dir != "-", context_arm = arm == "context";
    if (profile) fs::create_directories(profile_dir);
    if ((arm != "source" && arm != "context") || backend == "cpu" ||
        temperature != 0.3f || max_frames != 292 ||
        warm_runs < (profile ? 0 : 5) || warm_runs > 20 || expected_eos < -1 ||
        expected_eos >= max_frames || expected_frames < 1 ||
        expected_frames > max_frames) {
      throw std::runtime_error("canonical-v2 matched QNN benchmark contract range");
    }
    fs::create_directories(output_dir);
    auto packed = ReadFloats(cache_path, 6 * 2 * 126 * 16 * 64);
    auto token_ids = ReadInt64(token_path, 64);
    auto noise = ReadFloats(noise_path, 292 * 32);

    Ort::Env env(ORT_LOGGING_LEVEL_WARNING, "pocket-alba-static-benchmark");
    double load_start = Now();
    std::vector<Model> models;
    models.reserve(8);
    auto load = [&](const char *file, const char *name) -> Model & {
      std::cerr << "loading " << name << " hwm_kb=" << Hwm() << "\n" << std::flush;
      models.push_back(Load(env, root / file, name, backend, profile_dir, profile,
                            context_arm));
      std::cerr << "loaded " << name << " seconds=" << models.back().create_seconds
                << " hwm_kb=" << Hwm() << "\n" << std::flush;
      return models.back();
    };
    Model &text = load("text_conditioner.onnx", "text");
    Model &prefill = load("flow_prefill_text64.onnx", "prefill_text");
    Model &bos = load("flow_ar_bos1.onnx", "ar_bos");
    Model &ar = load("flow_ar_latent1.onnx", "ar_latent");
    Model &flow = load("flow.onnx", "flow");
    Model &decoder12 = load("mimi_decoder12.onnx", "decoder12");
    Model &decoder6 = load("mimi_decoder6.onnx", "decoder6");
    Model &decoder1 = load("mimi_decoder1.onnx", "decoder1");
    double setup_seconds = Now() - load_start;
    long setup_hwm_kb = Hwm();

    Ort::MemoryInfo memory = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    Ort::AllocatorWithDefaultOptions allocator;
    std::vector<float> s0{0.f}, t1{1.f};
    std::vector<Iteration> iterations;
    iterations.reserve(1 + warm_runs);

    for (int run_index = 0; run_index <= warm_runs; ++run_index) {
      Iteration record;
      record.kind = run_index == 0 ? "first" : "warm";
      record.wav_name = run_index == 0 ? "first.wav" : "warm-" + std::to_string(run_index) + ".wav";
      double generation_start = Now(), start = Now();

      // Full generation reset begins here: tokens rerun, immutable Alba cache
      // repacked into fresh tensors, all decoder state recreated, and the same
      // deterministic noise rows replayed.
      std::vector<Ort::Value> text_inputs;
      text_inputs.push_back(Tensor(memory, token_ids, {1, 64}));
      auto text_result = Run(text, text_inputs);
      record.text_seconds = Now() - start;
      auto text_embedding = CopyFloat(text_result[0]);

      auto state = InitFixedState(packed, allocator);
      std::vector<int64_t> positions(64);
      for (int i = 0; i < 64; ++i) positions[i] = 126 + i;
      auto text_value = Tensor(memory, text_embedding, {1, 64, 1024});
      start = Now();
      StaticCall(prefill, &text_value, positions, state, memory);
      record.prefill_seconds = Now() - start;

      std::vector<float> current(32), latents, logits;
      int eos = -1;
      for (int step = 0; step < max_frames; ++step) {
        positions = {190 + step};
        start = Now();
        std::vector<Ort::Value> result;
        if (step == 0) {
          result = StaticCall(bos, nullptr, positions, state, memory);
        } else {
          auto current_value = Tensor(memory, current, {1, 1, 32});
          result = StaticCall(ar, &current_value, positions, state, memory);
        }
        record.ar_seconds += Now() - start;
        float logit = result[1].GetTensorData<float>()[0];
        logits.push_back(logit);
        if (eos < 0 && logit > -4.f) eos = step;
        if (eos >= 0 && step >= eos + 3) break;

        std::vector<float> step_noise(noise.begin() + step * 32, noise.begin() + (step + 1) * 32);
        std::vector<Ort::Value> flow_inputs;
        flow_inputs.push_back(std::move(result[0]));
        flow_inputs.push_back(Tensor(memory, s0, {1, 1}));
        flow_inputs.push_back(Tensor(memory, t1, {1, 1}));
        flow_inputs.push_back(Tensor(memory, step_noise, {1, 32}));
        start = Now();
        auto flow_result = Run(flow, flow_inputs);
        record.flow_seconds += Now() - start;
        const float *direction = flow_result[0].GetTensorData<float>();
        for (int i = 0; i < 32; ++i) current[i] = step_noise[i] + direction[i];
        latents.insert(latents.end(), current.begin(), current.end());
      }

      record.eos_step = eos;
      record.latent_frames = int(latents.size() / 32);
      if (record.eos_step != expected_eos || record.latent_frames != expected_frames) {
        throw std::runtime_error("EOS/frame contract drift at iteration " + std::to_string(run_index));
      }
      auto decoder_state = InitDecoder(decoder12, allocator);
      std::vector<float> audio;
      int frame_start = 0;
      auto decode = [&](Model &model, int frames) {
        std::vector<float> chunk(latents.begin() + frame_start * 32,
                                 latents.begin() + (frame_start + frames) * 32);
        std::vector<Ort::Value> inputs;
        inputs.push_back(Tensor(memory, chunk, {1, frames, 32}));
        for (auto &value : decoder_state) inputs.push_back(std::move(value));
        double decode_start = Now();
        auto result = Run(model, inputs);
        record.decoder_seconds += Now() - decode_start;
        auto output = CopyFloat(result[0]);
        audio.insert(audio.end(), output.begin(), output.end());
        decoder_state.clear();
        for (int i = 0; i < 56; ++i) decoder_state.push_back(std::move(result[1 + i]));
        frame_start += frames;
      };
      while (frame_start < record.latent_frames) {
        int remaining = record.latent_frames - frame_start;
        if (remaining >= 12) decode(decoder12, 12);
        else if (remaining == 6) decode(decoder6, 6);
        else decode(decoder1, 1);
      }
      if (audio.size() != size_t(record.latent_frames * 1920)) {
        throw std::runtime_error("audio length");
      }
      bool finite = true, non_silent = false;
      for (float sample : audio) {
        finite = finite && std::isfinite(sample);
        non_silent = non_silent || sample != 0.f;
        record.peak = std::max(record.peak, std::abs(sample));
      }
      if (!finite || !non_silent || record.peak >= 1.f) {
        throw std::runtime_error("audio validity contract");
      }
      WriteWav(output_dir / record.wav_name, audio);
      record.samples = audio.size();
      record.generation_seconds = Now() - generation_start;
      record.vm_hwm_kb = Hwm();
      iterations.push_back(record);
    }

    std::vector<std::string> profile_paths;
    if (profile) {
      for (auto &model : models) {
        auto path = model.session->EndProfilingAllocated(allocator);
        profile_paths.emplace_back(path.get());
      }
    }
    std::cout << "{\"route\":\"fixed_alba_fallback_disabled_qnn_context_comparison"
              << "\",\"arm\":\"" << arm << "\",\"model_format\":\""
              << (context_arm ? "external_qnn_epcontext" : "source_onnx")
              << "\",\"source_onnx_unavailable\":" << (context_arm ? "true" : "false")
              << ",\"variant\":\"" << variant
              << "\",\"provider\":\"QNNExecutionProvider"
              << "\",\"cpu_fallback\":false"
              << ",\"graph_optimization\":\"basic"
              << "\",\"temperature\":" << temperature
              << ",\"seed\":0,\"noise_fixture\":\"NumPy RandomState MT19937 normal\""
              << ",\"canonical_transcript\":{\"version\":2,\"bytes\":226,\"sha256\":\"424b38073a00cf48e4c3ebaa246aec0b6549b3ed56a1bf7cfa26d037fb29db67\"}"
              << ",\"frontend\":{\"token_count\":64,\"token_fixture_sha256\":\"56d50c958627be19a7f2c86dde68a537a80f3f6d9087c16f55fde58c4d117c82\"}"
              << ",\"static_abi\":{\"capacity\":512,\"voice_positions\":126,\"text_positions\":64,\"frame_cap\":292,\"bos_absolute_position\":190}"
              << ",\"max_frames\":" << max_frames << ",\"warm_runs\":" << warm_runs
              << ",\"expected_eos_step\":" << expected_eos << ",\"expected_frames\":" << expected_frames
              << ",\"profiled\":" << (profile ? "true" : "false") << ",\"setup_seconds\":" << setup_seconds
              << ",\"setup_vm_hwm_kb\":" << setup_hwm_kb << ",\"iterations\":[";
    for (size_t i = 0; i < iterations.size(); ++i) {
      if (i) std::cout << ',';
      const auto &value = iterations[i];
      double audio_seconds = value.samples / 24000.0;
      std::cout << "{\"index\":" << i << ",\"kind\":\"" << value.kind
                << "\",\"wav\":\"" << value.wav_name
                << "\",\"generation_seconds\":" << value.generation_seconds
                << ",\"audio_seconds\":" << audio_seconds
                << ",\"rtf\":" << value.generation_seconds / audio_seconds
                << ",\"component_seconds\":{\"text\":" << value.text_seconds
                << ",\"prefill\":" << value.prefill_seconds
                << ",\"ar\":" << value.ar_seconds
                << ",\"flow\":" << value.flow_seconds
                << ",\"decoder\":" << value.decoder_seconds
                << "},\"eos_step\":" << value.eos_step
                << ",\"latent_frames\":" << value.latent_frames
                << ",\"samples\":" << value.samples
                << ",\"peak_float\":" << value.peak
                << ",\"vm_hwm_kb\":" << value.vm_hwm_kb << '}';
    }
    std::cout << "],\"state_reset\":{\"flow_cache\":\"fresh from immutable packed Alba for every iteration\","
                 "\"decoder\":\"fresh complete 56-tensor state for every iteration\","
                 "\"noise\":\"identical rows replayed from start for every iteration\","
                 "\"tokens\":\"text conditioner rerun from identical IDs every iteration\"},\"ort_profiles\":[";
    for (size_t i = 0; i < profile_paths.size(); ++i) {
      if (i) std::cout << ',';
      std::cout << '\"' << profile_paths[i] << '\"';
    }
    std::cout << "]}\n";
    return 0;
  } catch (const Ort::Exception &error) {
    std::cerr << "ORT " << error.GetOrtErrorCode() << ": " << error.what() << "\n";
    return 2;
  } catch (const std::exception &error) {
    std::cerr << "error: " << error.what() << "\n";
    return 3;
  }
}
