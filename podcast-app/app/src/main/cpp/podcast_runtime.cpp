#include <jni.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <dlfcn.h>
#include <filesystem>
#include <fstream>
#include <memory>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>
#ifdef PODCAST_WIRING_DIAGNOSTICS
#include <cstdio>
#include <unistd.h>
#endif

#include "onnxruntime_cxx_api.h"
#include "tensor_validation.h"

namespace {
constexpr int32_t kSampleRate = 44100;
constexpr int64_t kLatentChunkSamples = 3072;
constexpr int kSteps = 5;
constexpr uint64_t kSeed = 20260813;

std::string JString(JNIEnv *env, jstring value) {
  if (value == nullptr) throw std::runtime_error("null string argument");
  const char *chars = env->GetStringUTFChars(value, nullptr);
  if (chars == nullptr) throw std::runtime_error("string conversion failed");
  std::string result(chars);
  env->ReleaseStringUTFChars(value, chars);
  return result;
}

void Throw(JNIEnv *env, const std::string &message) {
  jclass type = env->FindClass("java/lang/RuntimeException");
  if (type != nullptr) env->ThrowNew(type, message.c_str());
}

template <typename T>
std::vector<T> ReadExact(const std::filesystem::path &path, size_t count) {
  std::ifstream input(path, std::ios::binary | std::ios::ate);
  if (!input) throw std::runtime_error("cannot open " + path.string());
  const auto bytes = input.tellg();
  if (bytes < 0 || static_cast<size_t>(bytes) != count * sizeof(T))
    throw std::runtime_error("size mismatch " + path.string());
  input.seekg(0);
  std::vector<T> result(count);
  if (!input.read(reinterpret_cast<char *>(result.data()), bytes))
    throw std::runtime_error("short read " + path.string());
  return result;
}

std::vector<uint32_t> DecodeUtf8(const std::string &text) {
  std::vector<uint32_t> output;
  for (size_t i = 0; i < text.size();) {
    const uint8_t first = static_cast<uint8_t>(text[i]);
    uint32_t codepoint = 0;
    size_t count = 0;
    if (first < 0x80) { codepoint = first; count = 1; }
    else if ((first & 0xE0) == 0xC0) { codepoint = first & 0x1F; count = 2; }
    else if ((first & 0xF0) == 0xE0) { codepoint = first & 0x0F; count = 3; }
    else if ((first & 0xF8) == 0xF0) { codepoint = first & 0x07; count = 4; }
    else throw std::runtime_error("invalid UTF-8 lead byte");
    if (i + count > text.size()) throw std::runtime_error("truncated UTF-8");
    for (size_t j = 1; j < count; ++j) {
      const uint8_t next = static_cast<uint8_t>(text[i + j]);
      if ((next & 0xC0) != 0x80) throw std::runtime_error("invalid UTF-8 continuation");
      codepoint = (codepoint << 6) | (next & 0x3F);
    }
    if ((count == 2 && codepoint < 0x80) || (count == 3 && codepoint < 0x800) ||
        (count == 4 && codepoint < 0x10000) || codepoint > 0x10FFFF ||
        (codepoint >= 0xD800 && codepoint <= 0xDFFF))
      throw std::runtime_error("non-canonical UTF-8");
    output.push_back(codepoint);
    i += count;
  }
  return output;
}

std::string NativeLibraryDirectory() {
  Dl_info info{};
  if (dladdr(reinterpret_cast<void *>(&NativeLibraryDirectory), &info) == 0 || info.dli_fname == nullptr)
    throw std::runtime_error("cannot locate native library directory");
  return std::filesystem::path(info.dli_fname).parent_path().string();
}

Ort::SessionOptions SessionOptions(const std::string &backend, const std::string &descriptor,
                                  const std::string &profile) {
  Ort::SessionOptions options;
  options.SetIntraOpNumThreads(1);
  options.SetInterOpNumThreads(1);
  options.SetExecutionMode(ExecutionMode::ORT_SEQUENTIAL);
  options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
  options.AddConfigEntry("session.disable_cpu_ep_fallback", "1");
  options.AddConfigEntry("ep.context_file_path", descriptor.c_str());
  std::unordered_map<std::string, std::string> provider = {
      {"backend_path", backend},
      {"offload_graph_io_quantization", "0"},
      {"htp_performance_mode", "burst"},
      {"soc_model", "43"},
  };
#ifdef PODCAST_WIRING_DIAGNOSTICS
  if (!profile.empty()) {
    options.EnableProfiling(profile.c_str());
    provider["profiling_level"] = "detailed";
    provider["profiling_file_path"] = profile + ".qnn.csv";
  }
#else
  if (!profile.empty()) throw std::runtime_error("profiling is debug-only");
#endif
  options.AppendExecutionProvider("QNN", provider);
  return options;
}

std::vector<int64_t> InputShape(Ort::Session &session, size_t index) {
  return session.GetInputTypeInfo(index).GetTensorTypeAndShapeInfo().GetShape();
}

struct Voice {
  std::vector<float> ttl;
  std::vector<float> dp;
};

Voice ReadVoice(const std::filesystem::path &path) {
  std::ifstream input(path, std::ios::binary | std::ios::ate);
  if (!input) throw std::runtime_error("cannot open voice asset");
  const auto bytes = input.tellg();
  input.seekg(0);
  std::array<int64_t, 6> dimensions{};
  input.read(reinterpret_cast<char *>(dimensions.data()), sizeof(dimensions));
  if (dimensions != std::array<int64_t, 6>{1, 50, 256, 1, 8, 16})
    throw std::runtime_error("voice dimensions mismatch");
  const size_t ttl_count = 50 * 256;
  const size_t dp_count = 8 * 16;
  if (bytes != static_cast<std::streamoff>(sizeof(dimensions) + (ttl_count + dp_count) * sizeof(float)))
    throw std::runtime_error("voice asset size mismatch");
  Voice voice{std::vector<float>(ttl_count), std::vector<float>(dp_count)};
  input.read(reinterpret_cast<char *>(voice.ttl.data()), voice.ttl.size() * sizeof(float));
  input.read(reinterpret_cast<char *>(voice.dp.data()), voice.dp.size() * sizeof(float));
  if (!input) throw std::runtime_error("voice asset short read");
  return voice;
}

struct Engine {
  explicit Engine(const std::string &pack_root, const std::string &voice_id,
                  const std::string &profile_directory)
      : root(pack_root), env(ORT_LOGGING_LEVEL_WARNING, "podcast-supertonic-qnn"),
        profile_dir(profile_directory) {
    if (voice_id != "M1/SID5") throw std::runtime_error("unsupported voice; expected M1/SID5");
    const std::string native_dir = NativeLibraryDirectory();
    setenv("ADSP_LIBRARY_PATH", native_dir.c_str(), 1);
    const std::string backend = native_dir + "/libQnnHtp.so";
    if (!std::filesystem::is_regular_file(backend)) throw std::runtime_error("APK is missing libQnnHtp.so");
    indexer = ReadExact<int32_t>(root / "assets/unicode-indexer.i32", 65536);
    voice = ReadVoice(root / "assets/voice.bin");
    auto create = [&](const char *name) {
      const std::string descriptor = (root / "contexts" / (std::string(name) + "-context.onnx")).string();
      if (!std::filesystem::is_regular_file(descriptor)) throw std::runtime_error("missing context descriptor " + descriptor);
      auto options = SessionOptions(backend, descriptor,
          profile_dir.empty() ? "" : (std::filesystem::path(profile_dir) / name).string());
      return std::make_unique<Ort::Session>(env, descriptor.c_str(), options);
    };
    duration = create("duration");
    text = create("text");
    vector = create("vector");
    vocoder = create("vocoder");

    const auto duration_text = InputShape(*duration, 0);
    const auto text_text = InputShape(*text, 0);
    const auto vector_latent = InputShape(*vector, 0);
    if (duration_text.size() != 2 || text_text.size() != 2 || duration_text != text_text ||
        vector_latent.size() != 3 || duration_text[0] != 1 || vector_latent[0] != 1)
      throw std::runtime_error("unsupported QNN context input shapes");
    text_length = duration_text[1];
    latent_channels = vector_latent[1];
    latent_length = vector_latent[2];
    if (text_length <= 9 || latent_channels <= 0 || latent_length <= 0)
      throw std::runtime_error("invalid QNN context capacities");
  }

