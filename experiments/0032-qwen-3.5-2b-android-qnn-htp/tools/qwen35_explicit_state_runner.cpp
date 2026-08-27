/*
 * Token-ID runner for experiment 0032's explicit-state Qwen3.5 QNN graph.
 *
 * Tokenization stays outside this binary: inputs and outputs are little-endian
 * int32 token-ID files. The loaded ExecuTorch/QNN method is reused while this
 * runner explicitly resets or advances every KV, recurrent, and convolution
 * state tensor.
 */
#include <executorch/backends/qualcomm/runtime/QnnExecuTorch.h>
#include <executorch/devtools/etdump/etdump_flatcc.h>
#include <executorch/extension/module/module.h>
#include <executorch/extension/tensor/tensor.h>
#include <executorch/runtime/backend/interface.h>
#include <executorch/runtime/backend/options.h>
#include <executorch/runtime/platform/runtime.h>

#include <gflags/gflags.h>

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

DEFINE_string(model_path, "model.pte", "Exact experiment-0032 ExecuTorch PTE.");
DEFINE_string(prompt_ids, "prompt.int32le",
              "Prompt token IDs as little-endian int32.");
DEFINE_string(output_ids, "generated.int32le",
              "Generated token IDs as little-endian int32.");
DEFINE_string(metrics_path, "metrics.json",
              "Per-request timing and identity JSON.");
DEFINE_string(etdump_path, "etdump.etdp", "ETDump output path.");
DEFINE_int32(max_new_tokens, 1,
             "Maximum generated tokens (canonical ceiling: 2048).");
DEFINE_int32(context_tokens, 4096, "Compiled context length.");
DEFINE_int32(n_layers, 24, "Number of model layers.");
DEFINE_string(eos_ids, "248044,248046", "Comma-separated model EOS token IDs.");
DEFINE_int32(log_level, 5, "QNN runtime log level.");
DEFINE_int32(profile_level, 2, "QNN profiling level.");
DEFINE_int32(htp_performance_mode, 0, "QNN HTP performance mode.");

using Clock = std::chrono::steady_clock;
using executorch::aten::ScalarType;
using executorch::aten::Tensor;
using executorch::extension::make_tensor_ptr;
using executorch::extension::Module;
using executorch::extension::TensorPtr;
using executorch::runtime::BackendOption;
using executorch::runtime::Error;
using executorch::runtime::EValue;
using executorch::runtime::MethodMeta;
using executorch::runtime::TensorInfo;

