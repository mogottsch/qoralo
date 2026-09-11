#pragma once

#include <cerrno>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <fcntl.h>
#include <unistd.h>

namespace lfm2 {

inline std::string SnapshotJsonString(const std::string& value) {
  static constexpr char hex[] = "0123456789abcdef";
  std::string out = "\"";
  for (unsigned char c : value) {
    if (c == '"' || c == '\\') { out += '\\'; out += static_cast<char>(c); }
    else if (c < 32) { out += "\\u00"; out += hex[c >> 4]; out += hex[c & 15]; }
    else out += static_cast<char>(c);
  }
  return out + "\"";
}

class SnapshotFile {
 public:
  explicit SnapshotFile(const std::filesystem::path& path) {
    fd_ = ::open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (fd_ < 0) throw std::runtime_error("exclusive snapshot file failed: " + path.string());
  }
  SnapshotFile(const SnapshotFile&) = delete;
  SnapshotFile& operator=(const SnapshotFile&) = delete;
  ~SnapshotFile() { if (fd_ >= 0) ::close(fd_); }
  void AppendAndFlush(const void* data, size_t size) {
    const auto* bytes = static_cast<const uint8_t*>(data);
    size_t done = 0;
    while (done < size) {
      const auto count = ::write(fd_, bytes + done, size - done);
      if (count < 0 && errno == EINTR) continue;
      if (count <= 0) throw std::runtime_error("snapshot write failed: " + std::string(std::strerror(errno)));
      done += static_cast<size_t>(count);
    }
    if (::fsync(fd_) != 0) throw std::runtime_error("snapshot fsync failed");
  }
 private:
  int fd_ = -1;
};

inline std::filesystem::path CreateExclusiveSnapshotDirectory(const std::filesystem::path& directory) {
  if (!std::filesystem::create_directory(directory)) throw std::runtime_error("snapshot directory already exists: " + directory.string());
  return directory;
}

// Only byte persistence: never sanitizes nonfinite floats, signed zero or INT64 IDs.
class TensorSnapshot {
 public:
  explicit TensorSnapshot(const std::filesystem::path& directory)
      : directory_(CreateExclusiveSnapshotDirectory(directory)), manifest_(directory_ / "tensors.jsonl") {
    const uint16_t one = 1;
    if (*reinterpret_cast<const uint8_t*>(&one) != 1) throw std::runtime_error("snapshot requires little-endian host");
  }
  void Add(const std::string& name, const std::string& dtype, const std::vector<uint32_t>& shape,
           const void* data, size_t size) {
    if (!data || size == 0 || size > 16 * 1024 * 1024 || count_ >= 128) throw std::runtime_error("snapshot size/count bound");
    if (dtype != "float32" && dtype != "int64") throw std::runtime_error("snapshot unsupported dtype");
    const std::string file = std::to_string(count_) + ".raw";
    SnapshotFile raw(directory_ / file);
    raw.AppendAndFlush(data, size);
    std::ostringstream row;
    row << "{\"name\":" << SnapshotJsonString(name) << ",\"file\":" << SnapshotJsonString(file)
        << ",\"dtype\":" << SnapshotJsonString(dtype) << ",\"byte_order\":\"little\",\"bytes\":" << size << ",\"shape\":[";
    for (size_t i = 0; i < shape.size(); ++i) { if (i) row << ','; row << shape[i]; }
    row << "]}\n";
    const auto text = row.str();
    manifest_.AppendAndFlush(text.data(), text.size());
    ++count_;
  }
  size_t Count() const { return count_; }
 private:
  std::filesystem::path directory_;
  SnapshotFile manifest_;
  size_t count_ = 0;
};

}  // namespace lfm2
