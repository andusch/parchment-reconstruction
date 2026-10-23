"""Headless CLI entry point, without a display."""

import argparse
import contextlib
import inspect
import io
import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from prw.identity import hash_value
from prw.joins import JoinHypothesis
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
    source = Path(inspect.getfile(cli)).read_text(encoding="utf-8")
    assert "PyQt" not in source
    assert "PySide" not in source
    assert "threading" not in source
    assert "multiprocessing" not in source


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


def _first_fragment(images: Path) -> tuple[Path, list[str]]:
    manifest = json.loads((images / "image_manifest.json").read_text(encoding="utf-8"))
    names = [
        entry["name"] for entry in manifest["images"] if entry["role"] == "fragment"
    ]
    return images / names[0], names


def _distinguish_first_fragment(path: Path) -> bytes:
    payload = bytearray(path.read_bytes())
    payload[-1] ^= 0x01
    if payload[-1] == 0:
        payload[-1] = 2
    written = bytes(payload)
    path.write_bytes(written)
    return written


def test_existing_image_is_itself_and_absent_ordinal_lists_manifest_names(
    tmp_path: Path,
) -> None:
    benchmarks, _fragment, _payload, _leaf = _synthetic_leaf(tmp_path)
    images = tmp_path / "images"
    first, names = _first_fragment(images)
    page = images / "page.tif"
    alias = images / "fragment-0.tif"
    alias.write_bytes(page.read_bytes())
    existing = _run("verify", str(alias))
    assert existing.returncode == 0, existing.stderr
    assert json.loads(existing.stdout)["content_hash"] == hash_value(page.read_bytes())
    assert json.loads(existing.stdout)["content_hash"] != hash_value(first.read_bytes())
    alias.unlink()

    labels = benchmarks / "labels.json"
    original_labels = labels.read_bytes()
    parked = tmp_path / "labels-parked.json"
    parked.write_bytes(original_labels)
    labels.unlink()
    written = _distinguish_first_fragment(first)
    digest = hash_value(written)

    def _assert_absent(completed: subprocess.CompletedProcess[str]) -> None:
        assert completed.returncode == 2
        assert completed.stdout == ""
        assert str(alias) in completed.stderr
        assert "Fragment files:" in completed.stderr
        assert "Traceback" not in completed.stderr
        for name in names:
            assert name in completed.stderr

    verified = _run("verify", str(alias))
    direct = _run("verify", str(first))
    assert direct.returncode == 0, direct.stderr
    assert json.loads(direct.stdout)["content_hash"] == digest
    _assert_absent(verified)
    assert verified.stdout != direct.stdout

    segment_args = (
        "--label",
        "shelf-4",
        "--foreground-threshold",
        "1",
        "--code-version",
        "test-code",
    )
    segmented = _run("segment", str(alias), *segment_args)
    direct_segment = _run("segment", str(first), *segment_args)
    assert direct_segment.returncode == 0, direct_segment.stderr
    assert json.loads(direct_segment.stdout)["envelope"]["source_hashes"] == [digest]
    _assert_absent(segmented)
    assert segmented.stdout != direct_segment.stdout

    scale_args = (*segment_args, "--pixels-per-mm", "10", "--uncertainty", "0.1")
    scaled = _run("segment", str(alias), *scale_args)
    direct_scaled = _run("segment", str(first), *scale_args)
    assert direct_scaled.returncode == 0, direct_scaled.stderr
    direct_scaled_body = json.loads(direct_scaled.stdout)
    assert direct_scaled_body["frame"] == "fragment_local_mm"
    assert direct_scaled_body["envelope"]["source_hashes"] == [digest]
    _assert_absent(scaled)
    assert scaled.stdout != direct_scaled.stdout
    assert not labels.exists()
    assert parked.read_bytes() == original_labels


