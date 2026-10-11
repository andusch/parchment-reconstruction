"""Headless CLI entry point, without a display."""

import json
import subprocess
import sys
from pathlib import Path

from prw.identity import hash_value
from prw.outline_agreement import polygon_iou
from prw.synthetic_tear import (
    SyntheticLeaf,
    fragment_polygon_in_source_pixels,
    generate_synthetic_leaf,
)


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


def _fragment(tmp_path: Path) -> tuple[Path, Path, bytes]:
    benchmarks, fragment, payload, _generated = _synthetic_leaf(tmp_path)
    return benchmarks, fragment, payload


def _synthetic_leaf(tmp_path: Path) -> tuple[Path, Path, bytes, SyntheticLeaf]:
    benchmarks = tmp_path / "benchmarks"
    images = tmp_path / "images"
    leaf = generate_synthetic_leaf(
        benchmarks,
        images_dir=images,
        missing_fragment_percentage=0.0,
        edge_erosion=0.0,
        rotation=0.0,
        lighting_variation=0.0,
        random_seed=3,
        code_version="test-code",
    )
    fragment = next(images.glob("fragment-*.tif"))
    return benchmarks, fragment, fragment.read_bytes(), leaf


def test_segment_prints_an_outline_or_a_checksum_failure(tmp_path: Path) -> None:
    _benchmarks, fragment, payload = _fragment(tmp_path)
    mismatched = _run(
        "segment",
        str(fragment),
        "--label",
        "shelf-4",
        "--foreground-threshold",
        "1",
        "--code-version",
        "test-code",
        "--expected",
        "sha256:" + "ab" * 32,
    )
    assert mismatched.returncode == 1
    failure = json.loads(mismatched.stdout)
    assert failure["record"] == "IntegrityFailure"
    assert "polygon" not in failure
    assert "polygon" not in mismatched.stdout

    segmented = _run(
        "segment",
        str(fragment),
        "--label",
        "shelf-4",
        "--foreground-threshold",
        "1",
        "--code-version",
        "test-code",
        "--expected",
        hash_value(payload),
    )
    assert segmented.returncode == 0, segmented.stderr
    outline = json.loads(segmented.stdout)
    assert outline["record"] == "FragmentOutlineRevision"
    assert outline["epistemic_class"] == "interpretation"
    assert outline["producer"] == "machine"
    assert outline["frame"] == "source_pixels"
    assert len(outline["polygon"]) >= 3
    assert outline["envelope"]["algorithm_name"] == "fragment_outline"
    assert outline["envelope"]["algorithm_version"] == "1"
    assert outline["envelope"]["model_hash"] == "absent"
    assert "random_seed" not in outline["envelope"]
    assert "correct_join" not in segmented.stdout


def test_segment_with_scale_prints_a_millimetre_outline(tmp_path: Path) -> None:
    _benchmarks, fragment, payload = _fragment(tmp_path)
    scaled = _run(
        "segment",
        str(fragment),
        "--label",
        "shelf-4",
        "--foreground-threshold",
        "1",
        "--code-version",
        "test-code",
        "--expected",
        hash_value(payload),
        "--pixels-per-mm",
        "2",
        "--uncertainty",
        "0",
    )
    assert scaled.returncode == 0, scaled.stderr
    outline = json.loads(scaled.stdout)
    assert outline["frame"] == "fragment_local_mm"
    assert outline["epistemic_class"] == "interpretation"
    assert outline["producer"] == "machine"
    assert outline["envelope"]["algorithm_name"] == "caller_supplied_scale"
    assert "polygon" in outline
    assert "correct_join" not in scaled.stdout


def test_agree_writes_under_benchmarks_and_refuses_a_join_file(tmp_path: Path) -> None:
    benchmarks, fragment, _payload, leaf = _synthetic_leaf(tmp_path)
    geometry = next(
        item for item in leaf.fragments if fragment.name == f"fragment-{item.id}.tif"
    )
    reference = fragment_polygon_in_source_pixels(geometry.page_polygon)
    reference_args = [
        f"--reference={x_coord!r},{y_coord!r}" for x_coord, y_coord in reference
    ]
    labels = (benchmarks / "labels.json").read_bytes()
    outside = {
        path.relative_to(tmp_path)
        for path in tmp_path.rglob("*")
        if benchmarks not in path.parents and path != benchmarks
    }
    agreed = _run(
        "agree",
        str(fragment),
        "--benchmarks",
        str(benchmarks),
        *reference_args,
        "--frame",
        "source_pixels",
        "--label",
        "shelf-4",
        "--foreground-threshold",
        "1",
        "--code-version",
        "test-code",
    )
    assert agreed.returncode == 0, agreed.stderr
    report = json.loads(agreed.stdout)
    predicted = report["predicted_polygons"][0]
    assert predicted != report["reference_polygons"][0]
    assert report["ious"] == [
        polygon_iou(
            predicted,
            reference,
            predicted_frame="source_pixels",
            reference_frame="source_pixels",
        )
    ]
    assert report["algorithm_name"] == "fragment_outline"
    assert report["reference"] == "generator polygon supplied by the caller"
    assert "polygon" not in report
    report_path = benchmarks / "outline_agreement" / "outline-agreement-0001.json"
    assert report_path.is_file()
    assert (benchmarks / "labels.json").read_bytes() == labels
    assert not (benchmarks / "manifest.json").exists()
    assert not (tmp_path / "originals").exists()
    later_outside = {
        path.relative_to(tmp_path)
        for path in tmp_path.rglob("*")
        if benchmarks not in path.parents and path != benchmarks
    }
    assert later_outside == outside

    refused = _run(
        "agree",
        str(fragment),
        "--benchmarks",
        str(benchmarks / "labels.json"),
        *reference_args,
        "--frame",
        "source_pixels",
        "--label",
        "shelf-4",
        "--foreground-threshold",
        "1",
        "--code-version",
        "test-code",
    )
    assert refused.returncode == 2
    assert "BenchmarkLabel join file" in refused.stderr
    assert refused.stdout == ""
    assert (benchmarks / "labels.json").read_bytes() == labels
    assert list((benchmarks / "outline_agreement").glob("*.json")) == [report_path]
