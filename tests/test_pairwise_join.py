"""Synthetic millimetre chords and in-memory fragment admissions."""

import inspect
import json
import math
import uuid
from pathlib import Path

from prw.frames import CoordinateFrame
from prw.identity import ABSENT, content_id, hash_value
from prw.joins import EdgeArc
from prw.outlines import Fragment, FragmentOutlineRevision
from prw.pairwise_join import (
    ALGORITHM_NAME,
    ALGORITHM_VERSION,
    SCORE_NAME,
    FailedPairwiseJoin,
    FragmentChords,
    PairwiseJoinLog,
    PairwiseJoins,
)
from prw.provenance import AlgorithmRun, ProvenanceEnvelope, run_id_inputs
from prw.scale import CalibrationObservation, CalibrationTransform

_RECORDED = "2020-01-01T00:00:00Z"
_CODE = "abc123"
type Point = tuple[float, float]
type Chord = tuple[Point, Point]


def _edge_envelope(digest: bytes, *, decoder_version: str = "1") -> ProvenanceEnvelope:
    return ProvenanceEnvelope.create(
        source_hashes=(hash_value(digest),),
        parameters={"descriptor": "chord", "minimum_edge_length_mm": 0.0},
        algorithm_name="edge_chord",
        algorithm_version="1",
        code_version="edge123",
        decoder_name="tiff",
        decoder_version=decoder_version,
    )


def _fragment(project_id: uuid.UUID, label: str, status: str) -> Fragment:
    if status == "catalogued":
        return Fragment.catalogued(project_id=project_id, label=label)
    if status == "confirmed":
        return Fragment.create(project_id=project_id, label=label).confirm()
    if status == "detected":
        return Fragment.create(project_id=project_id, label=label)
    raise AssertionError(status)


def _span(chord: Chord) -> tuple[Point, ...]:
    start, end = chord
    return (
        start,
        end,
        (start[0] + end[1] - start[1], start[1] + start[0] - end[0]),
    )


def _frame(fragment: Fragment, polygon: tuple[Point, ...]) -> CoordinateFrame:
    return CoordinateFrame.fragment_local_mm(
        owner_id=fragment.id,
        establishing_outline_revision_id=uuid.uuid4(),
        polygon=polygon,
    )


def _edge(
    fragment: Fragment,
    frame: CoordinateFrame,
    envelope: ProvenanceEnvelope,
    chord: Chord,
) -> EdgeArc:
    outline_run = AlgorithmRun.create(
        envelope, status="completed", started_at=_RECORDED
    )
    outline = FragmentOutlineRevision.create(
        fragment_id=fragment.id,
        frame_id=frame.id,
        polygon=(chord[0], chord[1], (chord[0][0], chord[1][1] + 1.0)),
        run_id=outline_run.id,
        provenance_id=envelope.id,
    )
    edge_run = AlgorithmRun.create(envelope, status="completed", started_at=_RECORDED)
    return EdgeArc.create(
        outline_revision_id=outline.id,
        frame=frame,
        geometry=chord,
        run_id=edge_run.id,
        provenance_id=envelope.id,
    )


def _calibration(
    frame: CoordinateFrame,
) -> tuple[CalibrationObservation, CalibrationTransform]:
    source_id = uuid.uuid4()
    pixels = CoordinateFrame.source_pixels(owner_id=source_id)
    transform = CalibrationTransform.create(
        source_image_id=source_id,
        from_frame_id=pixels.id,
        to_frame_id=frame.id,
        translation_x=0.0,
        translation_y=0.0,
        uniform_scale=10.0,
        producer="human",
    )
    observation = CalibrationObservation.create(
        source_image_id=source_id,
        producer="human",
        pixels_per_mm=10.0,
        uncertainty=0.1,
        frame_id=pixels.id,
        transform_id=transform.id,
        provenance_id=None,
    )
    return observation, transform


