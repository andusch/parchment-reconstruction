"""Ragged synthetic leaf: freeze labels, then recall and placement error."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "docs" / "ragged-synthetic-demo.md"
SCRIPT = ROOT / "samples" / "ragged-leaf" / "run.sh"
PIN = "2fe603838c5e160c3a1e3d6a65a3d487d8f1b28b"
PREVIOUS_PIN = "8a6c2e569ed8107cd47848e29005e528ec397a8e"
# git rev-parse 2fe603838c5e160c3a1e3d6a65a3d487d8f1b28b:src/prw
# CI checks out with fetch-depth 1, so that commit object may be absent.
SRC_PRW_TREE = "bd4a0645c85e71186cd6c2bdad51fccf870baf34"


def _measured_record() -> dict[str, object]:
    text = NOTE.read_text(encoding="utf-8")
    heading = "## Measured record\n"
    start = text.index(heading)
    fence = text.index("```json\n", start)
    body = text[fence + len("```json\n") :]
    payload, _separator, _rest = body.partition("\n```")
    loaded = json.loads(payload)
    if not isinstance(loaded, dict):
        raise AssertionError("The measured record is a JSON object.")
    return loaded


def _run(dest: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), str(dest)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _record_line(stdout: str) -> dict[str, object]:
    line = next(item for item in stdout.splitlines() if item.startswith("record "))
    loaded = json.loads(line.removeprefix("record "))
    if not isinstance(loaded, dict):
        raise AssertionError("The script record is a JSON object.")
    return loaded


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _commit_available(sha: str) -> bool:
    completed = _git("cat-file", "-e", f"{sha}^{{commit}}")
    if completed.returncode == 0:
        return True
    message = completed.stderr
    absent = "bad object" in message or "Not a valid object name" in message
    if absent:
        return False
    raise AssertionError(message or completed.stdout)


def test_missing_pin_object_is_absent() -> None:
    assert _commit_available("deadbeef" * 5) is False


def test_pinned_algorithms_match_the_measured_commit() -> None:
    head = _git("rev-parse", "HEAD:src/prw")
    assert head.returncode == 0, head.stderr
    assert head.stdout.strip() == SRC_PRW_TREE
    dirty = _git("diff", "--exit-code", "HEAD", "--", "src/prw")
    assert dirty.returncode == 0, dirty.stdout
    if not _commit_available(PIN):
        return
    pinned = _git("rev-parse", f"{PIN}:src/prw")
    assert pinned.returncode == 0, pinned.stderr
    assert pinned.stdout.strip() == SRC_PRW_TREE
    diff = _git("diff", "--exit-code", PIN, "--", "src/prw")
    assert diff.returncode == 0, diff.stdout or diff.stderr


def test_script_refuses_a_checkout_path_and_a_used_directory(tmp_path: Path) -> None:
    checkout = _run(ROOT)
    assert checkout.returncode == 2
    assert checkout.stdout == ""
    assert "checkout" in checkout.stderr

    used = tmp_path / "used"
    used.mkdir()
    (used / "marker").write_text("x", encoding="utf-8")
    occupied = _run(used)
    assert occupied.returncode == 2
    assert occupied.stdout == ""
    assert "not empty" in occupied.stderr


def test_ragged_demo_matches_the_note(tmp_path: Path) -> None:
    expected = _measured_record()
    note = NOTE.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    assert expected["recall_at_1"] == 0.25
    assert expected["recall_at_3"] == 0.75
    assert expected["recall_at_1_is_1"] is False
    assert expected["score_name"] == "negative_chord_gap_plus_curve_and_overlap"
    assert expected["rank_channel"] == "physical"
    assert expected["rank_epistemic_class"] == "hypothesis"
    assert expected["rank_1_is_frozen_join"] is True
    assert expected["placement_scored_pairs_are_frozen_joins"] is True
    assert "## Previous measured record" in note
    assert "recall_at_3" in note
    for phrase in (
        PIN,
        PREVIOUS_PIN,
        "--edge-erosion 0.15",
        "--rotation 0.3",
        "--lighting-variation 0.25",
        "--missing-fragment-percentage 0",
        "--pixels-per-mm 1",
        "--minimum-edge-length-mm 6",
        "--k 1",
        "--k 3",
        "negative_chord_gap_plus_curve_and_overlap",
        "negative_absolute_length_difference",
        "Q-SCI-15",
        "1999.137",
        "hypothesis",
    ):
        assert phrase in note
    assert PIN in script
    assert PREVIOUS_PIN not in script
    assert "--edge-erosion" in script
    assert "0.15" in script
    assert "claimed-ppi" not in script
    assert "--claimed-ppi" not in script

    dest = tmp_path / "ragged"
    completed = _run(dest)
    assert completed.returncode == 0, completed.stderr
    assert _record_line(completed.stdout) == expected
    for name in (
        "generate_exit 0",
        "rank_exit 0",
        "recall-1_exit 0",
        "recall-3_exit 0",
        "placement_exit 0",
        "assembly-rank_exit 0",
        "labels_unchanged yes",
        f"code_version {PIN}",
    ):
        assert name in completed.stdout

    benchmarks = dest / "benchmarks"
    labels = (benchmarks / "labels.json").read_bytes()
    assert labels == (dest / "frozen" / "labels.json").read_bytes()
    assert (benchmarks / "provenance.json").read_bytes() == (
        dest / "frozen" / "provenance.json"
    ).read_bytes()
    assert "sha256:" + hashlib.sha256(labels).hexdigest() == expected["label_file_hash"]
    assert not (benchmarks / "manifest.json").exists()
    assert not (dest / "originals").exists()

    recall_1 = json.loads(
        (benchmarks / "join_recall" / "join-recall-0001.json").read_text()
    )
    recall_3 = json.loads(
        (benchmarks / "join_recall" / "join-recall-0002.json").read_text()
    )
    placement = json.loads(
        (benchmarks / "placement_error" / "placement-error-0001.json").read_text()
    )
    assert recall_1["metric"] == "join_recall_at_k"
    assert recall_1["k"] == 1
    assert recall_1["recall"] == expected["recall_at_1"]
    assert recall_1["previous_report"] == "absent"
    assert recall_1["code_version"] == PIN
    assert recall_1["does_not_measure"] == "a historical join on real parchment"
    assert recall_3["k"] == 3
    assert recall_3["recall"] == expected["recall_at_3"]
    assert recall_3["previous_report"] == "join-recall-0001.json"
    assert placement["metric"] == "placement_error"
    assert placement["n"] == 2
    assert placement["previous_report"] == "absent"
    assert placement["code_version"] == PIN
    assert [
        row["rmse_mm"] for row in placement["error_list"] if row["status"] == "scored"
    ] == expected["placement_rmse_mm"]
    assert (
        sum(1 for row in placement["error_list"] if row["status"] == "unplaced")
        == expected["placement_unplaced_count"]
    )

    stored = json.loads(labels)
    frozen_pairs = {
        tuple(sorted(str(item) for item in row["fragment_ids"]))
        for row in stored
        if row["kind"] == "join"
    }
    assert len(frozen_pairs) == 4
    correspondence = {
        row["project_fragment_id"]: row["fixture_fragment_id"]
        for row in recall_1["correspondence"]
    }
    rank = json.loads((dest / "rank.json").read_text(encoding="utf-8"))
    assert rank["record"] == "physical_join_order"
    assert {join["channel"] for join in rank["joins"]} == {"physical"}
    assert {join["epistemic_class"] for join in rank["joins"]} == {"hypothesis"}
    first = rank["joins"][0]
    pair = tuple(
        sorted(
            (
                correspondence[str(first["fragment_a_id"])],
                correspondence[str(first["fragment_b_id"])],
            )
        )
    )
    assert pair in frozen_pairs
    assert list(pair) == expected["rank_1_fixture_fragment_ids"]
    assert first["score"] == expected["rank_1_score"]

    manifest = json.loads(
        (dest / "images" / "image_manifest.json").read_text(encoding="utf-8")
    )
    for item in manifest["images"]:
        payload = (dest / "images" / item["name"]).read_bytes()
        assert "sha256:" + hashlib.sha256(payload).hexdigest() == item["content_hash"]
        assert item["name"].endswith(".tif")
