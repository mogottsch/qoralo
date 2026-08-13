"""Fail-closed host orchestration for the experiment 0008 Android benchmark.

All adb commands are argv lists.  Readiness and the non-blocking repository phone
lock are established before a mutating command is allowed.  The command adapter,
clock, and sleeper are injected so the safety boundary can be tested without a
phone.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import re
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Mapping, Protocol, Sequence

TARGET_MODEL = "SM-S918B"
TARGET_ABI = "arm64-v8a"
DEFAULT_PACKAGE = "dev.moket.ttsbench"
DEFAULT_COMPONENT = f"{DEFAULT_PACKAGE}/.BenchmarkActivity"
REMOTE_STORAGE = "/sdcard"
REMOTE_FILES = f"{REMOTE_STORAGE}/Android/data/{DEFAULT_PACKAGE}/files"


class RunnerError(RuntimeError):
    """An expected, evidence-worthy orchestration failure."""


class LockConflict(RunnerError):
    pass


class DeviceNotReady(RunnerError):
    pass


class ThermalEligibilityError(DeviceNotReady):
    def __init__(self, message: str, polls: list["ThermalPoll"]):
        super().__init__(message)
        self.polls = polls


class CommandFailed(RunnerError):
    pass


@dataclass(frozen=True)
class Completed:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class Commands(Protocol):
    def run(self, argv: Sequence[str], *, timeout: float | None = None) -> Completed: ...


class SubprocessCommands:
    def run(self, argv: Sequence[str], *, timeout: float | None = None) -> Completed:
        try:
            p = subprocess.run(list(argv), text=True, capture_output=True, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise CommandFailed(f"command could not complete: {argv[0]}") from exc
        return Completed(p.returncode, p.stdout, p.stderr)


@dataclass(frozen=True)
class Device:
    serial: str
    state: str
    details: Mapping[str, str]


@dataclass(frozen=True)
class LocalFile:
    source: Path
    relative_path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class ThermalPoll:
    monotonic_seconds: float
    status: str | None
    battery_temperature_c: float | None
    eligible: bool
    reason: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(value: str) -> str:
    path = PurePosixPath(value)
    # Paths become operands to `adb shell`, whose argv is interpreted by a remote
    # shell.  A conservative component allowlist prevents metacharacters, spaces,
    # and option-like names from changing the intended command.
    safe_component = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
    if (not value or path.is_absolute() or ".." in path.parts or "." in path.parts
            or any(safe_component.fullmatch(part) is None for part in path.parts)):
        raise RunnerError(f"unsafe relative path: {value!r}")
    return path.as_posix()


def load_inventory(path: Path, source_dir: Path) -> list[LocalFile]:
    """Load and verify a deterministic {files:[path,size,sha256]} inventory."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows = raw["files"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RunnerError("invalid deployed-file inventory") from exc
    if not isinstance(rows, list) or not rows:
        raise RunnerError("inventory must contain at least one file")
    answer: list[LocalFile] = []
    seen: set[str] = set()
    for row in rows:
        try:
            rel = _safe_relative(row["path"])
            expected_size = int(row["size"])
            expected_hash = str(row["sha256"]).lower()
        except (KeyError, TypeError, ValueError) as exc:
            raise RunnerError("malformed inventory entry") from exc
        if rel in seen or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            raise RunnerError("duplicate path or invalid inventory digest")
        seen.add(rel)
        source = source_dir / rel
        if not source.is_file() or source.is_symlink():
            raise RunnerError(f"missing or linked staged file: {rel}")
        if source.stat().st_size != expected_size or sha256_file(source) != expected_hash:
            raise RunnerError(f"local staged file does not match inventory: {rel}")
        answer.append(LocalFile(source, rel, expected_size, expected_hash))
    if [item.relative_path for item in answer] != sorted(seen):
        raise RunnerError("inventory paths must be sorted")
    return answer


