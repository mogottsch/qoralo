// Deterministic matched source-ONNX versus external-EPContext QNN runner.
// Every neural session is fail-closed QNN; pre/postprocessing remains CPU work.

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <sys/resource.h>
#include <unordered_map>
#include <vector>

#include "onnxruntime_cxx_api.h"

namespace {
using Clock = std::chrono::steady_clock;
constexpr int64_t kTextLength = 239;
constexpr int64_t kLatentLength = 238;
constexpr int64_t kLatentChannels = 144;
constexpr int64_t kTrimmedSamples = 729746;
constexpr int32_t kSampleRate = 44100;
constexpr int32_t kSpeakerId = 0;
constexpr uint64_t kSeed = 20260813;

struct Args {
  std::string arm, action, asset_root, source_root, context_root, transcript,
      output_wav, output_raw, backend, profile_dir;
};

Args ParseArgs(int argc, char **argv) {
  Args a;
  auto take = [&](int *i) {
    if (*i + 1 >= argc)
      throw std::runtime_error("missing value");
    return std::string(argv[++*i]);
  };
  for (int i = 1; i < argc; ++i) {
    const std::string k = argv[i];
    if (k == "--arm")
      a.arm = take(&i);
    else if (k == "--action")
      a.action = take(&i);
    else if (k == "--asset-root")
      a.asset_root = take(&i);
    else if (k == "--source-root")
      a.source_root = take(&i);
    else if (k == "--context-root")
      a.context_root = take(&i);
    else if (k == "--transcript")
      a.transcript = take(&i);
    else if (k == "--output-wav")
      a.output_wav = take(&i);
    else if (k == "--output-raw")
      a.output_raw = take(&i);
    else if (k == "--backend")
      a.backend = take(&i);
    else if (k == "--profile-dir")
      a.profile_dir = take(&i);
    else
      throw std::runtime_error("unknown argument: " + k);
  }
  const bool valid_arm = a.arm == "source" || a.arm == "context";
  const bool valid_action =
      a.action == "setup" || a.action == "e2e" || a.action == "proof";
  const bool output_required = a.action != "setup";
  const bool profile_required = a.action == "proof";
  if (!valid_arm || !valid_action || a.asset_root.empty() ||
      a.transcript.empty() || a.backend.empty() ||
      (a.arm == "source" && a.source_root.empty()) ||
      (a.arm == "context" && a.context_root.empty()) ||
      (output_required && (a.output_wav.empty() || a.output_raw.empty())) ||
      (profile_required && a.profile_dir.empty()))
    throw std::runtime_error("invalid arguments");
  return a;
}

double SecondsSince(Clock::time_point t) {
  return std::chrono::duration<double>(Clock::now() - t).count();
}
long MaxRssKb() {
  struct rusage u{};
  return getrusage(RUSAGE_SELF, &u) == 0 ? u.ru_maxrss : -1;
}

template <typename T>
std::vector<T> ReadExact(const std::filesystem::path &p, size_t n) {
  std::ifstream s(p, std::ios::binary | std::ios::ate);
  if (!s)
    throw std::runtime_error("cannot open " + p.string());
  const auto bytes = s.tellg();
  if (bytes < 0 || static_cast<size_t>(bytes) != n * sizeof(T))
    throw std::runtime_error("size mismatch " + p.string());
  s.seekg(0);
  std::vector<T> v(n);
  if (!s.read(reinterpret_cast<char *>(v.data()), bytes))
    throw std::runtime_error("short read");
  return v;
}
std::string ReadText(const std::filesystem::path &p) {
  std::ifstream s(p);
  if (!s)
    throw std::runtime_error("cannot open transcript");
  return {std::istreambuf_iterator<char>(s), {}};
}
void WriteRaw(const std::filesystem::path &p, const std::vector<float> &v) {
  std::ofstream s(p, std::ios::binary | std::ios::trunc);
  if (!s.write(reinterpret_cast<const char *>(v.data()),
               v.size() * sizeof(float)))
    throw std::runtime_error("raw write failed");
}
void Put16(std::ofstream &s, uint16_t v) {
  char b[2] = {char(v), char(v >> 8)};
  s.write(b, 2);
}
void Put32(std::ofstream &s, uint32_t v) {
  char b[4] = {char(v), char(v >> 8), char(v >> 16), char(v >> 24)};
  s.write(b, 4);
}
void WriteWav(const std::filesystem::path &p, const std::vector<float> &v) {
  if (v.size() != kTrimmedSamples)
    throw std::runtime_error("trim size mismatch");
  std::ofstream s(p, std::ios::binary | std::ios::trunc);
  const uint32_t data = static_cast<uint32_t>(v.size() * 2);
  s.write("RIFF", 4);
  Put32(s, 36 + data);
  s.write("WAVEfmt ", 8);
  Put32(s, 16);
  Put16(s, 1);
  Put16(s, 1);
  Put32(s, kSampleRate);
  Put32(s, kSampleRate * 2);
  Put16(s, 2);
  Put16(s, 16);
  s.write("data", 4);
  Put32(s, data);
  for (float x : v) {
    long q = std::lround(std::max(-1.0f, std::min(1.0f, x)) * 32767.0f);
    q = std::max(-32768L, std::min(32767L, q));
    Put16(s, static_cast<uint16_t>(static_cast<int16_t>(q)));
  }
  if (!s)
    throw std::runtime_error("wav write failed");
}

struct Prepared {
  std::vector<int64_t> ids;
  std::vector<float> text_mask, ttl, dp;
  std::string processed;
};
Prepared Prepare(const Args &a) {
  std::string text = ReadText(a.transcript);
  while (!text.empty() &&
         (text.back() == '\n' || text.back() == '\r' || text.back() == ' '))
    text.pop_back();
  if (text.empty() || !std::all_of(text.begin(), text.end(),
                                   [](unsigned char c) { return c < 128; }))
    throw std::runtime_error("pinned ASCII transcript required");
  std::string processed = "<en>" + text + "</en>";
  if (processed.size() != kTextLength)
    throw std::runtime_error("processed text length mismatch");
  auto indexer = ReadExact<int32_t>(
      std::filesystem::path(a.asset_root) / "unicode_indexer.bin", 65536);
  Prepared p;
  p.processed = processed;
  p.ids.reserve(processed.size());
  for (unsigned char c : processed) {
    if (indexer[c] < 0)
      throw std::runtime_error("unmapped character");
    p.ids.push_back(indexer[c]);
  }
  p.text_mask.assign(kTextLength, 1.0f);
  std::ifstream v(std::filesystem::path(a.asset_root) / "voice.bin",
                  std::ios::binary);
  if (!v)
    throw std::runtime_error("voice open failed");
  std::array<int64_t, 6> d{};
  v.read(reinterpret_cast<char *>(d.data()), 48);
  if (d != std::array<int64_t, 6>{1, 50, 256, 1, 8, 16})
    throw std::runtime_error("voice dimensions mismatch");
  std::vector<float> all(1 * 50 * 256 + 1 * 8 * 16);
  v.read(reinterpret_cast<char *>(all.data()), all.size() * sizeof(float));
  if (!v)
    throw std::runtime_error("voice read failed");
  p.ttl.assign(all.begin() + kSpeakerId * 50 * 256,
               all.begin() + (kSpeakerId + 1) * 50 * 256);
  const size_t base = 1 * 50 * 256 + kSpeakerId * 8 * 16;
  p.dp.assign(all.begin() + base, all.begin() + base + 8 * 16);
  return p;
}

Ort::SessionOptions Options(const std::string &profile, bool profiling,
                            const std::string &backend,
                            const std::string &context_descriptor) {
  Ort::SessionOptions o;
  o.SetIntraOpNumThreads(1);
  o.SetInterOpNumThreads(1);
  o.SetExecutionMode(ExecutionMode::ORT_SEQUENTIAL);
  o.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
  o.AddConfigEntry("session.disable_cpu_ep_fallback", "1");
  if (!context_descriptor.empty())
    o.AddConfigEntry("ep.context_file_path", context_descriptor.c_str());
  std::unordered_map<std::string, std::string> po = {
      {"backend_path", backend},
      {"offload_graph_io_quantization", "0"},
      {"htp_performance_mode", "burst"},
      {"soc_model", "43"}};
  if (profiling) {
    o.EnableProfiling(profile.c_str());
    po["profiling_level"] = "detailed";
    po["profiling_file_path"] = profile + ".qnn.csv";
  }
  o.AppendExecutionProvider("QNN", po);
  return o;
}
struct TimedSession {
  std::unique_ptr<Ort::Session> session;
  double create = 0;
  std::string profile;
  std::string model;
};
TimedSession Create(Ort::Env &env, const std::string &model,
                    const std::string &profile, bool profiling,
                    const std::string &backend,
                    const std::string &context_descriptor) {
  auto o = Options(profile, profiling, backend, context_descriptor);
  auto t = Clock::now();
  auto s = std::make_unique<Ort::Session>(env, model.c_str(), o);
  return {std::move(s), SecondsSince(t), profile, model};
}

template <typename T>
Ort::Value Tensor(std::vector<T> &v, const std::vector<int64_t> &shape,
                  Ort::MemoryInfo &mem) {
  return Ort::Value::CreateTensor<T>(mem, v.data(), v.size(), shape.data(),
                                     shape.size());
}
std::vector<float> RunFloat(Ort::Session &s,
                            const std::vector<const char *> &names,
                            std::vector<Ort::Value> &inputs,
                            const char *output) {
  const char *outs[] = {output};
  auto r = s.Run(Ort::RunOptions{nullptr}, names.data(), inputs.data(),
                 inputs.size(), outs, 1);
  if (r.size() != 1 || !r[0].IsTensor())
    throw std::runtime_error("invalid output");
  auto info = r[0].GetTensorTypeAndShapeInfo();
  const float *p = r[0].GetTensorData<float>();
  return {p, p + info.GetElementCount()};
}

struct Rng {
  uint64_t x = kSeed;
  uint64_t Next() {
    x ^= x >> 12;
    x ^= x << 25;
    x ^= x >> 27;
    return x * 2685821657736338717ULL;
  }
  double U() { return ((Next() >> 11) + 1.0) * (1.0 / 9007199254740993.0); }
};
std::vector<float> Noise() {
  Rng r;
  std::vector<float> v(kLatentChannels * kLatentLength);
  for (size_t i = 0; i < v.size(); i += 2) {
    double a = std::sqrt(-2 * std::log(r.U())), b = 6.283185307179586 * r.U();
    v[i] = float(a * std::cos(b));
    if (i + 1 < v.size())
      v[i + 1] = float(a * std::sin(b));
  }
  return v;
}
struct RunTimes {
  double duration = 0, text = 0, vector = 0, vocoder = 0, total = 0;
};
double Median(std::vector<double> v) {
  std::sort(v.begin(), v.end());
  return v[v.size() / 2];
}
} // namespace

