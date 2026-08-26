// Experiment 0025 canonical Android LLM benchmark runner.
// Built against pinned LiteRT-LM v0.16.1 (924e79c91542761242244e4f1651851f822e4cbb).

#include <sys/resource.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <mutex>
#include <optional>
#include <sstream>
#include <string>
#include <thread>
#include <utility>
#include <variant>
#include <vector>

#include "absl/base/log_severity.h"
#include "absl/flags/flag.h"
#include "absl/flags/parse.h"
#include "absl/functional/any_invocable.h"
#include "absl/log/absl_check.h"
#include "absl/log/globals.h"
#include "absl/status/status.h"
#include "absl/status/status_macros.h"
#include "absl/status/statusor.h"
#include "absl/time/time.h"
#include "nlohmann/json.hpp"
#include "runtime/core/session_utils.h"
#include "runtime/engine/engine.h"
#include "runtime/engine/engine_factory.h"
#include "runtime/engine/engine_settings.h"
#include "runtime/engine/io_types.h"
#include "runtime/executor/llm_executor_settings.h"

ABSL_FLAG(std::string, backend, "cpu", "LiteRT-LM backend: cpu or gpu.");
ABSL_FLAG(std::string, model_path, "", "Exact .litertlm artifact path.");
ABSL_FLAG(std::string, workload_dir, "", "Directory containing canonical workload JSON files.");
ABSL_FLAG(std::string, output_dir, "", "Owned output directory.");
ABSL_FLAG(std::string, arm_id, "", "Stable arm identifier.");
ABSL_FLAG(std::string, cache_dir, ":nocache", "LiteRT cache directory or :nocache.");
ABSL_FLAG(int, max_num_tokens, 8192, "Session KV capacity.");
ABSL_FLAG(int, max_output_tokens, 2048, "Maximum generated tokens per canonical request.");
ABSL_FLAG(int, num_cpu_threads, 4, "CPU executor threads.");
ABSL_FLAG(int, request_timeout_seconds, 1800, "Per-request timeout.");
ABSL_FLAG(bool, smoke_only, false, "Run one bounded canonical-short smoke.");
ABSL_FLAG(bool, reset_probe_only, false, "Run exactly two bounded canonical-short requests to probe reset semantics.");
ABSL_FLAG(std::string, reset_mode, "fresh_session", "Request isolation mode: rewind (diagnostic only) or fresh_session.");
ABSL_FLAG(int, smoke_max_output_tokens, 64, "Smoke/probe generated-token ceiling.");

namespace {

using Clock = std::chrono::steady_clock;
using Json = nlohmann::ordered_json;
using litert::lm::Backend;
using litert::lm::BenchmarkInfo;
using litert::lm::BenchmarkTurnData;
using litert::lm::DecodeConfig;
using litert::lm::Engine;
using litert::lm::EngineFactory;
using litert::lm::EngineSettings;
using litert::lm::InputData;
using litert::lm::InputText;
using litert::lm::ModelAssets;
using litert::lm::Responses;
using litert::lm::SessionConfig;
using litert::lm::TaskState;

constexpr char kContractId[] = "android-llm-inference-v1";
constexpr char kRuntimeRevision[] = "924e79c91542761242244e4f1651851f822e4cbb";
constexpr char kRenderPolicy[] = "gemma4-no-tools-no-thinking-system-user-v1";

struct MemorySnapshot {
  int64_t pss_bytes = -1;
  int64_t vm_hwm_bytes = -1;
};

int64_t ReadKbField(const std::filesystem::path& path, const std::string& field) {
  std::ifstream stream(path);
  std::string line;
  while (std::getline(stream, line)) {
    if (line.rfind(field, 0) != 0) continue;
    std::istringstream values(line.substr(field.size()));
    int64_t kb = -1;
    values >> kb;
    return kb < 0 ? -1 : kb * 1024;
  }
  return -1;
}

MemorySnapshot ReadMemory() {
  return {
      .pss_bytes = ReadKbField("/proc/self/smaps_rollup", "Pss:"),
      .vm_hwm_bytes = ReadKbField("/proc/self/status", "VmHWM:"),
  };
}

Json CollectGpuProviderBinding() {
  Json mapped_libraries = Json::array();
  bool accelerator_library_loaded = false;
  bool gpu_driver_library_loaded = false;
  std::ifstream maps("/proc/self/maps");
  std::string line;
  while (std::getline(maps, line)) {
    if (line.find("libLiteRtGpuAccelerator.so") != std::string::npos) {
      accelerator_library_loaded = true;
      mapped_libraries.push_back(line);
    } else if (line.find("libOpenCL") != std::string::npos ||
               line.find("libGLES") != std::string::npos ||
               line.find("libvulkan") != std::string::npos) {
      gpu_driver_library_loaded = true;
      mapped_libraries.push_back(line);
    }
  }

  Json gpu_device_fds = Json::array();
  std::error_code iterator_error;
  for (const auto& entry :
       std::filesystem::directory_iterator("/proc/self/fd", iterator_error)) {
    std::error_code link_error;
    const auto target = std::filesystem::read_symlink(entry.path(), link_error);
    if (link_error) continue;
    const std::string value = target.string();
    if (value.find("kgsl") != std::string::npos ||
        value.find("mali") != std::string::npos ||
        value.find("dri/render") != std::string::npos) {
      gpu_device_fds.push_back(value);
    }
  }
  return {
      {"requested_neural_backend", "gpu"},
      {"litert_hardware_accelerators", "kGpu only (no CPU fallback bit)"},
      {"fully_delegated_to_single_delegate_hint", true},
      {"accelerator_library_loaded", accelerator_library_loaded},
      {"gpu_driver_library_loaded", gpu_driver_library_loaded},
      {"gpu_device_fds", gpu_device_fds},
      {"mapped_provider_and_driver_libraries", mapped_libraries},
      {"binding_proven",
       accelerator_library_loaded && gpu_driver_library_loaded},
      {"proof_boundary",
       "Captured from the benchmark process after GPU Engine compilation and initial Session creation; LiteRT-LM configures the GPU arm with HwAccelerators::kGpu only and a fully-delegated single-delegate hint."},
  };
}

class MemoryMonitor {
 public:
  ~MemoryMonitor() {
    if (worker_.joinable()) {
      running_.store(false);
      worker_.join();
    }
  }

