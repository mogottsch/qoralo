#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <random>
#include <stdexcept>
#include <vector>

namespace provider {
constexpr int64_t kText = 320, kLatent = 512, kChannels = 144, kHop = 3072, kRate = 44100;
constexpr int kSteps = 8;
constexpr float kSpeed = 1.05f;
constexpr uint32_t kSeed = 20260911;
struct Extent { float duration; int64_t predicted_frames, native_length; };
inline Extent extent(float raw) {
  const float duration = raw / kSpeed;
  if (!std::isfinite(duration) || duration <= 0 || duration > 69) throw std::runtime_error("Provider duration outside supported range");
  const float waveform = duration * float(kRate);
  const int64_t frames = int64_t(waveform);
  float size = waveform + float(kHop); size = size - 1.f; size = size / float(kHop);
  const int64_t length = int32_t(size);
  if (length <= 0 || length > kLatent || length != (frames + kHop - 1) / kHop)
    throw std::runtime_error("Provider native latent extent does not fit; no clipping or duration override");
  return {duration, frames, length};
}
inline std::vector<int32_t> edges(int64_t native, int64_t bucket, int radius) {
  if (native < 1 || native > bucket || radius < 1) throw std::runtime_error("Invalid native EDGE layout");
  std::vector<int32_t> result(static_cast<size_t>(bucket + 2 * radius));
  for (int64_t i = 0; i < bucket + 2 * radius; ++i) result[i] = int32_t(std::clamp(i - radius, int64_t(0), native - 1));
  return result;
}
// NumPy legacy RandomState standard_normal: MT19937 doubles + cached Marsaglia polar pair.
class Gaussian {
 public:
  void reset(uint32_t seed = kSeed) { mt.seed(seed); cached = false; saved = 0; consumed = 0; }
  float next() {
    ++consumed;
    if (cached) { cached = false; return static_cast<float>(saved); }
    double x1, x2, r2;
    do { x1 = 2.0 * uniform() - 1.0; x2 = 2.0 * uniform() - 1.0; r2 = x1*x1 + x2*x2; } while (r2 >= 1.0 || r2 == 0.0);
    const double factor = std::sqrt(-2.0 * std::log(r2) / r2);
    saved = factor * x1; cached = true;
    return static_cast<float>(factor * x2);
  }
  uint64_t count() const { return consumed; }
 private:
  double uniform() { const uint32_t a = mt() >> 5, b = mt() >> 6; return (double(a) * 67108864.0 + b) / 9007199254740992.0; }
  std::mt19937 mt{kSeed}; bool cached = false; double saved = 0; uint64_t consumed = 0;
};
inline int16_t pcm16(float value) {
  if (!std::isfinite(value)) throw std::runtime_error("Nonfinite provider waveform");
  const long q = static_cast<long>(std::floor(std::clamp(value, -1.f, 1.f) * 32768.f));
  return static_cast<int16_t>(std::clamp(q, -32768L, 32767L));
}
}
