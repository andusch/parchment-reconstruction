"""Synthetic in-memory edges, rigid poses, and pairwise joins."""

import dataclasses
import uuid

import pytest

from prw.frames import CoordinateFrame
from prw.identity import ABSENT, content_id, hash_value
from prw.joins import (
    EdgeArc,
    EdgeArcLog,
    JoinHypothesis,
    JoinHypothesisLog,
    RigidTransform,
)
from prw.provenance import AlgorithmRun, ProvenanceEnvelope, Score, StatusStream

_RECORDED = "2020-01-01T00:00:00Z"
_TRIANGLE = ((0.0, 0.0), (2.0, 0.0), (0.0, 2.0))
_EDGE = ((0.0, 0.0), (2.0, 0.0))
_OTHER_EDGE = ((0.0, 0.0), (0.0, 2.0))


def _envelope() -> ProvenanceEnvelope:
    return ProvenanceEnvelope.create(
        source_hashes=(hash_value(b"synthetic-source"),),
        parameters={"clearance": 0.2},
        algorithm_name="joins",
        algorithm_version="1",
        code_version="abc123",
        decoder_name="tiff",
        decoder_version="1",
    )


def _run(envelope: ProvenanceEnvelope) -> AlgorithmRun:
    return AlgorithmRun.create(envelope, status="completed", started_at=_RECORDED)


def _local(owner_id: uuid.UUID, outline_id: uuid.UUID) -> CoordinateFrame:
    return CoordinateFrame.fragment_local_mm(
        owner_id=owner_id,
        establishing_outline_revision_id=outline_id,
        polygon=_TRIANGLE,
    )


def _score(
    run: AlgorithmRun,
    *,
    channel: str = "physical",
    hypothesis_type: str = "join",
) -> Score:
    return Score(
        value=0.25,
        run_id=run.id,
        channel=channel,  # type: ignore[arg-type]
        hypothesis_type=hypothesis_type,  # type: ignore[arg-type]
    )


def _pair(
    envelope: ProvenanceEnvelope,
    run: AlgorithmRun,
) -> tuple[EdgeArc, EdgeArc, RigidTransform, JoinHypothesis]:
    fragment_a = uuid.uuid4()
    fragment_b = uuid.uuid4()
    outline_a = uuid.uuid4()
    outline_b = uuid.uuid4()
    frame_a = _local(fragment_a, outline_a)
    frame_b = _local(fragment_b, outline_b)
    edge_a = EdgeArc.create(
        outline_revision_id=outline_a,
        frame=frame_a,
        geometry=_EDGE,
        run_id=run.id,
        provenance_id=envelope.id,
    )
    edge_b = EdgeArc.create(
        outline_revision_id=outline_b,
        frame=frame_b,
        geometry=_OTHER_EDGE,
        run_id=run.id,
        provenance_id=envelope.id,
    )
    pose = RigidTransform.create(
        from_frame=frame_a,
        to_frame=frame_b,
        rotation_radians=0.5,
        translation_x=1.0,
        translation_y=2.0,
        provenance_id=envelope.id,
    )
    join = JoinHypothesis.create(
        run_id=run.id,
        fragment_a_id=fragment_a,
        edge_a_id=edge_a.id,
        fragment_b_id=fragment_b,
        edge_b_id=edge_b.id,
        transform_id=pose.id,
        scores=(_score(run),),
        provenance_id=envelope.id,
    )
    return edge_a, edge_b, pose, join


