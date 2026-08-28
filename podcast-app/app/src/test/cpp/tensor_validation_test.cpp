#include "tensor_validation.h"

#include <cassert>
#include <limits>
#include <stdexcept>
#include <vector>

int main() {
  RequireAllFinite(std::vector<float>{-1.0f, 0.0f, 1.0f}, "finite");
  for (float invalid : {std::numeric_limits<float>::infinity(), -std::numeric_limits<float>::infinity(),
                        std::numeric_limits<float>::quiet_NaN()}) {
    bool rejected = false;
    try {
      RequireAllFinite(std::vector<float>{0.0f, invalid, 1.0f}, "tensor");
    } catch (const std::runtime_error &) {
      rejected = true;
    }
    assert(rejected);
  }
  bool empty_rejected = false;
  try {
    RequireAllFinite({}, "tensor");
  } catch (const std::runtime_error &) {
    empty_rejected = true;
  }
  assert(empty_rejected);
  return 0;
}
