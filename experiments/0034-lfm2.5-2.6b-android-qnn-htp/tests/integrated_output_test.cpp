#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>

#include "integrated_output.hpp"

namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;

static std::vector<int32_t> Read(const fs::path& path) {
  std::ifstream input(path, std::ios::binary | std::ios::ate);
  if (!input) throw std::runtime_error("read failed");
  const auto bytes = input.tellg();
  if (bytes % static_cast<std::streamoff>(sizeof(int32_t)) != 0) throw std::runtime_error("unaligned");
  input.seekg(0); std::vector<int32_t> result(static_cast<size_t>(bytes) / sizeof(int32_t));
  input.read(reinterpret_cast<char*>(result.data()), bytes); return result;
}

int main(int argc, char** argv) {
  if (argc != 2) return 2;
  const fs::path root = argv[1]; fs::create_directories(root);

  // Late inference/profile failure must not erase tokens already append+fsync'd.
  const fs::path partial = root / "partial.int32le";
  {
    lfm2::ExclusiveTokenOutput output(partial.string());
    lfm2::BoundedTokenEmitter emitter(output, 16, 124900);
    emitter.Emit(597); emitter.Emit(4695);
    std::ostringstream errors;
    const bool profile_ok = lfm2::CaptureOptionalTelemetry(
        "injected", [] { throw std::runtime_error("injected profile failure"); }, errors);
    if (profile_ok || errors.str().find("optional_telemetry_missing phase=injected") == std::string::npos) return 3;
    try { throw std::runtime_error("injected late inference failure"); } catch (const std::exception&) {}
  }
  if (Read(partial) != std::vector<int32_t>({597, 4695})) return 4;
  try { lfm2::ExclusiveTokenOutput duplicate(partial.string()); return 5; } catch (const std::exception&) {}

  // MAX_NEW is the total output cap including the endpoint; EOS stops early.
  const fs::path capped = root / "capped.int32le";
  {
    lfm2::ExclusiveTokenOutput output(capped.string()); lfm2::BoundedTokenEmitter emitter(output, 4, 124900);
    emitter.Emit(597); int32_t next = 100;
    while (emitter.CanDecode()) emitter.Emit(next++);
    if (emitter.Tokens() != std::vector<int32_t>({597, 100, 101, 102})) return 6;
  }
  const fs::path eos = root / "eos.int32le";
  {
    lfm2::ExclusiveTokenOutput output(eos.string()); lfm2::BoundedTokenEmitter emitter(output, 16, 124900);
    emitter.Emit(597); emitter.Emit(124900);
    if (emitter.CanDecode() || emitter.Tokens().size() != 2) return 7;
  }

  // Static input helpers bind the direct-QNN INT64 ABI and state placement.
  auto positions = lfm2::MakePositionIds(0, 171);
  static_assert(std::is_same_v<decltype(positions)::value_type, int64_t>);
  if (positions.size() * sizeof(int64_t) != 1368 || positions.front() != 0 || positions.back() != 170) return 8;
  auto prefill_mask = lfm2::MakePrefillMask(171, 4096);
  if (prefill_mask.size() != 171 * 4096 || prefill_mask[3924] != -65504.0f || prefill_mask[3925] != 0.0f || prefill_mask.back() != 0.0f) return 9;
  auto ar1_mask = lfm2::MakeAr1Mask(171, 4096);
  if (ar1_mask.size() != 4096 || ar1_mask[170] != 0.0f || ar1_mask[171] != -65504.0f || ar1_mask.back() != 0.0f) return 10;
  std::vector<float> key_source(8 * 64 * 3), key_destination(8 * 64 * 7, -1.0f);
  std::vector<float> value_source(8 * 3 * 64), value_destination(8 * 7 * 64, -1.0f);
  for (size_t i = 0; i < key_source.size(); ++i) key_source[i] = static_cast<float>(i);
  for (size_t i = 0; i < value_source.size(); ++i) value_source[i] = static_cast<float>(i);
  lfm2::BridgeKeyPrefix(key_source, key_destination, 3, 7);
  lfm2::BridgeValuePrefix(value_source, value_destination, 3, 7);
  for (size_t row = 0; row < 8 * 64; ++row) {
    for (size_t col = 0; col < 3; ++col) if (key_destination[row * 7 + col] != key_source[row * 3 + col]) return 11;
    for (size_t col = 3; col < 7; ++col) if (key_destination[row * 7 + col] != 0.0f) return 12;
  }
  for (size_t head = 0; head < 8; ++head) {
    for (size_t i = 0; i < 3 * 64; ++i) if (value_destination[head * 7 * 64 + i] != value_source[head * 3 * 64 + i]) return 13;
    for (size_t i = 3 * 64; i < 7 * 64; ++i) if (value_destination[head * 7 * 64 + i] != 0.0f) return 14;
  }

  // First emission excludes later profile work; final emission includes the
  // intervening prefill profile but excludes trailing AR1 profile/free.
  const auto zero = Clock::time_point{};
  const auto timing = lfm2::SummarizeTiming({
      zero, zero + std::chrono::seconds(2), zero + std::chrono::seconds(8),
      zero + std::chrono::seconds(3), zero + std::chrono::seconds(5),
      zero + std::chrono::seconds(9), zero + std::chrono::seconds(10),
      zero + std::chrono::seconds(11)});
  if (timing.request_to_first_emitted_seconds != 2.0 || timing.request_to_final_emitted_seconds != 8.0 ||
      timing.prefill_profile_seconds != 2.0 || timing.ar1_profile_seconds != 1.0 ||
      timing.diagnostic_total_seconds != 11.0) return 15;

  std::cout << "integrated no-QNN control-flow checks passed\n";
  return 0;
}