def _chords(
    fragment: Fragment,
    envelope: ProvenanceEnvelope,
    chords: tuple[Chord, ...],
    *,
    calibrate: bool,
    frame: CoordinateFrame | None = None,
) -> FragmentChords:
    polygon = _span(chords[0]) if chords else ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0))
    local = frame if frame is not None else _frame(fragment, polygon)
    edges = (
        tuple(_edge(fragment, local, envelope, chord) for chord in chords)
        if local.kind == "fragment_local_mm"
        else ()
    )
    observation: CalibrationObservation | None = None
    transform: CalibrationTransform | None = None
    if calibrate:
        if local.kind != "fragment_local_mm":
            raise AssertionError("Calibration cites a millimetre frame.")
        observation, transform = _calibration(local)
    return FragmentChords(
        fragment=fragment,
        frame=local,
        edges=edges,
        envelope=envelope,
        observation=observation,
        transform=transform,
    )


def _propose(
    log: PairwiseJoinLog,
    pool: tuple[FragmentChords, ...],
) -> PairwiseJoins | FailedPairwiseJoin:
    return log.propose(pool, code_version=_CODE, recorded_at=_RECORDED)


def _apply(rotation: float, translation: Point, point: Point) -> Point:
    cosine = math.cos(rotation)
    sine = math.sin(rotation)
    return (
        cosine * point[0] - sine * point[1] + translation[0],
        sine * point[0] + cosine * point[1] + translation[1],
    )


def _close(left: Point, right: Point) -> bool:
    return math.isclose(left[0], right[0]) and math.isclose(left[1], right[1])


def test_detected_fragment_is_unpaired_and_one_pair_stays_one_pair() -> None:
    project_id = uuid.uuid4()
    catalogued = _fragment(project_id, "piece-a", "catalogued")
    confirmed = _fragment(project_id, "piece-b", "confirmed")
    detected = _fragment(project_id, "piece-c", "detected")
    left = _chords(
        catalogued,
        _edge_envelope(b"source-a"),
        (((0.0, 0.0), (4.0, 0.0)), ((0.0, 0.0), (0.0, 1.0))),
        calibrate=True,
    )
    right = _chords(
        confirmed,
        _edge_envelope(b"source-b"),
        (((1.0, 1.0), (1.0, 3.0)),),
        calibrate=True,
    )
    skipped = _chords(
        detected,
        _edge_envelope(b"source-c"),
        (((0.0, 0.0), (9.0, 0.0)),),
        calibrate=False,
    )
    result = _propose(PairwiseJoinLog(), (left, right, skipped))
    assert isinstance(result, PairwiseJoins)
    admitted = {catalogued.id, confirmed.id}
    assert len(result.joins) == 4
    for join in result.joins:
        assert {join.fragment_a_id, join.fragment_b_id} == admitted
        assert join.fragment_a_id != join.fragment_b_id
        assert join.edge_a_id != skipped.edges[0].id
        assert join.edge_b_id != skipped.edges[0].id
    lesser = min(admitted, key=str)
    assert {join.fragment_a_id for join in result.joins} == {lesser}


def test_single_admitted_fragment_completes_with_no_joins() -> None:
    project_id = uuid.uuid4()
    fragment = _fragment(project_id, "only", "catalogued")
    detected = _fragment(project_id, "skip", "detected")
    alone = _chords(
        fragment,
        _edge_envelope(b"only-source"),
        (((0.0, 0.0), (2.0, 0.0)),),
        calibrate=True,
    )
    skipped = _chords(
        detected,
        _edge_envelope(b"skip-source"),
        (((0.0, 0.0), (2.0, 0.0)),),
        calibrate=False,
    )
    log = PairwiseJoinLog()
    result = _propose(log, (alone, skipped))
    assert isinstance(result, PairwiseJoins)
    assert result.joins == ()
    assert result.transforms == ()
    assert result.proposed == ()
    assert result.run.status == "completed"
    assert result.run.attempt_id is None
    assert result.run.join_ids == ()
    assert log.joins == ()
    repeated = _propose(log, (alone,))
    assert repeated is result