def test_machine_edge_pose_and_join_use_the_data_model_classes() -> None:
    envelope = _envelope()
    run = _run(envelope)
    edge, _, pose, join = _pair(envelope, run)
    assert edge.epistemic_class == "interpretation"
    assert edge.producer == "machine"
    assert edge.run_id == run.id
    assert edge.provenance_id == envelope.id
    assert edge.id == content_id([run.id, edge.outline_revision_id, edge.geometry])
    assert pose.epistemic_class == "hypothesis"
    assert pose.id == content_id(pose.content_mapping())
    assert join.epistemic_class == "hypothesis"
    assert join.id == content_id([run.id, join.content_mapping()])
    assert join.scores[0].channel == "physical"
    assert join.scores[0].hypothesis_type == "join"
    edge_names = {field.name for field in dataclasses.fields(edge)}
    pose_names = {field.name for field in dataclasses.fields(pose)}
    join_names = {field.name for field in dataclasses.fields(join)}
    assert "status" not in edge_names
    assert "status" not in pose_names
    assert "status" not in join_names
    assert "operator_id" not in edge_names
    assert "session_id" not in edge_names
    assert "scale" not in pose_names
    assert "edge_ids" not in {field.name for field in dataclasses.fields(AlgorithmRun)}
    with pytest.raises(TypeError, match="edge_ids"):
        AlgorithmRun.create(
            envelope,
            status="completed",
            started_at=_RECORDED,
            edge_ids=(),  # type: ignore[call-arg]
        )


def test_rejected_class_and_pixel_frame() -> None:
    envelope = _envelope()
    run = _run(envelope)
    fragment_id = uuid.uuid4()
    outline_id = uuid.uuid4()
    local = _local(fragment_id, outline_id)
    pixels = CoordinateFrame.source_pixels(owner_id=uuid.uuid4())
    page = CoordinateFrame.page_global_mm(owner_id=uuid.uuid4())
    with pytest.raises(ValueError, match="interpretation"):
        EdgeArc.create(
            outline_revision_id=outline_id,
            frame=local,
            geometry=_EDGE,
            run_id=run.id,
            provenance_id=envelope.id,
            epistemic_class="hypothesis",
        )
    with pytest.raises(ValueError, match="interpretation"):
        EdgeArc.create(
            outline_revision_id=outline_id,
            frame=local,
            geometry=_EDGE,
            run_id=run.id,
            provenance_id=envelope.id,
            epistemic_class="observed",
        )
    with pytest.raises(ValueError, match="fragment_local_mm"):
        EdgeArc.create(
            outline_revision_id=outline_id,
            frame=pixels,
            geometry=_EDGE,
            run_id=run.id,
            provenance_id=envelope.id,
        )
    with pytest.raises(ValueError, match="hypothesis"):
        RigidTransform.create(
            from_frame=local,
            to_frame=local,
            rotation_radians=0.0,
            translation_x=0.0,
            translation_y=0.0,
            provenance_id=envelope.id,
            epistemic_class="interpretation",
        )
    with pytest.raises(ValueError, match="fragment_local_mm"):
        RigidTransform.create(
            from_frame=local,
            to_frame=pixels,
            rotation_radians=0.0,
            translation_x=0.0,
            translation_y=0.0,
            provenance_id=envelope.id,
        )
    with pytest.raises(ValueError, match="destination frame"):
        RigidTransform.create(
            from_frame=local,
            to_frame=page,
            rotation_radians=0.0,
            translation_x=0.0,
            translation_y=0.0,
            provenance_id=envelope.id,
        )
    edge, other, pose, _join = _pair(envelope, run)
    with pytest.raises(ValueError, match="hypothesis"):
        JoinHypothesis.create(
            run_id=run.id,
            fragment_a_id=uuid.uuid4(),
            edge_a_id=edge.id,
            fragment_b_id=uuid.uuid4(),
            edge_b_id=other.id,
            transform_id=pose.id,
            scores=(_score(run),),
            provenance_id=envelope.id,
            epistemic_class="interpretation",
        )