namespace {

struct InputBuffer {
  std::vector<uint8_t> bytes;
  TensorPtr tensor;
};

double milliseconds(Clock::time_point start, Clock::time_point end) {
  return std::chrono::duration<double, std::milli>(end - start).count();
}

std::vector<int32_t> read_ids(const std::string &path) {
  std::ifstream stream(path, std::ios::binary | std::ios::ate);
  if (!stream) {
    throw std::runtime_error("cannot open token IDs: " + path);
  }
  const auto bytes = stream.tellg();
  if (bytes <= 0 || bytes % static_cast<std::streamoff>(sizeof(int32_t)) != 0) {
    throw std::runtime_error("token-ID file must be nonempty int32le: " + path);
  }
  std::vector<int32_t> ids(static_cast<size_t>(bytes) / sizeof(int32_t));
  stream.seekg(0);
  stream.read(reinterpret_cast<char *>(ids.data()), bytes);
  if (!stream) {
    throw std::runtime_error("failed reading token IDs: " + path);
  }
  return ids;
}

void write_ids(const std::string &path, const std::vector<int32_t> &ids) {
  std::ofstream stream(path, std::ios::binary);
  stream.write(reinterpret_cast<const char *>(ids.data()),
               static_cast<std::streamsize>(ids.size() * sizeof(int32_t)));
  if (!stream) {
    throw std::runtime_error("failed writing token IDs: " + path);
  }
}

std::vector<int32_t> parse_ids(const std::string &text) {
  std::vector<int32_t> result;
  std::stringstream stream(text);
  std::string item;
  while (std::getline(stream, item, ',')) {
    result.push_back(std::stoi(item));
  }
  return result;
}

bool is_eos(int32_t token, const std::vector<int32_t> &eos_ids) {
  return std::find(eos_ids.begin(), eos_ids.end(), token) != eos_ids.end();
}

int32_t greedy_argmax(const Tensor &logits) {
  if (logits.scalar_type() != ScalarType::Float) {
    throw std::runtime_error("expected FP32 logits output");
  }
  const float *values = logits.const_data_ptr<float>();
  size_t best = 0;
  for (size_t index = 1; index < static_cast<size_t>(logits.numel()); ++index) {
    if (values[index] > values[best]) {
      best = index;
    }
  }
  return static_cast<int32_t>(best);
}

void copy_state(Tensor &input, const Tensor &output, int32_t position,
                bool state_a) {
  if (input.scalar_type() != ScalarType::Float ||
      output.scalar_type() != ScalarType::Float) {
    throw std::runtime_error("expected FP32 explicit state tensors");
  }
  float *destination = input.mutable_data_ptr<float>();
  const float *source = output.const_data_ptr<float>();
  if (input.nbytes() == output.nbytes()) {
    std::memcpy(destination, source, output.nbytes());
    return;
  }
  if (input.dim() != 4 || output.dim() != 4 || position < 0) {
    throw std::runtime_error("unexpected full-attention state shape");
  }
  if (state_a) {
    // Key input [1,H,D,context-1], output [1,H,D,1].
    const size_t cache = static_cast<size_t>(input.size(3));
    if (output.size(3) != 1 || static_cast<size_t>(position) >= cache) {
      throw std::runtime_error("key-cache position outside compiled context");
    }
    for (size_t index = 0; index < static_cast<size_t>(output.numel());
         ++index) {
      destination[index * cache + static_cast<size_t>(position)] =
          source[index];
    }
  } else {
    // Value input [1,H,context-1,D], output [1,H,1,D].
    const size_t cache = static_cast<size_t>(input.size(2));
    const size_t width = static_cast<size_t>(input.size(3));
    if (output.size(2) != 1 || static_cast<size_t>(position) >= cache ||
        output.numel() % width != 0) {
      throw std::runtime_error("value-cache position outside compiled context");
    }
    const size_t groups = static_cast<size_t>(output.numel()) / width;
    for (size_t group = 0; group < groups; ++group) {
      std::memcpy(destination +
                      (group * cache + static_cast<size_t>(position)) * width,
                  source + group * width, width * sizeof(float));
    }
  }
}

void configure_qnn() {
  executorch::runtime::BackendOptions<3> options;
  if (options.set_option(QNN_RUNTIME_LOG_LEVEL, FLAGS_log_level) != Error::Ok ||
      options.set_option(QNN_RUNTIME_PROFILE_LEVEL, FLAGS_profile_level) !=
          Error::Ok ||
      options.set_option(QNN_RUNTIME_HTP_PERFORMANCE_MODE,
                         FLAGS_htp_performance_mode) != Error::Ok ||
      executorch::runtime::set_option(QNN_BACKEND, options.view()) !=
          Error::Ok) {
    throw std::runtime_error("failed to configure QNN runtime options");
  }
}

} // namespace