def test_one_edge_pair_yields_two_poses_and_one_length_score() -> None:
    project_id = uuid.uuid4()
    first = _fragment(project_id, "alpha", "catalogued")
    second = _fragment(project_id, "beta", "confirmed")
    chord_a: Chord = ((0.0, 0.0), (4.0, 0.0))
    chord_b: Chord = ((0.0, 0.0), (0.0, 2.0))
    left = _chords(first, _edge_envelope(b"alpha"), (chord_a,), calibrate=True)
    right = _chords(second, _edge_envelope(b"beta"), (chord_b,), calibrate=True)
    lesser_fragment = min((first, second), key=lambda item: str(item.id))
    greater_fragment = max((first, second), key=lambda item: str(item.id))
    by_fragment = {left.fragment.id: left, right.fragment.id: right}
    fragment_a = by_fragment[lesser_fragment.id]
    fragment_b = by_fragment[greater_fragment.id]
    log = PairwiseJoinLog()
    result = _propose(log, (right, left))
    assert isinstance(result, PairwiseJoins)
    assert len(result.joins) == 2
    assert result.run.join_ids == tuple(join.id for join in result.joins)
    assert [event.status for event in result.proposed] == ["proposed", "proposed"]
    scores = [join.scores[0] for join in result.joins]
    assert scores[0].value == scores[1].value == -2.0
    assert scores[0].channel == "physical"
    assert scores[0].hypothesis_type == "join"
    assert scores[0].run_id == result.run.id
    stored_a = fragment_a.edges[0].geometry
    stored_b = fragment_b.edges[0].geometry
    assert isinstance(stored_a, tuple) and isinstance(stored_b, tuple)
    directions = (stored_b, (stored_b[1], stored_b[0]))
    for join, transform, direction in zip(
        result.joins, result.transforms, directions, strict=True
    ):
        assert join.fragment_a_id == lesser_fragment.id
        assert join.fragment_b_id == greater_fragment.id
        assert join.edge_a_id == fragment_a.edges[0].id
        assert join.edge_b_id == fragment_b.edges[0].id
        assert transform.from_frame_id == fragment_a.frame.id
        assert transform.to_frame_id == fragment_b.frame.id
        midpoint_a = (
            (stored_a[0][0] + stored_a[1][0]) / 2.0,
            (stored_a[0][1] + stored_a[1][1]) / 2.0,
        )
        midpoint_b = (
            (direction[0][0] + direction[1][0]) / 2.0,
            (direction[0][1] + direction[1][1]) / 2.0,
        )
        mapped = _apply(
            transform.rotation_radians,
            (transform.translation_x, transform.translation_y),
            midpoint_a,
        )
        assert _close(mapped, midpoint_b)
        mapped_end = _apply(
            transform.rotation_radians,
            (transform.translation_x, transform.translation_y),
            stored_a[1],
        )
        mapped_start = _apply(
            transform.rotation_radians,
            (transform.translation_x, transform.translation_y),
            stored_a[0],
        )
        mapped_direction = (
            mapped_end[0] - mapped_start[0],
            mapped_end[1] - mapped_start[1],
        )
        chosen = (
            direction[1][0] - direction[0][0],
            direction[1][1] - direction[0][1],
        )
        assert math.isclose(
            math.atan2(mapped_direction[1], mapped_direction[0]),
            math.atan2(chosen[1], chosen[0]),
            abs_tol=1e-9,
        )
    assert result.transforms[0].id != result.transforms[1].id
    assert result.joins[0].id != result.joins[1].id
    content = result.run.provenance.content_mapping()
    assert result.run.provenance.algorithm_name == ALGORITHM_NAME
    assert result.run.provenance.algorithm_version == ALGORITHM_VERSION
    parsed = json.loads(content["parameter_blob"])
    assert parsed["score"] == SCORE_NAME
    assert content["parameter_hash"] == hash_value(content["parameter_blob"].encode())
    assert content["parameter_hash"].startswith("sha256:")
    assert content["model_hash"] == ABSENT
    assert "random_seed" not in content
    assert content["code_version"] == _CODE
    assert content["decoder_name"] == "tiff"
    assert content["decoder_version"] == "1"
    assert content["source_hashes"] == tuple(
        sorted(
            {
                *left.envelope.source_hashes,
                *right.envelope.source_hashes,
            }
        )
    )
    repeated = _propose(log, (left, right))
    assert repeated is result
    fresh = _propose(PairwiseJoinLog(), (left, right))
    assert isinstance(fresh, PairwiseJoins)
    assert fresh.run.id == result.run.id
    assert [join.id for join in fresh.joins] == [join.id for join in result.joins]


