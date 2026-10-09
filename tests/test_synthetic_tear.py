"""Synthetic leaf geometry and BenchmarkLabel writes."""

import dataclasses
import json
from pathlib import Path

import pytest

from prw.identity import canonical_json
from prw.synthetic_tear import (
    SyntheticLeaf,
    erode_toward_centroid,
    generate_synthetic_leaf,
)


def _generate(
    directory: Path,
    *,
    missing_fragment_percentage: float = 0.0,
    edge_erosion: float = 0.0,
    rotation: float = 0.2,
    lighting_variation: float = 0.0,
    random_seed: int = 7,
) -> SyntheticLeaf:
    return generate_synthetic_leaf(
        directory,
        missing_fragment_percentage=missing_fragment_percentage,
        edge_erosion=edge_erosion,
        rotation=rotation,
        lighting_variation=lighting_variation,
        random_seed=random_seed,
        code_version="test-code",
    )


def test_erosion_moves_a_vertex_toward_the_centroid() -> None:
    square = ((0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0))
    eroded = erode_toward_centroid(square, 0.5)
    assert eroded[0] == pytest.approx((0.5, 0.5))
    before = (0.0 - 1.0) ** 2 + (0.0 - 1.0) ** 2
    after = (0.5 - 1.0) ** 2 + (0.5 - 1.0) ** 2
    assert after < before


def test_fragment_local_axes_and_page_placement(tmp_path: Path) -> None:
    leaf = _generate(tmp_path / "benchmarks")
    assert leaf.page_frame.kind == "page_global_mm"
    assert leaf.page_frame.origin == (0.0, 0.0)
    assert leaf.page_frame.axis_x_direction == "+x right"
    assert leaf.page_frame.axis_y_direction == "+y down"
    fragment = leaf.fragments[0]
    assert fragment.frame.kind == "fragment_local_mm"
    assert fragment.frame.unit == "mm"
    assert fragment.frame.axis_x_direction == "+x right"
    assert fragment.frame.axis_y_direction == "+y down"
    centroid_x, centroid_y = fragment.page_centroid
    pairs = zip(fragment.page_polygon, fragment.local_polygon, strict=True)
    for (page_x, page_y), (local_x, local_y) in pairs:
        assert local_x == pytest.approx(page_x - centroid_x)
        assert local_y == pytest.approx(page_y - centroid_y)
    assert leaf.placements[0].rotation_radians == 0.2


def test_same_seed_repeats_polygons_and_label_ids(tmp_path: Path) -> None:
    first = _generate(tmp_path / "one")
    second = _generate(tmp_path / "two")
    assert first.fragments[0].local_polygon == second.fragments[0].local_polygon
    assert [item.id for item in first.joins] == [item.id for item in second.joins]
    assert [item.id for item in first.placements] == [
        item.id for item in second.placements
    ]
    assert first.page.id == second.page.id
    other = _generate(tmp_path / "three", random_seed=8)
    assert first.cut_curves != other.cut_curves


def test_missing_percentage_omits_pieces_without_a_grapheme_status(
    tmp_path: Path,
) -> None:
    complete = _generate(tmp_path / "all", missing_fragment_percentage=0)
    partial = _generate(tmp_path / "some", missing_fragment_percentage=0.25)
    assert len(complete.fragments) == 4
    assert len(partial.fragments) == 3
    names = {item.name for item in dataclasses.fields(partial.fragments[0])}
    assert "text_status" not in names
    labels = json.loads((tmp_path / "some" / "labels.json").read_text())
    assert all(label["kind"] != "missing" for label in labels)


def test_labels_are_written_only_under_benchmarks(tmp_path: Path) -> None:
    benchmarks = tmp_path / "benchmarks"
    leaf = _generate(benchmarks, edge_erosion=0.25, lighting_variation=0.4)
    labels_path = benchmarks / "labels.json"
    provenance_path = benchmarks / "provenance.json"
    assert labels_path.is_file()
    assert provenance_path.is_file()
    assert not (tmp_path / "manifest.json").exists()
    assert not (tmp_path / "originals").exists()
    assert not (benchmarks / "originals").exists()
    assert not (benchmarks / "manifest.json").exists()
    stored = labels_path.read_text()
    assert "correct_join" not in stored
    assert "original_text" not in stored
    assert '"truth"' not in stored
    kinds = {label["kind"] for label in json.loads(stored)}
    assert kinds == {"page", "placement", "join"}
    blob = json.loads(leaf.envelope.parameter_blob)
    assert blob == {
        "edge_erosion": 0.25,
        "lighting_variation": 0.4,
        "missing_fragment_percentage": 0.0,
        "rotation": 0.2,
    }
    assert leaf.envelope.parameter_blob == canonical_json(blob)
    assert leaf.envelope.parameter_hash.startswith("sha256:")
    assert leaf.envelope.random_seed == 7
    assert leaf.envelope.model_hash == "absent"
    assert leaf.envelope.decoder_name == "absent"
    assert leaf.envelope.decoder_version == "absent"
    lit = _generate(
        tmp_path / "lit",
        edge_erosion=0.25,
        lighting_variation=0.9,
    )
    assert lit.fragments[0].local_polygon == leaf.fragments[0].local_polygon
    assert lit.envelope.parameter_hash != leaf.envelope.parameter_hash