  ~Engine() {
#ifdef PODCAST_WIRING_DIAGNOSTICS
    if (!profile_dir.empty()) {
      Ort::AllocatorWithDefaultOptions allocator;
      for (auto *session : {duration.get(), text.get(), vector.get(), vocoder.get()}) {
        if (session != nullptr) {
          try { session->EndProfilingAllocated(allocator); }
          catch (const std::exception &) { /* Missing evidence is classified by the harness, not fabricated. */ }
        }
      }
    }
#endif
  }

  std::filesystem::path root;
  Ort::Env env;
  std::string profile_dir;
  std::unique_ptr<Ort::Session> duration, text, vector, vocoder;
  std::vector<int32_t> indexer;
  Voice voice;
  int64_t text_length = 0;
  int64_t latent_channels = 0;
  int64_t latent_length = 0;
};

template <typename T>
Ort::Value Tensor(std::vector<T> &data, const std::vector<int64_t> &shape, Ort::MemoryInfo &memory) {
  return Ort::Value::CreateTensor<T>(memory, data.data(), data.size(), shape.data(), shape.size());
}

std::vector<float> RunFloat(Ort::Session &session, const std::vector<const char *> &names,
                            std::vector<Ort::Value> &inputs, const char *output_name) {
  const char *outputs[] = {output_name};
  auto values = session.Run(Ort::RunOptions{nullptr}, names.data(), inputs.data(), inputs.size(), outputs, 1);
  if (values.size() != 1 || !values[0].IsTensor()) throw std::runtime_error("invalid QNN output");
  auto info = values[0].GetTensorTypeAndShapeInfo();
  const float *data = values[0].GetTensorData<float>();
  std::vector<float> result(data, data + info.GetElementCount());
  RequireAllFinite(result, output_name);
  return result;
}

struct Rng {
  uint64_t state;
  uint64_t Next() { state ^= state >> 12; state ^= state << 25; state ^= state >> 27; return state * 2685821657736338717ULL; }
  double Uniform() { return ((Next() >> 11) + 1.0) * (1.0 / 9007199254740993.0); }
};

uint64_t StableSeed(const std::string &chapter_id) {
  uint64_t hash = 1469598103934665603ULL;
  for (unsigned char value : chapter_id) { hash ^= value; hash *= 1099511628211ULL; }
  return hash ^ kSeed;
}

std::vector<float> Noise(int64_t channels, int64_t length, int64_t active_length, uint64_t seed) {
  Rng rng{seed};
  std::vector<float> values(static_cast<size_t>(channels * length), 0.0f);
  for (int64_t channel = 0; channel < channels; ++channel) {
    for (int64_t position = 0; position < active_length; position += 2) {
      const double radius = std::sqrt(-2 * std::log(rng.Uniform()));
      const double angle = 6.283185307179586 * rng.Uniform();
      values[static_cast<size_t>(channel * length + position)] = static_cast<float>(radius * std::cos(angle));
      if (position + 1 < active_length)
        values[static_cast<size_t>(channel * length + position + 1)] = static_cast<float>(radius * std::sin(angle));
    }
  }
  return values;
}

struct PreparedText {
  std::vector<int64_t> ids;
  std::vector<float> mask;
};

PreparedText PrepareText(Engine &engine, const std::string &text) {
  std::string normalized = text;
  while (!normalized.empty() && std::isspace(static_cast<unsigned char>(normalized.back()))) normalized.pop_back();
  if (normalized.empty()) throw std::runtime_error("complete chapter is empty");
  auto codepoints = DecodeUtf8("<en>" + normalized + "</en>");
  if (static_cast<int64_t>(codepoints.size()) > engine.text_length)
    throw std::runtime_error("complete chapter exceeds compiled QNN text capacity; no splitting was attempted");
  PreparedText result;
  result.ids.assign(static_cast<size_t>(engine.text_length), 0);
  result.mask.assign(static_cast<size_t>(engine.text_length), 0.0f);
  for (size_t index = 0; index < codepoints.size(); ++index) {
    if (codepoints[index] >= engine.indexer.size() || engine.indexer[codepoints[index]] < 0)
      throw std::runtime_error("complete chapter contains an unmapped character");
    result.ids[index] = engine.indexer[codepoints[index]];
    result.mask[index] = 1.0f;
  }
  return result;
}

void Put16(std::ofstream &output, uint16_t value) {
  const char bytes[2] = {static_cast<char>(value), static_cast<char>(value >> 8)};
  output.write(bytes, 2);
}
void Put32(std::ofstream &output, uint32_t value) {
  const char bytes[4] = {static_cast<char>(value), static_cast<char>(value >> 8),
                         static_cast<char>(value >> 16), static_cast<char>(value >> 24)};
  output.write(bytes, 4);
}
void WriteWav(const std::filesystem::path &path, const std::vector<float> &wave, size_t samples) {
  if (samples == 0 || samples > wave.size() || samples > (UINT32_MAX - 36) / 2)
    throw std::runtime_error("invalid chapter waveform length");
  std::ofstream output(path, std::ios::binary | std::ios::trunc);
  const uint32_t data_bytes = static_cast<uint32_t>(samples * 2);
  output.write("RIFF", 4); Put32(output, 36 + data_bytes); output.write("WAVEfmt ", 8); Put32(output, 16);
  Put16(output, 1); Put16(output, 1); Put32(output, kSampleRate); Put32(output, kSampleRate * 2);
  Put16(output, 2); Put16(output, 16); output.write("data", 4); Put32(output, data_bytes);
  RequireAllFinite(wave, "vocoder waveform");
  for (size_t index = 0; index < samples; ++index) {
    const float clamped = std::max(-1.0f, std::min(1.0f, wave[index]));
    const long quantized = std::lround(clamped * 32767.0f);
    Put16(output, static_cast<uint16_t>(static_cast<int16_t>(std::max(-32768L, std::min(32767L, quantized)))));
  }
  output.flush();
  if (!output) throw std::runtime_error("chapter WAV write failed");
}

void Render(Engine &engine, const std::string &chapter_id, const std::string &chapter_text,
            const std::filesystem::path &output_path) {
  PreparedText prepared = PrepareText(engine, chapter_text);
  auto memory = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);

