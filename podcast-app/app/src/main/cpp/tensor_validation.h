#pragma once

#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

inline void RequireAllFinite(const std::vector<float> &values, const std::string &label) {
  if (values.empty()) throw std::runtime_error(label + " output is empty");
  for (float value : values) {
    if (!std::isfinite(value)) throw std::runtime_error(label + " output contains a non-finite value");
  }
}
