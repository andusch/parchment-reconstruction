"""One-fragment segmentation of synthetic rasters."""

import json
import struct
import uuid
from pathlib import Path

from prw.fixture_tiff import UnsupportedFixtureLayout
from prw.identity import content_id, hash_value
from prw.ingest import IntegrityFailure, UnsupportedMediaType
from prw.outlines import FragmentOutlineRevision
from prw.provenance import AlgorithmRun
from prw.segment import FailedSegmentation, SegmentationLog, SegmentedOutline
from prw.synthetic_tear import (
    DECODER_NAME,
    DECODER_VERSION,
    TIFF_WIDTH_OFFSET,
    _uncompressed_grayscale_tiff,
    generate_synthetic_leaf,
)

_RECORDED = "2020-01-01T00:00:00Z"
_LATER = "2024-06-01T12:00:00Z"


def _raster(
    width: int,
    height: int,
    foreground: set[tuple[int, int]],
    *,
    level: int = 255,
) -> bytes:
    samples = bytearray(width * height)
    for x_coord, y_coord in foreground:
        samples[y_coord * width + x_coord] = level
    return _uncompressed_grayscale_tiff(width, height, bytes(samples))


def _rectangle() -> bytes:
    foreground = {
        (x_coord, y_coord) for x_coord in range(1, 5) for y_coord in range(2, 5)
    }
    return _raster(8, 8, foreground)


def _segment(
    log: SegmentationLog,
    payload: bytes | bytearray,
    *,
    label: str = "shelf-4",
    threshold: int = 1,
    expected_hash: str | None = None,
    recorded_at: str = _RECORDED,
    project_id: uuid.UUID | None = None,
) -> object:
    return log.segment(
        payload,
        project_id=uuid.uuid4() if project_id is None else project_id,
        label=label,
        foreground_threshold=threshold,
        code_version="test-code",
        recorded_at=recorded_at,
        expected_hash=expected_hash,
    )


def test_one_component_is_a_source_pixel_outline_and_repeats() -> None:
    payload = _rectangle()
    project_id = uuid.uuid4()
    log = SegmentationLog()
    first = _segment(
        log,
        payload,
        project_id=project_id,
        expected_hash=hash_value(payload),
    )
    assert isinstance(first, SegmentedOutline)
    assert first.outline.epistemic_class == "interpretation"
    assert first.outline.producer == "machine"
    assert first.frame.kind == "source_pixels"
    assert first.proposed.status == "proposed"
    assert first.outline.polygon == (
        (1.0, 2.0),
        (4.0, 2.0),
        (4.0, 4.0),
        (1.0, 4.0),
    )
    assert first.outline.polygon[0] == (1.0, 2.0)
    envelope = first.run.provenance
    assert json.loads(envelope.parameter_blob) == {"foreground_threshold": 1}
    assert envelope.parameter_hash == hash_value(envelope.parameter_blob.encode())
    assert envelope.parameter_hash.startswith("sha256:")
    assert envelope.algorithm_name == "fragment_outline"
    assert envelope.algorithm_version == "1"
    assert envelope.model_hash == "absent"
    assert "random_seed" not in envelope.content_mapping()
    assert envelope.decoder_name == DECODER_NAME == "synthetic_uncompressed_tiff"
    assert envelope.decoder_version == DECODER_VERSION == "1"
    assert envelope.source_hashes == (hash_value(payload),)
    assert first.run.attempt_id is None
    assert first.run.join_ids == ()
    assert not hasattr(first.run, "outline_ids")
    assert first.fragment.id == content_id([project_id, "shelf-4"])
    assert first.fragment.label == "shelf-4"

    second = _segment(
        log,
        payload,
        project_id=project_id,
        recorded_at=_LATER,
        expected_hash=hash_value(payload),
    )
    assert second is first
    assert log.outlines == (first.outline,)
    assert log.runs == (first.run,)
    assert first.outline.id == content_id([first.run.id, first.outline.polygon])


def test_empty_split_and_hole_fail_without_a_polygon() -> None:
    cases = {
        "no_foreground": _raster(4, 4, set()),
        "multiple_components": _raster(
            6,
            4,
            {(0, 0), (1, 0), (0, 1), (1, 1), (4, 0), (5, 0), (4, 1), (5, 1)},
        ),
        "hole": _raster(
            7,
            7,
            {(x_coord, y_coord) for x_coord in range(1, 6) for y_coord in range(1, 6)}
            - {(3, 3)},
        ),
    }
    for kind, payload in cases.items():
        log = SegmentationLog()
        failed = _segment(log, payload)
        assert isinstance(failed, FailedSegmentation)
        assert failed.kind == kind
        assert not isinstance(failed, FragmentOutlineRevision)
        assert not hasattr(failed, "polygon")
        assert log.outlines == ()
        completed = AlgorithmRun.create(
            failed.run.provenance,
            status="completed",
            started_at=_RECORDED,
        )
        assert failed.run.id != completed.id
        assert failed.run.attempt_id is not None
        assert failed.run.status == "failed"


def test_checksum_and_layout_failures_leave_the_bytes_and_skip_the_run() -> None:
    payload = bytearray(_rectangle())
    before = bytes(payload)
    log = SegmentationLog()
    mismatch = _segment(log, payload, expected_hash=hash_value(b"other-bytes"))
    assert isinstance(mismatch, IntegrityFailure)
    assert not isinstance(mismatch, FragmentOutlineRevision)
    assert bytes(payload) == before
    assert log.runs == ()
    assert log.outlines == ()

    compressed = bytearray(before)
    struct.pack_into("<H", compressed, TIFF_WIDTH_OFFSET + 3 * 12, 5)
    layout = _segment(log, compressed)
    assert isinstance(layout, UnsupportedFixtureLayout)
    assert layout.kind == "compressed_strip"
    assert not hasattr(layout, "polygon")
    assert log.runs == ()

    media = _segment(log, b"not-a-tiff")
    assert isinstance(media, UnsupportedMediaType)
    assert log.outlines == ()


def test_page_mosaic_fails_and_the_label_is_not_the_manifest_id(tmp_path: Path) -> None:
    images = tmp_path / "images"
    generate_synthetic_leaf(
        tmp_path / "benchmarks",
        images_dir=images,
        missing_fragment_percentage=0.0,
        edge_erosion=0.25,
        rotation=0.0,
        lighting_variation=0.0,
        random_seed=7,
        code_version="test-code",
    )
    page = _segment(SegmentationLog(), (images / "page.tif").read_bytes())
    assert isinstance(page, FailedSegmentation)
    assert page.kind == "multiple_components"
    assert not hasattr(page, "group_scan")
    assert not hasattr(page, "polygon")

    manifest = json.loads((images / "image_manifest.json").read_text())
    entry = next(item for item in manifest["images"] if item["role"] == "fragment")
    project_id = uuid.uuid4()
    log = SegmentationLog()
    segmented = _segment(
        log,
        (images / entry["name"]).read_bytes(),
        project_id=project_id,
        label="caller-label",
    )
    assert isinstance(segmented, SegmentedOutline)
    assert segmented.fragment.label == "caller-label"
    assert segmented.fragment.id == content_id([project_id, "caller-label"])
    assert str(segmented.fragment.id) != entry["fragment_id"]
    assert log.outlines == (segmented.outline,)
