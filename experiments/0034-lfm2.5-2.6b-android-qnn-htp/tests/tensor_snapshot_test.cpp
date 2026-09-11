#include <cassert>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>
#include "../phone/tensor_snapshot.hpp"

int main(int argc, char** argv) {
  assert(argc == 2);
  const std::filesystem::path root = argv[1];
  const uint32_t special[] = {0x80000000U, 0x7fc12345U, 0x7f800000U};
  {
    lfm2::TensorSnapshot output(root / "outputs");
    output.Add("signed-zero/\"nan\"\n", "float32", {3}, special, sizeof(special));
    assert(output.Count() == 1);
    bool rejected = false;
    try { output.Add("bad", "float16", {1}, special, 2); }
    catch (const std::runtime_error&) { rejected = true; }
    assert(rejected && output.Count() == 1);
    // A later failure must leave the first exact raw tensor and manifest intact.
  }
  std::ifstream file(root / "outputs/0.raw", std::ios::binary);
  const std::string raw{std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>()};
  assert(raw == std::string(reinterpret_cast<const char*>(special), sizeof(special)));
  bool rejected = false;
  try { lfm2::TensorSnapshot again(root / "outputs"); }
  catch (const std::runtime_error&) { rejected = true; }
  assert(rejected);
  const int64_t positions[] = {0, 1, 170};
  lfm2::TensorSnapshot input(root / "inputs");
  input.Add("position_ids", "int64", {1, 3}, positions, sizeof(positions));
  assert(input.Count() == 1);
  return 0;
}
