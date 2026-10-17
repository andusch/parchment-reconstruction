"""The git ls-files gate rejects tracked .cursor/**/*.log paths."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "check_no_tracked_cursor_logs.sh"
GATE_COMMAND = "sh scripts/check_no_tracked_cursor_logs.sh"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result


def _init(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init", "-q")


def _gate(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(GATE)],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )


def test_gate_fails_while_a_cursor_log_is_tracked(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init(repo)
    cursor = repo / ".cursor"
    cursor.mkdir()
    (cursor / "debug-ec5036.log").write_text("session\n", encoding="utf-8")
    (cursor / "rules").mkdir()
    (cursor / "rules" / "keep.mdc").write_text("rule\n", encoding="utf-8")
    _git(repo, "add", "-f", ".cursor/debug-ec5036.log", ".cursor/rules/keep.mdc")

    result = _gate(repo)

    assert result.returncode == 1
    assert result.stdout == ".cursor/debug-ec5036.log\n"
    assert "tracked .cursor/**/*.log paths:" in result.stderr


def test_gate_fails_for_a_nested_cursor_log(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init(repo)
    nested = repo / ".cursor" / "session"
    nested.mkdir(parents=True)
    (nested / "debug.log").write_text("nested\n", encoding="utf-8")
    _git(repo, "add", "-f", ".cursor/session/debug.log")

    result = _gate(repo)

    assert result.returncode == 1
    assert result.stdout == ".cursor/session/debug.log\n"


def test_gate_passes_once_the_cursor_log_is_untracked(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init(repo)
    cursor = repo / ".cursor"
    cursor.mkdir()
    log = cursor / "debug-ec5036.log"
    log.write_text("session\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".cursor/**/*.log\n", encoding="utf-8")
    _git(repo, "add", "-f", ".cursor/debug-ec5036.log", ".gitignore")
    assert _gate(repo).returncode == 1

    _git(repo, "rm", "--cached", "-q", ".cursor/debug-ec5036.log")

    result = _gate(repo)
    assert result.returncode == 0
    assert result.stdout == ""
    assert log.is_file()
    ignored = _git(repo, "check-ignore", "-v", ".cursor/debug-ec5036.log")
    assert ".cursor/**/*.log" in ignored.stdout


def test_gate_ignores_logs_outside_cursor(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init(repo)
    (repo / "notes.log").write_text("notes\n", encoding="utf-8")
    other = repo / "other"
    other.mkdir()
    (other / "debug.log").write_text("other\n", encoding="utf-8")
    _git(repo, "add", "notes.log", "other/debug.log")

    result = _gate(repo)

    assert result.returncode == 0
    assert result.stdout == ""


def test_gitignore_pattern_ignores_cursor_logs_at_any_depth(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init(repo)
    (repo / ".gitignore").write_text(
        (ROOT / ".gitignore").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    paths = (
        ".cursor/debug-ec5036.log",
        ".cursor/nested/session.log",
        ".cursor/nested/deep/x.log",
    )
    for path in paths:
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("log\n", encoding="utf-8")
        ignored = _git(repo, "check-ignore", "-v", path)
        assert ".cursor/**/*.log" in ignored.stdout
    kept = repo / ".cursor" / "rules" / "keep.mdc"
    kept.parent.mkdir(parents=True, exist_ok=True)
    kept.write_text("rule\n", encoding="utf-8")
    outside = repo / "notes.log"
    outside.write_text("notes\n", encoding="utf-8")
    for path in (".cursor/rules/keep.mdc", "notes.log"):
        result = subprocess.run(
            ["git", "check-ignore", "-q", path],
            cwd=repo,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1


def test_ci_and_pre_commit_invoke_the_same_log_gate() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    pre_commit = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert GATE_COMMAND in ci
    assert GATE_COMMAND in pre_commit
    assert (ROOT / "scripts" / "check_no_tracked_cursor_logs.sh").is_file()