int main(int argc, char **argv) {
  const auto process_entry = Clock::now();
  try {
    const Args a = ParseArgs(argc, argv);
    const bool profiling = a.action == "proof";
    if (profiling)
      std::filesystem::create_directories(a.profile_dir);
    Prepared p = Prepare(a);
    Ort::Env env(ORT_LOGGING_LEVEL_WARNING, "supertonic-qnn-context");
    auto model = [&](const std::string &source_name,
                     const std::string &context_name) {
      return (std::filesystem::path(a.arm == "source" ? a.source_root
                                                       : a.context_root) /
              (a.arm == "source" ? source_name : context_name))
          .string();
    };
    auto create = [&](const std::string &label, const std::string &source_name,
                      const std::string &context_name) {
      const std::string path = model(source_name, context_name);
      const std::string descriptor = a.arm == "context" ? path : "";
      const std::string profile = profiling ? a.profile_dir + "/" + label : "";
      return Create(env, path, profile, profiling, a.backend, descriptor);
    };
    const auto session_sequence_start = Clock::now();
    TimedSession duration = create("duration", "duration_predictor.onnx",
                                   "duration-context.onnx");
    TimedSession text =
        create("text", "text_encoder.onnx", "text-context.onnx");
    TimedSession vector = create("vector",
                                 "vector_estimator-stable-softplus.onnx",
                                 "vector-context.onnx");
    TimedSession vocoder =
        create("vocoder", "vocoder.onnx", "vocoder-context.onnx");
    const double session_sequence_seconds = SecondsSince(session_sequence_start);
    const double process_entry_to_ready_seconds = SecondsSince(process_entry);
    const long rss_after_sessions = MaxRssKb();
    const double session_total =
        duration.create + text.create + vector.create + vocoder.create;
    if (a.action == "setup") {
      std::cout << "{\n  \"result\": \"passed\",\n  \"arm\": \""
                << a.arm << "\",\n  \"action\": \"setup\",\n  "
                << "\"session_create_seconds\": {\"duration\": "
                << duration.create << ", \"text\": " << text.create
                << ", \"vector\": " << vector.create
                << ", \"vocoder\": " << vocoder.create
                << ", \"sum\": " << session_total
                << ", \"sequence\": " << session_sequence_seconds
                << "},\n  \"process_entry_to_ready_seconds\": "
                << process_entry_to_ready_seconds
                << ",\n  \"ready_definition\": \"all four QNN session "
                   "constructors returned and sessions remain alive\",\n  "
                << "\"fallback_disabled\": true,\n  "
                << "\"profiling_enabled\": false,\n  "
                << "\"max_rss_at_ready_kb\": " << rss_after_sessions
                << "\n}\n";
      return 0;
    }

    const int runs = a.action == "e2e" ? 6 : 1;
    auto mem = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    std::vector<float> final_wave;
    std::vector<RunTimes> times;
    float predicted_duration = 0;
    for (int run = 0; run < runs; ++run) {
      RunTimes rt;
      auto all = Clock::now();
      auto t = Clock::now();
      std::vector<Ort::Value> din;
      din.push_back(Tensor(p.ids, {1, kTextLength}, mem));
      din.push_back(Tensor(p.dp, {1, 8, 16}, mem));
      din.push_back(Tensor(p.text_mask, {1, 1, kTextLength}, mem));
      auto dv =
          RunFloat(*duration.session, {"text_ids", "style_dp", "text_mask"},
                   din, "duration");
      rt.duration = SecondsSince(t);
      if (dv.size() != 1 || !std::isfinite(dv[0]) || dv[0] <= 0)
        throw std::runtime_error("invalid duration");
      predicted_duration = dv[0];
      t = Clock::now();
      std::vector<Ort::Value> tin;
      tin.push_back(Tensor(p.ids, {1, kTextLength}, mem));
      tin.push_back(Tensor(p.ttl, {1, 50, 256}, mem));
      tin.push_back(Tensor(p.text_mask, {1, 1, kTextLength}, mem));
      auto emb = RunFloat(*text.session, {"text_ids", "style_ttl", "text_mask"},
                          tin, "text_emb");
      rt.text = SecondsSince(t);
      if (emb.size() != 256 * kTextLength)
        throw std::runtime_error("text output shape");
      auto latent = Noise();
      std::vector<float> latent_mask(kLatentLength, 1), total{5};
      t = Clock::now();
      for (int step = 0; step < 5; ++step) {
        std::vector<float> current{float(step)};
        std::vector<Ort::Value> vin;
        vin.push_back(Tensor(latent, {1, kLatentChannels, kLatentLength}, mem));
        vin.push_back(Tensor(emb, {1, 256, kTextLength}, mem));
        vin.push_back(Tensor(p.ttl, {1, 50, 256}, mem));
        vin.push_back(Tensor(latent_mask, {1, 1, kLatentLength}, mem));
        vin.push_back(Tensor(p.text_mask, {1, 1, kTextLength}, mem));
        vin.push_back(Tensor(current, {1}, mem));
        vin.push_back(Tensor(total, {1}, mem));
        latent =
            RunFloat(*vector.session,
                     {"noisy_latent", "text_emb", "style_ttl", "latent_mask",
                      "text_mask", "current_step", "total_step"},
                     vin, "denoised_latent");
        if (latent.size() != kLatentChannels * kLatentLength)
          throw std::runtime_error("vector shape");
      }
      rt.vector = SecondsSince(t);
      t = Clock::now();
      std::vector<Ort::Value> vi;
      vi.push_back(Tensor(latent, {1, kLatentChannels, kLatentLength}, mem));
      auto wave = RunFloat(*vocoder.session, {"latent"}, vi, "wav_tts");
      rt.vocoder = SecondsSince(t);
      if (wave.size() < kTrimmedSamples)
        throw std::runtime_error("short wave");
      final_wave.assign(wave.begin(), wave.begin() + kTrimmedSamples);
      rt.total = SecondsSince(all);
      times.push_back(rt);
    }
    WriteRaw(a.output_raw, final_wave);
    WriteWav(a.output_wav, final_wave);
    const long rss_after_runs = MaxRssKb();
    std::array<std::string, 4> profiles{};
    if (profiling) {
      Ort::AllocatorWithDefaultOptions alloc;
      auto end_profile = [&](TimedSession &session) {
        auto value = session.session->EndProfilingAllocated(alloc);
        return std::string(value.get());
      };
      profiles = {end_profile(duration), end_profile(text), end_profile(vector),
                  end_profile(vocoder)};
    }
    auto arr = [&](auto f) {
      std::cout << "[";
      for (size_t i = 0; i < times.size(); ++i) {
        if (i)
          std::cout << ",";
        std::cout << f(times[i]);
      }
      std::cout << "]";
    };
    const double audio_duration = double(kTrimmedSamples) / kSampleRate;
    std::vector<double> warm_seconds;
    std::vector<double> warm_rtfs;
    for (size_t i = 1; i < times.size(); ++i) {
      warm_seconds.push_back(times[i].total);
      warm_rtfs.push_back(times[i].total / audio_duration);
    }
    std::cout << "{\n  \"result\": \"passed\",\n  \"arm\": \"" << a.arm
              << "\",\n  \"action\": \"" << a.action << "\",\n  \"runs\": "
              << runs
              << ",\n  \"fixed_contract\": {\"text_length\": 239, "
                 "\"latent_length\": 238, \"trimmed_samples\": 729746, "
                 "\"sample_rate\": 44100, \"audio_duration_seconds\": "
              << audio_duration << ", \"seed\": 20260813},\n  "
              << "\"predicted_duration_seconds\": " << predicted_duration
              << ",\n  \"session_create_seconds\": {\"duration\": "
              << duration.create << ", \"text\": " << text.create
              << ", \"vector\": " << vector.create
              << ", \"vocoder\": " << vocoder.create
              << ", \"sum\": " << session_total
              << ", \"sequence\": " << session_sequence_seconds
              << "},\n  \"process_entry_to_ready_seconds\": "
              << process_entry_to_ready_seconds
              << ",\n  \"run_total_seconds\": ";
    arr([](auto &r) { return r.total; });
    std::cout << ",\n  \"rtf\": ";
    arr([&](auto &r) { return r.total / audio_duration; });
    std::cout << ",\n  \"duration_seconds\": ";
    arr([](auto &r) { return r.duration; });
    std::cout << ",\n  \"text_seconds\": ";
    arr([](auto &r) { return r.text; });
    std::cout << ",\n  \"vector_five_steps_seconds\": ";
    arr([](auto &r) { return r.vector; });
    std::cout << ",\n  \"vocoder_seconds\": ";
    arr([](auto &r) { return r.vocoder; });
    std::cout << ",\n  \"warm_total_median_seconds\": "
              << (warm_seconds.empty() ? 0 : Median(warm_seconds))
              << ",\n  \"warm_median_rtf\": "
              << (warm_rtfs.empty() ? 0 : Median(warm_rtfs))
              << ",\n  \"max_rss_after_sessions_kb\": " << rss_after_sessions
              << ",\n  \"max_rss_after_runs_kb\": " << rss_after_runs
              << ",\n  \"fallback_disabled\": true,\n  "
              << "\"profiling_enabled\": " << (profiling ? "true" : "false")
              << ",\n  \"profiles\": {\"duration\": \"" << profiles[0]
              << "\", \"text\": \"" << profiles[1] << "\", \"vector\": \""
              << profiles[2] << "\", \"vocoder\": \"" << profiles[3]
              << "\"}\n}\n";
    return 0;
  } catch (const Ort::Exception &e) {
    std::cerr << "ORT error " << e.GetOrtErrorCode() << ": " << e.what()
              << "\n";
    return 2;
  } catch (const std::exception &e) {
    std::cerr << "error: " << e.what() << "\n";
    return 3;
  }
}
