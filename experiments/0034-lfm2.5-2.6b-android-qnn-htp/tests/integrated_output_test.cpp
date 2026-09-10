#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "integrated_output.hpp"

namespace fs = std::filesystem;

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
  const fs::path partial = root / "partial.int32le";
  {
    lfm2::ExclusiveTokenOutput output(partial.string());
    output.AppendAndFlush(597);
    output.AppendAndFlush(4695);
    std::ostringstream errors;
    const bool profile_ok = lfm2::CaptureOptionalTelemetry(
        "injected", [] { throw std::runtime_error("injected profile failure"); }, errors);
    if (profile_ok || errors.str().find("optional_telemetry_missing phase=injected") == std::string::npos) return 3;
    // Simulate a later inference/finite-scan failure by leaving scope with two already-flushed tokens.
  }
  if (Read(partial) != std::vector<int32_t>({597, 4695})) return 4;
  try {
    lfm2::ExclusiveTokenOutput duplicate(partial.string());
    return 5;
  } catch (const std::exception&) {
  }
  const fs::path full = root / "full.int32le";
  {
    lfm2::ExclusiveTokenOutput output(full.string());
    for (int32_t token : {597, 4695, 10966, 622}) output.AppendAndFlush(token);
  }
  if (Read(full) != std::vector<int32_t>({597, 4695, 10966, 622})) return 6;
  std::cout << "integrated output failure-injection checks passed\n";
  return 0;
}