def test_missing_calibration_or_pixel_frame_fails_under_its_own_id() -> None:
    project_id = uuid.uuid4()
    first = _fragment(project_id, "alpha", "catalogued")
    second = _fragment(project_id, "beta", "confirmed")
    chord: Chord = ((0.0, 0.0), (3.0, 0.0))
    ready = _chords(first, _edge_envelope(b"alpha"), (chord,), calibrate=True)
    missing = _chords(second, _edge_envelope(b"beta"), (chord,), calibrate=False)
    log = PairwiseJoinLog()
    failed = _propose(log, (ready, missing))
    assert isinstance(failed, FailedPairwiseJoin)
    assert failed.run.status == "failed"
    assert failed.run.attempt_id is not None
    assert failed.run.join_ids == ()
    assert log.joins == ()
    completed_same_inputs = content_id(
        run_id_inputs(failed.run.provenance, "completed", None)
    )
    assert failed.run.id != completed_same_inputs
    restored = _chords(second, missing.envelope, (chord,), calibrate=True)
    # The restored edges are new rows, so this is a later millimetre run.
    completed = _propose(PairwiseJoinLog(), (ready, restored))
    assert isinstance(completed, PairwiseJoins)
    assert completed.run.id != failed.run.id
    assert completed.transforms
    pixels = CoordinateFrame.source_pixels(owner_id=uuid.uuid4())
    pixel_pool = (
        ready,
        FragmentChords(
            fragment=second,
            frame=pixels,
            edges=missing.edges,
            envelope=missing.envelope,
        ),
    )
    pixel_failed = _propose(PairwiseJoinLog(), pixel_pool)
    assert isinstance(pixel_failed, FailedPairwiseJoin)
    assert pixel_failed.run.attempt_id is not None
    assert pixel_failed.run.join_ids == ()
    later = _propose(PairwiseJoinLog(), (ready, restored))
    assert isinstance(later, PairwiseJoins)
    assert pixel_failed.run.id != later.run.id


def test_same_inputs_keep_the_join_ids_and_a_long_residual_stays_proposed() -> None:
    project_id = uuid.uuid4()
    first = _fragment(project_id, "alpha", "catalogued")
    second = _fragment(project_id, "beta", "catalogued")
    left = _chords(
        first,
        _edge_envelope(b"alpha"),
        (((0.0, 0.0), (1.0, 0.0)),),
        calibrate=True,
    )
    right = _chords(
        second,
        _edge_envelope(b"beta"),
        (((0.0, 0.0), (100.0, 0.0)),),
        calibrate=True,
    )
    first_run = _propose(PairwiseJoinLog(), (left, right))
    second_run = _propose(PairwiseJoinLog(), (right, left))
    assert isinstance(first_run, PairwiseJoins)
    assert isinstance(second_run, PairwiseJoins)
    assert first_run.run.id == second_run.run.id
    assert [join.id for join in first_run.joins] == [
        join.id for join in second_run.joins
    ]
    assert [join.scores[0].value for join in first_run.joins] == [-99.0, -99.0]
    assert [event.status for event in first_run.proposed] == ["proposed", "proposed"]


def test_differing_decoders_fail_the_run() -> None:
    project_id = uuid.uuid4()
    first = _fragment(project_id, "alpha", "catalogued")
    second = _fragment(project_id, "beta", "confirmed")
    chord: Chord = ((0.0, 0.0), (2.0, 0.0))
    left = _chords(first, _edge_envelope(b"alpha"), (chord,), calibrate=True)
    right = _chords(
        second,
        _edge_envelope(b"beta", decoder_version="2"),
        (chord,),
        calibrate=True,
    )
    failed = _propose(PairwiseJoinLog(), (left, right))
    assert isinstance(failed, FailedPairwiseJoin)
    assert failed.run.join_ids == ()
    assert failed.run.attempt_id is not None


def test_module_does_not_reference_labels_json() -> None:
    import prw.pairwise_join as pairwise_join

    source = Path(inspect.getfile(pairwise_join)).read_text(encoding="utf-8")
    assert "labels.json" not in source
