cmake_minimum_required(VERSION 3.22.1)
project(podcast_runtime LANGUAGES CXX)

if(NOT EXISTS "${ONNXRUNTIME_INCLUDE_DIR}/onnxruntime_cxx_api.h")
  message(FATAL_ERROR "ONNXRUNTIME_INCLUDE_DIR must contain onnxruntime_cxx_api.h")
endif()
if(NOT EXISTS "${ONNXRUNTIME_LIBRARY}")
  message(FATAL_ERROR "ONNXRUNTIME_LIBRARY is missing")
endif()

add_library(onnxruntime SHARED IMPORTED)
set_target_properties(onnxruntime PROPERTIES IMPORTED_LOCATION "${ONNXRUNTIME_LIBRARY}")

add_library(podcast_runtime SHARED podcast_runtime.cpp)
target_compile_features(podcast_runtime PRIVATE cxx_std_17)
target_compile_definitions(podcast_runtime PRIVATE $<$<CONFIG:Debug>:PODCAST_WIRING_DIAGNOSTICS=1>)
target_compile_options(podcast_runtime PRIVATE -Wall -Wextra -Werror -fexceptions -frtti)
target_include_directories(podcast_runtime PRIVATE "${ONNXRUNTIME_INCLUDE_DIR}")
target_link_libraries(podcast_runtime PRIVATE onnxruntime android log dl)