int main(int argc, char **argv) {
  try {
    executorch::runtime::runtime_init();
    gflags::ParseCommandLineFlags(&argc, &argv, true);
    if (argc != 1) {
      throw std::runtime_error("unexpected positional arguments");
    }
    if (FLAGS_n_layers <= 0 || FLAGS_max_new_tokens <= 0 ||
        FLAGS_max_new_tokens > 2048 || FLAGS_context_tokens <= 1) {
      throw std::runtime_error("invalid layer, context, or generation limits");
    }
    configure_qnn();

    const auto setup_start = Clock::now();
    auto tracer = std::make_unique<executorch::etdump::ETDumpGen>();
    auto *tracer_ptr = tracer.get();
    Module module(FLAGS_model_path, Module::LoadMode::MmapUseMlockIgnoreErrors,
                  std::move(tracer));
    if (module.load_forward() != Error::Ok) {
      throw std::runtime_error("failed to load forward method");
    }
    auto meta_result = module.method_meta("forward");
    if (!meta_result.ok()) {
      throw std::runtime_error("failed to load forward metadata");
    }
    MethodMeta meta = meta_result.get();
    const size_t expected_inputs = static_cast<size_t>(3 + 2 * FLAGS_n_layers);
    const size_t expected_outputs = static_cast<size_t>(1 + 2 * FLAGS_n_layers);
    if (meta.num_inputs() != expected_inputs ||
        meta.num_outputs() != expected_outputs) {
      throw std::runtime_error("PTE does not match explicit-state ABI");
    }

    std::vector<std::unique_ptr<InputBuffer>> inputs;
    inputs.reserve(expected_inputs);
    std::vector<EValue> values;
    values.reserve(expected_inputs);
    for (size_t index = 0; index < expected_inputs; ++index) {
      auto info_result = meta.input_tensor_meta(index);
      if (!info_result.ok()) {
        throw std::runtime_error("missing input tensor metadata");
      }
      TensorInfo info = info_result.get();
      auto buffer = std::make_unique<InputBuffer>();
      buffer->bytes.resize(info.nbytes(), 0);
      std::vector<executorch::aten::SizesType> sizes(info.sizes().begin(),
                                                     info.sizes().end());
      std::vector<executorch::aten::DimOrderType> dim_order(
          info.dim_order().begin(), info.dim_order().end());
      buffer->tensor = make_tensor_ptr(
          std::move(sizes), buffer->bytes.data(), std::move(dim_order), {},
          info.scalar_type(), executorch::aten::TensorShapeDynamism::STATIC);
      values.emplace_back(*buffer->tensor);
      inputs.push_back(std::move(buffer));
    }
    if (inputs[0]->tensor->scalar_type() != ScalarType::Int ||
        inputs[1]->tensor->scalar_type() != ScalarType::Float ||
        inputs[2]->tensor->scalar_type() != ScalarType::Int) {
      throw std::runtime_error("unexpected token/mask/position dtypes");
    }
    const auto setup_end = Clock::now();

    const auto request_start = Clock::now();
    const auto reset_start = Clock::now();
    for (size_t index = 3; index < inputs.size(); ++index) {
      std::memset(inputs[index]->bytes.data(), 0, inputs[index]->bytes.size());
    }
    float *mask = inputs[1]->tensor->mutable_data_ptr<float>();
    std::fill(mask, mask + inputs[1]->tensor->numel(), -65504.0f);
    mask[inputs[1]->tensor->numel() - 1] = 0.0f;
    const auto reset_end = Clock::now();

    const auto prompt_load_start = Clock::now();
    std::vector<int32_t> prompt = read_ids(FLAGS_prompt_ids);
    const auto prompt_load_end = Clock::now();
    if (prompt.size() + static_cast<size_t>(FLAGS_max_new_tokens) >
        static_cast<size_t>(FLAGS_context_tokens)) {
      throw std::runtime_error("prompt plus max_new_tokens exceeds context");
    }
    const auto eos_ids = parse_ids(FLAGS_eos_ids);
    std::vector<int32_t> generated;
    generated.reserve(FLAGS_max_new_tokens);
    std::vector<double> execute_ms;
    execute_ms.reserve(prompt.size() + FLAGS_max_new_tokens - 1);
    int32_t input_token = 0;
    bool first_token_delivered = false;
    Clock::time_point prefill_end;
    Clock::time_point first_token_time;
    std::string stop_reason = "max_tokens";

    const size_t total_steps =
        prompt.size() + static_cast<size_t>(FLAGS_max_new_tokens) - 1;
    const auto prefill_start = Clock::now();
    for (size_t position = 0; position < total_steps; ++position) {
      if (position < prompt.size()) {
        input_token = prompt[position];
      } else {
        input_token = generated.back();
      }
      *inputs[0]->tensor->mutable_data_ptr<int32_t>() = input_token;
      *inputs[2]->tensor->mutable_data_ptr<int32_t>() =
          static_cast<int32_t>(position);
      if (position > 0) {
        mask[position - 1] = 0.0f;
      }

      const auto execute_start = Clock::now();
      auto output_result = module.execute("forward", values);
      const auto execute_end = Clock::now();
      if (!output_result.ok()) {
        throw std::runtime_error("forward execution failed");
      }
      execute_ms.push_back(milliseconds(execute_start, execute_end));
      auto &outputs = output_result.get();
      if (outputs.size() != expected_outputs) {
        throw std::runtime_error("wrong explicit-state output count");
      }
      for (int32_t layer = 0; layer < FLAGS_n_layers; ++layer) {
        copy_state(*inputs[3 + layer]->tensor, outputs[1 + layer].toTensor(),
                   static_cast<int32_t>(position), true);
        copy_state(*inputs[3 + FLAGS_n_layers + layer]->tensor,
                   outputs[1 + FLAGS_n_layers + layer].toTensor(),
                   static_cast<int32_t>(position), false);
      }

      if (position + 1 >= prompt.size()) {
        if (!first_token_delivered) {
          prefill_end = execute_end;
        }
        const int32_t next = greedy_argmax(outputs[0].toTensor());
        generated.push_back(next);
        if (!first_token_delivered) {
          first_token_time = Clock::now();
          first_token_delivered = true;
        }
        if (is_eos(next, eos_ids)) {
          stop_reason = "eos";
          break;
        }
        if (generated.size() >= static_cast<size_t>(FLAGS_max_new_tokens)) {
          break;
        }
      }
    }
    const auto request_end = Clock::now();
    write_ids(FLAGS_output_ids, generated);

    auto dump = tracer_ptr->get_etdump_data();
    if (dump.buf != nullptr && dump.size > 0) {
      std::ofstream stream(FLAGS_etdump_path, std::ios::binary);
      stream.write(static_cast<const char *>(dump.buf), dump.size);
      free(dump.buf);
    }

    const size_t prompt_exec_count = prompt.size();
    double prefill_execute_ms = 0.0;
    for (size_t index = 0;
         index < std::min(prompt_exec_count, execute_ms.size()); ++index) {
      prefill_execute_ms += execute_ms[index];
    }
    double decode_execute_ms = 0.0;
    for (size_t index = prompt_exec_count; index < execute_ms.size(); ++index) {
      decode_execute_ms += execute_ms[index];
    }
    std::ofstream metrics(FLAGS_metrics_path);
    metrics
        << "{\n"
        << "  \"schema_version\": 1,\n"
        << "  \"runner\": \"qwen35_explicit_state_runner\",\n"
        << "  \"state_abi\": 1,\n"
        << "  \"prompt_tokens\": " << prompt.size() << ",\n"
        << "  \"generated_tokens\": " << generated.size() << ",\n"
        << "  \"stop_reason\": \"" << stop_reason << "\",\n"
        << "  \"setup_ms\": " << milliseconds(setup_start, setup_end) << ",\n"
        << "  \"reset_ms\": " << milliseconds(reset_start, reset_end) << ",\n"
        << "  \"reset_included_in_total\": true,\n"
        << "  \"token_ids_load_ms\": "
        << milliseconds(prompt_load_start, prompt_load_end) << ",\n"
        << "  \"request_total_ms\": "
        << milliseconds(request_start, request_end) << ",\n"
        << "  \"ttft_ms\": " << milliseconds(request_start, first_token_time)
        << ",\n"
        << "  \"prefill_ms\": " << milliseconds(prefill_start, prefill_end)
        << ",\n"
        << "  \"post_prefill_to_first_token_ms\": "
        << milliseconds(prefill_end, first_token_time) << ",\n"
        << "  \"decode_ms\": "
        << (generated.size() > 1 ? milliseconds(first_token_time, request_end)
                                 : 0.0)
        << ",\n"
        << "  \"prefill_execute_ms\": " << prefill_execute_ms << ",\n"
        << "  \"decode_execute_ms\": " << decode_execute_ms << ",\n"
        << "  \"method_reused_across_token_steps\": true,\n"
        << "  \"loaded_route_reused_across_requests\": false,\n"
        << "  \"campaign_eligibility\": \"single_request_viability_only\",\n"
        << "  \"request_isolation\": \"explicit_zero_initial_state_inputs\"\n"
        << "}\n";
    if (!metrics) {
      throw std::runtime_error("failed writing metrics");
    }
    return 0;
  } catch (const std::exception &error) {
    std::fprintf(stderr, "qwen35 runner error: %s\n", error.what());
    return 1;
  }
}
