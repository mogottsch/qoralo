#!/usr/bin/env python3
"""Build the experiment-0008 harness with the one audited four-thread extension.

The source experiment is copied to an ignored work directory before patching. No
file in experiment 0008 is modified. The resulting APK remains ignored; its
hash-addressed build provenance is committed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SWEEP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SWEEP_ROOT.parents[2]
SOURCE_ANDROID = REPO_ROOT / "experiments" / "0008-sherpa-onnx-android-tts-benchmark" / "android"
SOURCE_AAR = SOURCE_ANDROID / "libs" / "sherpa-onnx-1.13.5.aar"
PATCH = SWEEP_ROOT / "android" / "allow-four-threads.patch"
FOCUSED_TEST = SWEEP_ROOT / "android" / "FourThreadDescriptorTest.java"
EXPECTED_AAR_SHA256 = "6419cd8bc983e0c4fab06067f0fe0313fdc0f7103818ac1e7a08d50787b7a82b"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(argv: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, cwd=cwd, env=env, text=True, encoding="utf-8", errors="replace",
                            capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(argv)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
    return result


def source_manifest() -> list[dict]:
    roots = [
        SOURCE_ANDROID / "build.gradle.kts",
        SOURCE_ANDROID / "settings.gradle.kts",
        SOURCE_ANDROID / "gradle.properties",
        SOURCE_ANDROID / "app" / "build.gradle.kts",
    ]
    roots.extend(sorted(path for path in (SOURCE_ANDROID / "app" / "src").rglob("*") if path.is_file()))
    rows = []
    for path in roots:
        rows.append({
            "path": path.relative_to(REPO_ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=REPO_ROOT / "artifacts" / "0009" / "thread-sweep" / "android-build",
    )
    parser.add_argument(
        "--gradle",
        type=Path,
        default=REPO_ROOT / "artifacts" / "tools" / "gradle-8.10.2" / "bin" / "gradle",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=SWEEP_ROOT / "results" / "build-provenance.json",
    )
    args = parser.parse_args()
    build_dir = args.build_dir.resolve()
    gradle = args.gradle.resolve()

    if not gradle.is_file():
        raise SystemExit(f"Gradle 8.10.2 binary not found: {gradle}")
    if SOURCE_AAR.stat().st_size != 49_095_090 or sha256_file(SOURCE_AAR) != EXPECTED_AAR_SHA256:
        raise SystemExit("pinned sherpa-onnx 1.13.5 AAR is absent or has drifted")

    rows = source_manifest()
    tree_digest = hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if build_dir.exists():
        shutil.rmtree(build_dir)
    shutil.copytree(
        SOURCE_ANDROID,
        build_dir,
        ignore=shutil.ignore_patterns(".gradle", "build", "libs"),
    )
    (build_dir / "libs").mkdir(parents=True)
    shutil.copy2(SOURCE_AAR, build_dir / "libs" / SOURCE_AAR.name)

    # Reject offset/fuzzy application so the audited one-line source delta cannot
    # silently attach to a merely similar future source tree.
    run(["patch", "--batch", "--forward", "--fuzz=0", "-p1", "-i", str(PATCH)], cwd=build_dir)
    test_destination = (
        build_dir / "app" / "src" / "test" / "java" / "dev" / "moket" / "ttsbench" /
        FOCUSED_TEST.name
    )
    shutil.copy2(FOCUSED_TEST, test_destination)
    # The inherited experiment-0008 domain test locates these three committed
    # descriptors by walking upward from the Gradle working directory. Supply
    # descriptor-only fixtures in the isolated copy; no model payload is copied
    # or packaged.
    descriptor_fixtures = {
        "models/pocket/android-descriptor.json": REPO_ROOT / "experiments" / "0008-sherpa-onnx-android-tts-benchmark" / "models" / "pocket" / "android-descriptor.json",
        "models/kokoro/benchmark-descriptor.json": REPO_ROOT / "experiments" / "0008-sherpa-onnx-android-tts-benchmark" / "models" / "kokoro" / "benchmark-descriptor.json",
        "models/supertonic-3/android-descriptor.json": REPO_ROOT / "experiments" / "0008-sherpa-onnx-android-tts-benchmark" / "models" / "supertonic-3" / "android-descriptor.json",
    }
    for relative, source in descriptor_fixtures.items():
        destination = build_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    patched_descriptor = (
        build_dir / "app" / "src" / "main" / "java" / "dev" / "moket" / "ttsbench" /
        "BenchmarkDescriptor.java"
    )
    patched_text = patched_descriptor.read_text(encoding="utf-8")
    expected_fragment = 'numThreads != 1 && numThreads != 2 && numThreads != 4'
    if patched_text.count(expected_fragment) != 1 or "threads must be 1, 2, or 4" not in patched_text:
        raise SystemExit("four-thread patch did not produce the audited source")

    env = dict(os.environ)
    configured_sdk = Path(env.get("ANDROID_SDK_ROOT") or env.get("ANDROID_HOME") or "")
    fallback_sdk = Path.home() / "Android" / "Sdk"
    if not (configured_sdk / "platforms").is_dir() and (fallback_sdk / "platforms").is_dir():
        configured_sdk = fallback_sdk
    if not (configured_sdk / "platforms").is_dir():
        raise SystemExit("Android SDK is unavailable")
    env["ANDROID_SDK_ROOT"] = str(configured_sdk)
    env["ANDROID_HOME"] = str(configured_sdk)
    gradle_version = run([str(gradle), "--version"], cwd=build_dir, env=env).stdout
    build = run(
        [str(gradle), "--no-daemon", "testDebugUnitTest", "assembleDebug"],
        cwd=build_dir,
        env=env,
    )
    apk = build_dir / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
    inspector = REPO_ROOT / "experiments" / "0008-sherpa-onnx-android-tts-benchmark" / "tools" / "inspect_apk.py"
    inspection = json.loads(
        run(["python3", str(inspector), str(apk), "--aar", str(build_dir / "libs" / SOURCE_AAR.name)],
            cwd=REPO_ROOT).stdout
    )

    git_commit = run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT).stdout.strip()
    report = {
        "schema_version": 1,
        "experiment": "0009-android-tts-optimization/thread-sweep",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_experiment": "experiments/0008-sherpa-onnx-android-tts-benchmark/android",
        "source_git_commit": git_commit,
        "source_files": rows,
        "source_tree_manifest_sha256": tree_digest,
        "sweep_only_changes": [
            {
                "path": "app/src/main/java/dev/moket/ttsbench/BenchmarkDescriptor.java",
                "purpose": "accept num_threads=4 in addition to the existing 1 and 2",
                "patch": "android/allow-four-threads.patch",
                "patch_sha256": sha256_file(PATCH),
            },
            {
                "path": "app/src/test/java/dev/moket/ttsbench/FourThreadDescriptorTest.java",
                "purpose": "prove that only 1, 2, and 4 are accepted",
                "source": "android/FourThreadDescriptorTest.java",
                "source_sha256": sha256_file(FOCUSED_TEST),
            },
        ],
        "runtime": {
            "provider": "cpu",
            "sherpa_onnx_version": "1.13.5",
            "sherpa_onnx_tag_commit": "3dc7c569f31ca2cd4a20ed6f7db780327e6714c5",
            "aar_bytes": SOURCE_AAR.stat().st_size,
            "aar_sha256": sha256_file(SOURCE_AAR),
        },
        "build": {
            "gradle_binary": str(gradle.relative_to(REPO_ROOT)) if gradle.is_relative_to(REPO_ROOT) else str(gradle),
            "gradle_version_summary": next(
                (line.strip() for line in gradle_version.splitlines() if line.strip().startswith("Gradle ")),
                "unavailable",
            ),
            "command": "gradle --no-daemon testDebugUnitTest assembleDebug",
            "unit_tests": "passed",
            "build_result": "passed",
            "stdout_sha256": hashlib.sha256(build.stdout.encode("utf-8")).hexdigest(),
            "stderr_sha256": hashlib.sha256(build.stderr.encode("utf-8")).hexdigest(),
            "ignored_apk_path": str(apk.relative_to(REPO_ROOT)),
        },
        "apk_inspection": inspection,
        "limitations": [
            "The debug APK is an experiment harness, not a production application.",
            "The APK is ignored; this report and later device receipts retain its digest.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(apk)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