  void Start() {
    running_.store(true);
    worker_ = std::thread([this] {
      while (running_.load()) {
        const auto sample = ReadMemory();
        {
          std::lock_guard<std::mutex> lock(mu_);
          if (sample.pss_bytes >= 0) peak_pss_bytes_ = std::max(peak_pss_bytes_, sample.pss_bytes);
          if (sample.vm_hwm_bytes >= 0) peak_vm_hwm_bytes_ = std::max(peak_vm_hwm_bytes_, sample.vm_hwm_bytes);
          ++samples_;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
      }
      const auto sample = ReadMemory();
      std::lock_guard<std::mutex> lock(mu_);
      if (sample.pss_bytes >= 0) peak_pss_bytes_ = std::max(peak_pss_bytes_, sample.pss_bytes);
      if (sample.vm_hwm_bytes >= 0) peak_vm_hwm_bytes_ = std::max(peak_vm_hwm_bytes_, sample.vm_hwm_bytes);
      ++samples_;
    });
  }

  Json Stop() {
    running_.store(false);
    if (worker_.joinable()) worker_.join();
    struct rusage usage {};
    const int rusage_status = getrusage(RUSAGE_SELF, &usage);
    std::lock_guard<std::mutex> lock(mu_);
    return {
        {"peak_sampled_pss_bytes", peak_pss_bytes_ >= 0 ? Json(peak_pss_bytes_) : Json(nullptr)},
        {"peak_sampled_vm_hwm_bytes", peak_vm_hwm_bytes_ >= 0 ? Json(peak_vm_hwm_bytes_) : Json(nullptr)},
        {"ru_maxrss_bytes", rusage_status == 0 ? Json(static_cast<int64_t>(usage.ru_maxrss) * 1024) : Json(nullptr)},
        {"sampling_interval_seconds", 0.1},
        {"sample_count", samples_},
        {"lifecycle", "benchmark process from immediately before setup through final request"},
    };
  }

 private:
  std::atomic<bool> running_{false};
  std::thread worker_;
  std::mutex mu_;
  int64_t peak_pss_bytes_ = -1;
  int64_t peak_vm_hwm_bytes_ = -1;
  int64_t samples_ = 0;
};

std::string ReadFile(const std::filesystem::path& path) {
  std::ifstream stream(path, std::ios::binary);
  std::ostringstream buffer;
  buffer << stream.rdbuf();
  return buffer.str();
}

absl::Status WriteFile(const std::filesystem::path& path, const std::string& value) {
  std::ofstream stream(path, std::ios::binary);
  if (!stream) return absl::InternalError("could not open output file: " + path.string());
  stream.write(value.data(), value.size());
  if (!stream) return absl::InternalError("could not write output file: " + path.string());
  return absl::OkStatus();
}

double Seconds(Clock::duration duration) {
  return std::chrono::duration<double>(duration).count();
}

double Seconds(absl::Duration duration) { return absl::ToDoubleSeconds(duration); }

std::string Trim(const std::string& text) {
  const auto first = text.find_first_not_of(" \t\n\r");
  if (first == std::string::npos) return "";
  const auto last = text.find_last_not_of(" \t\n\r");
  return text.substr(first, last - first + 1);
}

// Audited specialization of both pinned deployment templates for exactly one
// system message, one user message, no tools, add_generation_prompt=true, and
// enable_thinking=false. tools/thinking/multi-turn branches are out of scope.
absl::StatusOr<std::string> RenderCanonicalPrompt(const Json& workload) {
  if (workload.value("workload_id", "") != kContractId) {
    return absl::InvalidArgumentError("workload_id mismatch");
  }
  if (!workload.contains("messages") || workload["messages"].size() != 2 ||
      workload["messages"][0].value("role", "") != "system" ||
      workload["messages"][1].value("role", "") != "user") {
    return absl::InvalidArgumentError("canonical messages must be exactly system then user");
  }
  const auto& generation = workload["generation"];
  if (generation.value("strategy", "") != "greedy" || generation.value("do_sample", true) ||
      generation.value("max_new_tokens", -1) != 2048 ||
      !generation.value("model_eos_enabled", false)) {
    return absl::InvalidArgumentError("canonical generation contract mismatch");
  }
  const std::string system = Trim(workload["messages"][0].value("content", ""));
  const std::string user = Trim(workload["messages"][1].value("content", ""));
  if (system.empty() || user.empty()) return absl::InvalidArgumentError("empty canonical message");
  return "<bos><|turn>system\n" + system + "<turn|>\n<|turn>user\n" + user +
         "<turn|>\n<|turn>model\n";
}

absl::StatusOr<std::vector<int>> GetEffectiveTokenIds(
    Engine& engine, const SessionConfig& session_config,
    const std::string& rendered_prompt) {
  auto& tokenizer =
      const_cast<litert::support::Tokenizer&>(engine.GetTokenizer());
  std::vector<InputData> contents;
  contents.emplace_back(InputText(rendered_prompt));
  ABSL_ASSIGN_OR_RETURN(
      auto templated,
      litert::lm::ApplyPromptTemplates(contents, litert::lm::ContentType::kNA,
                                       session_config, tokenizer,
                                       /*is_first_turn=*/true));
  ABSL_ASSIGN_OR_RETURN(
      auto preprocessed,
      litert::lm::PreprocessContents(templated, session_config, tokenizer,
                                     /*benchmark_info=*/std::nullopt));
  std::vector<int> combined;
  for (const auto& item : preprocessed) {
    const auto* input_text = std::get_if<InputText>(&item);
    if (input_text == nullptr) {
      return absl::InternalError("preprocessed input is not text");
    }
    ABSL_ASSIGN_OR_RETURN(const auto* tensor,
                          input_text->GetPreprocessedTextTensor());
    if (tensor == nullptr) return absl::InternalError("token tensor is null");
    LITERT_ASSIGN_OR_RETURN(
        auto rows,
        litert::support::Tokenizer::TensorBufferToTokenIds(*tensor));
    if (rows.size() != 1) return absl::InternalError("expected one token row");
    combined.insert(combined.end(), rows.front().begin(), rows.front().end());
  }
  if (combined.empty()) return absl::InternalError("effective token IDs are empty");
  return combined;
}

std::string TaskStateName(TaskState state) {
  switch (state) {
    case TaskState::kUnknown: return "unknown";
    case TaskState::kCreated: return "created";
    case TaskState::kQueued: return "queued";
    case TaskState::kProcessing: return "processing";
    case TaskState::kDone: return "done";
    case TaskState::kMaxNumTokensReached: return "max_num_tokens_reached";
    case TaskState::kFailed: return "failed";
    case TaskState::kDependentTaskFailed: return "dependent_task_failed";
    case TaskState::kCancelled: return "cancelled";
    case TaskState::kDependentTaskCancelled: return "dependent_task_cancelled";
    case TaskState::kLastCallbackQueued: return "last_callback_queued";
  }
  return "unknown";
}

struct DecodeCapture {
  std::mutex mu;
  std::string text;
  std::vector<int> token_ids;
  std::optional<Clock::time_point> first_token_time;
  std::optional<Clock::time_point> completion_time;
  std::optional<std::string> error;
  TaskState last_state = TaskState::kUnknown;
};

absl::AnyInvocable<void(absl::StatusOr<Responses>)> MakeDecodeCallback(DecodeCapture* capture) {
  return [capture](absl::StatusOr<Responses> response) mutable {
    const auto now = Clock::now();
    std::lock_guard<std::mutex> lock(capture->mu);
    if (!response.ok()) {
      capture->error = response.status().ToString();
      capture->completion_time = now;
      return;
    }
    capture->last_state = response->GetTaskState();
    const auto& texts = response->GetTexts();
    const auto& ids = response->GetTokenIds();
    const bool has_payload = !texts.empty() || !ids.empty();
    if (has_payload && !capture->first_token_time.has_value()) capture->first_token_time = now;
    if (!texts.empty()) capture->text += texts.front();
    if (!ids.empty()) capture->token_ids.insert(capture->token_ids.end(), ids.front().begin(), ids.front().end());
    if (!has_payload && litert::lm::IsTaskEndState(response->GetTaskState())) capture->completion_time = now;
  };
}

absl::StatusOr<Json> RunRequest(Engine& engine, Engine::Session& session,
                                const Json& workload, const std::string& tier,
                                const std::string& run_id, const std::string& phase,
                                int output_cap, int timeout_seconds,
                                size_t expected_input_tokens,
                                const std::filesystem::path& output_dir) {
  uint64_t prefill_index_before = 0;
  uint64_t decode_index_before = 0;
  std::optional<std::string> benchmark_info_before_error;
  auto info_before = session.GetBenchmarkInfo();
  if (info_before.ok()) {
    prefill_index_before = info_before->GetTotalPrefillTurns();
    decode_index_before = info_before->GetTotalDecodeTurns();
  } else {
    benchmark_info_before_error = info_before.status().ToString();
  }
  ABSL_ASSIGN_OR_RETURN(const int current_step, session.GetCurrentStep());
  const bool rewind_called = current_step != 0;
  if (rewind_called) {
    ABSL_RETURN_IF_ERROR(session.RewindToStep(0));
  }
  ABSL_ASSIGN_OR_RETURN(const int reset_step, session.GetCurrentStep());
  if (reset_step != 0) return absl::InternalError("session did not begin request at step zero");

  const auto request_start = Clock::now();
  ABSL_ASSIGN_OR_RETURN(const std::string rendered_prompt, RenderCanonicalPrompt(workload));
  std::vector<InputData> input;
  input.emplace_back(InputText(rendered_prompt));
  ABSL_RETURN_IF_ERROR(session.RunPrefill(input));
  const auto prefill_return = Clock::now();

  DecodeConfig decode_config = DecodeConfig::CreateDefault();
  decode_config.SetMaxOutputTokens(output_cap);
  DecodeCapture capture;
  ABSL_ASSIGN_OR_RETURN(auto controller,
                        session.RunDecodeAsync(MakeDecodeCallback(&capture), decode_config));
  const absl::Status wait_status = controller->WaitUntilDone(absl::Seconds(timeout_seconds));
  const auto wait_return = Clock::now();
  if (absl::IsDeadlineExceeded(wait_status)) {
    controller->Cancel().IgnoreError();
  } else if (!wait_status.ok()) {
    std::lock_guard<std::mutex> lock(capture.mu);
    if (!capture.error.has_value()) capture.error = wait_status.ToString();
  }

  // Task-controller completion does not guarantee that the callback pool is
  // drained. Wait for the engine before snapshotting the exact raw output.
  // This is part of output collection, not a requirement for BenchmarkInfo.
  const absl::Status engine_wait_status =
      engine.WaitUntilDone(absl::Seconds(timeout_seconds));

  std::string output_text;
  std::vector<int> emitted_ids;
  std::optional<Clock::time_point> first_token_time;
  std::optional<Clock::time_point> completion_time;
  std::optional<std::string> callback_error;
  TaskState last_state;
  {
    std::lock_guard<std::mutex> lock(capture.mu);
    output_text = capture.text;
    emitted_ids = capture.token_ids;
    first_token_time = capture.first_token_time;
    completion_time = capture.completion_time;
    callback_error = capture.error;
    last_state = capture.last_state;
  }
  if (!engine_wait_status.ok() && !callback_error.has_value()) {
    callback_error = engine_wait_status.ToString();
  }
  const auto effective_completion = completion_time.value_or(wait_return);
  const std::filesystem::path output_path = output_dir / "outputs" / (run_id + ".txt");
  // Persist successful or partial raw output before optional instrumentation
  // inspection. Missing BenchmarkInfo must never discard generated text.
  ABSL_RETURN_IF_ERROR(WriteFile(output_path, output_text));

  uint64_t prefill_index_after = prefill_index_before;
  uint64_t decode_index_after = decode_index_before;
  std::optional<uint64_t> runtime_prefill_tokens;
  std::optional<uint64_t> runtime_decode_tokens;
  std::optional<absl::Duration> runtime_prefill_duration;
  std::optional<absl::Duration> runtime_decode_duration;
  std::optional<std::string> benchmark_info_after_error;
  auto info_after = session.GetBenchmarkInfo();
  if (!info_after.ok()) {
    benchmark_info_after_error = info_after.status().ToString();
  } else {
    prefill_index_after = info_after->GetTotalPrefillTurns();
    decode_index_after = info_after->GetTotalDecodeTurns();
    if (prefill_index_after > prefill_index_before) {
      runtime_prefill_tokens = 0;
      runtime_prefill_duration = absl::ZeroDuration();
      for (uint64_t index = prefill_index_before; index < prefill_index_after; ++index) {
        ABSL_ASSIGN_OR_RETURN(const BenchmarkTurnData turn,
                              info_after->GetPrefillTurn(index));
        *runtime_prefill_tokens += turn.num_tokens;
        *runtime_prefill_duration += turn.duration;
      }
    }
    if (decode_index_after > decode_index_before) {
      runtime_decode_tokens = 0;
      runtime_decode_duration = absl::ZeroDuration();
      for (uint64_t index = decode_index_before; index < decode_index_after; ++index) {
        ABSL_ASSIGN_OR_RETURN(const BenchmarkTurnData turn,
                              info_after->GetDecodeTurn(index));
        *runtime_decode_tokens += turn.num_tokens;
        *runtime_decode_duration += turn.duration;
      }
    }
  }

  std::string stop_reason = "eos";
  if (absl::IsDeadlineExceeded(wait_status)) {
    stop_reason = "timeout";
  } else if (callback_error.has_value() || !wait_status.ok() ||
             last_state == TaskState::kFailed ||
             last_state == TaskState::kDependentTaskFailed) {
    stop_reason = "error";
  } else if (last_state == TaskState::kMaxNumTokensReached ||
             emitted_ids.size() >= static_cast<size_t>(output_cap) ||
             (runtime_decode_tokens.has_value() &&
              *runtime_decode_tokens >= static_cast<uint64_t>(output_cap))) {
    stop_reason = "max_tokens";
  }

  const double protocol_decode_seconds = first_token_time.has_value()
      ? Seconds(effective_completion - *first_token_time)
      : 0.0;
  const int64_t protocol_decode_numerator =
      emitted_ids.empty() ? 0 : static_cast<int64_t>(emitted_ids.size()) - 1;
  const Json null_json = nullptr;
  Json missing_reasons = Json::object();
  if (!runtime_prefill_duration.has_value()) {
    missing_reasons["timing.prefill_seconds"] =
        "LiteRT-LM direct Session BenchmarkInfo exposed no new prefill turn for the completed logical request; synchronous frontend-plus-prefill wall time is retained separately.";
    missing_reasons["throughput.prefill_tokens_per_second"] =
        "No runtime-isolated prefill duration was exposed; frontend-plus-prefill wall time is not relabeled as prefill throughput.";
  }
  if (!runtime_decode_duration.has_value()) {
    missing_reasons["timing.runtime_decode_turn_seconds"] =
        "LiteRT-LM direct Session BenchmarkInfo exposed no new decode turn; callback-clock decode timing is retained instead.";
    missing_reasons["throughput.runtime_decode_tokens_per_second"] =
        "No runtime BenchmarkInfo decode turn was exposed; callback-clock decode throughput is retained instead.";
  }
  Json result = {
      {"id", run_id},
      {"phase", phase},
      {"tier", tier},
      {"render_policy", kRenderPolicy},
      {"session_step_before_reset", current_step},
      {"rewind_called", rewind_called},
      {"session_step_after_reset", reset_step},
      {"request_timeout_seconds", timeout_seconds},
      {"output_token_cap", output_cap},
      {"expected_input_tokens", expected_input_tokens},
      {"runtime_input_token_count_matches", runtime_prefill_tokens.has_value() ? Json(*runtime_prefill_tokens == expected_input_tokens) : null_json},
      {"output_tokens", emitted_ids.size()},
      {"runtime_generated_tokens", runtime_decode_tokens.has_value() ? Json(*runtime_decode_tokens) : null_json},
      {"runtime_prefill_tokens", runtime_prefill_tokens.has_value() ? Json(*runtime_prefill_tokens) : null_json},
      {"emitted_token_ids", emitted_ids},
      {"stop_reason", stop_reason},
      {"runtime_task_state", TaskStateName(last_state)},
      {"runtime_error", callback_error.has_value() ? Json(*callback_error) : Json(nullptr)},
      {"runtime_benchmark_info", {
          {"prefill_turns_before", prefill_index_before},
          {"prefill_turns_after", prefill_index_after},
          {"decode_turns_before", decode_index_before},
          {"decode_turns_after", decode_index_after},
          {"before_error", benchmark_info_before_error.has_value() ? Json(*benchmark_info_before_error) : null_json},
          {"after_error", benchmark_info_after_error.has_value() ? Json(*benchmark_info_after_error) : null_json},
      }},
      {"timing", {
          {"request_to_first_token_seconds", first_token_time.has_value() ? Json(Seconds(*first_token_time - request_start)) : null_json},
          {"prefill_seconds", runtime_prefill_duration.has_value() ? Json(Seconds(*runtime_prefill_duration)) : null_json},
          {"post_prefill_to_first_token_seconds", first_token_time.has_value() ? Json(Seconds(*first_token_time - prefill_return)) : null_json},
          {"decode_seconds", first_token_time.has_value() ? Json(protocol_decode_seconds) : null_json},
          {"runtime_decode_turn_seconds", runtime_decode_duration.has_value() ? Json(Seconds(*runtime_decode_duration)) : null_json},
          {"total_seconds", Seconds(effective_completion - request_start)},
          {"request_frontend_plus_prefill_seconds", Seconds(prefill_return - request_start)},
      }},
      {"throughput", {
          {"prefill_tokens_per_second", runtime_prefill_duration.has_value() && *runtime_prefill_duration > absl::ZeroDuration() ? Json(static_cast<double>(*runtime_prefill_tokens) / Seconds(*runtime_prefill_duration)) : null_json},
          {"decode_tokens_per_second", protocol_decode_seconds > 0.0 ? Json(static_cast<double>(protocol_decode_numerator) / protocol_decode_seconds) : null_json},
          {"runtime_decode_tokens_per_second", runtime_decode_duration.has_value() && *runtime_decode_duration > absl::ZeroDuration() ? Json(static_cast<double>(*runtime_decode_tokens) / Seconds(*runtime_decode_duration)) : null_json},
          {"decode_first_token_included", false},
      }},
      {"output_relative_path", std::filesystem::relative(output_path, output_dir).string()},
      {"output_bytes", output_text.size()},
      {"missing_reasons", missing_reasons},
  };
  return result;
}

absl::Status MainHelper(int argc, char** argv) {
  absl::ParseCommandLine(argc, argv);
  absl::SetMinLogLevel(absl::LogSeverityAtLeast::kError);
  absl::SetStderrThreshold(absl::LogSeverityAtLeast::kFatal);

  const std::string model_path = absl::GetFlag(FLAGS_model_path);
  const std::string workload_dir = absl::GetFlag(FLAGS_workload_dir);
  const std::string output_dir_value = absl::GetFlag(FLAGS_output_dir);
  const std::string arm_id = absl::GetFlag(FLAGS_arm_id);
  if (model_path.empty() || workload_dir.empty() || output_dir_value.empty() || arm_id.empty()) {
    return absl::InvalidArgumentError("model_path, workload_dir, output_dir, and arm_id are required");
  }
  const std::filesystem::path output_dir(output_dir_value);
  std::filesystem::create_directories(output_dir / "outputs");

  std::vector<std::pair<std::string, Json>> workloads;
  for (const std::string tier : {"short", "medium", "long"}) {
    const auto path = std::filesystem::path(workload_dir) / (tier + ".json");
    std::ifstream stream(path);
    if (!stream) return absl::NotFoundError("missing workload: " + path.string());
    Json workload;
    stream >> workload;
    if (workload.value("tier", "") != tier) return absl::InvalidArgumentError("workload tier mismatch");
    ABSL_RETURN_IF_ERROR(RenderCanonicalPrompt(workload).status());
    workloads.emplace_back(tier, std::move(workload));
  }

  MemoryMonitor memory_monitor;
  memory_monitor.Start();
  const auto setup_start = Clock::now();
  ABSL_ASSIGN_OR_RETURN(ModelAssets model_assets, ModelAssets::Create(model_path));
  ABSL_ASSIGN_OR_RETURN(Backend backend, litert::lm::GetBackendFromString(absl::GetFlag(FLAGS_backend)));
  ABSL_ASSIGN_OR_RETURN(EngineSettings engine_settings,
                        EngineSettings::CreateDefault(std::move(model_assets), backend));
  engine_settings.GetMutableBenchmarkParams() = litert::lm::proto::BenchmarkParams();
  auto& executor_settings = engine_settings.GetMutableMainExecutorSettings();
  executor_settings.SetMaxNumTokens(absl::GetFlag(FLAGS_max_num_tokens));
  executor_settings.SetSamplerBackend(Backend::CPU);
  executor_settings.SetCacheDir(absl::GetFlag(FLAGS_cache_dir));
  if (backend == Backend::CPU) {
    ABSL_ASSIGN_OR_RETURN(auto cpu_config,
                          executor_settings.MutableBackendConfig<litert::lm::CpuConfig>());
    cpu_config.number_of_threads = absl::GetFlag(FLAGS_num_cpu_threads);
    cpu_config.enable_ynnpack = false;
    executor_settings.SetBackendConfig(cpu_config);
  }
  ABSL_ASSIGN_OR_RETURN(auto engine,
                        EngineFactory::CreateDefault(std::move(engine_settings)));

  SessionConfig session_config = SessionConfig::CreateDefault();
  auto& sampler = session_config.GetMutableSamplerParams();
  // LiteRT-LM v0.16.1's CPU sampler implements only the TOP_P enum.
  // TOP_P with k=1 and p=1 is the exact supported argmax equivalent and is
  // used for both neural backends via the CPU sampler.
  sampler.set_type(litert::lm::proto::SamplerParameters::TOP_P);
  sampler.set_k(1);
  sampler.set_p(1.0f);
  sampler.set_temperature(1.0f);
  sampler.clear_seed();
  session_config.SetSamplerBackend(Backend::CPU);
  session_config.SetApplyPromptTemplateInSession(false);
  session_config.SetMaxOutputTokens(absl::GetFlag(FLAGS_max_output_tokens));
  const auto initial_session_creation_start = Clock::now();
  ABSL_ASSIGN_OR_RETURN(auto session, engine->CreateSession(session_config));
  const double initial_session_creation_seconds =
      Seconds(Clock::now() - initial_session_creation_start);
  const auto setup_end = Clock::now();
  Json gpu_provider_binding = nullptr;
  if (backend == Backend::GPU) {
    gpu_provider_binding = CollectGpuProviderBinding();
    ABSL_RETURN_IF_ERROR(WriteFile(output_dir / "gpu-provider-binding.json",
                                   gpu_provider_binding.dump(2) + "\n"));
    if (!gpu_provider_binding["binding_proven"].get<bool>()) {
      return absl::FailedPreconditionError(
          "GPU provider binding was not proven after Engine and Session creation; refusing to publish this route as GPU");
    }
  }

  Json prompt_inventory = Json::object();
  for (const auto& [tier, workload] : workloads) {
    ABSL_ASSIGN_OR_RETURN(const std::string rendered, RenderCanonicalPrompt(workload));
    ABSL_ASSIGN_OR_RETURN(auto token_ids,
                          GetEffectiveTokenIds(*engine, session->GetSessionConfig(), rendered));
    if (token_ids.size() + absl::GetFlag(FLAGS_max_output_tokens) >
        static_cast<size_t>(absl::GetFlag(FLAGS_max_num_tokens))) {
      return absl::InvalidArgumentError(tier + " prompt plus output ceiling exceeds max_num_tokens");
    }
    const auto rendered_path = output_dir / ("rendered-" + tier + ".txt");
    ABSL_RETURN_IF_ERROR(WriteFile(rendered_path, rendered));
    prompt_inventory[tier] = {
        {"render_policy", kRenderPolicy},
        {"rendered_relative_path", rendered_path.filename().string()},
        {"rendered_bytes", rendered.size()},
        {"input_tokens", token_ids.size()},
        {"token_ids", token_ids},
        {"max_num_tokens", absl::GetFlag(FLAGS_max_num_tokens)},
        {"max_output_tokens", absl::GetFlag(FLAGS_max_output_tokens)},
        {"truncated", false},
    };
  }

  Json runs = Json::array();
  auto persist_checkpoint = [&]() -> absl::Status {
    Json checkpoint = {
        {"schema_version", 1},
        {"experiment", "0025-gemma-4-e2b-it-android"},
        {"arm_id", arm_id},
        {"backend", absl::GetFlag(FLAGS_backend)},
        {"runtime_revision", kRuntimeRevision},
        {"setup", {
            {"seconds", Seconds(setup_end - setup_start)},
            {"initial_session_creation_seconds", initial_session_creation_seconds},
            {"boundary", "before ModelAssets::Create through one Engine and the initial direct Session ready with KV capacity"},
        }},
        {"prompts", prompt_inventory},
        {"gpu_provider_binding", gpu_provider_binding},
        {"completed_logical_request_count", runs.size()},
        {"runs", runs},
        {"checkpoint_complete", false},
    };
    return WriteFile(output_dir / "checkpoint.json", checkpoint.dump(2) + "\n");
  };
  auto annotate_isolation = [](Json* run, const std::string& strategy,
                               double seconds, bool included_in_setup) {
    (*run)["request_isolation_strategy"] = strategy;
    (*run)["session_recreation_seconds"] = seconds;
    (*run)["session_recreation_in_total_request"] = false;
    (*run)["session_recreation_in_setup"] = included_in_setup;
  };
  if (absl::GetFlag(FLAGS_smoke_only) &&
      absl::GetFlag(FLAGS_reset_probe_only)) {
    return absl::InvalidArgumentError("smoke_only and reset_probe_only are mutually exclusive");
  }
  if (absl::GetFlag(FLAGS_smoke_only)) {
    ABSL_ASSIGN_OR_RETURN(Json run,
                          RunRequest(*engine, *session, workloads[0].second, "short",
                                     "smoke-short-01", "smoke",
                                     absl::GetFlag(FLAGS_smoke_max_output_tokens),
                                     absl::GetFlag(FLAGS_request_timeout_seconds),
                                     prompt_inventory["short"]["input_tokens"].get<size_t>(),
                                     output_dir));
    annotate_isolation(&run, "setup_created_initial_session",
                       initial_session_creation_seconds, true);
    runs.push_back(std::move(run));
    ABSL_RETURN_IF_ERROR(persist_checkpoint());
  } else if (absl::GetFlag(FLAGS_reset_probe_only)) {
    const std::string reset_mode = absl::GetFlag(FLAGS_reset_mode);
    if (reset_mode != "rewind" && reset_mode != "fresh_session") {
      return absl::InvalidArgumentError("reset_mode must be rewind or fresh_session");
    }
    ABSL_ASSIGN_OR_RETURN(Json first,
                          RunRequest(*engine, *session, workloads[0].second, "short",
                                     "probe-short-01", "reset_probe",
                                     absl::GetFlag(FLAGS_smoke_max_output_tokens),
                                     absl::GetFlag(FLAGS_request_timeout_seconds),
                                     prompt_inventory["short"]["input_tokens"].get<size_t>(),
                                     output_dir));
    first["reset_mode"] = reset_mode;
    annotate_isolation(&first, "setup_created_initial_session",
                       initial_session_creation_seconds, true);
    runs.push_back(std::move(first));
    ABSL_RETURN_IF_ERROR(persist_checkpoint());

    double recreation_seconds = 0.0;
    if (reset_mode == "fresh_session") {
      const auto recreation_start = Clock::now();
      session.reset();
      ABSL_ASSIGN_OR_RETURN(session, engine->CreateSession(session_config));
      recreation_seconds = Seconds(Clock::now() - recreation_start);
    }
    ABSL_ASSIGN_OR_RETURN(Json second,
                          RunRequest(*engine, *session, workloads[0].second, "short",
                                     "probe-short-02", "reset_probe",
                                     absl::GetFlag(FLAGS_smoke_max_output_tokens),
                                     absl::GetFlag(FLAGS_request_timeout_seconds),
                                     prompt_inventory["short"]["input_tokens"].get<size_t>(),
                                     output_dir));
    second["reset_mode"] = reset_mode;
    annotate_isolation(&second,
                       reset_mode == "fresh_session"
                           ? "fresh_session_per_logical_request"
                           : "diagnostic_rewind_to_step_zero",
                       recreation_seconds, false);
    runs.push_back(std::move(second));
    ABSL_RETURN_IF_ERROR(persist_checkpoint());
  } else {
    if (absl::GetFlag(FLAGS_reset_mode) != "fresh_session") {
      return absl::InvalidArgumentError(
          "canonical campaign requires fresh_session request isolation");
    }
    ABSL_ASSIGN_OR_RETURN(Json first,
                          RunRequest(*engine, *session, workloads[0].second, "short",
                                     "first-short-01", "first",
                                     absl::GetFlag(FLAGS_max_output_tokens),
                                     absl::GetFlag(FLAGS_request_timeout_seconds),
                                     prompt_inventory["short"]["input_tokens"].get<size_t>(),
                                     output_dir));
    annotate_isolation(&first, "setup_created_initial_session",
                       initial_session_creation_seconds, true);
    runs.push_back(std::move(first));
    ABSL_RETURN_IF_ERROR(persist_checkpoint());
    for (const auto& [tier, workload] : workloads) {
      for (int index = 1; index <= 5; ++index) {
        const auto recreation_start = Clock::now();
        session.reset();
        ABSL_ASSIGN_OR_RETURN(session, engine->CreateSession(session_config));
        const double recreation_seconds =
            Seconds(Clock::now() - recreation_start);
        const std::string run_id =
            "loaded-route-" + tier + "-0" + std::to_string(index);
        ABSL_ASSIGN_OR_RETURN(Json run,
                              RunRequest(*engine, *session, workload, tier, run_id,
                                         "loaded_route",
                                         absl::GetFlag(FLAGS_max_output_tokens),
                                         absl::GetFlag(FLAGS_request_timeout_seconds),
                                         prompt_inventory[tier]["input_tokens"].get<size_t>(),
                                         output_dir));
        annotate_isolation(&run, "fresh_session_per_logical_request",
                           recreation_seconds, false);
        runs.push_back(std::move(run));
        ABSL_RETURN_IF_ERROR(persist_checkpoint());
      }
    }
  }

  Json result = {
      {"schema_version", 1},
      {"experiment", "0025-gemma-4-e2b-it-android"},
      {"arm_id", arm_id},
      {"backend", absl::GetFlag(FLAGS_backend)},
      {"runtime", {
          {"name", "LiteRT-LM"},
          {"version", "v0.16.1"},
          {"revision", kRuntimeRevision},
      }},
      {"route", {
          {"model_path", model_path},
          {"cache_dir", absl::GetFlag(FLAGS_cache_dir)},
          {"max_num_tokens", absl::GetFlag(FLAGS_max_num_tokens)},
          {"max_output_tokens", absl::GetFlag(FLAGS_max_output_tokens)},
          {"num_cpu_threads", absl::GetFlag(FLAGS_num_cpu_threads)},
          {"sampler", "CPU TOP_P(k=1,p=1) exact argmax implementation for both CPU and GPU neural backends"},
          {"thinking_enabled", false},
          {"prompt_template_applied_in_session", false},
          {"render_policy", kRenderPolicy},
          {"smoke_only", absl::GetFlag(FLAGS_smoke_only)},
          {"reset_probe_only", absl::GetFlag(FLAGS_reset_probe_only)},
          {"reset_mode", absl::GetFlag(FLAGS_reset_mode)},
          {"loaded_engine_reused", true},
          {"model_remap_or_reload_between_requests", false},
          {"accelerator_recompilation_between_requests", false},
          {"retained_prompt_or_kv_reuse_between_requests", false},
      }},
      {"setup", {
          {"seconds", Seconds(setup_end - setup_start)},
          {"initial_session_creation_seconds", initial_session_creation_seconds},
          {"boundary", "before ModelAssets::Create through one Engine and the initial direct Session ready with KV capacity"},
      }},
      {"prompts", prompt_inventory},
      {"gpu_provider_binding", gpu_provider_binding},
      {"runs", runs},
      {"memory", memory_monitor.Stop()},
  };
  const auto result_path = output_dir / "runner-result.json";
  ABSL_RETURN_IF_ERROR(WriteFile(result_path, result.dump(2) + "\n"));
  Json completed_checkpoint = result;
  completed_checkpoint["completed_logical_request_count"] = runs.size();
  completed_checkpoint["checkpoint_complete"] = true;
  ABSL_RETURN_IF_ERROR(WriteFile(output_dir / "checkpoint.json",
                                 completed_checkpoint.dump(2) + "\n"));
  std::cout << result.dump() << std::endl;
  return absl::OkStatus();
}

}  // namespace

int main(int argc, char** argv) {
  ABSL_CHECK_OK(MainHelper(argc, argv));
  return 0;
}