  std::vector<Ort::Value> duration_inputs;
  duration_inputs.push_back(Tensor(prepared.ids, {1, engine.text_length}, memory));
  duration_inputs.push_back(Tensor(engine.voice.dp, {1, 8, 16}, memory));
  duration_inputs.push_back(Tensor(prepared.mask, {1, 1, engine.text_length}, memory));
  auto duration = RunFloat(*engine.duration, {"text_ids", "style_dp", "text_mask"}, duration_inputs, "duration");
  if (duration.size() != 1 || !std::isfinite(duration[0]) || duration[0] <= 0)
    throw std::runtime_error("invalid Supertonic duration");
  const int64_t wav_samples = static_cast<int64_t>(std::floor(duration[0] * kSampleRate));
  const int64_t active_latent = (wav_samples + kLatentChunkSamples - 1) / kLatentChunkSamples;
  if (active_latent <= 0 || active_latent > engine.latent_length)
    throw std::runtime_error("complete chapter exceeds compiled QNN latent capacity; no splitting was attempted");

  std::vector<Ort::Value> text_inputs;
  text_inputs.push_back(Tensor(prepared.ids, {1, engine.text_length}, memory));
  text_inputs.push_back(Tensor(engine.voice.ttl, {1, 50, 256}, memory));
  text_inputs.push_back(Tensor(prepared.mask, {1, 1, engine.text_length}, memory));
  auto embedding = RunFloat(*engine.text, {"text_ids", "style_ttl", "text_mask"}, text_inputs, "text_emb");
  if (embedding.size() != static_cast<size_t>(256 * engine.text_length))
    throw std::runtime_error("Supertonic text embedding shape mismatch");

