#!/usr/bin/env python3
"""Install the committed experiment runner into the pinned ignored LiteRT-LM tree."""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
from pathlib import Path

EXPECTED_REVISION = "924e79c91542761242244e4f1651851f822e4cbb"
TARGET = r'''

# Experiment 0025 runner. This generated target is not an upstream modification.
cc_binary(
    name = "litert_lm_canonical_runner",
    srcs = ["litert_lm_canonical_runner.cc"],
    additional_linker_inputs = select({
        "@platforms//os:windows": ["@litert//litert/c:windows_exported_symbols.def"],
        "@platforms//os:linux": [":litert_lm_main.exported_symbols"],
        "//conditions:default": [],
    }),
    linkopts = select({
        "@litert//litert:litert_runtime_link_mode_dynamic": [],
        "@platforms//os:windows": ["/DEF:$(location @litert//litert/c:windows_exported_symbols.def)"],
        "@platforms//os:linux": ["-Wl,--dynamic-list=$(location :litert_lm_main.exported_symbols)"],
        "//conditions:default": ["-Wl,--export-dynamic-symbol=LiteRt*"],
    }) + select({
        "@platforms//os:android": ["-lEGL", "-lGLESv3"],
        "//conditions:default": [],
    }),
    deps = [
        ":engine_factory",
        ":engine_impl_selected",
        ":engine_interface",
        ":engine_settings",
        ":io_types",
        "@com_google_absl//absl/base:log_severity",
        "@com_google_absl//absl/flags:flag",
        "@com_google_absl//absl/flags:parse",
        "@com_google_absl//absl/functional:any_invocable",
        "@com_google_absl//absl/log:absl_check",
        "@com_google_absl//absl/log:globals",
        "@com_google_absl//absl/status",
        "@com_google_absl//absl/status:status_macros",
        "@com_google_absl//absl/status:statusor",
        "@com_google_absl//absl/time",
        "@nlohmann_json//:json",
        "//runtime/core:session_utils",
        "//runtime/executor:llm_executor_settings",
        "//support/tokenizer",
    ],
)
'''


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--runner", type=Path, default=Path(__file__).with_name("litert_lm_canonical_runner.cc"))
    args = parser.parse_args()

    tree = args.tree.resolve()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tree, text=True).strip()
    if revision != EXPECTED_REVISION:
        raise SystemExit(f"unexpected LiteRT-LM revision: {revision}")
    dirty_before = subprocess.check_output(["git", "status", "--short"], cwd=tree, text=True)
    allowed = {" M runtime/engine/BUILD", "?? runtime/engine/litert_lm_canonical_runner.cc"}
    unexpected = {line for line in dirty_before.splitlines() if line not in allowed}
    if unexpected:
        raise SystemExit(f"unexpected pre-existing LiteRT-LM changes: {sorted(unexpected)}")

    destination = tree / "runtime/engine/litert_lm_canonical_runner.cc"
    shutil.copyfile(args.runner.resolve(), destination)
    build = tree / "runtime/engine/BUILD"
    text = build.read_text(encoding="utf-8")
    marker = "# Experiment 0025 runner. This generated target is not an upstream modification."
    if marker in text:
        text = text[: text.index(marker)].rstrip() + "\n"
    build.write_text(text.rstrip() + "\n" + TARGET, encoding="utf-8")

    print(f"revision={revision}")
    print(f"runner_sha256={sha256(args.runner.resolve())}")
    print(subprocess.check_output(["git", "status", "--short"], cwd=tree, text=True), end="")


if __name__ == "__main__":
    main()