def test_equal_fragments_and_a_third_fragment_are_rejected() -> None:
    envelope = _envelope()
    run = _run(envelope)
    edge, other, pose, _join = _pair(envelope, run)
    shared = uuid.uuid4()
    with pytest.raises(ValueError, match="distinct fragment"):
        JoinHypothesis.create(
            run_id=run.id,
            fragment_a_id=shared,
            edge_a_id=edge.id,
            fragment_b_id=shared,
            edge_b_id=other.id,
            transform_id=pose.id,
            scores=(_score(run),),
            provenance_id=envelope.id,
        )
    with pytest.raises(TypeError, match="fragment_c_id"):
        JoinHypothesis.create(  # type: ignore[call-arg]
            run_id=run.id,
            fragment_a_id=uuid.uuid4(),
            edge_a_id=edge.id,
            fragment_b_id=uuid.uuid4(),
            edge_b_id=other.id,
            transform_id=pose.id,
            scores=(_score(run),),
            provenance_id=envelope.id,
            fragment_c_id=uuid.uuid4(),
        )


def test_scale_field_and_second_channel_are_rejected() -> None:
    envelope = _envelope()
    run = _run(envelope)
    fragment_id = uuid.uuid4()
    outline_id = uuid.uuid4()
    local = _local(fragment_id, outline_id)
    with pytest.raises(TypeError, match="scale"):
        RigidTransform.create(  # type: ignore[call-arg]
            from_frame=local,
            to_frame=local,
            rotation_radians=0.0,
            translation_x=0.0,
            translation_y=0.0,
            provenance_id=envelope.id,
            scale=1.0,
        )
    edge, other, pose, _join = _pair(envelope, run)
    with pytest.raises(ValueError, match="one score"):
        JoinHypothesis.create(
            run_id=run.id,
            fragment_a_id=uuid.uuid4(),
            edge_a_id=edge.id,
            fragment_b_id=uuid.uuid4(),
            edge_b_id=other.id,
            transform_id=pose.id,
            scores=(_score(run), _score(run, channel="language")),
            provenance_id=envelope.id,
        )
    with pytest.raises(ValueError, match="physical"):
        JoinHypothesis.create(
            run_id=run.id,
            fragment_a_id=uuid.uuid4(),
            edge_a_id=edge.id,
            fragment_b_id=uuid.uuid4(),
            edge_b_id=other.id,
            transform_id=pose.id,
            scores=(_score(run, channel="htr"),),
            provenance_id=envelope.id,
        )


def test_content_cannot_be_replaced_in_place() -> None:
    envelope = _envelope()
    run = _run(envelope)
    edge, _, pose, join = _pair(envelope, run)
    before_geometry = edge.geometry
    before_rotation = pose.rotation_radians
    before_join = join.content_bytes()
    with pytest.raises(dataclasses.FrozenInstanceError):
        edge.geometry = _OTHER_EDGE  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        pose.rotation_radians = 1.25  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        join.fragment_a_id = uuid.uuid4()  # type: ignore[misc]
    assert edge.geometry == before_geometry
    assert pose.rotation_radians == before_rotation
    assert join.content_bytes() == before_join


def test_insert_appends_proposed_or_a_machine_rejection() -> None:
    envelope = _envelope()
    run = _run(envelope)
    edge, _, _pose, join = _pair(envelope, run)
    content = envelope.content_mapping()
    assert join.provenance_id == envelope.id
    assert edge.provenance_id == envelope.id
    assert content["parameter_blob"] == '{"clearance":0.2}'
    assert content["parameter_hash"] == hash_value(b'{"clearance":0.2}')
    assert content["parameter_hash"].startswith("sha256:")
    assert content["model_hash"] == ABSENT
    assert "random_seed" not in content
    before = join.content_bytes()
    stream = StatusStream()
    proposed = EdgeArcLog().insert(
        stream,
        edge,
        recorded_at=_RECORDED,
        actor=str(run.id),
    )
    assert proposed.status == "proposed"
    assert stream.current_status(edge.id) == "proposed"
    joins = JoinHypothesisLog()
    rejected = joins.insert(
        stream,
        join,
        recorded_at=_RECORDED,
        actor=str(run.id),
        machine_rejection=True,
    )
    assert rejected.status == "rejected"
    assert rejected.id.version == 4
    assert stream.current_status(join.id) == "rejected"
    assert join.content_bytes() == before
    assert joins.by_id(join.id) is join
    assert join.id == content_id(join.id_inputs())
