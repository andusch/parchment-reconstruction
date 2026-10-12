"""Synthetic millimetre chords and one pixel-frame outline."""

import dataclasses
import inspect
import uuid
from pathlib import Path

import pytest

from prw.edge_chord import (
    ALGORITHM_NAME,
    ALGORITHM_VERSION,
    ChordEdges,
    EdgeChordLog,
    FailedEdgeChord,
)
from prw.frames import CoordinateFrame
from prw.identity import ABSENT, content_id, hash_value
from prw.outlines import FragmentOutlineRevision
from prw.provenance import AlgorithmRun, ProvenanceEnvelope, run_id_inputs

_RECORDED = "2020-01-01T00:00:00Z"
_SQUARE = ((0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0))
_RECTANGLE = ((0.0, 0.0), (4.0, 0.0), (4.0, 1.0), (0.0, 1.0))
_ZERO = ((0.0, 0.0), (3.0, 0.0), (3.0, 0.0), (0.0, 2.0))


def _outline_envelope() -> ProvenanceEnvelope:
    return ProvenanceEnvelope.create(
        source_hashes=(hash_value(b"synthetic-source"),),
        parameters={"pixels_per_mm": 10},
        algorithm_name="caller_supplied_scale",
        algorithm_version="1",
        code_version="outline123",
        decoder_name="tiff",
        decoder_version="1",
    )


def _outline(
    envelope: ProvenanceEnvelope,
    frame: CoordinateFrame,
    polygon: tuple[tuple[float, float], ...],
) -> FragmentOutlineRevision:
    run = AlgorithmRun.create(envelope, status="completed", started_at=_RECORDED)
    return FragmentOutlineRevision.create(
        fragment_id=frame.owner_id,
        frame_id=frame.id,
        polygon=polygon,
        run_id=run.id,
        provenance_id=envelope.id,
    )


def _local(polygon: tuple[tuple[float, float], ...]) -> CoordinateFrame:
    return CoordinateFrame.fragment_local_mm(
        owner_id=uuid.uuid4(),
        establishing_outline_revision_id=uuid.uuid4(),
        polygon=polygon,
    )


def _build(
    log: EdgeChordLog,
    outline: FragmentOutlineRevision,
    frame: CoordinateFrame,
    envelope: ProvenanceEnvelope,
    *,
    minimum: float,
) -> ChordEdges | FailedEdgeChord:
    return log.build(
        outline,
        frame,
        envelope,
        minimum_edge_length_mm=minimum,
        code_version="abc123",
        recorded_at=_RECORDED,
    )


def test_quadrilateral_yields_four_chords_including_the_closing_side() -> None:
    envelope = _outline_envelope()
    frame = _local(_SQUARE)
    outline = _outline(envelope, frame, _SQUARE)
    log = EdgeChordLog()
    result = _build(log, outline, frame, envelope, minimum=2.0)
    assert isinstance(result, ChordEdges)
    assert tuple(edge.geometry for edge in result.edges) == (
        ((0.0, 0.0), (2.0, 0.0)),
        ((2.0, 0.0), (2.0, 2.0)),
        ((2.0, 2.0), (0.0, 2.0)),
        ((0.0, 2.0), (0.0, 0.0)),
    )
    assert [event.status for event in result.proposed] == ["proposed"] * 4
    content = result.run.provenance.content_mapping()
    assert result.run.provenance.algorithm_name == ALGORITHM_NAME
    assert result.run.provenance.algorithm_version == ALGORITHM_VERSION
    assert content["parameter_blob"] == (
        '{"descriptor":"chord","minimum_edge_length_mm":2.0}'
    )
    assert content["parameter_hash"] == hash_value(content["parameter_blob"].encode())
    assert content["parameter_hash"].startswith("sha256:")
    assert content["model_hash"] == ABSENT
    assert "random_seed" not in content
    assert content["source_hashes"] == envelope.source_hashes
    assert content["decoder_name"] == envelope.decoder_name
    assert content["decoder_version"] == envelope.decoder_version
    assert content["code_version"] == "abc123"
    assert result.run.join_ids == ()
    assert "edge_ids" not in {field.name for field in dataclasses.fields(AlgorithmRun)}
    repeated = _build(log, outline, frame, envelope, minimum=2.0)
    assert repeated is result
    fresh = _build(EdgeChordLog(), outline, frame, envelope, minimum=2.0)
    assert isinstance(fresh, ChordEdges)
    assert fresh.run.id == result.run.id
    assert [edge.id for edge in fresh.edges] == [edge.id for edge in result.edges]
    assert repeated.edges[0].id == content_id(
        [result.run.id, outline.id, result.edges[0].geometry]
    )


