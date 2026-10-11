"""Synthetic leaf geometry, fixture rasters, and BenchmarkLabel writes."""

import dataclasses
import json
import math
import struct
from pathlib import Path

import pytest

from prw.identity import canonical_json, content_id, hash_value
from prw.ingest import IntegrityFailure, VerifiedBytes, ingest_bytes
from prw.synthetic_tear import (
    DECODER_NAME,
    DECODER_VERSION,
    PAGE_IMAGE_HEIGHT,
    PAGE_IMAGE_WIDTH,
    TIFF_HEIGHT_OFFSET,
    TIFF_MAGIC,
    TIFF_WIDTH_OFFSET,
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
        images_dir=directory.parent / f"{directory.name}-images",
        missing_fragment_percentage=missing_fragment_percentage,
        edge_erosion=edge_erosion,
        rotation=rotation,
        lighting_variation=lighting_variation,
        random_seed=random_seed,
        code_version="test-code",
    )


def _images(directory: Path) -> Path:
    return directory.parent / f"{directory.name}-images"


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
    cosine = math.cos(0.2)
    sine = math.sin(0.2)
    pairs = zip(fragment.page_polygon, fragment.local_polygon, strict=True)
    for (page_x, page_y), (local_x, local_y) in pairs:
        assert page_x == pytest.approx(local_x * cosine - local_y * sine + centroid_x)
        assert page_y == pytest.approx(local_x * sine + local_y * cosine + centroid_y)
    assert leaf.placements[0].rotation_radians == 0.2
    assert fragment.frame.establishing_outline_revision_id == (
        fragment.outline_revision_id
    )
    assert fragment.outline_revision_id == content_id(
        {"kind": "outline", "local_polygon": fragment.local_polygon}
    )


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


def test_rotation_changes_the_page_raster_and_not_the_local_polygon(
    tmp_path: Path,
) -> None:
    upright = _generate(tmp_path / "upright", rotation=0.0, edge_erosion=0.25)
    turned = _generate(tmp_path / "turned", rotation=0.2, edge_erosion=0.25)
    plain = _generate(tmp_path / "plain", rotation=0.0, edge_erosion=0.0)
    assert upright.fragments[0].local_polygon == turned.fragments[0].local_polygon
    assert upright.fragments[0].page_polygon != turned.fragments[0].page_polygon
    assert plain.fragments[0].local_polygon != upright.fragments[0].local_polygon
    assert upright.fragments[0].outline_revision_id == content_id(
        {"kind": "outline", "local_polygon": upright.fragments[0].local_polygon}
    )
    assert upright.fragments[0].outline_revision_id != content_id(
        {"kind": "outline", "local_polygon": plain.fragments[0].local_polygon}
    )
    upright_page = (_images(tmp_path / "upright") / "page.tif").read_bytes()
    turned_page = (_images(tmp_path / "turned") / "page.tif").read_bytes()
    assert upright_page != turned_page


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
    assert leaf.envelope.decoder_name == DECODER_NAME
    assert leaf.envelope.decoder_version == DECODER_VERSION
    images = _images(benchmarks)
    manifest_text = (images / "image_manifest.json").read_text()
    assert "correct_join" not in manifest_text
    assert "original_text" not in manifest_text
    assert '"truth"' not in manifest_text
    assert not (benchmarks / "page.tif").exists()
    assert not (images / "labels.json").exists()
    lit = _generate(
        tmp_path / "lit",
        edge_erosion=0.25,
        lighting_variation=0.9,
    )
    assert lit.fragments[0].local_polygon == leaf.fragments[0].local_polygon
    assert lit.envelope.parameter_hash != leaf.envelope.parameter_hash
    leaf_page = (_images(benchmarks) / "page.tif").read_bytes()
    lit_page = (_images(tmp_path / "lit") / "page.tif").read_bytes()
    assert leaf_page != lit_page


def _tiff_size(payload: bytes) -> tuple[int, int]:
    assert payload[:4] == TIFF_MAGIC
    width = struct.unpack_from("<I", payload, TIFF_WIDTH_OFFSET)[0]
    height = struct.unpack_from("<I", payload, TIFF_HEIGHT_OFFSET)[0]
    return width, height


def test_same_seed_reproduces_tiff_bytes_and_manifest_digests(tmp_path: Path) -> None:
    first = _generate(tmp_path / "one", lighting_variation=0.4)
    second = _generate(tmp_path / "two", lighting_variation=0.4)
    first_page = (_images(tmp_path / "one") / "page.tif").read_bytes()
    second_page = (_images(tmp_path / "two") / "page.tif").read_bytes()
    assert first_page == second_page
    assert _tiff_size(first_page) == (PAGE_IMAGE_WIDTH, PAGE_IMAGE_HEIGHT)
    assert [image.content_hash for image in first.images] == [
        image.content_hash for image in second.images
    ]
    manifest_path = _images(tmp_path / "one") / "image_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    names = {entry["name"] for entry in manifest["images"]}
    assert names == {image.name for image in first.images}
    for entry in manifest["images"]:
        payload = (_images(tmp_path / "one") / entry["name"]).read_bytes()
        assert entry["content_hash"] == hash_value(payload)
        assert entry["content_hash"].startswith("sha256:")
        assert entry["byte_length"] == len(payload)
        assert _tiff_size(payload) == (entry["width"], entry["height"])
    assert "correct_join" not in json.dumps(manifest)


def test_ingest_accepts_a_generated_tiff_and_rejects_a_tampered_byte(
    tmp_path: Path,
) -> None:
    leaf = _generate(tmp_path / "benchmarks")
    page = next(image for image in leaf.images if image.role == "page")
    payload = bytearray((_images(tmp_path / "benchmarks") / page.name).read_bytes())
    verified = ingest_bytes(payload, expected_hash=page.content_hash)
    assert isinstance(verified, VerifiedBytes)
    assert verified.content_hash == page.content_hash
    payload[-1] ^= 0x01
    failure = ingest_bytes(bytes(payload), expected_hash=page.content_hash)
    assert isinstance(failure, IntegrityFailure)
    assert failure.expected_hash == page.content_hash
    assert failure.presented_hash != page.content_hash


def test_fixture_destination_refuses_a_project_database(tmp_path: Path) -> None:
    project = tmp_path / "project"
    originals = project / "originals"
    originals.mkdir(parents=True)
    (project / "manifest.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="project evidence database"):
        _generate(originals)
    with pytest.raises(ValueError, match="project evidence database"):
        generate_synthetic_leaf(
            project / "benchmarks",
            images_dir=project / "images",
            missing_fragment_percentage=0.0,
            edge_erosion=0.0,
            rotation=0.0,
            lighting_variation=0.0,
            random_seed=1,
            code_version="test-code",
        )
