"""Ranked-join review session, without a display."""

import json
import math
import subprocess
import sys
import uuid
from modulefinder import ModuleFinder
from pathlib import Path

import pytest

from prw.review import (
    LOCAL_OPERATOR,
    PoolImage,
    RankRequest,
    ReviewFailure,
    ReviewSession,
    failure_line,
    hypothesis_lines,
    load_ranked_joins,
)
from prw.synthetic_tear import generate_synthetic_leaf

_RECORDED = "2026-11-09T00:00:00Z"
_LATER = "2026-11-09T00:00:01Z"


def _fragments(tmp_path: Path) -> tuple[Path, tuple[Path, ...]]:
    benchmarks = tmp_path / "benchmarks"
    images = tmp_path / "images"
    generate_synthetic_leaf(
        benchmarks,
        images_dir=images,
        missing_fragment_percentage=0,
        edge_erosion=0,
        rotation=0,
        lighting_variation=0,
        random_seed=3,
        code_version="test-code",
    )
    found = tuple(sorted(images.glob("fragment-*.tif")))
    assert len(found) >= 3
    return benchmarks, found


def _request(
    paths: tuple[Path, ...] | list[Path], labels: tuple[str, ...]
) -> RankRequest:
    return RankRequest(
        images=tuple(
            PoolImage(label=label, path=path)
            for label, path in zip(labels, paths, strict=True)
        ),
        foreground_threshold=1,
        pixels_per_mm=10,
        uncertainty=0.1,
        minimum_edge_length_mm=0,
        code_version="test-code",
        recorded_at=_RECORDED,
    )


def _session(tmp_path: Path) -> ReviewSession:
    _benchmarks, found = _fragments(tmp_path)
    loaded = load_ranked_joins(_request((found[0], found[2]), ("piece-a", "piece-b")))
    assert isinstance(loaded, ReviewSession)
    return loaded


def _midpoint(edge: tuple[tuple[float, float], ...]) -> tuple[float, float]:
    start, end = edge
    return ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)


def test_review_does_not_import_qt_or_benchmark_writers() -> None:
    finder = ModuleFinder()
    finder.import_hook("prw.review")
    names = set(finder.modules)
    assert "prw.synthetic_tear" not in names
    assert "prw.join_recall" not in names
    assert "prw.outline_agreement" not in names
    assert "prw.placement_error" not in names
    assert "prw.assembly_join_presence" not in names
    assert not any("PySide" in name or "PyQt" in name for name in names)


def test_ranked_lines_call_every_row_a_hypothesis(tmp_path: Path) -> None:
    session = _session(tmp_path)
    rows = session.rows()
    lines = hypothesis_lines(session)
    assert len(rows) >= 2
    assert [row.rank for row in rows] == list(range(1, len(rows) + 1))
    scores = [row.score for row in rows]
    assert scores == sorted(scores, reverse=True)
    assert lines[0].startswith("Rank 1 hypothesis")
    paired = zip(rows, lines, strict=True)
    assert all(line.startswith(f"Rank {row.rank} hypothesis") for row, line in paired)
    assert {row.epistemic_class for row in rows} == {"hypothesis"}
    assert {row.channel for row in rows} == {"physical"}
    assert {row.status for row in rows} == {"proposed"}
    assert "hypothesis" in session.banner()
    assert "Rank 1" in session.banner()
    assert "not a historical join" in session.banner()
    assert "correct_join" not in session.banner()
    assert "correct_join" not in "\n".join(lines)
    assert "does not delete" in session.decision_note()
    assert {item.epistemic_class for item in session.fragments()} == {"interpretation"}
    assert "interpretation" in session.outline_line()
    assert "piece-a" in session.outline_line()
    assert "piece-b" in session.outline_line()


def test_review_order_matches_the_headless_rank_command(tmp_path: Path) -> None:
    _benchmarks, found = _fragments(tmp_path)
    loaded = load_ranked_joins(_request((found[0], found[2]), ("piece-a", "piece-b")))
    assert isinstance(loaded, ReviewSession)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "prw.cli",
            "rank",
            "--image",
            "piece-a",
            str(found[0]),
            "--image",
            "piece-b",
            str(found[2]),
            "--foreground-threshold",
            "1",
            "--code-version",
            "test-code",
            "--pixels-per-mm",
            "10",
            "--uncertainty",
            "0.1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    printed = json.loads(completed.stdout)
    assert [str(row.join_id) for row in loaded.rows()] == [
        item["id"] for item in printed["joins"]
    ]
    assert [row.score for row in loaded.rows()] == [
        float(item["score"]) for item in printed["joins"]
    ]