def test_missing_image_names_the_fragment_files(tmp_path: Path) -> None:
    _benchmarks, _fragment, _payload, _leaf = _synthetic_leaf(tmp_path)
    images = tmp_path / "images"
    _first, names = _first_fragment(images)

    missing = _run("verify", str(images / "not-a-page.tif"))
    assert missing.returncode == 2
    assert missing.stdout == ""
    assert str(images / "not-a-page.tif") in missing.stderr
    assert "Traceback" not in missing.stderr
    for name in names:
        assert name in missing.stderr

    out_of_range = _run("verify", str(images / "fragment-9.tif"))
    assert out_of_range.returncode == 2
    assert out_of_range.stdout == ""
    assert str(images / "fragment-9.tif") in out_of_range.stderr
    assert "Traceback" not in out_of_range.stderr
    for name in names:
        assert name in out_of_range.stderr

    absent_page = _run("verify", str(tmp_path / "empty" / "page.tif"))
    assert absent_page.returncode == 2
    assert absent_page.stdout == ""
    assert str(tmp_path / "empty" / "page.tif") in absent_page.stderr
    assert "Fragment files:" not in absent_page.stderr

    manifest_path = images / "image_manifest.json"
    manifest_text = manifest_path.read_text(encoding="utf-8")
    manifest_path.unlink()
    without_manifest = _run("verify", str(images / "fragment-0.tif"))
    assert without_manifest.returncode == 2
    assert without_manifest.stdout == ""
    assert str(images / "fragment-0.tif") in without_manifest.stderr
    for name in names:
        assert name in without_manifest.stderr

    manifest_path.write_text("{", encoding="utf-8")
    corrupt = _run("verify", str(images / "fragment-0.tif"))
    assert corrupt.returncode == 2
    assert corrupt.stdout == ""
    assert corrupt.stderr.strip() == "An image manifest is JSON."
    assert "Traceback" not in corrupt.stderr
    manifest_path.write_text(manifest_text, encoding="utf-8")


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


def _files(directory: Path) -> set[Path]:
    return {path for path in directory.rglob("*") if path.is_file()}


def test_edge_prints_millimetre_chords_or_a_pixel_failure(tmp_path: Path) -> None:
    _benchmarks, fragment, _payload, _leaf = _synthetic_leaf(tmp_path)
    traced = _run(
        "edge",
        str(fragment),
        "--label",
        "shelf-4",
        "--foreground-threshold",
        "1",
        "--code-version",
        "test-code",
        "--pixels-per-mm",
        "10",
        "--uncertainty",
        "0.1",
    )
    assert traced.returncode == 0, traced.stderr
    printed = json.loads(traced.stdout)
    assert printed["record"] == "ChordEdges"
    assert printed["edges"]
    assert {edge["epistemic_class"] for edge in printed["edges"]} == {"interpretation"}
    assert printed["envelope"]["algorithm_name"] == "edge_chord"
    assert printed["envelope"]["model_hash"] == "absent"
    assert "random_seed" not in printed["envelope"]
    assert "correct_join" not in traced.stdout
    assert "pose" not in traced.stdout

    pixel = _run(
        "edge",
        str(fragment),
        "--label",
        "shelf-4",
        "--foreground-threshold",
        "1",
        "--code-version",
        "test-code",
    )
    assert pixel.returncode == 1
    failure = json.loads(pixel.stdout)
    assert failure == {
        "record": "FailedEdgeChord",
        "run_id": failure["run_id"],
        "status": "failed",
    }
    assert "geometry" not in pixel.stdout
    assert "pose" not in pixel.stdout
    assert "translation" not in pixel.stdout


def test_one_repeated_pool_flag_parses() -> None:
    import prw.cli as cli

    parsed = cli._parser().parse_args(
        [
            "rank",
            "--image",
            "piece-a",
            "a.tif",
            "--image",
            "piece-b",
            "b.tif",
            "--foreground-threshold",
            "1",
            "--code-version",
            "test-code",
        ]
    )
    assert parsed.images == [
        ["piece-a", "a.tif"],
        ["piece-b", "b.tif"],
    ]
    assert not hasattr(parsed, "paths")
    assert not hasattr(parsed, "labels")

    recalled = cli._parser().parse_args(
        [
            "recall",
            "--image",
            "piece-a",
            "a.tif",
            "--image",
            "piece-b",
            "b.tif",
            "--benchmarks",
            "benchmarks",
            "--k",
            "1",
            "--foreground-threshold",
            "1",
            "--code-version",
            "test-code",
        ]
    )
    assert recalled.images == [
        ["piece-a", "a.tif"],
        ["piece-b", "b.tif"],
    ]


