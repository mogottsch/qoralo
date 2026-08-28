#!/usr/bin/env bash
set -euo pipefail
PROJECT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$PROJECT/app/build/native-policy-test"
mkdir -p "$OUT"
${CXX:-c++} -std=c++17 -Wall -Wextra -Werror \
  -I"$PROJECT/app/src/main/cpp" \
  "$PROJECT/app/src/test/cpp/tensor_validation_test.cpp" \
  -o "$OUT/tensor_validation_test"
"$OUT/tensor_validation_test"
echo "native policy tests: passed"
