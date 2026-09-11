// Source-only0031 aligned-reference derivative; exactly one GPU long request, not a campaign.
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

ABSL_FLAG(std::string, backend, "gpu", "LiteRT-LM backend: cpu or gpu.");
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
constexpr char kRenderPolicy[] = "gemma4-single-runtime-bos-aligned-reference-v1";

// Frozen actual QNN input, int32le SHA256 3b5c04febbc9d55c529ee7ece510607203dbdc8256a6abc05ba0498cf4e52b64
const std::vector<int> kExpectedAlignedInputIds = {2,105,9731,107,3048,659,496,2263,5192,2028,1208,496,3736,1594,236761,58025,528,40137,5422,57243,236761,3574,711,4928,506,30998,236764,11497,11808,236764,8369,18558,236764,653,506,1707,600,611,659,1646,10418,236761,106,107,105,2364,107,6190,506,2269,57728,10630,8652,236761,108,236770,236761,669,2434,563,22020,1806,2263,34711,18362,580,506,1638,10055,236772,36359,4744,236761,7850,64026,19015,496,11236,2028,6077,840,1521,4182,13198,236764,3958,150548,49060,4890,17373,1061,2028,840,815,29227,1099,8299,236764,532,3958,127649,6178,919,6571,528,8770,573,11442,11172,8487,236761,2343,10802,1921,23227,10884,236764,11172,8487,236764,532,8369,8299,236761,108,236778,236761,669,3739,14102,7474,1932,573,12571,531,28959,4310,236764,6151,1070,5089,3107,625,6842,1308,886,2864,236761,562,9116,607,11162,10884,740,5233,577,10559,1186,1056,506,15808,6478,563,103374,236761,669,25809,1374,2881,573,1800,496,886,236772,4764,3517,532,496,4890,6478,2180,26614,910,21238,18998,236761,108,236800,236761,669,4744,815,5809,6571,532,506,8172,1458,1149,81661,1695,6585,1208,4204,236761,587,12779,2028,5734,236764,2147,36599,75043,236764,7659,7704,236764,33652,185290,236764,532,506,6730,2307,236772,2394,15612,776,711,735,15779,6571,61567,236761,43633,43363,20688,1076,2425,532,1657,1494,236772,7632,12933,1921,577,26777,4319,1082,9050,618,103362,236761,108,236812,236761,93750,25565,9729,23211,236761,562,2822,2864,6097,1186,496,1982,14787,236764,496,7860,2864,5132,3131,7704,529,8687,236764,532,496,1440,2864,12668,506,6684,4403,4275,684,506,3739,236761,30121,18558,1335,3418,2028,8369,19804,1581,1056,506,4453,92916,236772,236828,11172,17234,659,15779,236761,108,236810,236761,7578,531,1171,8369,5132,981,496,2430,9871,1680,1816,7412,236764,1651,877,6910,53350,57038,8487,529,506,2744,21739,236761,138903,53350,15517,506,3209,6381,529,7835,21739,236761,562,33652,600,81225,1186,886,9292,21238,3914,577,44265,607,614,42148,9918,1534,877,6910,532,18756,236761,108,236825,236761,669,1171,2864,740,13018,3104,43945,236764,31770,33652,46723,236764,15612,25519,236764,653,54534,41468,600,3209,10512,5571,236761,149571,10512,1921,3582,12309,532,2307,236772,2394,1883,1651,44257,506,15808,2028,6478,236761,669,2072,1921,22435,506,1171,15412,21112,699,506,1638,236772,8494,5296,236761,108,236832,236761,54102,3439,659,711,4512,236761,117820,3836,8299,1149,5387,506,5154,3487,531,2352,11072,6224,236764,532,19416,740,2352,1800,2066,532,4022,236761,669,8535,8735,506,10055,532,11775,1883,1680,532,1308,506,7073,532,1677,711,9779,614,723,68882,2066,1550,618,5743,236761,108,236828,236761,149072,659,27164,834,600,7334,14860,31164,4595,11325,236761,562,72117,2483,563,711,11269,6684,236787,496,11207,9116,1149,29910,8369,104026,236764,14820,236772,18985,31368,236764,12457,88078,236764,653,496,2822,7350,236761,669,4068,4322,19565,1186,3363,506,4453,3938,5724,1133,35299,1816,532,44217,69281,496,25898,3325,3539,236761,108,236819,236761,669,11054,48479,2229,699,1607,7021,236761,4943,659,3303,18224,236772,3947,131160,236764,1070,659,3399,63680,236764,532,1070,659,147121,17489,6095,684,496,7732,5904,10864,236761,562,2028,5346,7057,563,29368,127389,236793,3738,33847,236764,2129,119727,236764,6518,236764,99161,1996,236764,532,14274,5904,1921,4595,11744,531,1418,9116,236761,108,236770,236771,236761,30121,5482,532,11184,236772,9944,6868,740,2352,22014,529,506,2028,18710,236761,669,30998,5233,8735,92875,33847,236764,7930,127389,236764,506,1626,23428,236772,32061,15424,236764,506,5225,8369,1527,236764,532,496,15424,529,8369,104026,236761,1030,2752,8290,886,2028,2523,236789,236751,92875,8990,2264,2523,14778,531,3011,16590,8369,18558,236761,108,236770,236770,236761,669,3739,3548,496,22167,236772,144560,8299,21486,236764,840,506,21486,563,711,614,14787,531,6360,7121,600,1551,21739,236761,562,2028,1149,4721,657,1061,1345,236772,1340,236772,25425,8369,236764,4241,614,14481,4721,7501,236764,5370,506,21486,236764,990,855,236764,653,5121,236761,669,5396,7835,1527,532,4721,3282,659,912,529,1418,1845,236761,108,236770,236778,236761,3656,3958,7248,54534,18327,657,6478,11381,840,75538,16071,1063,1913,113671,6675,236761,12023,28399,88027,580,506,20974,1651,784,22823,12627,1161,506,54534,236761,47672,8787,1921,8701,1144,19284,1298,236764,532,496,4253,37031,1845,3914,22784,573,5663,236772,10212,4914,236761,108,236770,236800,236761,669,1594,4744,563,7659,607,3867,2913,981,236761,14857,59020,236764,2264,30998,1657,236764,653,496,104127,10883,12229,740,108040,6511,12505,236761,669,7073,6178,614,14417,4744,6623,236764,8735,7798,34818,4588,236764,532,34628,1186,16412,13129,684,506,1873,5274,236761,108,236770,236812,236761,9483,10884,815,496,16200,58024,10134,236761,1030,12502,1680,506,1171,2028,653,92875,2129,563,8678,653,506,33652,563,4464,236764,64283,10263,1171,236764,532,10842,1186,1056,496,2864,740,577,10951,2180,4767,2028,13317,236764,6478,11381,236764,54534,41468,236764,653,4068,15612,25519,236761,137201,14274,7474,496,21112,4785,12652,2157,236761,108,236770,236810,236761,562,33652,1149,6381,16812,31368,600,776,711,3819,1183,11325,7579,236761,669,30998,21238,6178,8341,529,506,1171,7835,8369,31744,531,506,54067,236764,1651,506,27164,10445,3938,6097,506,1626,64686,92916,236772,236828,1816,236761,1637,506,33652,3914,39216,8369,8341,19753,236764,506,26919,532,22784,12210,10134,659,9941,236761,108,236770,236825,236761,138903,53350,79368,506,3016,8434,11172,21739,236761,1030,6178,506,1548,529,7835,21739,10725,684,506,51422,39961,8448,532,5022,3363,506,1171,7835,8369,563,5012,236761,562,3161,50196,8369,3136,2180,1061,43354,236764,31637,236764,532,92875,9834,563,711,7271,4914,236761,108,236770,236832,236761,669,2434,30895,10802,531,577,83344,3209,580,496,1607,9574,5588,236761,32236,2028,236764,1458,2016,236764,182809,236764,33652,25027,236764,8583,1527,236764,12454,3835,236764,532,2028,8289,1921,5233,577,14481,236761,562,3209,16955,563,3742,618,861,23842,4914,5205,529,17483,14717,506,3303,1845,236761,108,236770,236828,236761,4943,4681,3914,4691,506,1440,61220,2915,506,3938,21486,528,910,16200,4403,4771,236761,10544,496,9116,1921,5121,653,1686,600,30028,47713,607,496,3282,236761,7966,2492,22523,1194,506,11172,236764,13471,506,21486,236764,653,30264,506,1458,3618,1093,2619,496,1607,61220,532,108040,496,25134,9960,236761,108,236770,236819,236761,29179,18756,740,4305,496,2822,236772,51505,11519,236764,12176,496,38608,1494,236772,7632,1686,740,3204,75043,699,6517,19401,236761,10508,12505,740,577,6684,1056,910,4615,532,9052,1050,209134,659,27750,236761,40436,1374,577,1151,40314,618,4813,2028,6571,236764,54534,6571,236764,653,2307,236772,2394,236772,12655,2425,2180,1982,4914,236761,108,236778,236771,236761,669,39698,563,614,3546,1024,11652,5274,4914,4319,1082,496,14268,573,625,236761,31029,810,236772,4764,8735,4196,607,506,5274,236764,1651,30611,12773,39216,9116,9834,236764,61220,236764,27834,10802,236764,16305,236764,532,4914,16412,236761,62420,2979,4595,2303,607,496,12625,3282,236761,108,236778,236770,236761,669,2434,795,13901,22167,3325,528,496,3209,5420,236761,669,1873,3736,7073,1677,711,6317,22323,3904,236764,59893,10634,236764,3117,236764,93354,236764,54814,236764,653,21354,18080,236761,562,1816,600,16349,506,46983,93190,4322,815,13646,1186,600,506,9116,1602,711,12968,24976,580,1724,4453,3938,17234,236761,108,236778,236778,236761,29239,11172,54358,740,735,1607,5225,8369,18558,532,877,6910,5384,236761,17647,659,48160,684,4453,30028,532,659,711,86552,1131,886,3136,236761,204015,607,1607,51881,16374,659,711,6212,618,25134,236764,1581,1056,910,1470,5990,7499,531,577,59340,3107,236761,108,236778,236800,236761,120635,12804,563,5121,236772,14566,236761,669,8535,56401,11409,1816,532,2487,21238,1056,2653,236764,38905,506,27791,618,506,4721,3282,236764,532,6895,10802,600,2752,10997,47713,236761,562,27791,1677,711,3291,496,5743,236772,1114,236772,721,236772,8556,1354,8423,506,15605,43354,532,8448,3643,6869,600,1550,236761,108,236778,236812,236761,669,30998,6178,72284,53255,573,506,1171,21425,3736,4258,236761,1174,17707,18756,22988,236764,840,16812,236772,189078,3938,563,2036,711,496,3149,1786,4194,1547,52025,236764,1845,3841,236764,532,16688,16412,740,127739,236761,7129,5773,13041,563,27164,532,4970,4319,1082,24271,855,236761,108,236778,236810,236761,8099,236772,24825,5154,10802,740,577,61598,684,4322,1883,236764,19416,1883,236764,7884,4588,236764,532,8172,236772,9731,39252,236761,669,32149,8735,506,12725,3439,625,740,6869,532,15852,506,1884,618,16305,236761,91417,24301,563,912,529,506,4914,236764,711,496,15246,600,1418,109245,6471,32704,236761,108,236778,236825,236761,562,6684,2072,62079,1144,506,9116,12183,699,3217,506,2434,2473,5347,625,236761,20148,53255,1149,711,42728,573,21191,10884,528,2822,14845,236764,532,496,2708,236772,20624,9116,1149,2036,577,118780,768,11172,8487,563,2311,5111,236761,669,1626,25809,1374,9779,1239,211302,2180,182170,1698,6035,236761,108,236778,236832,236761,669,9960,992,88906,28937,6310,699,33652,6571,236761,33775,17234,4208,11764,532,6463,2157,236764,44275,7704,4208,1657,18437,236764,532,33652,126209,2171,607,4403,532,3938,236761,49847,1186,506,2028,2129,2425,1093,711,3890,3363,506,9116,19009,48539,580,506,5154,236761,108,236778,236828,236761,7714,10445,3938,563,1944,3487,531,8274,618,1816,236764,21304,2028,18710,532,2455,14820,20183,236761,9567,2129,2479,236764,16812,1527,236764,532,38180,236772,236778,236810,236825,19953,3209,12505,531,4453,17234,236761,1637,5026,17507,3938,93190,3209,236764,506,39698,740,1138,600,4453,236772,11240,15412,2180,9199,506,3303,3736,10802,236761,108,236778,236819,236761,669,30998,1374,4595,54089,3418,20974,236764,39937,236764,532,646,11152,16266,236761,1030,5233,23669,8398,21238,532,4914,18998,2180,16890,614,54534,528,10764,236761,47672,236772,15396,7724,19681,531,506,5274,532,1921,1894,236764,4319,1082,9883,236764,506,3364,10884,532,2864,10802,236761,108,236800,236771,236761,669,13258,4893,563,837,16266,28054,19276,29436,981,236761,669,4914,1374,1386,26638,532,5676,2536,6684,684,39983,1298,901,12280,236764,837,54358,11536,236764,532,1144,12800,47713,236761,1030,1374,711,2490,496,6595,16947,1594,1131,496,3719,236772,1399,1583,3539,236761,108,6974,496,1265,236772,66436,8330,25809,573,506,2434,236761,42085,506,2132,211302,236764,8701,506,10802,600,1374,4595,7732,236764,532,1345,607,496,10231,2148,2918,236761,6890,12822,57243,4319,1082,496,2633,236761,106,107,105,4368,107};

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
  return "<|turn>system\n" + system + "<turn|>\n<|turn>user\n" + user +
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
  const bool rewind_called = false;
  if (current_step != 0) return absl::FailedPreconditionError("aligned reference requires a fresh step-zero Session; no rewind/replay");
  ABSL_ASSIGN_OR_RETURN(const int reset_step, session.GetCurrentStep());
  if (reset_step != 0) return absl::InternalError("session did not begin request at step zero");

  const auto request_start = Clock::now();
  ABSL_ASSIGN_OR_RETURN(const std::string rendered_prompt, RenderCanonicalPrompt(workload));
  ABSL_ASSIGN_OR_RETURN(auto actual_input_ids,
      GetEffectiveTokenIds(engine, session.GetSessionConfig(), rendered_prompt));
  const bool alignment_matches = actual_input_ids == kExpectedAlignedInputIds;
  const Json alignment = {
      {"actual_effective_token_ids", actual_input_ids},
      {"expected_effective_token_ids", kExpectedAlignedInputIds},
      {"all_ids_equal", alignment_matches},
      {"expected_int32le_sha256", "3b5c04febbc9d55c529ee7ece510607203dbdc8256a6abc05ba0498cf4e52b64"},
      {"prefill_not_yet_started", true},
      {"basis", "Actual session preprocessing, not just a count or rendered-text comparison"}};
  ABSL_RETURN_IF_ERROR(WriteFile(output_dir / "input-alignment-before-prefill.json", alignment.dump(2) + "\n"));
  if (!alignment_matches) return absl::FailedPreconditionError("effective input mismatch: full IDs retained; no neural request was submitted");
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

  if (absl::GetFlag(FLAGS_backend) != "gpu" ||
      absl::GetFlag(FLAGS_max_num_tokens) != 8192 ||
      absl::GetFlag(FLAGS_max_output_tokens) != 2048 ||
      absl::GetFlag(FLAGS_request_timeout_seconds) != 1800 ||
      absl::GetFlag(FLAGS_num_cpu_threads) != 4 ||
      absl::GetFlag(FLAGS_cache_dir).empty() || absl::GetFlag(FLAGS_cache_dir) == ":nocache" ||
      absl::GetFlag(FLAGS_smoke_only) || absl::GetFlag(FLAGS_reset_probe_only) ||
      absl::GetFlag(FLAGS_reset_mode) != "fresh_session") {
    return absl::InvalidArgumentError("one aligned GPU long/8192-context/max2048/1800s/4-CPU-thread reference only; no alternate scope");
  }
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
  for (const std::string tier : {"long"}) {
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
        {"experiment", "0031-aligned-reference-diagnostic"},
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
  ABSL_ASSIGN_OR_RETURN(Json run,
      RunRequest(*engine, *session, workloads[0].second, "long",
                 "aligned-reference-long-01", "aligned_reference",
                 2048, 1800, kExpectedAlignedInputIds.size(), output_dir));
  annotate_isolation(&run, "setup_created_fresh_session_one_aligned_request",
                     initial_session_creation_seconds, true);
  runs.push_back(std::move(run));
  ABSL_RETURN_IF_ERROR(persist_checkpoint());

  Json result = {
      {"schema_version", 1},
      {"experiment", "0031-aligned-reference-diagnostic"},
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
          {"sampler", "Unchanged CPU TOP_P(k=1,p=1,temp=1); intended singleton argmax, ties/numerical parity unproven"},
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
