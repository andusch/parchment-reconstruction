"""Headless CLI entry point, without a display."""

import json
import subprocess
import sys
from pathlib import Path

from prw.identity import hash_value
from prw.synthetic_tear import generate_synthetic_leaf


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "prw.cli", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_imports_no_qt() -> None:
    import prw.cli as cli

    assert callable(cli.main)
    roots = {name.split(".", maxsplit=1)[0].lower() for name in sys.modules}
    assert roots.isdisjoint({"pyqt5", "pyqt6", "pyside2", "pyside6", "pyqt"})


def test_verify_prints_a_hash_or_an_integrity_failure(tmp_path: Path) -> None:
    images = tmp_path / "images"
    generate_synthetic_leaf(
        tmp_path / "benchmarks",
        images_dir=images,
        missing_fragment_percentage=0.0,
        edge_erosion=0.0,
        rotation=0.0,
        lighting_variation=0.0,
        random_seed=3,
        code_version="test-code",
    )
    page = images / "page.tif"
    payload = page.read_bytes()
    matched = _run("verify", str(page), "--expected", hash_value(payload))
    assert matched.returncode == 0
    verified = json.loads(matched.stdout)
    assert verified["record"] == "VerifiedBytes"
    assert verified["content_hash"] == hash_value(payload)
    assert "hypothesis" not in matched.stdout

    mismatched = _run("verify", str(page), "--expected", "sha256:" + "ab" * 32)
    assert mismatched.returncode == 1
    failure = json.loads(mismatched.stdout)
    assert failure["record"] == "IntegrityFailure"
    assert failure["expected_hash"] == "sha256:" + "ab" * 32
    assert failure["presented_hash"] == hash_value(payload)
    assert "hypothesis" not in mismatched.stdout
    assert "correct_join" not in mismatched.stdout


def test_frame_prints_centroid_origin_and_millimetre_axes() -> None:
    completed = _run("frame", "--polygon", "0,0", "2,0", "2,2", "0,2")
    assert completed.returncode == 0
    frame = json.loads(completed.stdout)
    assert frame["kind"] == "fragment_local_mm"
    assert frame["origin"] == [1.0, 1.0]
    assert frame["axis_x_direction"] == "+x right"
    assert frame["axis_y_direction"] == "+y down"
    assert frame["unit"] == "mm"
    assert frame["origin_description"] == "first-outline centroid"


def test_provenance_omits_the_seed_unless_the_call_uses_randomness() -> None:
    deterministic = _run(
        "provenance",
        "--algorithm-name",
        "demo",
        "--algorithm-version",
        "1",
        "--code-version",
        "test-code",
        "--parameter",
        "edge_erosion=0.25",
    )
    assert deterministic.returncode == 0
    envelope = json.loads(deterministic.stdout)
    assert "random_seed" not in envelope
    assert envelope["parameter_hash"].startswith("sha256:")
    assert json.loads(envelope["parameter_blob"]) == {"edge_erosion": 0.25}

    seeded = _run(
        "provenance",
        "--algorithm-name",
        "demo",
        "--algorithm-version",
        "1",
        "--code-version",
        "test-code",
        "--parameter",
        "edge_erosion=0.25",
        "--random-seed",
        "7",
    )
    assert seeded.returncode == 0
    assert json.loads(seeded.stdout)["random_seed"] == 7


def test_generate_writes_only_under_the_benchmarks_path(tmp_path: Path) -> None:
    benchmarks = tmp_path / "benchmarks"
    completed = _run(
        "generate",
        "--benchmarks",
        str(benchmarks),
        "--images",
        str(benchmarks),
        "--missing-fragment-percentage",
        "0",
        "--edge-erosion",
        "0",
        "--rotation",
        "0.2",
        "--lighting-variation",
        "0.4",
        "--random-seed",
        "7",
        "--code-version",
        "test-code",
    )
    assert completed.returncode == 0, completed.stderr
    printed = json.loads(completed.stdout)
    assert printed["provenance"]["random_seed"] == 7
    assert printed["provenance"]["parameter_hash"].startswith("sha256:")
    assert "lighting_variation" in printed["provenance"]["parameter_blob"]
    assert "correct_join" not in completed.stdout
    assert "hypothesis" not in completed.stdout
    assert (benchmarks / "labels.json").is_file()
    assert (benchmarks / "provenance.json").is_file()
    assert (benchmarks / "image_manifest.json").is_file()
    assert (benchmarks / "page.tif").is_file()
    assert not (benchmarks / "manifest.json").exists()
    assert not (tmp_path / "manifest.json").exists()
    assert not (tmp_path / "originals").exists()
    outside = [
        path
        for path in tmp_path.rglob("*")
        if path != benchmarks and benchmarks not in path.parents
    ]
    assert outside == []

    project = tmp_path / "project"
    (project / "originals").mkdir(parents=True)
    (project / "manifest.json").write_text("{}\n", encoding="utf-8")
    refused = _run(
        "generate",
        "--benchmarks",
        str(project / "benchmarks"),
        "--images",
        str(project / "images"),
        "--missing-fragment-percentage",
        "0",
        "--edge-erosion",
        "0",
        "--rotation",
        "0",
        "--lighting-variation",
        "0",
        "--random-seed",
        "1",
        "--code-version",
        "test-code",
    )
    assert refused.returncode == 2
    assert "project evidence database" in refused.stderr
    assert "correct_join" not in refused.stdout
