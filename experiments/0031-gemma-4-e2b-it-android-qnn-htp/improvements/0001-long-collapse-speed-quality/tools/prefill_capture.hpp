#pragma once
// Observation only: reads already prepared buffers, never changes model state.
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <mutex>
#include <string>
#include <time.h>
#include <unistd.h>
#include <nlohmann/json.hpp>

namespace gemma_prefill_capture {
using Json = nlohmann::ordered_json;
inline uint64_t monotonic_ns() noexcept {
  timespec ts{};
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return uint64_t(ts.tv_sec) * 1000000000ULL + uint64_t(ts.tv_nsec);
}
inline bool write_all(int fd, const void* data, size_t size) noexcept {
  const auto* p = static_cast<const unsigned char*>(data);
  while (size) {
    ssize_t n = ::write(fd, p, size);
    if (n < 0 && errno == EINTR) continue;
    if (n <= 0) return false;
    p += n; size -= static_cast<size_t>(n);
  }
  return true;
}
struct State {
  std::mutex mutex;
  int directory{-1}, journal{-1};
  size_t bytes{0}, captures{0}, journal_bytes{0};
  bool disabled{false};
  State() noexcept {
    const char* path = std::getenv("GEMMA_PREFILL_CAPTURE_DIR");
    if (!path || !*path) { disabled = true; return; }
    directory = ::open(path, O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
    if (directory >= 0)
      journal = ::openat(directory, "capture.jsonl", O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (journal < 0) error("open capture directory/journal");
  }
  ~State() { if (journal >= 0) ::close(journal); if (directory >= 0) ::close(directory); }
  void error(const char* where) noexcept {
    disabled = true;
    std::fprintf(stderr, "GEMMA_PREFILL_CAPTURE_ERROR %s errno=%d\n", where, errno);
    std::fflush(stderr);
  }
  bool record(const Json& value) {
    std::string line = value.dump() + "\n";
    if (journal_bytes + line.size() > 512 * 1024 || !write_all(journal, line.data(), line.size()) || ::fdatasync(journal) != 0) {
      error("journal write/cap"); return false;
    }
    journal_bytes += line.size(); return true;
  }
};
inline State& state() { static State value; return value; }
inline void save(const char* phase, int step, const char* name, const void* data,
                 size_t size, Json metadata) noexcept {
  try {
    auto& s = state(); std::lock_guard<std::mutex> lock(s.mutex);
    if (s.disabled) return;
    if (step < 0 || step > 15 || !data || size == 0 || size > 3 * 1024 * 1024 ||
        s.captures >= 129 || s.bytes + size > 80 * 1024 * 1024) { s.error("payload contract/cap"); return; }
    for (const char* p = name; *p; ++p)
      if (!((*p >= 'a' && *p <= 'z') || (*p >= '0' && *p <= '9') || *p == '_')) { s.error("tensor name"); return; }
    char file[160]; std::snprintf(file, sizeof(file), "%02d-%s-%s.raw", step, phase, name);
    metadata["phase"] = phase; metadata["step"] = step; metadata["name"] = name;
    metadata["file"] = file; metadata["bytes"] = size; metadata["event"] = "begin";
    metadata["monotonic_ns"] = monotonic_ns();
    if (!s.record(metadata)) return;
    int fd = ::openat(s.directory, file, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (fd < 0) { s.error("exclusive raw open"); return; }
    bool ok = write_all(fd, data, size) && ::fdatasync(fd) == 0;
    int close_result = ::close(fd);
    if (!ok || close_result != 0) { s.error("raw write/close"); return; }
    s.bytes += size; ++s.captures;
    metadata["event"] = "complete"; metadata["monotonic_ns"] = monotonic_ns();
    metadata["total_payload_bytes"] = s.bytes; metadata["completed_payloads"] = s.captures;
    s.record(metadata);
  } catch (...) { state().error("observer exception; native computation continues"); }
}
}  // namespace gemma_prefill_capture
