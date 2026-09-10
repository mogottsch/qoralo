#pragma once

#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <ostream>
#include <stdexcept>
#include <string>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

namespace lfm2 {

inline bool UsesMonolithicDispatch(const std::string& alias) { return alias == "monolith"; }

class ExclusiveTokenOutput {
 public:
  explicit ExclusiveTokenOutput(const std::string& path) {
    fd_ = ::open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (fd_ < 0) throw std::runtime_error("exclusive output open failed: " + path + ": " + std::strerror(errno));
  }
  ExclusiveTokenOutput(const ExclusiveTokenOutput&) = delete;
  ExclusiveTokenOutput& operator=(const ExclusiveTokenOutput&) = delete;
  ~ExclusiveTokenOutput() { if (fd_ >= 0) ::close(fd_); }

  void AppendAndFlush(int32_t token) {
    const auto* bytes = reinterpret_cast<const uint8_t*>(&token);
    size_t written = 0;
    while (written < sizeof(token)) {
      const ssize_t count = ::write(fd_, bytes + written, sizeof(token) - written);
      if (count < 0 && errno == EINTR) continue;
      if (count <= 0) throw std::runtime_error("token output write failed: " + std::string(std::strerror(errno)));
      written += static_cast<size_t>(count);
    }
    if (::fsync(fd_) != 0) throw std::runtime_error("token output flush failed: " + std::string(std::strerror(errno)));
  }

 private:
  int fd_ = -1;
};

class BoundedTokenEmitter {
 public:
  BoundedTokenEmitter(ExclusiveTokenOutput& output, size_t total_cap, int32_t eos)
      : output_(output), total_cap_(total_cap), eos_(eos) {
    if (total_cap_ == 0) throw std::runtime_error("total output cap must be positive");
  }
  void Emit(int32_t token) {
    if (tokens_.size() >= total_cap_) throw std::runtime_error("total output cap exceeded");
    output_.AppendAndFlush(token);
    tokens_.push_back(token);
  }
  bool CanDecode() const { return !tokens_.empty() && tokens_.size() < total_cap_ && tokens_.back() != eos_; }
  const std::vector<int32_t>& Tokens() const { return tokens_; }

 private:
  ExclusiveTokenOutput& output_;
  size_t total_cap_;
  int32_t eos_;
  std::vector<int32_t> tokens_;
};

template <typename Callback>
bool CaptureOptionalTelemetry(const std::string& phase, Callback&& callback, std::ostream& errors) noexcept {
  try {
    callback();
    return true;
  } catch (const std::exception& error) {
    errors << "optional_telemetry_missing phase=" << phase << " error=" << error.what() << "\n";
    return false;
  } catch (...) {
    errors << "optional_telemetry_missing phase=" << phase << " error=unknown\n";
    return false;
  }
}

inline std::vector<int64_t> MakePositionIds(int64_t first, size_t count) {
  std::vector<int64_t> positions(count);
  for (size_t index = 0; index < count; ++index) positions[index] = first + static_cast<int64_t>(index);
  return positions;
}

inline std::vector<float> MakePrefillMask(size_t sequence, size_t capacity) {
  if (sequence == 0 || sequence >= capacity) throw std::runtime_error("invalid prefill mask shape");
  const size_t past = capacity - sequence;
  std::vector<float> mask(sequence * capacity, -65504.0f);
  for (size_t row = 0; row < sequence; ++row) {
    std::fill(mask.begin() + row * capacity + past,
              mask.begin() + row * capacity + past + row + 1, 0.0f);
  }
  return mask;
}

inline std::vector<float> MakeAr1Mask(size_t position, size_t capacity) {
  if (position >= capacity - 1) throw std::runtime_error("invalid AR1 mask position");
  std::vector<float> mask(capacity, -65504.0f);
  std::fill(mask.begin(), mask.begin() + position, 0.0f);
  mask.back() = 0.0f;
  return mask;
}

inline void BridgeKeyPrefix(const std::vector<float>& source, std::vector<float>& destination,
                            size_t sequence, size_t cache_length) {
  constexpr size_t rows = 8 * 64;
  if (source.size() != rows * sequence || destination.size() != rows * cache_length || sequence > cache_length) {
    throw std::runtime_error("key bridge shape mismatch");
  }
  std::fill(destination.begin(), destination.end(), 0.0f);
  for (size_t row = 0; row < rows; ++row) {
    std::copy_n(source.begin() + row * sequence, sequence, destination.begin() + row * cache_length);
  }
}

inline void BridgeValuePrefix(const std::vector<float>& source, std::vector<float>& destination,
                              size_t sequence, size_t cache_length) {
  constexpr size_t heads = 8, width = 64;
  if (source.size() != heads * sequence * width || destination.size() != heads * cache_length * width || sequence > cache_length) {
    throw std::runtime_error("value bridge shape mismatch");
  }
  std::fill(destination.begin(), destination.end(), 0.0f);
  for (size_t head = 0; head < heads; ++head) {
    std::copy_n(source.begin() + head * sequence * width, sequence * width,
                destination.begin() + head * cache_length * width);
  }
}

using IntegratedTimePoint = std::chrono::steady_clock::time_point;
struct IntegratedTimingMarkers {
  IntegratedTimePoint request_start;
  IntegratedTimePoint first_emitted;
  IntegratedTimePoint final_emitted;
  IntegratedTimePoint prefill_profile_start;
  IntegratedTimePoint prefill_profile_end;
  IntegratedTimePoint ar1_profile_start;
  IntegratedTimePoint ar1_profile_end;
  IntegratedTimePoint diagnostic_end;
};
struct IntegratedTimingSummary {
  double request_to_first_emitted_seconds;
  double request_to_final_emitted_seconds;
  double prefill_profile_seconds;
  double ar1_profile_seconds;
  double diagnostic_total_seconds;
};
inline IntegratedTimingSummary SummarizeTiming(const IntegratedTimingMarkers& markers) {
  const auto seconds = [](auto duration) { return std::chrono::duration<double>(duration).count(); };
  if (!(markers.request_start <= markers.first_emitted &&
        markers.first_emitted <= markers.final_emitted &&
        markers.request_start <= markers.prefill_profile_start &&
        markers.prefill_profile_start <= markers.prefill_profile_end &&
        markers.prefill_profile_end <= markers.ar1_profile_start &&
        markers.final_emitted <= markers.ar1_profile_start &&
        markers.ar1_profile_start <= markers.ar1_profile_end &&
        markers.ar1_profile_end <= markers.diagnostic_end)) {
    throw std::runtime_error("integrated timing markers out of order");
  }
  return {
      seconds(markers.first_emitted - markers.request_start),
      seconds(markers.final_emitted - markers.request_start),
      seconds(markers.prefill_profile_end - markers.prefill_profile_start),
      seconds(markers.ar1_profile_end - markers.ar1_profile_start),
      seconds(markers.diagnostic_end - markers.request_start),
  };
}

}  // namespace lfm2
