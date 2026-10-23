#!/usr/bin/env python3
"""Drive the parchment-workbench CLI in an isolated synthetic-fixture directory.

The instance lives under the OS temp directory. Proof transcripts are written
under ``.cursor/skills/verify-prw/artifacts`` and are not removed by cleanup.
Keep the seed flags in this file identical to the Launch section of SKILL.md.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import pty
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import NamedTuple, TypedDict

REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = REPO_ROOT / ".cursor" / "skills" / "verify-prw" / "artifacts"
EXPECTED_VERSION = "0.0.0"
EXPECTED_COMMANDS = (
    "agree",
    "assemble",
    "assembly-rank",
    "edge",
    "frame",
    "generate",
    "join-presence",
    "placement-error",
    "provenance",
    "rank",
    "recall",
    "segment",
    "verify",
)
SEED_ARGUMENTS = (
    "--missing-fragment-percentage",
    "0",
    "--edge-erosion",
    "0",
    "--rotation",
    "0",
    "--lighting-variation",
    "0",
    "--random-seed",
    "3",
)
FORBIDDEN_PARTS = frozenset({"data", "scans", "real_data"})
TOKEN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RUN_ID = re.compile(r"^[0-9a-f]{32}$")
HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
STATUS_KEYS = (
    "run_id",
    "root",
    "images",
    "benchmarks",
    "scratch",
    "page",
    "page_hash",
    "page_bytes",
    "fragments",
    "version",
    "code_version",
    "worktree",
    "commands",
)


class HarnessError(Exception):
    """The instance is missing, unsafe, or not ready to drive."""

    def __init__(self, message: str, status: int = 1) -> None:
        super().__init__(message)
        self.status = status


class DriveResult(NamedTuple):
    returncode: int
    stdout: bytes
    stderr: bytes
    argv: tuple[str, ...]


class Snapshot(TypedDict):
    run_id: str
    root: str
    images: str
    benchmarks: str
    scratch: str
    page: str
    page_hash: str
    page_bytes: int
    fragments: list[str]
    fragment_hashes: list[str]
    version: str
    code_version: str
    worktree: str
    commands: list[str]


def main(argv: Sequence[str] | None = None) -> int:
    """Run launch, doctor, exports, run, or cleanup."""
    raw = list(sys.argv[1:] if argv is None else argv)
    prw_args: list[str] = []
    if raw[:1] == ["run"]:
        if "--" not in raw:
            print("run requires -- before the prw arguments.", file=sys.stderr)
            return 2
        split = raw.index("--")
        prw_args = raw[split + 1 :]
        raw = raw[:split]
        if not prw_args:
            print("run requires prw arguments after --.", file=sys.stderr)
            return 2
    parser = _parser()
    args = parser.parse_args(raw)
    try:
        _require_repo()
        if args.command == "launch":
            return _launch()
        if args.command == "doctor":
            _print_status("prw-verify doctor ok", _check(args.run))
            return 0
        if args.command == "exports":
            _print_exports(_check(args.run))
            return 0
        if args.command == "run":
            return _run(args.run, args.feature, args.entry, args.step, prw_args)
        if args.command == "cleanup":
            return _cleanup(args.run, announce=True)
    except HarnessError as exc:
        print(str(exc), file=sys.stderr)
        return exc.status
    print(f"Unknown command {args.command}.", file=sys.stderr)
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="verify_prw.py")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("launch")
    doctor = commands.add_parser("doctor")
    doctor.add_argument("--run", required=True)
    exports = commands.add_parser("exports")
    exports.add_argument("--run", required=True)
    run = commands.add_parser("run")
    run.add_argument("--run", required=True)
    run.add_argument("--feature", required=True)
    run.add_argument("--entry", required=True)
    run.add_argument("--step", required=True)
    cleanup = commands.add_parser("cleanup")
    cleanup.add_argument("--run", required=True)
    return parser


def _launch() -> int:
    run_id = uuid.uuid4().hex
    root = _instance_root(run_id)
    try:
        _create_instance(root, run_id)
        with _lock(root):
            code_version = _git_head()
            generated = _execute(
                root,
                [
                    "generate",
                    "--benchmarks",
                    str(root / "benchmarks"),
                    "--images",
                    str(root / "images"),
                    *SEED_ARGUMENTS,
                    "--code-version",
                    code_version,
                ],
            )
            _write_transcript(root / "seed" / "generate", generated, meta=None)
            _require_seed_generate(generated)
            snapshot = _snapshot(root, run_id)
            verified = _execute(
                root,
                ["verify", snapshot["page"], "--expected", snapshot["page_hash"]],
            )
            _write_transcript(root / "seed" / "verify", verified, meta=None)
            _require_seed_verify(verified, snapshot["page_hash"])
            _write_state(root, snapshot, ready=True)
        _print_status(f"prw-verify ready {run_id}", _check(run_id))
    except HarnessError as exc:
        print(str(exc), file=sys.stderr)
        existed = _instance_root(run_id).exists()
        try:
            _cleanup(run_id, announce=False)
        except HarnessError as cleanup_error:
            print(str(cleanup_error), file=sys.stderr)
        else:
            if existed:
                print(
                    f"prw-verify launch failed; instance removed {run_id}",
                    file=sys.stderr,
                )
        return exc.status
    return 0


def _run(
    run_id: str,
    feature: str,
    entry: str,
    step: str,
    prw_args: Sequence[str],
) -> int:
    _require_token(feature, "feature")
    _require_token(step, "step")
    if entry == "" or "\n" in entry or len(entry) > 300:
        raise HarnessError("entry is one single-line phrase.", status=2)
    _refuse_argument_paths(prw_args)
    snapshot = _check(run_id)
    evidence = ARTIFACTS / feature / run_id / step
    if evidence.exists():
        raise HarnessError(f"Evidence already exists: {evidence}", status=2)
    partial = evidence.parent / f"{step}.partial"
    meta = {
        "feature": feature,
        "entry": entry,
        "step": step,
        "run_id": snapshot["run_id"],
    }
    with _lock(_instance_root(run_id)):
        result = _execute(_instance_root(run_id), prw_args)
        _write_transcript(partial, result, meta=meta)
        evidence.parent.mkdir(parents=True, exist_ok=True)
        partial.rename(evidence)
    _emit(f"prw-verify ran {feature} {step}")
    _emit(f"exit_code: {result.returncode}")
    _emit(f"command: {evidence / 'command.txt'}")
    _emit(f"stdout: {evidence / 'stdout.txt'}")
    _emit(f"stderr: {evidence / 'stderr.txt'}")
    _emit(f"meta: {evidence / 'meta.txt'}")
    return result.returncode


def _cleanup(run_id: str, *, announce: bool) -> int:
    _require_run_id(run_id)
    root = _instance_root(run_id)
    if not root.exists():
        if announce:
            _emit(f"prw-verify cleanup absent {run_id}")
        return 0
    _assert_owned(root, run_id)
    _finish_active_drive(root)
    shutil.rmtree(root)
    if announce:
        _emit(f"prw-verify cleanup removed {run_id}")
    return 0


def _create_instance(root: Path, run_id: str) -> None:
    if root.exists():
        raise HarnessError(f"Instance already exists: {root}", status=2)
    _assert_safe_instance(root)
    root.mkdir(parents=True)
    if root.is_symlink():
        raise HarnessError("The instance root is a symlink.", status=2)
    (root / ".prw-verify-instance").write_text(f"{run_id}\n", encoding="utf-8")
    (root / "drive.lock").touch()
    for name in ("images", "benchmarks", "scratch"):
        (root / name).mkdir()
    _write_state(
        root,
        {
            "run_id": run_id,
            "root": str(root),
            "images": str(root / "images"),
            "benchmarks": str(root / "benchmarks"),
            "scratch": str(root / "scratch"),
            "page": "",
            "page_hash": "",
            "page_bytes": 0,
            "fragments": [],
            "fragment_hashes": [],
            "version": "",
            "code_version": "",
            "worktree": "",
            "commands": [],
        },
        ready=False,
    )


def _check(run_id: str) -> Snapshot:
    """Return the live snapshot when this instance is worth driving."""
    _require_run_id(run_id)
    root = _instance_root(run_id)
    if not root.is_dir():
        raise HarnessError(f"No instance for {run_id}.", status=1)
    _assert_owned(root, run_id)
    _assert_safe_instance(root)
    state = _read_state(root)
    if state.get("ready") is not True or state.get("run_id") != run_id:
        raise HarnessError("The instance is not ready.", status=1)
    _reject_active_pid(root)
    live = _snapshot(root, run_id)
    compared = (
        "root",
        "images",
        "benchmarks",
        "scratch",
        "page",
        "page_hash",
        "page_bytes",
        "fragments",
        "fragment_hashes",
        "version",
        "commands",
    )
    for key in compared:
        if live[key] != state.get(key):
            raise HarnessError(
                f"The instance drifted from launch ({key}).",
                status=1,
            )
    if live["code_version"] != state.get("code_version"):
        raise HarnessError("HEAD changed since launch.", status=1)
    return live


def _snapshot(root: Path, run_id: str) -> Snapshot:
    images = root / "images"
    benchmarks = root / "benchmarks"
    for name in ("labels.json", "provenance.json"):
        path = benchmarks / name
        if not path.is_file() or path.stat().st_size == 0:
            raise HarnessError(f"Seed is missing {name}.", status=1)
    manifest = _load_manifest(images / "image_manifest.json")
    page_hash = ""
    page_bytes = 0
    fragments: list[str] = []
    fragment_hashes: list[str] = []
    for entry in manifest:
        role = entry.get("role")
        name = entry.get("name")
        content_hash = entry.get("content_hash")
        byte_length = entry.get("byte_length")
        if not isinstance(name, str) or not isinstance(content_hash, str):
            raise HarnessError("An image manifest names each file.", status=1)
        if not isinstance(byte_length, int) or isinstance(byte_length, bool):
            raise HarnessError("An image manifest records byte_length.", status=1)
        if HASH.fullmatch(content_hash) is None:
            raise HarnessError("An image manifest hash is sha256:.", status=1)
        path = images / name
        if role == "page" and name == "page.tif":
            page_hash = content_hash
            page_bytes = byte_length
        elif role == "fragment" and _is_fragment_file_name(name):
            fragments.append(name)
            fragment_hashes.append(content_hash)
        else:
            raise HarnessError(f"Unexpected manifest image {name}.", status=1)
        _require_file_hash(path, content_hash, byte_length)
    if page_hash == "" or page_bytes <= 0:
        raise HarnessError("Seed is missing page.tif.", status=1)
    if len(fragments) < 2:
        raise HarnessError("Seed produced fewer than two fragments.", status=1)
    version = _package_version()
    if version != EXPECTED_VERSION:
        raise HarnessError(
            f"prw version is {version}; verify-prw expects {EXPECTED_VERSION}.",
            status=1,
        )
    commands = list(_command_names())
    return {
        "run_id": run_id,
        "root": str(root),
        "images": str(images),
        "benchmarks": str(benchmarks),
        "scratch": str(root / "scratch"),
        "page": str(images / "page.tif"),
        "page_hash": page_hash,
        "page_bytes": page_bytes,
        "fragments": fragments,
        "fragment_hashes": fragment_hashes,
        "version": version,
        "code_version": _git_head(),
        "worktree": _worktree(),
        "commands": commands,
    }


def _require_seed_generate(result: DriveResult) -> None:
    payload = _require_json_object(result, "generate")
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("random_seed") != 3:
        raise HarnessError("Seed generate did not record random_seed 3.", status=1)
    if _forbidden_words(result.stdout):
        raise HarnessError("Seed generate printed a forbidden word.", status=1)


def _require_seed_verify(result: DriveResult, page_hash: str) -> None:
    payload = _require_json_object(result, "verify")
    if payload.get("record") != "VerifiedBytes":
        raise HarnessError("Seed verify did not print VerifiedBytes.", status=1)
    if payload.get("content_hash") != page_hash:
        raise HarnessError("Seed verify hash does not match the manifest.", status=1)
    if payload.get("media_type") != "image/tiff":
        raise HarnessError("Seed verify did not record image/tiff.", status=1)
    if _forbidden_words(result.stdout):
        raise HarnessError("Seed verify printed a forbidden word.", status=1)


def _require_json_object(result: DriveResult, what: str) -> dict[str, object]:
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip()
        raise HarnessError(f"{what} failed ({result.returncode}). {detail}", status=1)
    try:
        loaded = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise HarnessError(f"{what} did not print JSON.", status=1) from exc
    if not isinstance(loaded, dict):
        raise HarnessError(f"{what} did not print a JSON object.", status=1)
    return loaded


def _forbidden_words(payload: bytes) -> bool:
    text = payload.decode("utf-8", errors="replace")
    return "hypothesis" in text or "correct_join" in text


def _execute(root: Path, prw_args: Sequence[str]) -> DriveResult:
    argv = ("uv", "run", "python", "-m", "prw.cli", *prw_args)
    if shutil.which("uv") is None:
        raise HarnessError("uv is not on PATH.", status=2)
    try:
        master_fd, slave_fd = pty.openpty()
    except OSError as exc:
        raise HarnessError(f"Could not open a PTY: {exc}", status=1) from exc
    proc: subprocess.Popen[bytes] | None = None
    try:
        proc = subprocess.Popen(
            argv,
            stdin=slave_fd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=REPO_ROOT,
            start_new_session=True,
            close_fds=True,
        )
        os.close(slave_fd)
        slave_fd = -1
        _record_leader(root, proc.pid)
        stdout, stderr = proc.communicate()
    except HarnessError:
        _stop_process(proc, signal.SIGTERM)
        raise
    except KeyboardInterrupt:
        _stop_process(proc, signal.SIGTERM)
        raise
    finally:
        if slave_fd >= 0:
            os.close(slave_fd)
        os.close(master_fd)
        _clear_pid(root)
    code = 1 if proc.returncode is None else proc.returncode
    return DriveResult(code, stdout, stderr, argv)


def _record_leader(root: Path, pid: int) -> None:
    helper_pgid = os.getpgrp()
    deadline = time.monotonic() + 2
    while True:
        try:
            pgid = os.getpgid(pid)
        except ProcessLookupError:
            return
        if pgid == pid and pgid != helper_pgid:
            (root / "active.pid").write_text(f"{pid} {pgid}\n", encoding="utf-8")
            return
        if time.monotonic() >= deadline:
            raise HarnessError(
                "The prw process did not become its own session leader.",
                status=1,
            )
        time.sleep(0.01)


def _stop_process(proc: subprocess.Popen[bytes] | None, sig: int) -> None:
    if proc is None or proc.poll() is not None:
        return
    _signal_pid(proc.pid, sig)


def _finish_active_drive(root: Path) -> None:
    lock_path = root / "drive.lock"
    if not lock_path.exists():
        _signal_recorded(root, signal.SIGTERM)
        return
    handle = lock_path.open("a+")
    signalled = False
    try:
        deadline = time.monotonic() + 5
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                if not signalled:
                    _signal_recorded(root, signal.SIGTERM)
                    signalled = True
                if time.monotonic() >= deadline:
                    _signal_recorded(root, signal.SIGKILL)
                    raise HarnessError(
                        "A drive did not exit; cleanup left the instance in place.",
                        status=2,
                    ) from None
                time.sleep(0.05)
                continue
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            return
    finally:
        handle.close()


def _signal_recorded(root: Path, sig: int) -> None:
    recorded = _read_pid(root)
    if recorded is None:
        return
    pid, pgid = recorded
    _signal_pid(pid, sig, expected_pgid=pgid)


def _signal_pid(pid: int, sig: int, expected_pgid: int | None = None) -> None:
    if pid <= 1:
        raise HarnessError("Refusing to signal a system process.", status=2)
    live = _ps(pid)
    if live is None:
        return
    live_pgid, command = live
    if "prw.cli" not in command:
        raise HarnessError(
            "active.pid is not a prw.cli process; cleanup left it untouched.",
            status=2,
        )
    helper_pgid = os.getpgrp()
    if live_pgid == helper_pgid or live_pgid <= 1:
        raise HarnessError(
            "active.pid shares the helper process group; cleanup left it untouched.",
            status=2,
        )
    if expected_pgid is not None and (live_pgid != expected_pgid or live_pgid != pid):
        raise HarnessError(
            "active.pid does not match the live session; cleanup left it untouched.",
            status=2,
        )
    try:
        if live_pgid == pid:
            os.killpg(live_pgid, sig)
        else:
            os.kill(pid, sig)
    except ProcessLookupError:
        return


def _reject_active_pid(root: Path) -> None:
    recorded = _read_pid(root)
    if recorded is None:
        return
    pid, _pgid = recorded
    if _ps(pid) is None:
        raise HarnessError("Stale active.pid; run cleanup for this run id.", status=1)
    raise HarnessError("A drive is in progress for this run id.", status=1)


def _read_pid(root: Path) -> tuple[int, int] | None:
    path = root / "active.pid"
    if not path.exists():
        return None
    parts = path.read_text(encoding="utf-8").split()
    if len(parts) != 2:
        raise HarnessError("active.pid is malformed.", status=2)
    try:
        return int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise HarnessError("active.pid is malformed.", status=2) from exc


def _clear_pid(root: Path) -> None:
    path = root / "active.pid"
    with contextlib.suppress(FileNotFoundError):
        path.unlink()


def _ps(pid: int) -> tuple[int, str] | None:
    completed = subprocess.run(
        ["ps", "-p", str(pid), "-o", "pgid=,command="],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    line = completed.stdout.strip()
    pgid_text, separator, command = line.partition(" ")
    if separator != " " or command.strip() == "":
        return None
    try:
        return int(pgid_text), command.strip()
    except ValueError:
        return None


@contextlib.contextmanager
def _lock(root: Path) -> Iterator[None]:
    handle = (root / "drive.lock").open("a+")
    acquired = False
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise HarnessError(
                "This run already has a drive in progress.",
                status=1,
            ) from exc
        acquired = True
        yield
    finally:
        if acquired:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _write_transcript(
    directory: Path,
    result: DriveResult,
    *,
    meta: Mapping[str, str] | None,
) -> None:
    if directory.exists():
        raise HarnessError(f"Transcript already exists: {directory}", status=2)
    directory.mkdir(parents=True)
    (directory / "command.txt").write_text(
        shlex.join(result.argv) + "\n",
        encoding="utf-8",
    )
    (directory / "stdout.txt").write_bytes(result.stdout)
    (directory / "stderr.txt").write_bytes(result.stderr)
    (directory / "exit_code.txt").write_text(f"{result.returncode}\n", encoding="utf-8")
    (directory / "cwd.txt").write_text(f"{REPO_ROOT}\n", encoding="utf-8")
    if meta is not None:
        keys = ("feature", "entry", "step", "run_id")
        lines = [f"{key}: {meta[key]}" for key in keys]
        (directory / "meta.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_state(root: Path, snapshot: Snapshot, *, ready: bool) -> None:
    payload = dict(snapshot)
    payload["ready"] = ready
    temporary = root / "state.json.tmp"
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(root / "state.json")


def _read_state(root: Path) -> dict[str, object]:
    path = root / "state.json"
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HarnessError("state.json is not readable.", status=1) from exc
    if not isinstance(loaded, dict):
        raise HarnessError("state.json is not an object.", status=1)
    return loaded


def _load_manifest(path: Path) -> list[dict[str, object]]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HarnessError(
            "image_manifest.json is not readable JSON.",
            status=1,
        ) from exc
    images = loaded.get("images") if isinstance(loaded, dict) else None
    if not isinstance(images, list):
        raise HarnessError("image_manifest.json does not list images.", status=1)
    entries: list[dict[str, object]] = []
    for entry in images:
        if not isinstance(entry, dict):
            raise HarnessError("image_manifest.json does not list images.", status=1)
        entries.append(entry)
    return entries


def _require_file_hash(path: Path, content_hash: str, byte_length: int) -> None:
    if not path.is_file():
        raise HarnessError(f"Seed is missing {path.name}.", status=1)
    if path.stat().st_size != byte_length:
        raise HarnessError(f"{path.name} size does not match the manifest.", status=1)
    if _file_sha256(path) != content_hash:
        raise HarnessError(f"{path.name} hash does not match the manifest.", status=1)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _is_fragment_file_name(name: str) -> bool:
    """Same fragment file rule as ``prw.cli._is_fragment_file_name``."""
    return (
        name == Path(name).name
        and name.startswith("fragment-")
        and name.endswith(".tif")
        and name != "fragment-.tif"
    )


def _package_version() -> str:
    completed = _uv(["-c", "import prw; print(prw.__version__)"])
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise HarnessError(f"Could not import prw. {detail}", status=1)
    return completed.stdout.strip()


def _command_names() -> tuple[str, ...]:
    completed = _uv(["-m", "prw.cli", "--help"])
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise HarnessError(f"prw --help failed. {detail}", status=1)
    match = re.search(r"\{([^{}]+)\}", completed.stdout)
    if match is None:
        raise HarnessError("prw --help did not list subcommands.", status=1)
    names = tuple(sorted(part.strip() for part in match.group(1).split(",")))
    if names != EXPECTED_COMMANDS:
        found = ",".join(names)
        expected = ",".join(EXPECTED_COMMANDS)
        raise HarnessError(
            f"prw subcommands are {found}; verify-prw expects {expected}.",
            status=1,
        )
    return names


def _uv(args: list[str]) -> subprocess.CompletedProcess[str]:
    if shutil.which("uv") is None:
        raise HarnessError("uv is not on PATH.", status=2)
    return subprocess.run(
        ["uv", "run", "python", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _git_head() -> str:
    completed = _git("rev-parse", "HEAD")
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "git rev-parse failed"
        raise HarnessError(detail, status=1)
    return completed.stdout.strip()


def _worktree() -> str:
    completed = _git("status", "--porcelain")
    if completed.returncode != 0:
        raise HarnessError("git status failed.", status=1)
    return "clean" if completed.stdout == "" else "dirty"


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _print_status(headline: str, snapshot: Snapshot) -> None:
    _emit(headline)
    values = {
        "run_id": snapshot["run_id"],
        "root": snapshot["root"],
        "images": snapshot["images"],
        "benchmarks": snapshot["benchmarks"],
        "scratch": snapshot["scratch"],
        "page": snapshot["page"],
        "page_hash": snapshot["page_hash"],
        "page_bytes": str(snapshot["page_bytes"]),
        "fragments": " ".join(snapshot["fragments"]),
        "version": snapshot["version"],
        "code_version": snapshot["code_version"],
        "worktree": snapshot["worktree"],
        "commands": ",".join(snapshot["commands"]),
    }
    for key in STATUS_KEYS:
        _emit(f"{key}: {values[key]}")


def _print_exports(snapshot: Snapshot) -> None:
    images = Path(snapshot["images"])
    fields = {
        "RUN_ID": snapshot["run_id"],
        "ROOT": snapshot["root"],
        "IMAGES": snapshot["images"],
        "BENCHMARKS": snapshot["benchmarks"],
        "SCRATCH": snapshot["scratch"],
        "PAGE": snapshot["page"],
        "PAGE_HASH": snapshot["page_hash"],
        "PAGE_BYTES": str(snapshot["page_bytes"]),
        "CODE": snapshot["code_version"],
        "FRAGMENT_A": snapshot["fragments"][0],
        "FRAGMENT_B": snapshot["fragments"][1],
        "FRAGMENT_A_PATH": str(images / snapshot["fragments"][0]),
        "FRAGMENT_B_PATH": str(images / snapshot["fragments"][1]),
        "FRAGMENT_A_HASH": snapshot["fragment_hashes"][0],
        "FRAGMENT_B_HASH": snapshot["fragment_hashes"][1],
    }
    for key, value in fields.items():
        _emit(f"{key}={shlex.quote(value)}")


def _refuse_argument_paths(args: Sequence[str]) -> None:
    repo = REPO_ROOT.resolve()
    for arg in args:
        if arg.startswith("-"):
            continue
        candidate = Path(arg)
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        parts = set(resolved.parts)
        if parts & FORBIDDEN_PARTS:
            raise HarnessError(
                f"Refusing to drive a project data path: {arg}",
                status=2,
            )
        inside_repo = resolved == repo or repo in resolved.parents
        if inside_repo and resolved.suffix.lower() in {".tif", ".tiff"}:
            raise HarnessError(
                f"Refusing to drive a TIFF inside the checkout: {arg}",
                status=2,
            )


def _assert_owned(root: Path, run_id: str) -> None:
    if root.is_symlink():
        raise HarnessError("The instance root is a symlink.", status=2)
    marker = root / ".prw-verify-instance"
    try:
        text = marker.read_text(encoding="utf-8")
    except OSError as exc:
        raise HarnessError("The instance marker is missing.", status=2) from exc
    if text != f"{run_id}\n":
        raise HarnessError("The instance marker does not match the run id.", status=2)
    state_path = root / "state.json"
    if not state_path.exists():
        return
    state = _read_state(root)
    if state.get("run_id") != run_id:
        raise HarnessError("state.json does not match the run id.", status=2)


def _assert_safe_instance(root: Path) -> None:
    repo = REPO_ROOT.resolve()
    if root == repo or repo in root.parents:
        raise HarnessError("The instance must stay outside the checkout.", status=2)
    if set(root.parts) & FORBIDDEN_PARTS:
        raise HarnessError(
            "The instance path is inside a project data directory.",
            status=2,
        )
    for parent in (root, *root.parents):
        if (parent / "manifest.json").is_file():
            raise HarnessError(
                "The instance is inside a directory that holds manifest.json.",
                status=2,
            )


def _instance_root(run_id: str) -> Path:
    _require_run_id(run_id)
    base = (Path(tempfile.gettempdir()) / "prw-verify").resolve()
    root = (base / run_id).resolve()
    if root.parent != base or root.name != run_id:
        raise HarnessError(
            "The instance path escaped the prw-verify directory.",
            status=2,
        )
    return root


def _require_run_id(run_id: str) -> None:
    if RUN_ID.fullmatch(run_id) is None:
        raise HarnessError("run id must be 32 lowercase hex characters.", status=2)


def _require_token(value: str, label: str) -> None:
    if TOKEN.fullmatch(value) is None:
        raise HarnessError(
            f"{label} must be lowercase words separated by hyphens.",
            status=2,
        )


def _require_repo() -> None:
    pyproject = REPO_ROOT / "pyproject.toml"
    cli = REPO_ROOT / "src" / "prw" / "cli.py"
    if not pyproject.is_file() or not cli.is_file():
        raise HarnessError(
            "verify_prw.py is not inside the parchment-reconstruction checkout.",
            status=2,
        )
    text = pyproject.read_text(encoding="utf-8")
    if 'name = "parchment-workbench"' not in text:
        raise HarnessError("pyproject.toml is not parchment-workbench.", status=2)


def _emit(line: str) -> None:
    print(line, flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
