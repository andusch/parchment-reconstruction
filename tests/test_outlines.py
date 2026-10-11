"""Synthetic in-memory fragments and machine outline revisions."""

import dataclasses
import uuid

import pytest

from prw.identity import ABSENT, content_id, hash_value
from prw.outlines import Fragment, FragmentOutlineRevision, OutlineRevisionLog
from prw.provenance import AlgorithmRun, ProvenanceEnvelope, StatusStream

_RECORDED = "2020-01-01T00:00:00Z"
_TRIANGLE = ((0.0, 0.0), (2.0, 0.0), (0.0, 2.0))
_LATER_TRIANGLE = ((0.0, 0.0), (3.0, 0.0), (0.0, 2.0))


def _envelope() -> ProvenanceEnvelope:
    return ProvenanceEnvelope.create(
        source_hashes=(hash_value(b"synthetic-source"),),
        parameters={"threshold": 12},
        algorithm_name="outline",
        algorithm_version="1",
        code_version="abc123",
        decoder_name="tiff",
        decoder_version="1",
    )


def _run(envelope: ProvenanceEnvelope) -> AlgorithmRun:
    return AlgorithmRun.create(envelope, status="completed", started_at=_RECORDED)


def _outline(
    envelope: ProvenanceEnvelope,
    run: AlgorithmRun,
    fragment: Fragment,
    *,
    polygon: tuple[tuple[float, float], ...] = _TRIANGLE,
    epistemic_class: str = "interpretation",
    producer: str = "machine",
    supersedes_id: uuid.UUID | None = None,
) -> FragmentOutlineRevision:
    return FragmentOutlineRevision.create(
        fragment_id=fragment.id,
        frame_id=uuid.uuid4(),
        polygon=polygon,
        run_id=run.id,
        provenance_id=envelope.id,
        producer=producer,
        epistemic_class=epistemic_class,
        supersedes_id=supersedes_id,
    )


def test_machine_fragment_id_uses_the_project_and_the_label() -> None:
    project_id = uuid.uuid4()
    fragment = Fragment.create(project_id=project_id, label="shelf-4")
    assert fragment.identification_status == "detected"
    assert fragment.id == content_id([project_id, "shelf-4"])
    assert fragment.id == content_id(fragment.id_inputs())
    assert fragment.id != content_id([project_id, "shelf-4", "detected"])
    repeated = Fragment.create(project_id=project_id, label="shelf-4")
    assert repeated.id == fragment.id
    other_project = Fragment.create(project_id=uuid.uuid4(), label="shelf-4")
    assert other_project.id != fragment.id


def test_rejected_class_and_producer() -> None:
    envelope = _envelope()
    run = _run(envelope)
    fragment = Fragment.create(project_id=uuid.uuid4(), label="piece")
    with pytest.raises(ValueError, match="interpretation"):
        _outline(envelope, run, fragment, epistemic_class="observed")
    with pytest.raises(ValueError, match="interpretation"):
        _outline(envelope, run, fragment, epistemic_class="hypothesis")
    with pytest.raises(ValueError, match="machine"):
        _outline(envelope, run, fragment, producer="human")


def test_deterministic_envelope_has_no_seed_and_is_cited() -> None:
    envelope = _envelope()
    run = _run(envelope)
    fragment = Fragment.create(project_id=uuid.uuid4(), label="piece")
    outline = _outline(envelope, run, fragment)
    content = envelope.content_mapping()
    assert outline.provenance_id == envelope.id
    assert outline.run_id == run.id
    assert content["parameter_blob"] == '{"threshold":12}'
    assert content["parameter_hash"] == hash_value(b'{"threshold":12}')
    assert content["parameter_hash"].startswith("sha256:")
    assert content["model_hash"] == ABSENT
    assert "random_seed" not in content
    assert envelope.random_seed is None
    assert outline.epistemic_class == "interpretation"
    assert outline.producer == "machine"
    names = {field.name for field in dataclasses.fields(outline)}
    assert "status" not in names
    assert "operator_id" not in names
    assert "session_id" not in names
    assert outline.supersedes_id is None
    assert outline.id == content_id([run.id, outline.polygon])


def test_polygon_cannot_be_replaced_in_place() -> None:
    envelope = _envelope()
    run = _run(envelope)
    fragment = Fragment.create(project_id=uuid.uuid4(), label="piece")
    outline = _outline(envelope, run, fragment)
    before = outline.polygon
    with pytest.raises(dataclasses.FrozenInstanceError):
        outline.polygon = _LATER_TRIANGLE  # type: ignore[misc]
    assert outline.polygon == before
    assert outline.id == content_id([run.id, before])


def test_superseding_row_leaves_the_first_polygon_and_appends_proposed() -> None:
    envelope = _envelope()
    run = _run(envelope)
    fragment = Fragment.create(project_id=uuid.uuid4(), label="piece")
    first = _outline(envelope, run, fragment)
    log = OutlineRevisionLog()
    stream = StatusStream()
    proposed = log.insert(
        stream,
        first,
        recorded_at=_RECORDED,
        actor=str(run.id),
    )
    assert proposed.status == "proposed"
    assert proposed.id.version == 4
    assert stream.current_status(first.id) == "proposed"
    later = first.supersede(_LATER_TRIANGLE)
    assert later.supersedes_id == first.id
    assert later.id != first.id
    assert later.id == content_id([run.id, later.polygon])
    assert later.polygon == _LATER_TRIANGLE
    assert first.polygon == _TRIANGLE
    log.insert(stream, later, recorded_at=_RECORDED, actor=str(run.id))
    stored = log.by_id(first.id)
    assert stored.polygon == _TRIANGLE
    assert stored is first
    assert log.by_id(later.id).polygon == _LATER_TRIANGLE
    assert stream.current_status(later.id) == "proposed"
    assert [row.id for row in log.rows] == [first.id, later.id]
    with pytest.raises(ValueError, match="new row"):
        log.insert(stream, first, recorded_at=_RECORDED, actor=str(run.id))