def test_reject_and_accept_keep_every_hypothesis(tmp_path: Path) -> None:
    session = _session(tmp_path)
    rows = session.rows()
    assert len(rows) >= 2
    stored_ids = session.hypothesis_ids()
    first = rows[0]
    second = rows[1]
    before_first = session.content_bytes(first.join_id)
    before_second = session.content_bytes(second.join_id)
    rejected = session.decide(
        first.join_id,
        "reject",
        actor=LOCAL_OPERATOR,
        decided_at=_LATER,
    )
    assert rejected.decision == "reject"
    assert rejected.actor == LOCAL_OPERATOR
    assert rejected.id.version == 4
    assert rejected.target_hypothesis_id == first.join_id
    kept = session.decide(
        second.join_id,
        "accept",
        actor=LOCAL_OPERATOR,
        decided_at=_LATER,
    )
    assert kept.decision == "accept"
    assert session.hypothesis_ids() == stored_ids
    assert session.content_bytes(first.join_id) == before_first
    assert session.content_bytes(second.join_id) == before_second
    after = {row.join_id: row for row in session.rows()}
    assert set(after) == set(stored_ids)
    assert after[first.join_id].status == "rejected-via-ValidationDecision"
    assert after[first.join_id].decision == "reject"
    assert after[first.join_id].epistemic_class == "hypothesis"
    assert after[second.join_id].status == "proposed"
    assert after[second.join_id].decision == "accept"
    assert after[second.join_id].epistemic_class == "hypothesis"
    lines = hypothesis_lines(session)
    assert len(lines) == len(rows)
    assert all("hypothesis" in line for line in lines)
    assert any("rejected-via-ValidationDecision" in line for line in lines)
    assert any("validation accept" in line for line in lines)
    assert "correct_join" not in "\n".join(lines)


def test_defer_does_not_change_status_or_drop_a_row(tmp_path: Path) -> None:
    session = _session(tmp_path)
    before = session.rows()
    target = before[0]
    content = session.content_bytes(target.join_id)
    session.decide(
        target.join_id,
        "defer",
        actor=LOCAL_OPERATOR,
        decided_at=_LATER,
    )
    after = session.rows()
    assert [row.join_id for row in after] == [row.join_id for row in before]
    assert after[0].status == "proposed"
    assert after[0].decision == "defer"
    assert after[0].epistemic_class == "hypothesis"
    assert session.content_bytes(target.join_id) == content
    assert len(session.decisions()) == 1


def test_placement_sketch_is_a_hypothesis_in_local_millimetres(tmp_path: Path) -> None:
    session = _session(tmp_path)
    row = session.rows()[0]
    sketch = session.placement(row.join_id)
    assert sketch.frame == "fragment_local_mm"
    assert sketch.epistemic_class == "hypothesis"
    assert sketch.anchor_label == row.fragment_b_label
    assert sketch.moved_label == row.fragment_a_label
    assert len(sketch.anchor_polygon) >= 3
    assert len(sketch.moved_polygon) >= 3
    assert "hypothesis" in sketch.caption
    assert "fragment-local" in sketch.caption
    assert "not a page" in sketch.caption
    moved = _midpoint(sketch.moved_edge)
    anchor = _midpoint(sketch.anchor_edge)
    assert math.isclose(moved[0], anchor[0], abs_tol=1e-6)
    assert math.isclose(moved[1], anchor[1], abs_tol=1e-6)
    with pytest.raises(ValueError, match="No join hypothesis"):
        session.placement(uuid.uuid4())


def test_one_fragment_proposes_no_join(tmp_path: Path) -> None:
    _benchmarks, found = _fragments(tmp_path)
    loaded = load_ranked_joins(_request((found[0],), ("piece-a",)))
    assert isinstance(loaded, ReviewSession)
    assert loaded.hypothesis_ids() == ()
    assert hypothesis_lines(loaded) == ("No join hypothesis was proposed.",)
    assert loaded.fragments()[0].epistemic_class == "interpretation"
    assert loaded.fragments()[0].producer == "machine"


def test_a_label_file_and_a_non_tiff_are_not_joins(tmp_path: Path) -> None:
    benchmarks, _found = _fragments(tmp_path)
    labels = benchmarks / "labels.json"
    before = labels.read_bytes()
    with pytest.raises(ValueError, match="BenchmarkLabel"):
        load_ranked_joins(_request((labels,), ("piece-a",)))
    assert labels.read_bytes() == before
    note = tmp_path / "note.txt"
    note.write_bytes(b"not-a-tiff\n")
    failed = load_ranked_joins(_request((note,), ("piece-a",)))
    assert isinstance(failed, ReviewFailure)
    assert failed.record == "UnsupportedMediaType"
    line = failure_line(failed)
    assert line.startswith("UnsupportedMediaType")
    assert "Rank 1" not in line
    missing = tmp_path / "images" / "missing.tif"
    with pytest.raises(ValueError, match="not a fixture image"):
        load_ranked_joins(_request((missing,), ("piece-a",)))