def test_interleaved_pool_argv_is_rejected() -> None:
    import prw.cli as cli

    commands = (
        [
            "rank",
            "a.tif",
            "--label",
            "piece-a",
            "b.tif",
            "--label",
            "piece-b",
            "--foreground-threshold",
            "1",
            "--code-version",
            "test-code",
            "--pixels-per-mm",
            "10",
            "--uncertainty",
            "0.1",
        ],
        [
            "rank",
            "a.tif",
            "b.tif",
            "--label",
            "piece-a",
            "--label",
            "piece-b",
            "--foreground-threshold",
            "1",
            "--code-version",
            "test-code",
            "--pixels-per-mm",
            "10",
            "--uncertainty",
            "0.1",
        ],
        [
            "recall",
            "a.tif",
            "--label",
            "piece-a",
            "b.tif",
            "--label",
            "piece-b",
            "--benchmarks",
            "benchmarks",
            "--k",
            "1",
            "--foreground-threshold",
            "1",
            "--code-version",
            "test-code",
            "--pixels-per-mm",
            "10",
            "--uncertainty",
            "0.1",
        ],
    )
    for argv in commands:
        stderr = io.StringIO()
        with (
            pytest.raises(SystemExit) as caught,
            contextlib.redirect_stderr(stderr),
        ):
            cli._parser().parse_args(argv)
        assert caught.value.code == 2
        message = stderr.getvalue()
        assert "the following arguments are required: --image" in message
        assert "Traceback" not in message


def test_assigning_parse_known_args_fails() -> None:
    import prw.cli as cli

    source = Path(inspect.getfile(cli)).read_text(encoding="utf-8")
    assert "parse_known_args" not in source
    assert "parse_known_intermixed_args" not in source
    parser = cli._parser()
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    for name in ("rank", "recall"):
        command = subparsers.choices[name]
        parse_known_args = command.parse_known_args
        assert parse_known_args.__func__ is argparse.ArgumentParser.parse_known_args


def test_rank_prints_physical_order_and_refuses_a_join_file(tmp_path: Path) -> None:
    benchmarks, _fragment, _payload, _leaf = _synthetic_leaf(tmp_path)
    images = tmp_path / "images"
    fragments = sorted(images.glob("fragment-*.tif"))
    assert len(fragments) >= 3
    labels = (benchmarks / "labels.json").read_bytes()
    ranked = _run(
        "rank",
        "--image",
        "piece-a",
        str(fragments[0]),
        "--image",
        "piece-b",
        str(fragments[2]),
        "--foreground-threshold",
        "1",
        "--code-version",
        "test-code",
        "--pixels-per-mm",
        "10",
        "--uncertainty",
        "0.1",
    )
    assert ranked.returncode == 0, ranked.stderr
    printed = json.loads(ranked.stdout)
    assert printed["record"] == "physical_join_order"
    scores = [item["score"] for item in printed["joins"]]
    assert scores
    assert scores == sorted(scores, reverse=True)
    assert {item["epistemic_class"] for item in printed["joins"]} == {"hypothesis"}
    assert {item["channel"] for item in printed["joins"]} == {"physical"}
    assert printed["envelope"]["algorithm_name"] == "pairwise_rigid_join"
    assert "pose" not in ranked.stdout
    assert "correct_join" not in ranked.stdout
    assert (benchmarks / "labels.json").read_bytes() == labels

    interleaved = _run(
        "rank",
        str(fragments[0]),
        "--label",
        "piece-a",
        str(fragments[2]),
        "--label",
        "piece-b",
        "--foreground-threshold",
        "1",
        "--code-version",
        "test-code",
        "--pixels-per-mm",
        "10",
        "--uncertainty",
        "0.1",
    )
    assert interleaved.returncode == 2
    assert interleaved.stdout == ""
    assert "the following arguments are required: --image" in interleaved.stderr
    assert "Traceback" not in interleaved.stderr
    assert "physical_join_order" not in interleaved.stdout
    assert (benchmarks / "labels.json").read_bytes() == labels

    missing_image = _run(
        "rank",
        "--image",
        "piece-a",
        str(images / "fragment-0.tif"),
        "--image",
        "piece-b",
        str(fragments[2]),
        "--foreground-threshold",
        "1",
        "--code-version",
        "test-code",
        "--pixels-per-mm",
        "10",
        "--uncertainty",
        "0.1",
    )
    assert missing_image.returncode == 2
    assert missing_image.stdout == ""
    assert str(images / "fragment-0.tif") in missing_image.stderr
    assert "Fragment files:" in missing_image.stderr
    assert "Traceback" not in missing_image.stderr
    for fragment in fragments:
        assert fragment.name in missing_image.stderr
    assert (benchmarks / "labels.json").read_bytes() == labels

    missing = _run(
        "rank",
        "--image",
        "piece-a",
        str(fragments[0]),
        "--image",
        "piece-b",
        str(fragments[2]),
        "--foreground-threshold",
        "1",
        "--code-version",
        "test-code",
    )
    assert missing.returncode == 1
    failure = json.loads(missing.stdout)
    assert failure["record"] == "FailedPairwiseJoin"
    assert failure["status"] == "failed"
    assert "joins" not in failure
    assert "pose" not in missing.stdout
    assert "translation" not in missing.stdout
    assert (benchmarks / "labels.json").read_bytes() == labels

    refused = _run(
        "rank",
        "--image",
        "piece-a",
        str(benchmarks / "labels.json"),
        "--foreground-threshold",
        "1",
        "--code-version",
        "test-code",
        "--pixels-per-mm",
        "10",
        "--uncertainty",
        "0.1",
    )
    assert refused.returncode == 2
    assert "BenchmarkLabel join file" in refused.stderr
    assert refused.stdout == ""
    assert (benchmarks / "labels.json").read_bytes() == labels


