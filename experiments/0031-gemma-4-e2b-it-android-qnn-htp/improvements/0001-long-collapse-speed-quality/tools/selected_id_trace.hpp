#pragma once
// Observation only: called AFTER the unchanged sampler selects its real ID,
// BEFORE dialog stop/text filtering. This does not implement a sampler or stop.
#include <cstdint>
#include <cstdio>

inline void gemma_trace_selected_id(std::uint64_t ordinal, std::int32_t token,
                                    bool configured_eos, std::uint64_t n_past) noexcept {
  std::fprintf(stderr,
      "GEMMA_SELECTED_ID_V1 ordinal=%llu token=%d configured_eos=%u n_past=%llu\n",
      static_cast<unsigned long long>(ordinal), static_cast<int>(token),
      static_cast<unsigned>(configured_eos), static_cast<unsigned long long>(n_past));
  // A failed observation write must not alter model/sampler/termination behavior.
  // The collector assesses trace coverage separately and never fills missing IDs.
  std::fflush(stderr);
}
