"""Caller-supplied scale into fragment_local_mm."""

import dataclasses
import json
import uuid
from pathlib import Path

import prw.scale as scale_module
from prw.frames import (
    AXIS_X_RIGHT,
    AXIS_Y_DOWN,
    CoordinateFrame,
    polygon_centroid,
)
from prw.identity import hash_value
from prw.outlines import Fragment, FragmentOutlineRevision
from prw.provenance import AlgorithmRun, ProvenanceEnvelope
from prw.scale import (
    PIXEL_CENTER,
    CallerScale,
    ScaledOutline,
    ScaleLog,
    UnscaledOutline,
)
from prw.segment import SegmentationLog, SegmentedOutline
from prw.synthetic_tear import _uncompressed_grayscale_tiff

_RECORDED = "2020-01-01T00:00:00Z"
_SQUARE = ((0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0))
_LARGER = ((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0))


def _pixel_outline(
    polygon: tuple[tuple[float, float], ...],
    *,
    frame: CoordinateFrame | None = None,
) -> tuple[FragmentOutlineRevision, CoordinateFrame]:
    source = uuid.uuid4()
    pixel_frame = frame or CoordinateFrame.source_pixels(owner_id=source)
    fragment = Fragment.create(project_id=uuid.uuid4(), label="shelf-4")
    envelope = ProvenanceEnvelope.create(
        source_hashes=(hash_value(b"synthetic-source"),),
        parameters={"foreground_threshold": 1},
        algorithm_name="fragment_outline",
        algorithm_version="1",
        code_version="test-code",
        decoder_name="synthetic_uncompressed_tiff",
        decoder_version="1",
    )
    run = AlgorithmRun.create(envelope, status="completed", started_at=_RECORDED)
    outline = FragmentOutlineRevision.create(
        fragment_id=fragment.id,
        frame_id=pixel_frame.id,
        polygon=polygon,
        run_id=run.id,
        provenance_id=envelope.id,
    )
    return outline, pixel_frame


def _apply(
    log: ScaleLog,
    outline: FragmentOutlineRevision,
    frame: CoordinateFrame,
    scale: CallerScale | None,
) -> UnscaledOutline | ScaledOutline:
    return log.apply(
        outline,
        frame,
        scale,
        source_hashes=(hash_value(b"synthetic-source"),),
        code_version="test-code",
        decoder_name="synthetic_uncompressed_tiff",
        decoder_version="1",
        recorded_at=_RECORDED,
    )


def test_supplied_scale_centers_the_local_polygon_and_keeps_the_pixel_row() -> None:
    outline, frame = _pixel_outline(_SQUARE)
    before = outline.polygon
    log = ScaleLog()
    scaled = _apply(
        log,
        outline,
        frame,
        CallerScale(pixels_per_mm=2, uncertainty=0.25, producer="human"),
    )
    assert isinstance(scaled, ScaledOutline)
    assert scaled.pixel_outline is outline
    assert outline.polygon == before
    assert log.outlines[0] is outline
    assert scaled.outline.epistemic_class == "interpretation"
    assert scaled.outline.producer == "machine"
    assert scaled.outline.supersedes_id == outline.id
    assert scaled.observation.epistemic_class == "observed"
    assert scaled.transform.epistemic_class == "observed"
    assert scaled.observation.provenance_id is None
    assert "provenance_id" not in scaled.observation.content_mapping()
    assert scaled.observation.evidence_description == "caller-supplied measurement"
    assert scaled.observation.pixels_per_mm == 2
    assert scaled.observation.uncertainty == 0.25
    assert scaled.transform.uniform_scale == 2
    assert scaled.transform.rotation_radians == 0.0
    assert scaled.transform.translation_x == -0.75
    assert scaled.transform.translation_y == -0.75
    assert scaled.transform.from_frame_id == frame.id
    assert scaled.transform.to_frame_id == scaled.frame.id
    assert scaled.frame.kind == "fragment_local_mm"
    assert scaled.frame.axis_x_direction == AXIS_X_RIGHT
    assert scaled.frame.axis_y_direction == AXIS_Y_DOWN
    assert scaled.frame.establishing_outline_revision_id == scaled.outline.id
    assert scaled.outline.polygon == (
        (-0.5, -0.5),
        (0.5, -0.5),
        (0.5, 0.5),
        (-0.5, 0.5),
    )
    assert polygon_centroid(scaled.outline.polygon) == scaled.frame.origin
    assert scaled.frame.origin == (0.0, 0.0)
    envelope = scaled.run.provenance
    assert json.loads(envelope.parameter_blob) == {
        "pixel_center": [PIXEL_CENTER[0], PIXEL_CENTER[1]],
        "pixels_per_mm": 2.0,
        "uncertainty": 0.25,
    }
    assert envelope.parameter_hash.startswith("sha256:")
    assert envelope.model_hash == "absent"
    assert "random_seed" not in envelope.content_mapping()
    assert scaled.proposed.status == "proposed"
    assert scaled.run.attempt_id is None
    assert not hasattr(scaled.run, "outline_ids")

    repeated = _apply(
        log,
        outline,
        frame,
        CallerScale(pixels_per_mm=2, uncertainty=0.25, producer="human"),
    )
    assert repeated is scaled
    assert len(log.runs) == 1
    assert [row.id for row in log.outlines] == [outline.id, scaled.outline.id]