  std::vector<float> latent_mask(static_cast<size_t>(engine.latent_length), 0.0f);
  std::fill(latent_mask.begin(), latent_mask.begin() + active_latent, 1.0f);
  auto latent = Noise(engine.latent_channels, engine.latent_length, active_latent, StableSeed(chapter_id));
  std::vector<float> total_step{static_cast<float>(kSteps)};
  for (int step = 0; step < kSteps; ++step) {
    std::vector<float> current_step{static_cast<float>(step)};
    std::vector<Ort::Value> vector_inputs;
    vector_inputs.push_back(Tensor(latent, {1, engine.latent_channels, engine.latent_length}, memory));
    vector_inputs.push_back(Tensor(embedding, {1, 256, engine.text_length}, memory));
    vector_inputs.push_back(Tensor(engine.voice.ttl, {1, 50, 256}, memory));
    vector_inputs.push_back(Tensor(latent_mask, {1, 1, engine.latent_length}, memory));
    vector_inputs.push_back(Tensor(prepared.mask, {1, 1, engine.text_length}, memory));
    vector_inputs.push_back(Tensor(current_step, {1}, memory));
    vector_inputs.push_back(Tensor(total_step, {1}, memory));
    latent = RunFloat(*engine.vector,
                      {"noisy_latent", "text_emb", "style_ttl", "latent_mask", "text_mask", "current_step", "total_step"},
                      vector_inputs, "denoised_latent");
    if (latent.size() != static_cast<size_t>(engine.latent_channels * engine.latent_length))
      throw std::runtime_error("Supertonic vector output shape mismatch");
  }