class PhoneLock:
    def __init__(self, path: Path):
        self.path = path
        self._stream = None

    def __enter__(self) -> "PhoneLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = self.path.open("a+")
        try:
            fcntl.flock(self._stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self._stream.close()
            self._stream = None
            raise LockConflict(f"phone lock is held: {self.path}") from exc
        self._stream.seek(0)
        self._stream.truncate()
        self._stream.write(f"pid={os.getpid()}\n")
        self._stream.flush()
        return self

    def __exit__(self, *_: object) -> None:
        if self._stream is not None:
            fcntl.flock(self._stream.fileno(), fcntl.LOCK_UN)
            self._stream.close()
            self._stream = None


def parse_devices(output: str) -> list[Device]:
    devices: list[Device] = []
    for line in output.splitlines():
        if not line.strip() or line.startswith("List of devices") or line.startswith("*"):
            continue
        fields = line.split()
        if len(fields) < 2:
            continue
        details = dict(field.split(":", 1) for field in fields[2:] if ":" in field)
        devices.append(Device(fields[0], fields[1], details))
    return devices


def parse_battery_temperature(text: str) -> float | None:
    match = re.search(r"^\s*temperature:\s*(-?\d+)\s*$", text, re.MULTILINE)
    return None if match is None else int(match.group(1)) / 10.0


def parse_thermal_status(text: str) -> str | None:
    match = re.search(r"Thermal Status:\s*(?:0|NONE)\b", text, re.IGNORECASE)
    if match:
        return "NONE"
    numeric = re.search(r"Thermal Status:\s*(\d+)\b", text, re.IGNORECASE)
    if numeric:
        return f"STATUS_{numeric.group(1)}"
    named = re.search(r"Thermal Status:\s*([A-Z_]+)\b", text, re.IGNORECASE)
    return None if named is None else named.group(1).upper()


class DeviceRunner:
    def __init__(
        self,
        commands: Commands,
        *,
        lock_path: Path,
        artifact_dir: Path,
        package: str = DEFAULT_PACKAGE,
        component: str = DEFAULT_COMPONENT,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.commands = commands
        self.lock_path = lock_path
        self.artifact_dir = artifact_dir
        self.package = package
        self.component = component
        self.clock = clock
        self.sleep = sleep
        self.serial: str | None = None

    def _adb(self, *args: str, timeout: float | None = None, check: bool = True) -> Completed:
        prefix = ["adb"]
        if self.serial:
            prefix += ["-s", self.serial]
        result = self.commands.run([*prefix, *args], timeout=timeout)
        if check and result.returncode != 0:
            raise CommandFailed(f"adb command failed: {args[0] if args else 'adb'}")
        return result

    def readiness(self) -> dict[str, str]:
        listed = self.commands.run(["adb", "devices", "-l"], timeout=15)
        if listed.returncode != 0:
            raise DeviceNotReady("adb device enumeration failed")
        devices = parse_devices(listed.stdout)
        if len(devices) != 1:
            raise DeviceNotReady(f"expected exactly one device, observed {len(devices)}")
        device = devices[0]
        if device.state != "device":
            raise DeviceNotReady(f"device is not authorized and online: {device.state}")
        self.serial = device.serial
        model = self._adb("shell", "getprop", "ro.product.model").stdout.strip()
        if model != TARGET_MODEL:
            raise DeviceNotReady(f"wrong device model: {model or 'unknown'}")
        abi = self._adb("shell", "getprop", "ro.product.cpu.abi").stdout.strip()
        boot = self._adb("shell", "getprop", "sys.boot_completed").stdout.strip()
        policy = self._adb("shell", "dumpsys", "window", "policy").stdout
        unlocked = bool(re.search(r"(?:mShowingLockscreen|isKeyguardShowing)=false\b", policy))
        if boot != "1" or abi != TARGET_ABI or not unlocked:
            raise DeviceNotReady("device is booting, locked, or has the wrong ABI")
        def prop(name: str) -> str:
            return self._adb("shell", "getprop", name).stdout.strip()
        return {"serial": device.serial, "manufacturer": prop("ro.product.manufacturer"),
                "model": model, "device": prop("ro.product.device"), "abi": abi,
                "android_release": prop("ro.build.version.release"),
                "api_level": prop("ro.build.version.sdk"),
                "build_fingerprint": prop("ro.build.fingerprint"),
                "kernel": self._adb("shell", "uname", "-r").stdout.strip(),
                "package_version": self._adb("shell", "dumpsys", "package", self.package, check=False).stdout,
                "boot_completed": boot}

    @contextlib.contextmanager
    def safe_session(self):
        # Taking the repository lock first also prevents read/write races with older runners.
        with PhoneLock(self.lock_path):
            metadata = self.readiness()
            yield metadata

    def _free_bytes(self) -> int:
        # The package-specific directory need not exist before the first install.
        # Query its backing external-storage filesystem without creating anything.
        result = self._adb("shell", "df", "-k", REMOTE_STORAGE)
        lines = [line.split() for line in result.stdout.splitlines() if line.strip()]
        if len(lines) < 2 or len(lines[-1]) < 4 or not lines[-1][3].isdigit():
            raise DeviceNotReady("could not determine app external-storage capacity")
        return int(lines[-1][3]) * 1024

    def stage(self, apk: Path, apk_sha256: str, model_id: str, inventory: Path, model_dir: Path) -> dict:
        if not apk.is_file() or apk.is_symlink():
            raise RunnerError("APK is absent or linked")
        apk_sha256 = apk_sha256.lower()
        if not re.fullmatch(r"[0-9a-f]{64}", apk_sha256) or sha256_file(apk) != apk_sha256:
            raise RunnerError("APK does not match its expected SHA-256")
        model_id = _safe_relative(model_id)
        files = load_inventory(inventory, model_dir)  # host verification cannot touch the phone
        required = apk.stat().st_size + sum(item.size for item in files)
        with self.safe_session() as device:
            free = self._free_bytes()
            if free < required * 2:
                raise DeviceNotReady(f"insufficient storage: need safety allowance {required * 2}, have {free}")
            self._adb("install", "-r", str(apk), timeout=300)
            remote_dir = f"{REMOTE_FILES}/models/{model_id}"
            self._adb("shell", "mkdir", "-p", remote_dir)
            deployed = []
            for item in files:
                remote = f"{remote_dir}/{item.relative_path}"
                remote_parent = str(PurePosixPath(remote).parent)
                temporary = f"{remote}.incoming-{uuid.uuid4().hex}"
                self._adb("shell", "mkdir", "-p", remote_parent)
                self._adb("push", str(item.source), temporary, timeout=600)
                observed = self._adb("shell", "sha256sum", temporary).stdout.split()
                if not observed or observed[0].lower() != item.sha256:
                    self._adb("shell", "rm", "-f", temporary, check=False)
                    raise CommandFailed(f"device hash mismatch: {item.relative_path}")
                self._adb("shell", "mv", temporary, remote)
                deployed.append({"path": item.relative_path, "size": item.size, "sha256": item.sha256})
            return {"device": device, "model_id": model_id, "required_bytes": required, "free_bytes": free, "files": deployed}

    def thermal_wait(self, *, baseline_c: float | None, maximum_wait_seconds: float = 1200, poll_seconds: float = 60) -> list[ThermalPoll]:
        started = self.clock()
        polls: list[ThermalPoll] = []
        while True:
            thermal = self._adb("shell", "dumpsys", "thermalservice").stdout
            battery = self._adb("shell", "dumpsys", "battery").stdout
            status = parse_thermal_status(thermal)
            temperature = parse_battery_temperature(battery)
            eligible = status == "NONE" and temperature is not None and temperature <= 35.0
            reason = "eligible"
            if baseline_c is not None and temperature is not None and temperature > baseline_c + 1.0:
                eligible, reason = False, "battery temperature exceeds campaign baseline allowance"
            elif status != "NONE":
                reason = "Android thermal status is not NONE or unavailable"
            elif temperature is None or temperature > 35.0:
                reason = "battery temperature is unavailable or above 35.0 C"
            polls.append(ThermalPoll(self.clock(), status, temperature, eligible, reason))
            if eligible:
                return polls
            elapsed = self.clock() - started
            if elapsed >= maximum_wait_seconds:
                raise ThermalEligibilityError(f"thermal eligibility not restored: {reason}", polls)
            self.sleep(min(poll_seconds, maximum_wait_seconds - elapsed))

    def _new_run_dir(self, candidate_id: str) -> Path:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        for _ in range(100):
            name = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{candidate_id}-{uuid.uuid4().hex[:12]}"
            path = self.artifact_dir / name
            try:
                path.mkdir()
                return path
            except FileExistsError:
                continue
        raise RunnerError("could not allocate a collision-free evidence directory")

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        with path.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")

    @staticmethod
    def _failure(candidate_id: str, outcome: str, reason: str, exit_state: str | int | None, evidence: list[dict]) -> dict:
        missing = {name: {"value": None, "reason": reason} for name in ("load_wall_seconds", "cold_rtf", "warm_median_rtf")}
        return {"schema_version": 1, "experiment": "0008", "candidate_id": candidate_id,
                "outcome": outcome, "reason": reason, "exit_state": exit_state,
                "metrics": missing, "evidence": evidence}

    def _capture(self, run_dir: Path, name: str, *adb_args: str) -> dict:
        result = self._adb(*adb_args, check=False)
        path = run_dir / name
        path.write_text(result.stdout + ("\n[stderr]\n" + result.stderr if result.stderr else ""), encoding="utf-8")
        return {"path": name, "sha256": sha256_file(path), "returncode": result.returncode}

    def _pull_result_artifacts(self, result: dict, run_dir: Path, campaign_id: str) -> list[dict]:
        rows = result.get("artifacts")
        if rows is None:
            runs = result.get("runs", [])
            if not isinstance(runs, list):
                raise RunnerError("result runs must be a list")
            try:
                rows = [{"path": f"{campaign_id}/{row['wav_path']}", "sha256": row["wav_sha256"]}
                        for row in runs if row.get("wav_path")]
            except (KeyError, TypeError) as exc:
                raise RunnerError("result contains malformed WAV evidence") from exc
        if not isinstance(rows, list):
            raise RunnerError("result artifacts must be a list")
        pulled: list[dict] = []
        for row in rows:
            try:
                rel = _safe_relative(str(row["path"]))
                digest = str(row["sha256"]).lower()
            except (KeyError, TypeError) as exc:
                raise RunnerError("result contains a malformed artifact entry") from exc
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise RunnerError("result contains an invalid artifact digest")
            destination = run_dir / "device" / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(destination.name + ".incoming")
            if destination.exists() or temporary.exists():
                raise RunnerError("refusing to overwrite pulled evidence")
            remote = f"{REMOTE_FILES}/results/{rel}"
            self._adb("pull", remote, str(temporary), timeout=300)
            try:
                observed_digest = sha256_file(temporary)
            except OSError as exc:
                raise RunnerError(f"pulled evidence is missing: {rel}") from exc
            if observed_digest != digest:
                raise RunnerError(f"pulled evidence hash mismatch: {rel}")
            os.replace(temporary, destination)
            pulled.append({"path": f"device/{rel}", "sha256": digest, "size": destination.stat().st_size})
        return pulled

    def run_candidate(self, candidate_id: str, descriptor_remote: str, descriptor_sha256: str, *,
                      baseline_c: float | None, timeout_seconds: float = 1800,
                      poll_seconds: float = 1) -> Path:
        candidate_id = _safe_relative(candidate_id)
        descriptor_remote = _safe_relative(descriptor_remote)
        descriptor_sha256 = descriptor_sha256.lower()
        if not re.fullmatch(r"[0-9a-f]{64}", descriptor_sha256):
            raise RunnerError("descriptor SHA-256 is invalid")
        campaign_id = f"{candidate_id}-{uuid.uuid4().hex}"
        run_dir = self._new_run_dir(candidate_id)
        evidence: list[dict] = []
        exit_state: str | int | None = None
        execution_started = False
        try:
            with self.safe_session() as device:
                try:
                    polls = self.thermal_wait(baseline_c=baseline_c)
                except ThermalEligibilityError as exc:
                    polls = exc.polls
                    self._write_json(run_dir / "thermal-polls.json", [poll.__dict__ for poll in polls])
                    evidence.append({"path": "thermal-polls.json", "sha256": sha256_file(run_dir / "thermal-polls.json")})
                    raise
                self._write_json(run_dir / "thermal-polls.json", [poll.__dict__ for poll in polls])
                evidence.append({"path": "thermal-polls.json", "sha256": sha256_file(run_dir / "thermal-polls.json")})
                self._adb("shell", "am", "force-stop", self.package)
                execution_started = True
                remote_result = f"{REMOTE_FILES}/results/{campaign_id}/{campaign_id}.json"
                # The random, write-once campaign path must not pre-exist; no evidence is deleted.
                absent = self._adb("shell", "test", "!", "-e", remote_result, check=False)
                if absent.returncode != 0:
                    raise CommandFailed("random campaign result path already exists")
                self._adb("shell", "am", "start", "-W", "-n", self.component,
                          "--es", "descriptor", descriptor_remote,
                          "--es", "descriptor_sha256", descriptor_sha256,
                          "--es", "campaign_id", campaign_id)
                started = self.clock()
                result_text: str | None = None
                process_was_seen = False
                telemetry = run_dir / "telemetry.jsonl"
                while self.clock() - started < timeout_seconds:
                    probe = self._adb("shell", "test", "-f", remote_result, check=False)
                    if probe.stderr and re.search(r"offline|no devices|not found|closed", probe.stderr, re.IGNORECASE):
                        raise CommandFailed("device connection was lost while awaiting the result")
                    if probe.returncode == 0:
                        result_text = self._adb("exec-out", "cat", remote_result).stdout
                        break
                    pid = self._adb("shell", "pidof", self.package, check=False).stdout.strip()
                    process_was_seen |= bool(pid)
                    sample = {"monotonic_seconds": self.clock(), "pid": pid or None,
                              "meminfo": self._adb("shell", "dumpsys", "meminfo", self.package, check=False).stdout,
                              "battery": self._adb("shell", "dumpsys", "battery", check=False).stdout,
                              "thermal": self._adb("shell", "dumpsys", "thermalservice", check=False).stdout}
                    with telemetry.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(sample, sort_keys=True) + "\n")
                    if process_was_seen and not pid:
                        exit_state = "process_died"
                        break
                    self.sleep(poll_seconds)
                evidence.append(self._capture(run_dir, "logcat.txt", "logcat", "-d", "-v", "threadtime"))
                if telemetry.exists():
                    evidence.append({"path": "telemetry.jsonl", "sha256": sha256_file(telemetry)})
                if result_text is None:
                    log = (run_dir / "logcat.txt").read_text(encoding="utf-8", errors="replace")
                    if self.clock() - started >= timeout_seconds:
                        outcome, reason = "timeout", "benchmark exceeded the host timeout"
                    elif re.search(r"OutOfMemoryError|out of memory|lowmemorykiller", log, re.IGNORECASE):
                        outcome, reason = "oom", "process died with out-of-memory evidence"
                    elif re.search(r"Fatal signal|FATAL EXCEPTION|tombstone", log, re.IGNORECASE):
                        outcome, reason = "native_crash", "process died with crash evidence"
                    else:
                        outcome, reason = "failure", "process died before writing a result"
                    failure = self._failure(candidate_id, outcome, reason, exit_state, evidence)
                    self._write_json(run_dir / "failure.json", failure)
                    return run_dir
                try:
                    result = json.loads(result_text)
                    if not isinstance(result, dict):
                        raise ValueError("result is not an object")
                except (ValueError, TypeError) as exc:
                    raw = run_dir / "malformed-device-result.txt"
                    raw.write_text(result_text, encoding="utf-8")
                    evidence.append({"path": raw.name, "sha256": sha256_file(raw)})
                    failure = self._failure(candidate_id, "failure", "device result is malformed", "result_written", evidence)
                    self._write_json(run_dir / "failure.json", failure)
                    return run_dir
                self._write_json(run_dir / "device-result.json", result)
                evidence.append({"path": "device-result.json", "sha256": sha256_file(run_dir / "device-result.json")})
                try:
                    evidence.extend(self._pull_result_artifacts(result, run_dir, campaign_id))
                except RunnerError as exc:
                    failure = self._failure(candidate_id, "failure", str(exc), "partial_result", evidence)
                    self._write_json(run_dir / "failure.json", failure)
                    return run_dir
                self._write_json(run_dir / "host-run.json", {"schema_version": 1, "campaign_id": campaign_id,
                                                               "device": device, "evidence": evidence})
                return run_dir
        except RunnerError as exc:
            outcome = "failure" if execution_started else "blocked"
            state = exit_state or ("connection_or_host_command_failed" if execution_started else None)
            failure = self._failure(candidate_id, outcome, str(exc), state, evidence)
            self._write_json(run_dir / "failure.json", failure)
            return run_dir