def test_a_later_polygon_does_not_move_the_origin() -> None:
    first, frame = _pixel_outline(_SQUARE)
    log = ScaleLog()
    scaled = _apply(
        log,
        first,
        frame,
        CallerScale(pixels_per_mm=2, uncertainty=0, producer="human"),
    )
    assert isinstance(scaled, ScaledOutline)
    donor, _frame = _pixel_outline(_LARGER, frame=frame)
    later_pixel = FragmentOutlineRevision.create(
        fragment_id=first.fragment_id,
        frame_id=frame.id,
        polygon=_LARGER,
        run_id=donor.run_id,
        provenance_id=donor.provenance_id,
    )
    placed = log.place_later(later_pixel, scaled, recorded_at=_RECORDED)
    assert placed.frame is scaled.frame
    assert placed.frame.id == scaled.frame.id
    assert placed.frame.origin == scaled.frame.origin
    assert placed.frame.establishing_outline_revision_id == scaled.outline.id
    assert placed.outline.polygon == (
        (-0.5, -0.5),
        (1.5, -0.5),
        (1.5, 1.5),
        (-0.5, 1.5),
    )
    assert polygon_centroid(placed.outline.polygon) != scaled.frame.origin
    assert placed.outline.supersedes_id == later_pixel.id
    assert log.outlines[0].polygon == _SQUARE


def test_machine_calibration_stores_provenance() -> None:
    outline, frame = _pixel_outline(_SQUARE)
    scaled = _apply(
        ScaleLog(),
        outline,
        frame,
        CallerScale(pixels_per_mm=2, uncertainty=0.1, producer="machine"),
    )
    assert isinstance(scaled, ScaledOutline)
    assert scaled.observation.provenance_id == scaled.run.provenance_id
    assert scaled.outline.provenance_id == scaled.run.provenance_id
    assert scaled.outline.epistemic_class == "interpretation"


def test_absent_scale_leaves_source_pixels() -> None:
    outline, frame = _pixel_outline(_SQUARE)
    log = ScaleLog()
    kept = log.apply(outline, frame, None)
    assert isinstance(kept, UnscaledOutline)
    assert kept.outline is outline
    assert frame.kind == "source_pixels"
    assert outline.polygon == _SQUARE
    names = {field.name for field in dataclasses.fields(kept)}
    assert names == {"outline"}
    assert log.outlines == ()
    assert log.runs == ()


def test_segmented_outline_uses_the_caller_scale_not_a_header() -> None:
    samples = bytearray(8 * 8)
    for y_coord in range(2, 6):
        for x_coord in range(1, 5):
            samples[y_coord * 8 + x_coord] = 255
    payload = _uncompressed_grayscale_tiff(8, 8, bytes(samples))
    segmented = SegmentationLog().segment(
        payload,
        project_id=uuid.uuid4(),
        label="caller-label",
        foreground_threshold=1,
        code_version="test-code",
        recorded_at=_RECORDED,
    )
    assert isinstance(segmented, SegmentedOutline)
    pixel_polygon = segmented.outline.polygon
    scaled = ScaleLog().apply(
        segmented.outline,
        segmented.frame,
        CallerScale(pixels_per_mm=4, uncertainty=0.2, producer="human"),
        source_hashes=segmented.run.provenance.source_hashes,
        code_version="test-code",
        decoder_name=segmented.run.provenance.decoder_name,
        decoder_version=segmented.run.provenance.decoder_version,
        recorded_at=_RECORDED,
    )
    assert isinstance(scaled, ScaledOutline)
    assert segmented.outline.polygon == pixel_polygon
    assert segmented.frame.kind == "source_pixels"
    assert polygon_centroid(scaled.outline.polygon) == scaled.frame.origin
    assert scaled.observation.pixels_per_mm == 4
    source = Path(scale_module.__file__ or "").read_text()
    assert "MILLIMETRES_PER_PIXEL" not in source