  std::vector<Ort::Value> vocoder_inputs;
  vocoder_inputs.push_back(Tensor(latent, {1, engine.latent_channels, engine.latent_length}, memory));
  auto wave = RunFloat(*engine.vocoder, {"latent"}, vocoder_inputs, "wav_tts");
  if (wav_samples > static_cast<int64_t>(wave.size())) throw std::runtime_error("Supertonic vocoder output is too short");
  std::filesystem::create_directories(output_path.parent_path());
  WriteWav(output_path, wave, static_cast<size_t>(wav_samples));
}

jlong NativeCreate(JNIEnv *env, jclass, jstring pack_root, jstring voice_id, jstring profiles) {
  try {
    return reinterpret_cast<jlong>(new Engine(JString(env, pack_root), JString(env, voice_id), JString(env, profiles)));
  } catch (const Ort::Exception &error) {
    Throw(env, std::string("ORT/QNN initialization failed: ") + error.what());
  } catch (const std::exception &error) {
    Throw(env, error.what());
  }
  return 0;
}

jstring NativeProvenance(JNIEnv *env, jclass, jlong handle) {
  auto *engine = reinterpret_cast<Engine *>(handle);
  if (engine == nullptr) { Throw(env, "Supertonic engine is closed"); return nullptr; }
  const std::string json =
      "{\"runtimeApiVersion\":1,\"model\":\"SUPERTONIC_3_EXTERNAL_CONTEXT\","
      "\"backend\":\"QNN_HTP\",\"runtimeVersion\":\"ONNX Runtime 1.27.1 / QAIRT 2.49.0.260730\","
      "\"cpuFallbackEnabled\":false,\"readyComponents\":[\"duration_context\",\"text_context\","
      "\"vector_context\",\"vocoder_context\",\"htp\",\"text_length=" +
      std::to_string(engine->text_length) + "\",\"latent_length=" +
      std::to_string(engine->latent_length) + "\",\"latent_channels=" +
      std::to_string(engine->latent_channels) + "\",\"diffusion_steps=5\",\"sample_rate_hz=44100\",\"channel_count=1\",\"pcm_bits=16\"]}";
  return env->NewStringUTF(json.c_str());
}

