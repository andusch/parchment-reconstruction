"""Synthetic in-memory envelopes, run ids, and status events."""

import dataclasses
import uuid

import pytest

from prw.identity import content_id, hash_value
from prw.provenance import (
    AlgorithmRun,
    AssemblyContent,
    ProvenanceEnvelope,
    StatusStream,
    insert_hypothesis,
)

_RECORDED = "2020-01-01T00:00:00Z"
_LATER = "2024-06-01T12:00:00Z"


def _envelope(
    *,
    source_hashes: tuple[str, ...] | None = None,
    random_seed: int | None = None,
    model_hash: str | None = None,
) -> ProvenanceEnvelope:
    hashes = (hash_value(b"source-a"),) if source_hashes is None else source_hashes
    return ProvenanceEnvelope.create(
        source_hashes=hashes,
        parameters={"edge_erosion": 1, "rotation": 0},
        algorithm_name="joins",
        algorithm_version="1",
        code_version="abc123",
        decoder_name="tiff",
        decoder_version="1",
        model_hash=model_hash,
        random_seed=random_seed,
    )


def _run_tail(envelope: ProvenanceEnvelope, seed: int | str) -> list[object]:
    return [
        envelope.algorithm_name,
        envelope.algorithm_version,
        envelope.code_version,
        envelope.parameter_hash,
        envelope.model_hash,
        *sorted(envelope.source_hashes),
        seed,
    ]


def test_deterministic_envelope_omits_seed_and_stores_the_parameter_blob() -> None:
    envelope = _envelope()
    content = envelope.content_mapping()
    assert envelope.parameter_blob == '{"edge_erosion":1,"rotation":0}'
    assert envelope.parameter_hash == hash_value(envelope.parameter_blob.encode())
    assert content["model_hash"] == "absent"
    assert "random_seed" not in content
    assert envelope.id == content_id(content)
    with pytest.raises(ValueError, match="empty string"):
        _envelope(model_hash="")


def test_seeded_envelope_keeps_the_json_integer() -> None:
    envelope = _envelope(random_seed=7)
    assert envelope.random_seed == 7
    assert envelope.content_mapping()["random_seed"] == 7
    zero = _envelope(random_seed=0)
    assert zero.content_mapping()["random_seed"] == 0
    seeded_run = AlgorithmRun.create(envelope, status="completed", started_at=_RECORDED)
    assert seeded_run.id == content_id(["completed", *_run_tail(envelope, 7)])


def test_completed_run_id_repeats_and_excludes_the_timestamp() -> None:
    envelope = _envelope()
    first = AlgorithmRun.create(envelope, status="completed", started_at=_RECORDED)
    second = AlgorithmRun.create(envelope, status="completed", started_at=_LATER)
    assert first.attempt_id is None
    assert first.id == second.id
    assert first.id == content_id(["completed", *_run_tail(envelope, "absent")])
    assert first.provenance_id == envelope.id


def test_failed_run_id_differs_by_attempt_id() -> None:
    envelope = _envelope()
    completed = AlgorithmRun.create(envelope, status="completed", started_at=_RECORDED)
    failed = AlgorithmRun.create(envelope, status="failed", started_at=_RECORDED)
    assert failed.attempt_id is not None
    assert failed.id != completed.id
    assert failed.id == content_id(
        ["failed", failed.attempt_id, *_run_tail(envelope, "absent")]
    )
    repeated = AlgorithmRun.create(
        envelope,
        status="failed",
        started_at=_LATER,
        attempt_id=failed.attempt_id,
    )
    assert repeated.id == failed.id
    other = AlgorithmRun.create(envelope, status="failed", started_at=_RECORDED)
    assert other.attempt_id != failed.attempt_id
    assert other.id != failed.id
    cancelled = AlgorithmRun.create(envelope, status="cancelled", started_at=_RECORDED)
    assert cancelled.id == content_id(
        ["cancelled", cancelled.attempt_id, *_run_tail(envelope, "absent")]
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        failed.status = "completed"  # type: ignore[misc]


def test_source_hash_order_does_not_change_the_completed_run_id() -> None:
    first_hash = hash_value(b"source-a")
    second_hash = hash_value(b"source-b")
    left = _envelope(source_hashes=(first_hash, second_hash))
    right = _envelope(source_hashes=(second_hash, first_hash))
    assert left.id != right.id
    left_run = AlgorithmRun.create(left, status="completed", started_at=_RECORDED)
    right_run = AlgorithmRun.create(right, status="completed", started_at=_LATER)
    assert left_run.id == right_run.id


def test_rejected_event_leaves_hypothesis_content_unchanged() -> None:
    envelope = _envelope()
    run = AlgorithmRun.create(envelope, status="completed", started_at=_RECORDED)
    missing = uuid.uuid4()
    assembly = AssemblyContent.create(
        page_frame_id=uuid.uuid4(),
        producer="machine",
        unplaced_fragment_ids=(missing,),
        run_id=run.id,
        provenance_id=envelope.id,
    )
    assert assembly.epistemic_class == "hypothesis"
    assert assembly.producer == "machine"
    assert assembly.unplaced_fragment_ids == (missing,)
    assert "status" not in {field.name for field in dataclasses.fields(assembly)}
    before = assembly.content_bytes()
    assert str(missing).encode() in before
    stream = StatusStream()
    rejected = insert_hypothesis(
        stream,
        assembly,
        recorded_at=_RECORDED,
        actor=str(run.id),
        machine_rejection=True,
    )
    assert rejected.status == "rejected"
    assert rejected.id.version == 4
    assert assembly.content_bytes() == before
    assert assembly.id == content_id([run.id, assembly.content_mapping()])
    stream.append(
        target_id=assembly.id,
        status="rejected-via-ValidationDecision",
        recorded_at=_LATER,
        actor="scholar",
    )
    assert stream.current_status(assembly.id) == "rejected-via-ValidationDecision"
    assert assembly.content_bytes() == before
    assert assembly.id == content_id(assembly.id_inputs())


def test_first_event_is_proposed_unless_the_write_is_a_machine_rejection() -> None:
    assembly = AssemblyContent.create(
        page_frame_id=uuid.uuid4(),
        producer="human",
        unplaced_fragment_ids=(uuid.uuid4(),),
    )
    stream = StatusStream()
    proposed = insert_hypothesis(
        stream,
        assembly,
        recorded_at=_RECORDED,
        actor="scholar",
    )
    assert proposed.status == "proposed"
    assert stream.current_status(assembly.id) == "proposed"
    with pytest.raises(ValueError, match="machine"):
        insert_hypothesis(
            stream,
            AssemblyContent.create(
                page_frame_id=assembly.page_frame_id,
                producer="human",
            ),
            recorded_at=_RECORDED,
            actor="scholar",
            machine_rejection=True,
        )
    with pytest.raises(ValueError, match="first status event"):
        stream.append(
            target_id=uuid.uuid4(),
            status="contested",
            recorded_at=_RECORDED,
            actor="run",
        )
