#pragma once

#include <cerrno>
#include <cstdint>
#include <cstring>
#include <ostream>
#include <stdexcept>
#include <string>

#include <fcntl.h>
#include <unistd.h>

namespace lfm2 {

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

}  // namespace lfm2