jboolean NativeRender(JNIEnv *env, jclass, jlong handle, jstring chapter_id, jstring text, jstring output) {
  auto *engine = reinterpret_cast<Engine *>(handle);
  if (engine == nullptr) { Throw(env, "Supertonic engine is closed"); return JNI_FALSE; }
  try {
    Render(*engine, JString(env, chapter_id), JString(env, text), JString(env, output));
    return JNI_TRUE;
  } catch (const Ort::Exception &error) {
    Throw(env, std::string("ORT/QNN render failed: ") + error.what());
  } catch (const std::exception &error) {
    Throw(env, error.what());
  }
  return JNI_FALSE;
}

void NativeDestroy(JNIEnv *, jclass, jlong handle) { delete reinterpret_cast<Engine *>(handle); }

#ifdef PODCAST_WIRING_DIAGNOSTICS
void DurationDiagnosticLog(void *, OrtLoggingLevel severity, const char *category,
                           const char *logid, const char *location, const char *message) {
  std::fprintf(stderr, "[duration-load ort severity=%d category=%s id=%s location=%s] %s\n",
               static_cast<int>(severity), category, logid, location, message);
  std::fflush(stderr);
}

// Deliberately isolated from Engine/Render: one constructor, zero Session::Run calls.
jstring NativeDurationLoadOnly(JNIEnv *env, jclass, jstring pack_root, jstring evidence_dir) {
  try {
    const auto root = std::filesystem::path(JString(env, pack_root));
    const auto output = std::filesystem::path(JString(env, evidence_dir));
    const std::string native_dir = NativeLibraryDirectory();
    const std::string descriptor = (root / "contexts/duration-context.onnx").string();
    const std::string backend = native_dir + "/libQnnHtp.so";
    const char *old_adsp = std::getenv("ADSP_LIBRARY_PATH");
    const char *ld_path = std::getenv("LD_LIBRARY_PATH");
    std::fprintf(stderr, "[duration-load] pid=%d uid=%d gid=%d; ORT runtime=%s; ADSP before=%s; LD_LIBRARY_PATH=%s\n",
                 getpid(), getuid(), getgid(), OrtGetApiBase()->GetVersionString(),
                 old_adsp ? old_adsp : "<unset>", ld_path ? ld_path : "<unset>");
    Dl_info ort_info{};
    if (dladdr(reinterpret_cast<void *>(&OrtGetApiBase), &ort_info)) {
      std::fprintf(stderr, "[duration-load] loaded ORT library=%s\n", ort_info.dli_fname);
    }
    // Baseline exactly matches the failed app. Do NOT append vendor search paths here.
    setenv("ADSP_LIBRARY_PATH", native_dir.c_str(), 1);
    std::fprintf(stderr, "[duration-load] ADSP effective=%s; descriptor=%s; backend=%s\n",
                 std::getenv("ADSP_LIBRARY_PATH"), descriptor.c_str(), backend.c_str());
    std::fprintf(stderr, "[duration-load] provider options: soc_model=43 htp_performance_mode=burst offload_graph_io_quantization=0; session.disable_cpu_ep_fallback=1\n");
    std::fprintf(stderr, "[duration-load] device config expectation from pinned ORT source: SOC=43; ARCH not requested; not a direct deviceCreate-struct capture\n");
    for (const char *path : {"/vendor/lib64/libcdsprpc.so", "/vendor/lib/libcdsprpc.so",
                             "/vendor/lib/rfsa/adsp", "/vendor/dsp/cdsp", "/system/lib/rfsa/adsp", "/vendor/dsp"}) {
      std::fprintf(stderr, "[duration-load] filesystem R_OK=%d path=%s (not linker namespace proof)\n", access(path, R_OK), path);
    }
    std::fflush(stderr);
    Ort::Env ort_env(ORT_LOGGING_LEVEL_VERBOSE, "podcast-duration-load-only", DurationDiagnosticLog, nullptr);
    auto options = SessionOptions(backend, descriptor, (output / "duration-profile").string());
    options.SetLogSeverityLevel(0);
    Ort::ThrowOnError(Ort::GetApi().SetSessionLogVerbosityLevel(options, 1));
    options.SetLogId("duration-load-only");
    std::fprintf(stderr, "[duration-load] constructor BEGIN; no other session or neural execution is permitted\n");
    std::fflush(stderr);
    {
      Ort::Session duration_session(ort_env, descriptor.c_str(), options);
      std::fprintf(stderr, "[duration-load] constructor RETURNED; inputCount=%zu outputCount=%zu; Session::Run never called\n",
                   duration_session.GetInputCount(), duration_session.GetOutputCount());
      Ort::AllocatorWithDefaultOptions allocator;
      auto profile = duration_session.EndProfilingAllocated(allocator);
      std::fprintf(stderr, "[duration-load] profile=%s\n", profile.get());
    }
    std::fflush(stderr);
    return env->NewStringUTF("duration_session_created_and_closed_without_run");
  } catch (const Ort::Exception &error) {
    std::fprintf(stderr, "[duration-load] ORT error code=%d: %s\n", error.GetOrtErrorCode(), error.what());
    std::fflush(stderr);
    Throw(env, std::string("duration-load-only ORT error: ") + error.what());
  } catch (const std::exception &error) { Throw(env, error.what()); }
  return nullptr;
}
#endif