def test_recall_writes_only_a_new_report(tmp_path: Path) -> None:
    benchmarks, _fragment, _payload, _leaf = _synthetic_leaf(tmp_path)
    images = tmp_path / "images"
    fragments = sorted(images.glob("fragment-*.tif"))
    assert len(fragments) >= 3
    labels = (benchmarks / "labels.json").read_bytes()
    provenance = (benchmarks / "provenance.json").read_bytes()
    before = _files(benchmarks)
    image_bytes = _files(images)
    recalled = _run(
        "recall",
        "--image",
        "piece-a",
        str(fragments[0]),
        "--image",
        "piece-b",
        str(fragments[2]),
        "--benchmarks",
        str(benchmarks),
        "--k",
        "1",
        "--foreground-threshold",
        "1",
        "--code-version",
        "test-code",
        "--pixels-per-mm",
        "10",
        "--uncertainty",
        "0.1",
    )
    assert recalled.returncode == 0, recalled.stderr
    report = json.loads(recalled.stdout)
    assert report["k"] == 1
    assert report["algorithm_name"] == "pairwise_rigid_join"
    assert "recall" in report
    assert "correct_join" not in recalled.stdout
    report_path = benchmarks / "join_recall" / "join-recall-0001.json"
    assert _files(benchmarks) - before == {report_path}
    assert (benchmarks / "labels.json").read_bytes() == labels
    assert (benchmarks / "provenance.json").read_bytes() == provenance
    assert _files(images) == image_bytes
    assert not (tmp_path / "originals").exists()
    assert not (benchmarks / "manifest.json").exists()

    refused = _run(
        "recall",
        "--image",
        "piece-a",
        str(benchmarks / "labels.json"),
        "--benchmarks",
        str(benchmarks),
        "--k",
        "1",
        "--foreground-threshold",
        "1",
        "--code-version",
        "test-code",
        "--pixels-per-mm",
        "10",
        "--uncertainty",
        "0.1",
    )
    assert refused.returncode == 2
    assert "BenchmarkLabel join file" in refused.stderr
    assert refused.stdout == ""
    assert (benchmarks / "labels.json").read_bytes() == labels
    assert _files(benchmarks) - before == {report_path}