def test_short_side_and_zero_length_side_are_omitted() -> None:
    envelope = _outline_envelope()
    frame = _local(_RECTANGLE)
    outline = _outline(envelope, frame, _RECTANGLE)
    short = _build(EdgeChordLog(), outline, frame, envelope, minimum=2.0)
    assert isinstance(short, ChordEdges)
    assert tuple(edge.geometry for edge in short.edges) == (
        ((0.0, 0.0), (4.0, 0.0)),
        ((4.0, 1.0), (0.0, 1.0)),
    )
    zero_frame = _local(_ZERO)
    zero_outline = _outline(envelope, zero_frame, _ZERO)
    zero = _build(EdgeChordLog(), zero_outline, zero_frame, envelope, minimum=0.0)
    assert isinstance(zero, ChordEdges)
    assert ((3.0, 0.0), (3.0, 0.0)) not in tuple(edge.geometry for edge in zero.edges)
    assert len(zero.edges) == 3
    with pytest.raises(ValueError, match="minimum_edge_length_mm"):
        _build(EdgeChordLog(), outline, frame, envelope, minimum=-0.1)


def test_empty_completed_run_leaves_the_outline_unchanged() -> None:
    envelope = _outline_envelope()
    frame = _local(_SQUARE)
    outline = _outline(envelope, frame, _SQUARE)
    polygon = outline.polygon
    log = EdgeChordLog()
    result = _build(log, outline, frame, envelope, minimum=10.0)
    assert isinstance(result, ChordEdges)
    assert result.edges == ()
    assert result.proposed == ()
    assert result.run.status == "completed"
    assert result.run.attempt_id is None
    assert result.outline is outline
    assert outline.polygon == polygon == _SQUARE
    assert log.edges == ()
    assert result.run.join_ids == ()


def test_pixel_frame_fails_under_its_own_id() -> None:
    envelope = _outline_envelope()
    pixels = CoordinateFrame.source_pixels(owner_id=uuid.uuid4())
    outline = _outline(envelope, pixels, _SQUARE)
    polygon = outline.polygon
    log = EdgeChordLog()
    failed = _build(log, outline, pixels, envelope, minimum=0.0)
    assert isinstance(failed, FailedEdgeChord)
    assert failed.run.status == "failed"
    assert failed.run.attempt_id is not None
    assert failed.outline is outline
    assert outline.polygon == polygon
    assert log.edges == ()
    completed_same_inputs = content_id(
        run_id_inputs(failed.run.provenance, "completed", None)
    )
    assert failed.run.id != completed_same_inputs
    local = _local(_SQUARE)
    millimetre = _outline(envelope, local, _SQUARE)
    completed = _build(EdgeChordLog(), millimetre, local, envelope, minimum=0.0)
    assert isinstance(completed, ChordEdges)
    assert failed.run.id != completed.run.id
    page = CoordinateFrame.page_global_mm(owner_id=outline.fragment_id)
    page_outline = _outline(envelope, page, _SQUARE)
    page_failed = _build(EdgeChordLog(), page_outline, page, envelope, minimum=0.0)
    assert isinstance(page_failed, FailedEdgeChord)
    assert page_failed.run.attempt_id is not None


def test_module_does_not_reference_labels_json() -> None:
    import prw.edge_chord as edge_chord

    source = Path(inspect.getfile(edge_chord)).read_text(encoding="utf-8")
    assert "labels.json" not in source
    assert "JoinHypothesis" not in source
