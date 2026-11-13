"""One-fragment segmentation of synthetic rasters."""

import json
import struct
import uuid
from pathlib import Path

import pytest

from prw.identity import content_id, hash_value
from prw.ingest import IntegrityFailure, UnsupportedMediaType
from prw.lossless_tiff import TiffDecodeFailure
from prw.outlines import FragmentOutlineRevision
from prw.provenance import AlgorithmRun
from prw.segment import (
    FILL_WITHOUT_4_INTERIOR,
    NOT_ABOVE_FRAME_SPLIT,
    FailedSegmentation,
    SegmentationLog,
    SegmentedOutline,
)
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
    treatment: str | None = None,
    mount: str | None = None,
) -> object:
    return log.segment(
        payload,
        project_id=uuid.uuid4() if project_id is None else project_id,
        label=label,
        foreground_threshold=threshold,
        code_version="test-code",
        recorded_at=recorded_at,
        expected_hash=expected_hash,
        enclosed_background_treatment=treatment,
        border_mount_treatment=mount,
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
    struct.pack_into("<H", compressed, TIFF_WIDTH_OFFSET + 3 * 12, 7)
    layout = _segment(log, compressed)
    assert isinstance(layout, TiffDecodeFailure)
    assert layout.kind == "jpeg_compression"
    assert not hasattr(layout, "polygon")
    assert not isinstance(layout, FragmentOutlineRevision)
    assert log.runs == ()
    stored = bytes(compressed)
    value_at = TIFF_WIDTH_OFFSET + 3 * 12
    assert stored[value_at : value_at + 2] == struct.pack("<H", 7)

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


def _block(
    width: int,
    height: int,
    *,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    missing: set[tuple[int, int]] | None = None,
) -> bytes:
    foreground = {
        (x_coord, y_coord)
        for x_coord in range(x0, x1 + 1)
        for y_coord in range(y0, y1 + 1)
    }
    if missing:
        foreground -= missing
    return _raster(width, height, foreground)


def test_omitted_treatment_still_fails_a_one_pixel_hole() -> None:
    payload = _block(7, 7, x0=1, y0=1, x1=5, y1=5, missing={(3, 3)})
    failed = _segment(SegmentationLog(), payload)
    assert isinstance(failed, FailedSegmentation)
    assert failed.kind == "hole"
    assert json.loads(failed.run.provenance.parameter_blob) == {
        "foreground_threshold": 1
    }


def test_fill_without_4_interior_closes_a_speckle_and_records_the_rule() -> None:
    payload = _block(7, 7, x0=1, y0=1, x1=5, y1=5, missing={(3, 3)})
    solid = _block(7, 7, x0=1, y0=1, x1=5, y1=5)
    opened = _segment(SegmentationLog(), payload, treatment=FILL_WITHOUT_4_INTERIOR)
    untreated = _segment(SegmentationLog(), solid)
    assert isinstance(opened, SegmentedOutline)
    assert isinstance(untreated, SegmentedOutline)
    assert opened.outline.polygon == untreated.outline.polygon
    assert opened.outline.epistemic_class == "interpretation"
    assert opened.outline.producer == "machine"
    blob = json.loads(opened.run.provenance.parameter_blob)
    assert blob == {
        "enclosed_background_treatment": "fill_without_4_interior",
        "foreground_threshold": 1,
    }
    assert opened.run.provenance.algorithm_version == "1"
    assert opened.run.provenance.model_hash == "absent"
    assert "random_seed" not in opened.run.provenance.content_mapping()
    assert "pixels_per_mm" not in blob


def test_fill_closes_a_crack_longer_than_eleven_pixels() -> None:
    missing = {(x_coord, 3) for x_coord in range(2, 22)}
    assert len(missing) == 20
    payload = _block(24, 7, x0=1, y0=1, x1=22, y1=5, missing=missing)
    solid = _block(24, 7, x0=1, y0=1, x1=22, y1=5)
    opened = _segment(SegmentationLog(), payload, treatment=FILL_WITHOUT_4_INTERIOR)
    baseline = _segment(SegmentationLog(), solid)
    assert isinstance(opened, SegmentedOutline)
    assert isinstance(baseline, SegmentedOutline)
    assert (
        opened.outline.polygon
        == baseline.outline.polygon
        == (
            (1.0, 1.0),
            (22.0, 1.0),
            (22.0, 5.0),
            (1.0, 5.0),
        )
    )


def test_a_hole_with_a_4_interior_still_fails_when_the_treatment_is_on() -> None:
    center = {(4, 4), (4, 3), (4, 5), (3, 4), (5, 4)}
    payload = _block(9, 9, x0=1, y0=1, x1=7, y1=7, missing=center)
    failed = _segment(SegmentationLog(), payload, treatment=FILL_WITHOUT_4_INTERIOR)
    assert isinstance(failed, FailedSegmentation)
    assert failed.kind == "hole"
    assert not hasattr(failed, "polygon")
    blob = json.loads(failed.run.provenance.parameter_blob)
    assert blob["enclosed_background_treatment"] == "fill_without_4_interior"


def test_treatment_does_not_fill_a_border_inlet_or_merge_components() -> None:
    inlet = _block(
        8,
        8,
        x0=1,
        y0=1,
        x1=6,
        y1=6,
        missing={(3, 0), (3, 1), (3, 2)},
    )
    # (3, 0) is outside the block, so the inlet from the top edge is (3, 1), (3, 2).
    treated = _segment(SegmentationLog(), inlet, treatment=FILL_WITHOUT_4_INTERIOR)
    plain = _segment(SegmentationLog(), inlet)
    assert isinstance(treated, SegmentedOutline)
    assert isinstance(plain, SegmentedOutline)
    assert treated.outline.polygon == plain.outline.polygon

    split = _raster(
        6,
        4,
        {(0, 0), (1, 0), (0, 1), (1, 1), (4, 0), (5, 0), (4, 1), (5, 1)},
    )
    failed = _segment(SegmentationLog(), split, treatment=FILL_WITHOUT_4_INTERIOR)
    assert isinstance(failed, FailedSegmentation)
    assert failed.kind == "multiple_components"
    assert not hasattr(failed, "polygon")


def _mounted(
    width: int,
    height: int,
    *,
    mount: int,
    piece: set[tuple[int, int]],
    piece_level: int,
    zeros: set[tuple[int, int]] | None = None,
) -> bytes:
    samples = bytearray(width * height)
    for index in range(width * height):
        samples[index] = mount
    for x_coord, y_coord in piece:
        samples[y_coord * width + x_coord] = piece_level
    if zeros:
        for x_coord, y_coord in zeros:
            samples[y_coord * width + x_coord] = 0
    return _uncompressed_grayscale_tiff(width, height, bytes(samples))


def _rectangle_pixels(x0: int, y0: int, x1: int, y1: int) -> set[tuple[int, int]]:
    return {
        (x_coord, y_coord)
        for x_coord in range(x0, x1 + 1)
        for y_coord in range(y0, y1 + 1)
    }


def test_border_mount_treatment_follows_the_lighter_interior() -> None:
    piece = _rectangle_pixels(2, 2, 6, 6)
    payload = _mounted(9, 9, mount=20, piece=piece, piece_level=180)
    treated = _segment(SegmentationLog(), payload, mount=NOT_ABOVE_FRAME_SPLIT)
    plain = _segment(SegmentationLog(), payload)
    assert isinstance(treated, SegmentedOutline)
    assert isinstance(plain, SegmentedOutline)
    assert treated.outline.polygon == (
        (2.0, 2.0),
        (6.0, 2.0),
        (6.0, 6.0),
        (2.0, 6.0),
    )
    assert plain.outline.polygon == (
        (0.0, 0.0),
        (8.0, 0.0),
        (8.0, 8.0),
        (0.0, 8.0),
    )
    assert (0.0, 0.0) not in treated.outline.polygon
    assert (8.0, 8.0) not in treated.outline.polygon
    assert treated.outline.epistemic_class == "interpretation"
    assert treated.outline.producer == "machine"
    blob = json.loads(treated.run.provenance.parameter_blob)
    assert blob == {
        "border_mount_treatment": "not_above_frame_split",
        "foreground_threshold": 1,
    }
    assert "enclosed_background_treatment" not in blob
    assert treated.run.provenance.parameter_hash == hash_value(
        treated.run.provenance.parameter_blob.encode()
    )
    assert treated.run.provenance.algorithm_version == "1"
    assert treated.run.provenance.model_hash == "absent"
    assert "random_seed" not in treated.run.provenance.content_mapping()
    assert json.loads(plain.run.provenance.parameter_blob) == {
        "foreground_threshold": 1
    }


def test_mount_and_fill_compose_only_when_both_are_named() -> None:
    piece = _rectangle_pixels(2, 2, 8, 5)
    zeros = {(4, 3), (5, 3), (6, 3)}
    payload = _mounted(11, 8, mount=20, piece=piece, piece_level=180, zeros=zeros)
    solid = _mounted(11, 8, mount=20, piece=piece, piece_level=180)
    both = _segment(
        SegmentationLog(),
        payload,
        mount=NOT_ABOVE_FRAME_SPLIT,
        treatment=FILL_WITHOUT_4_INTERIOR,
    )
    mount_only = _segment(SegmentationLog(), payload, mount=NOT_ABOVE_FRAME_SPLIT)
    fill_only = _segment(SegmentationLog(), payload, treatment=FILL_WITHOUT_4_INTERIOR)
    baseline = _segment(SegmentationLog(), solid, mount=NOT_ABOVE_FRAME_SPLIT)
    assert isinstance(both, SegmentedOutline)
    assert isinstance(baseline, SegmentedOutline)
    assert isinstance(mount_only, FailedSegmentation)
    assert mount_only.kind == "hole"
    assert isinstance(fill_only, SegmentedOutline)
    assert (
        both.outline.polygon
        == baseline.outline.polygon
        == (
            (2.0, 2.0),
            (8.0, 2.0),
            (8.0, 5.0),
            (2.0, 5.0),
        )
    )
    assert fill_only.outline.polygon[0] == (0.0, 0.0)
    assert (10.0, 7.0) in fill_only.outline.polygon
    assert json.loads(both.run.provenance.parameter_blob) == {
        "border_mount_treatment": "not_above_frame_split",
        "enclosed_background_treatment": "fill_without_4_interior",
        "foreground_threshold": 1,
    }
    mount_blob = json.loads(mount_only.run.provenance.parameter_blob)
    assert "enclosed_background_treatment" not in mount_blob
    fill_blob = json.loads(fill_only.run.provenance.parameter_blob)
    assert "border_mount_treatment" not in fill_blob


def test_a_4_interior_hole_still_fails_when_the_mount_treatment_is_on() -> None:
    piece = _rectangle_pixels(1, 1, 7, 7)
    center = {(4, 4), (4, 3), (4, 5), (3, 4), (5, 4)}
    payload = _mounted(9, 9, mount=20, piece=piece, piece_level=180, zeros=center)
    failed = _segment(
        SegmentationLog(),
        payload,
        mount=NOT_ABOVE_FRAME_SPLIT,
        treatment=FILL_WITHOUT_4_INTERIOR,
    )
    assert isinstance(failed, FailedSegmentation)
    assert failed.kind == "hole"
    assert not hasattr(failed, "polygon")


def test_mount_treatment_keeps_a_bright_edge_and_a_second_component() -> None:
    # The cutting meets the bottom edge. The dark frame does not.
    piece = _rectangle_pixels(2, 2, 7, 7)
    payload = _mounted(10, 8, mount=30, piece=piece, piece_level=180)
    treated = _segment(SegmentationLog(), payload, mount=NOT_ABOVE_FRAME_SPLIT)
    assert isinstance(treated, SegmentedOutline)
    assert treated.outline.polygon == (
        (2.0, 2.0),
        (7.0, 2.0),
        (7.0, 7.0),
        (2.0, 7.0),
    )
    assert (0.0, 0.0) not in treated.outline.polygon
    assert (9.0, 7.0) not in treated.outline.polygon
    assert (2.0, 7.0) in treated.outline.polygon

    speck = set(piece)
    speck.add((1, 1))
    split = _mounted(9, 9, mount=20, piece=speck, piece_level=180)
    failed = _segment(SegmentationLog(), split, mount=NOT_ABOVE_FRAME_SPLIT)
    assert isinstance(failed, FailedSegmentation)
    assert failed.kind == "multiple_components"
    assert not hasattr(failed, "polygon")


def test_unknown_mount_treatment_is_rejected() -> None:
    payload = _mounted(
        7, 7, mount=20, piece=_rectangle_pixels(2, 2, 4, 4), piece_level=180
    )
    with pytest.raises(ValueError, match="not_above_frame_split"):
        _segment(SegmentationLog(), payload, mount="ceiling_46")


def test_unknown_treatment_is_rejected_and_the_default_polygon_is_unchanged() -> None:
    payload = _rectangle()
    with pytest.raises(ValueError, match="fill_without_4_interior"):
        _segment(SegmentationLog(), payload, treatment="area_at_most_11")
    baseline = _segment(SegmentationLog(), payload)
    treated = _segment(SegmentationLog(), payload, treatment=FILL_WITHOUT_4_INTERIOR)
    assert isinstance(baseline, SegmentedOutline)
    assert isinstance(treated, SegmentedOutline)
    assert treated.outline.polygon == baseline.outline.polygon
    assert json.loads(baseline.run.provenance.parameter_blob) == {
        "foreground_threshold": 1
    }