def _assembly_args(fragments: list[Path], *extra: str) -> list[str]:
    return [
        "--image",
        "piece-a",
        str(fragments[0]),
        "--image",
        "piece-b",
        str(fragments[2]),
        "--foreground-threshold",
        "1",
        "--code-version",
        "test-code",
        "--pixels-per-mm",
        "10",
        "--uncertainty",
        "0.1",
        "--minimum-edge-length-mm",
        "6",
        "--n",
        "2",
        "--translation-tolerance-mm",
        "1",
        "--rotation-tolerance-radians",
        "1",
        "--min-width-mm",
        "0",
        "--max-width-mm",
        "1000",
        "--min-height-mm",
        "0",
        "--max-height-mm",
        "1000",
        *extra,
    ]


def _without(args: list[str], flag: str) -> list[str]:
    kept: list[str] = []
    skip = False
    for item in args:
        if skip:
            skip = False
            continue
        if item == flag:
            skip = True
            continue
        kept.append(item)
    return kept


def test_assemble_prints_search_or_a_failure_without_a_placement(
    tmp_path: Path,
) -> None:
    benchmarks, _fragment, _payload, _leaf = _synthetic_leaf(tmp_path)
    images = tmp_path / "images"
    fragments = sorted(images.glob("fragment-*.tif"))
    assert len(fragments) >= 3
    labels = (benchmarks / "labels.json").read_bytes()
    searched = _run("assemble", *_assembly_args(fragments))
    assert searched.returncode == 0, searched.stderr
    printed = json.loads(searched.stdout)
    assert printed["record"] == "AssemblySearch"
    assert isinstance(printed["assemblies"], list)
    assert printed["screening"]
    assert {event["gate"] for event in printed["screening"]} == {"physical"}
    assert printed["envelope"]["algorithm_name"] == "rigid_assembly_search"
    assert "correct_join" not in searched.stdout
    assert "truth" not in searched.stdout
    assert (benchmarks / "labels.json").read_bytes() == labels

    missing_page = _run(
        "assemble",
        *_without(
            _without(
                _without(
                    _without(_assembly_args(fragments), "--min-width-mm"),
                    "--max-width-mm",
                ),
                "--min-height-mm",
            ),
            "--max-height-mm",
        ),
    )
    assert missing_page.returncode == 1, missing_page.stderr
    failure = json.loads(missing_page.stdout)
    assert failure["record"] == "FailedAssemblySearch"
    assert failure["status"] == "failed"
    assert "placement" not in missing_page.stdout
    assert "assemblies" not in failure
    assert (benchmarks / "labels.json").read_bytes() == labels

    missing_n = _run("assemble", *_without(_assembly_args(fragments), "--n"))
    assert missing_n.returncode == 1, missing_n.stderr
    assert json.loads(missing_n.stdout)["record"] == "FailedAssemblySearch"
    assert "placement" not in missing_n.stdout

    pixels = _run(
        "assemble",
        *_without(
            _without(_assembly_args(fragments), "--pixels-per-mm"),
            "--uncertainty",
        ),
    )
    assert pixels.returncode == 1, pixels.stderr
    assert json.loads(pixels.stdout)["record"] == "FailedAssemblySearch"
    assert "placement" not in pixels.stdout

    refused = _run(
        "assemble",
        "--image",
        "piece-a",
        str(benchmarks / "labels.json"),
        "--foreground-threshold",
        "1",
        "--code-version",
        "test-code",
        "--pixels-per-mm",
        "10",
        "--uncertainty",
        "0.1",
        "--n",
        "1",
        "--translation-tolerance-mm",
        "1",
        "--rotation-tolerance-radians",
        "1",
        "--min-width-mm",
        "0",
        "--max-width-mm",
        "1000",
        "--min-height-mm",
        "0",
        "--max-height-mm",
        "1000",
    )
    assert refused.returncode == 2
    assert "BenchmarkLabel join file" in refused.stderr
    assert refused.stdout == ""
    assert (benchmarks / "labels.json").read_bytes() == labels