static JNINativeMethod kMethods[] = {
    {const_cast<char *>("create"), const_cast<char *>("(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)J"), reinterpret_cast<void *>(NativeCreate)},
    {const_cast<char *>("provenance"), const_cast<char *>("(J)Ljava/lang/String;"), reinterpret_cast<void *>(NativeProvenance)},
    {const_cast<char *>("renderCompleteChapter"), const_cast<char *>("(JLjava/lang/String;Ljava/lang/String;Ljava/lang/String;)Z"), reinterpret_cast<void *>(NativeRender)},
    {const_cast<char *>("destroy"), const_cast<char *>("(J)V"), reinterpret_cast<void *>(NativeDestroy)},
};
}  // namespace

JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM *vm, void *) {
  JNIEnv *env = nullptr;
  if (vm->GetEnv(reinterpret_cast<void **>(&env), JNI_VERSION_1_6) != JNI_OK) return JNI_ERR;
  jclass type = env->FindClass("dev/vibevoice/podcast/runtime/SupertonicNative");
  if (type == nullptr) return JNI_ERR;
  if (env->RegisterNatives(type, kMethods, sizeof(kMethods) / sizeof(kMethods[0])) != JNI_OK) return JNI_ERR;
#ifdef PODCAST_WIRING_DIAGNOSTICS
  jclass diagnostic_type = env->FindClass("dev/vibevoice/podcast/wiring/DurationLoadNative");
  if (diagnostic_type == nullptr) return JNI_ERR;
  JNINativeMethod diagnostic_methods[] = {
      {const_cast<char *>("probe"), const_cast<char *>("(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;"),
       reinterpret_cast<void *>(NativeDurationLoadOnly)},
  };
  if (env->RegisterNatives(diagnostic_type, diagnostic_methods, 1) != JNI_OK) return JNI_ERR;
#endif
  return JNI_VERSION_1_6;
}
