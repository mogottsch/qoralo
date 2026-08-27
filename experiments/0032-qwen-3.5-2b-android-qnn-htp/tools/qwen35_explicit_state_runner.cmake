add_executable(
  qwen35_explicit_state_runner
  ${CMAKE_CURRENT_LIST_DIR}/qwen35_explicit_state_runner.cpp
)
target_include_directories(
  qwen35_explicit_state_runner PUBLIC ${_common_include_directories}
)
target_link_libraries(
  qwen35_explicit_state_runner
  qnn_executorch_backend
  executorch_core
  extension_module
  extension_tensor
  full_portable_ops_lib
  etdump
  flatccrt
  gflags
)
set_target_properties(
  qwen35_explicit_state_runner PROPERTIES LINK_FLAGS "-Wl,-rpath='$ORIGIN'"
)