def test_assembly_rank_prints_physical_order_and_refuses_a_join(
    tmp_path: Path,
) -> None:
    import prw.cli as cli
    from prw.provenance import Score

    benchmarks, _fragment, _payload, _leaf = _synthetic_leaf(tmp_path)
    images = tmp_path / "images"
    fragments = sorted(images.glob("fragment-*.tif"))
    labels = (benchmarks / "labels.json").read_bytes()
    ranked = _run("assembly-rank", *_assembly_args(fragments))
    assert ranked.returncode == 0, ranked.stderr
    printed = json.loads(ranked.stdout)
    assert printed["record"] == "physical_assembly_order"
    assert isinstance(printed["assemblies"], list)
    scores = [item["score"] for item in printed["assemblies"]]
    assert scores == sorted(scores, reverse=True)
    assert {item["epistemic_class"] for item in printed["assemblies"]} <= {"hypothesis"}
    assert printed["envelope"]["algorithm_name"] == "rigid_assembly_search"
    assert "correct_join" not in ranked.stdout
    assert (benchmarks / "labels.json").read_bytes() == labels

    refused = _run(
        "assembly-rank",
        "--image",
        "piece-a",
        str(benchmarks / "labels.json"),
        "--foreground-threshold",
        "1",
        "--code-version",
        "test-code",
        "--pixels-per-mm",
        "10",
        "--uncertainty",
        "0.1",
        "--n",
        "1",
        "--translation-tolerance-mm",
        "1",
        "--rotation-tolerance-radians",
        "1",
        "--min-width-mm",
        "0",
        "--max-width-mm",
        "1000",
        "--min-height-mm",
        "0",
        "--max-height-mm",
        "1000",
    )
    assert refused.returncode == 2
    assert "BenchmarkLabel join file" in refused.stderr
    assert "assembly-rank" in refused.stderr
    assert refused.stdout == ""
    assert (benchmarks / "labels.json").read_bytes() == labels

    run_id = uuid.uuid4()
    provenance_id = uuid.uuid4()
    join = JoinHypothesis.create(
        run_id=run_id,
        fragment_a_id=uuid.uuid4(),
        edge_a_id=uuid.uuid4(),
        fragment_b_id=uuid.uuid4(),
        edge_b_id=uuid.uuid4(),
        transform_id=uuid.uuid4(),
        scores=(
            Score(
                value=1.0,
                run_id=run_id,
                channel="physical",
                hypothesis_type="join",
            ),
        ),
        provenance_id=provenance_id,
    )
    with pytest.raises(ValueError, match="join"):
        cli._ordered_assemblies((join,), (), ())


def test_assembly_reports_write_only_a_new_file(tmp_path: Path) -> None:
    benchmarks, _fragment, _payload, _leaf = _synthetic_leaf(tmp_path)
    images = tmp_path / "images"
    fragments = sorted(images.glob("fragment-*.tif"))
    labels = (benchmarks / "labels.json").read_bytes()
    provenance = (benchmarks / "provenance.json").read_bytes()
    before = _files(benchmarks)
    image_bytes = _files(images)
    args = _assembly_args(fragments, "--benchmarks", str(benchmarks))

    placed = _run("placement-error", *args)
    assert placed.returncode == 0, placed.stderr
    placement_report = json.loads(placed.stdout)
    assert placement_report["metric"] == "placement_error"
    assert placement_report["n"] == 2
    placement_path = benchmarks / "placement_error" / "placement-error-0001.json"
    assert placement_path.is_file()
    assert _files(benchmarks) - before == {placement_path}
    assert (benchmarks / "labels.json").read_bytes() == labels
    assert (benchmarks / "provenance.json").read_bytes() == provenance
    assert _files(images) == image_bytes
    assert "correct_join" not in placed.stdout

    present = _run("join-presence", *args)
    assert present.returncode == 0, present.stderr
    presence_report = json.loads(present.stdout)
    assert presence_report["metric"] == "assembly_join_presence"
    assert presence_report["n"] == 2
    presence_path = (
        benchmarks / "assembly_join_presence" / "assembly-join-presence-0001.json"
    )
    assert presence_path.is_file()
    assert _files(benchmarks) - before == {placement_path, presence_path}
    assert (benchmarks / "labels.json").read_bytes() == labels
    assert (benchmarks / "provenance.json").read_bytes() == provenance
    assert _files(images) == image_bytes
    assert "correct_join" not in present.stdout
    assert not (tmp_path / "originals").exists()
    assert not (benchmarks / "manifest.json").exists()
