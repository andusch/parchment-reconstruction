"""Caller-built joins and rectangles for a rigid page search."""

import json
import math
import uuid

import pytest

from prw.assembly_search import (
    ALGORITHM_NAME,
    ALGORITHM_VERSION,
    SCORE_NAME,
    AssemblySearch,
    AssemblySearchLog,
    FailedAssemblySearch,
    FragmentOutline,
)
from prw.frames import CoordinateFrame, PageFrame
from prw.identity import ABSENT, hash_value
from prw.joins import JoinHypothesis, RigidTransform
from prw.outlines import Fragment, FragmentOutlineRevision
from prw.provenance import (
    AlgorithmRun,
    ProvenanceEnvelope,
    Score,
    StatusStream,
)

_RECORDED = "2020-01-01T00:00:00Z"
_LATER = "2020-01-01T00:00:01Z"
_RECT = ((0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (0.0, 1.0))


def _envelope(
    decoder_version: str = "1",
    source: bytes = b"synthetic-source",
) -> ProvenanceEnvelope:
    return ProvenanceEnvelope.create(
        source_hashes=(hash_value(source),),
        parameters={"clearance": 0.2},
        algorithm_name="pairwise_rigid_join",
        algorithm_version="1",
        code_version="join123",
        decoder_name="tiff",
        decoder_version=decoder_version,
    )


def _run(envelope: ProvenanceEnvelope, status: str = "completed") -> AlgorithmRun:
    return AlgorithmRun.create(
        envelope,
        status=status,  # type: ignore[arg-type]
        started_at=_RECORDED,
    )


def _outline(
    fragment: Fragment,
    envelope: ProvenanceEnvelope,
    polygon: tuple[tuple[float, float], ...] = _RECT,
) -> FragmentOutline:
    run = _run(envelope)
    frame = CoordinateFrame.fragment_local_mm(
        owner_id=fragment.id,
        establishing_outline_revision_id=uuid.uuid4(),
        polygon=polygon,
    )
    outline = FragmentOutlineRevision.create(
        fragment_id=fragment.id,
        frame_id=frame.id,
        polygon=polygon,
        run_id=run.id,
        provenance_id=envelope.id,
    )
    return FragmentOutline(fragment=fragment, frame=frame, outline=outline)


def _join(
    left: FragmentOutline,
    right: FragmentOutline,
    run: AlgorithmRun,
    envelope: ProvenanceEnvelope,
    *,
    value: float,
    translation_x: float,
) -> tuple[JoinHypothesis, RigidTransform]:
    pose = RigidTransform.create(
        from_frame=left.frame,
        to_frame=right.frame,
        rotation_radians=0.0,
        translation_x=translation_x,
        translation_y=0.0,
        provenance_id=envelope.id,
    )
    join = JoinHypothesis.create(
        run_id=run.id,
        fragment_a_id=left.fragment.id,
        edge_a_id=uuid.uuid4(),
        fragment_b_id=right.fragment.id,
        edge_b_id=uuid.uuid4(),
        transform_id=pose.id,
        scores=(
            Score(
                value=value,
                run_id=run.id,
                channel="physical",
                hypothesis_type="join",
            ),
        ),
        provenance_id=envelope.id,
    )
    return join, pose


def _page() -> tuple[PageFrame, CoordinateFrame]:
    frame = CoordinateFrame.page_global_mm(owner_id=uuid.uuid4())
    page = PageFrame.create(
        frame,
        min_width_mm=0.0,
        max_width_mm=20.0,
        min_height_mm=0.0,
        max_height_mm=10.0,
    )
    return page, frame


def _mark(stream: StatusStream, join: JoinHypothesis, status: str = "proposed") -> None:
    stream.append(
        target_id=join.id,
        status="proposed",
        recorded_at=_RECORDED,
        actor="search-test",
    )
    if status != "proposed":
        stream.append(
            target_id=join.id,
            status=status,  # type: ignore[arg-type]
            recorded_at=_LATER,
            actor="search-test",
        )


def _search(
    log: AssemblySearchLog,
    *,
    joins: tuple[JoinHypothesis, ...],
    poses: tuple[RigidTransform, ...],
    runs: tuple[AlgorithmRun, ...],
    events: StatusStream,
    outlines: tuple[FragmentOutline, ...],
    n: object = 2,
    translation: object = 0.0,
    rotation: object = 0.0,
    page: object | None = None,
    page_frame: object | None = None,
) -> AssemblySearch | FailedAssemblySearch:
    stored_page, stored_frame = _page()
    return log.search(
        joins,
        poses,
        runs,
        events,
        outlines,
        stored_page if page is None else page,
        stored_frame if page_frame is None else page_frame,
        n=n,
        translation_tolerance_mm=translation,
        rotation_tolerance_radians=rotation,
        code_version="abc123",
        recorded_at=_RECORDED,
    )


def test_parameter_blob_records_the_score_n_tolerances_and_page_ranges() -> None:
    project = uuid.uuid4()
    envelope = _envelope()
    run = _run(envelope)
    left = _outline(Fragment.catalogued(project_id=project, label="a"), envelope)
    right = _outline(Fragment.catalogued(project_id=project, label="b"), envelope)
    spare = _outline(Fragment.catalogued(project_id=project, label="c"), envelope)
    join, pose = _join(left, right, run, envelope, value=-0.5, translation_x=-2.0)
    events = StatusStream()
    _mark(events, join)
    page, frame = _page()
    result = AssemblySearchLog().search(
        (join,),
        (pose,),
        (run,),
        events,
        (left, right, spare),
        page,
        frame,
        n=2,
        translation_tolerance_mm=0.0,
        rotation_tolerance_radians=0.0,
        code_version="abc123",
        recorded_at=_RECORDED,
    )
    assert isinstance(result, AssemblySearch)
    parameters = json.loads(result.run.provenance.parameter_blob)
    assert parameters["score"] == SCORE_NAME
    assert parameters["n"] == 2
    assert parameters["translation_tolerance_mm"] == 0.0
    assert parameters["rotation_tolerance_radians"] == 0.0
    assert parameters["page_origin"] == "minimum_corner"
    assert parameters["anchor"] == "least_fragment_id_bytes"
    assert parameters["anchor_rotation_radians"] == 0
    assert parameters["page_frame_id"] == str(page.id)
    assert parameters["min_width_mm"] == 0.0
    assert parameters["max_width_mm"] == 20.0
    assert parameters["min_height_mm"] == 0.0
    assert parameters["max_height_mm"] == 10.0
    content = result.run.provenance.content_mapping()
    assert content["algorithm_name"] == ALGORITHM_NAME
    assert content["algorithm_version"] == ALGORITHM_VERSION
    assert content["model_hash"] == ABSENT
    assert content["parameter_hash"].startswith("sha256:")
    assert "random_seed" not in content
    assert content["source_hashes"] == (hash_value(b"synthetic-source"),)
    assert content["decoder_name"] == "tiff"
    assert content["decoder_version"] == "1"
    assert result.run.attempt_id is None
    assembly = result.assemblies[0]
    assert assembly.unplaced_fragment_ids == (spare.fragment.id,)
    assert assembly.scores[0].channel == "physical"
    assert assembly.scores[0].hypothesis_type == "assembly"
    assert assembly.scores[0].value == -0.5
    assert assembly.epistemic_class == "hypothesis"
    pose_row = result.poses[0]
    assert pose_row.to_frame_id == frame.id
    assert pose_row.from_frame_id in {left.frame.id, right.frame.id}
    assert pose_row.epistemic_class == "hypothesis"
    points = _placed_points(result, (left, right, spare))
    assert min(point[0] for point in points) == pytest.approx(0.0)
    assert min(point[1] for point in points) == pytest.approx(0.0)
    assert any(
        abs(x_coord) < 1e-9 and abs(y_coord) < 1e-9 for x_coord, y_coord in points
    )


def _placed_points(
    result: AssemblySearch,
    outlines: tuple[FragmentOutline, ...],
) -> list[tuple[float, float]]:
    by_fragment = {item.fragment.id: item for item in outlines}
    by_pose = {pose.id: pose for pose in result.poses}
    points: list[tuple[float, float]] = []
    for assembly in result.assemblies:
        for placement in assembly.placements:
            pose = by_pose[placement.transform_id]
            cosine = math.cos(pose.rotation_radians)
            sine = math.sin(pose.rotation_radians)
            polygon = by_fragment[placement.fragment_id].outline.polygon
            for x_coord, y_coord in polygon:
                points.append(
                    (
                        cosine * x_coord - sine * y_coord + pose.translation_x,
                        sine * x_coord + cosine * y_coord + pose.translation_y,
                    )
                )
    return points


def test_overlap_is_dropped_and_a_disconnected_pair_is_not_inserted() -> None:
    project = uuid.uuid4()
    envelope = _envelope()
    run = _run(envelope)
    overlapping_left = _outline(
        Fragment.catalogued(project_id=project, label="overlap-a"), envelope
    )
    overlapping_right = _outline(
        Fragment.catalogued(project_id=project, label="overlap-b"), envelope
    )
    overlap, overlap_pose = _join(
        overlapping_left,
        overlapping_right,
        run,
        envelope,
        value=4.0,
        translation_x=0.0,
    )
    first_left = _outline(
        Fragment.catalogued(project_id=project, label="d-a"), envelope
    )
    first_right = _outline(
        Fragment.catalogued(project_id=project, label="d-b"), envelope
    )
    second_left = _outline(
        Fragment.catalogued(project_id=project, label="d-c"), envelope
    )
    second_right = _outline(
        Fragment.catalogued(project_id=project, label="d-d"), envelope
    )
    low, low_pose = _join(
        first_left, first_right, run, envelope, value=1.0, translation_x=-2.0
    )
    high, high_pose = _join(
        second_left, second_right, run, envelope, value=3.0, translation_x=-2.0
    )
    events = StatusStream()
    for join in (overlap, low, high):
        _mark(events, join)
    overlapped = _search(
        AssemblySearchLog(),
        joins=(overlap,),
        poses=(overlap_pose,),
        runs=(run,),
        events=events,
        outlines=(overlapping_left, overlapping_right),
        n=2,
    )
    assert isinstance(overlapped, AssemblySearch)
    assert overlapped.assemblies == ()
    assert overlapped.run.status == "completed"
    assert overlapped.screening[0].outcome == "admitted"
    assert overlapped.screening[0].gate == "physical"
    disconnected = _search(
        AssemblySearchLog(),
        joins=(low, high),
        poses=(low_pose, high_pose),
        runs=(run,),
        events=events,
        outlines=(first_left, first_right, second_left, second_right),
        n=1,
    )
    assert isinstance(disconnected, AssemblySearch)
    assert len(disconnected.assemblies) == 1
    assert disconnected.assemblies[0].join_ids == (high.id,)
    assert low.id not in disconnected.assemblies[0].join_ids
    assert disconnected.assemblies[0].scores[0].value == 3.0


def test_equal_scores_follow_id_bytes_and_both_assemblies_stay() -> None:
    project = uuid.uuid4()
    envelope = _envelope()
    run = _run(envelope)
    joins = []
    poses = []
    outlines = []
    for label, partner in (("e-a", "e-b"), ("e-c", "e-d")):
        left = _outline(Fragment.catalogued(project_id=project, label=label), envelope)
        right = _outline(
            Fragment.catalogued(project_id=project, label=partner), envelope
        )
        join, pose = _join(left, right, run, envelope, value=2.0, translation_x=-2.0)
        joins.append(join)
        poses.append(pose)
        outlines.extend((left, right))
    events = StatusStream()
    for join in joins:
        _mark(events, join)
    result = _search(
        AssemblySearchLog(),
        joins=tuple(joins),
        poses=tuple(poses),
        runs=(run,),
        events=events,
        outlines=tuple(outlines),
        n=2,
    )
    assert isinstance(result, AssemblySearch)
    assert len(result.assemblies) == 2
    assert result.assemblies[0].scores[0].value == result.assemblies[1].scores[0].value
    assert result.assemblies[0].id.bytes < result.assemblies[1].id.bytes
    assert result.run.assembly_ids == tuple(item.id for item in result.assemblies)


def test_a_rejected_join_makes_the_assembly_contested() -> None:
    project = uuid.uuid4()
    envelope = _envelope()
    run = _run(envelope)
    left = _outline(Fragment.catalogued(project_id=project, label="r-a"), envelope)
    right = _outline(Fragment.catalogued(project_id=project, label="r-b"), envelope)
    join, pose = _join(left, right, run, envelope, value=1.0, translation_x=-2.0)
    events = StatusStream()
    _mark(events, join, "rejected")
    result = _search(
        AssemblySearchLog(),
        joins=(join,),
        poses=(pose,),
        runs=(run,),
        events=events,
        outlines=(left, right),
        n=1,
    )
    assert isinstance(result, AssemblySearch)
    assembly = result.assemblies[0]
    before = assembly.content_bytes()
    assert result.proposed[0].status == "proposed"
    assert result.contested[0].status == "contested"
    assert result.contested[0].target_id == assembly.id
    assert assembly.content_bytes() == before
    assert assembly.join_ids == (join.id,)


def test_invalidated_and_detected_joins_are_excluded() -> None:
    project = uuid.uuid4()
    envelope = _envelope()
    run = _run(envelope)
    kept_left = _outline(Fragment.catalogued(project_id=project, label="k-a"), envelope)
    kept_right = _outline(
        Fragment.catalogued(project_id=project, label="k-b"), envelope
    )
    old_left = _outline(
        Fragment.catalogued(project_id=project, label="old-a"), envelope
    )
    old_right = _outline(
        Fragment.catalogued(project_id=project, label="old-b"), envelope
    )
    detected = _outline(Fragment.create(project_id=project, label="seen"), envelope)
    partner = _outline(
        Fragment.catalogued(project_id=project, label="partner"), envelope
    )
    kept, kept_pose = _join(
        kept_left, kept_right, run, envelope, value=1.0, translation_x=-2.0
    )
    invalidated, invalidated_pose = _join(
        old_left, old_right, run, envelope, value=9.0, translation_x=-2.0
    )
    detected_join, detected_pose = _join(
        detected, partner, run, envelope, value=8.0, translation_x=-2.0
    )
    events = StatusStream()
    _mark(events, kept)
    _mark(events, invalidated, "invalidated")
    _mark(events, detected_join)
    result = _search(
        AssemblySearchLog(),
        joins=(invalidated, detected_join, kept),
        poses=(invalidated_pose, detected_pose, kept_pose),
        runs=(run,),
        events=events,
        outlines=(kept_left, kept_right, old_left, old_right, detected, partner),
        n=3,
    )
    assert isinstance(result, AssemblySearch)
    outcomes = {event.hypothesis_id: event.outcome for event in result.screening}
    assert outcomes[kept.id] == "admitted"
    assert outcomes[invalidated.id] == "excluded"
    assert outcomes[detected_join.id] == "excluded"
    assert [assembly.join_ids for assembly in result.assemblies] == [(kept.id,)]
    assert detected.fragment.id not in result.assemblies[0].unplaced_fragment_ids
    assert partner.fragment.id in result.assemblies[0].unplaced_fragment_ids


def test_every_overlapping_subset_completes_with_screening_and_no_assembly() -> None:
    project = uuid.uuid4()
    envelope = _envelope()
    run = _run(envelope)
    left = _outline(Fragment.catalogued(project_id=project, label="o-a"), envelope)
    right = _outline(Fragment.catalogued(project_id=project, label="o-b"), envelope)
    join, pose = _join(left, right, run, envelope, value=1.0, translation_x=-0.5)
    events = StatusStream()
    _mark(events, join)
    result = _search(
        AssemblySearchLog(),
        joins=(join,),
        poses=(pose,),
        runs=(run,),
        events=events,
        outlines=(left, right),
        n=1,
    )
    assert isinstance(result, AssemblySearch)
    assert result.assemblies == ()
    assert result.run.assembly_ids == ()
    assert result.run.status == "completed"
    assert len(result.screening) == 1
    assert result.screening[0].outcome == "admitted"


def test_a_missing_n_or_a_join_without_status_fails_without_screening() -> None:
    project = uuid.uuid4()
    envelope = _envelope()
    run = _run(envelope)
    left = _outline(Fragment.catalogued(project_id=project, label="m-a"), envelope)
    right = _outline(Fragment.catalogued(project_id=project, label="m-b"), envelope)
    join, pose = _join(left, right, run, envelope, value=1.0, translation_x=-2.0)
    events = StatusStream()
    _mark(events, join)
    missing_log = AssemblySearchLog()
    missing = _search(
        missing_log,
        joins=(join,),
        poses=(pose,),
        runs=(run,),
        events=events,
        outlines=(left, right),
        n=None,
    )
    assert isinstance(missing, FailedAssemblySearch)
    assert missing.run.status == "failed"
    assert missing.run.attempt_id is not None
    assert missing.run.assembly_ids == ()
    assert missing_log.screening == ()
    assert missing_log.assemblies == ()
    unstated = _search(
        AssemblySearchLog(),
        joins=(join,),
        poses=(pose,),
        runs=(run,),
        events=StatusStream(),
        outlines=(left, right),
        n=1,
    )
    assert isinstance(unstated, FailedAssemblySearch)
    assert unstated.run.assembly_ids == ()
    log = AssemblySearchLog()
    failed = log.search(
        (join,),
        (pose,),
        (run,),
        StatusStream(),
        (left, right),
        *_page(),
        n=1,
        translation_tolerance_mm=0.0,
        rotation_tolerance_radians=0.0,
        code_version="abc123",
        recorded_at=_RECORDED,
    )
    assert isinstance(failed, FailedAssemblySearch)
    assert log.screening == ()
    assert log.assemblies == ()
