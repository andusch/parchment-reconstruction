"""Hand-built assemblies with caller-supplied physical scores."""

import uuid

import pytest

from prw.assembly_rank import physical_assembly_order
from prw.identity import content_id, hash_value
from prw.joins import JoinHypothesis
from prw.provenance import (
    AlgorithmRun,
    AssemblyContent,
    ProvenanceEnvelope,
    Score,
    StatusStream,
)

_RECORDED = "2020-01-01T00:00:00Z"
_LATER = "2020-01-01T00:00:01Z"


def _envelope(source: bytes = b"synthetic-source") -> ProvenanceEnvelope:
    return ProvenanceEnvelope.create(
        source_hashes=(hash_value(source),),
        parameters={"clearance": 0.2},
        algorithm_name="assemblies",
        algorithm_version="1",
        code_version="abc123",
        decoder_name="tiff",
        decoder_version="1",
    )


def _run(envelope: ProvenanceEnvelope, status: str = "completed") -> AlgorithmRun:
    return AlgorithmRun.create(
        envelope,
        status=status,  # type: ignore[arg-type]
        started_at=_RECORDED,
    )


def _score(
    run: AlgorithmRun,
    value: float,
    *,
    channel: str = "physical",
    hypothesis_type: str = "assembly",
) -> Score:
    return Score(
        value=value,
        run_id=run.id,
        channel=channel,  # type: ignore[arg-type]
        hypothesis_type=hypothesis_type,  # type: ignore[arg-type]
    )


def _assembly(
    run: AlgorithmRun,
    envelope: ProvenanceEnvelope,
    value: float,
    *,
    scores: tuple[Score, ...] | None = None,
) -> AssemblyContent:
    stored_scores = (_score(run, value),) if scores is None else scores
    return AssemblyContent.create(
        page_frame_id=uuid.uuid4(),
        producer="machine",
        unplaced_fragment_ids=(uuid.uuid4(),),
        scores=stored_scores,
        provenance_id=envelope.id,
        run_id=run.id,
    )


def _status(
    assemblies: tuple[AssemblyContent, ...],
    status: str = "proposed",
) -> StatusStream:
    stream = StatusStream()
    for assembly in assemblies:
        stream.append(
            target_id=assembly.id,
            status="proposed",
            recorded_at=_RECORDED,
            actor="rank-test",
        )
        if status != "proposed":
            stream.append(
                target_id=assembly.id,
                status=status,  # type: ignore[arg-type]
                recorded_at=_LATER,
                actor="rank-test",
            )
    return stream


def test_higher_score_precedes_and_equal_scores_follow_id_bytes() -> None:
    envelope = _envelope()
    run = _run(envelope)
    low = _assembly(run, envelope, 0.0)
    tied_left = _assembly(run, envelope, 1.0)
    tied_right = _assembly(run, envelope, 1.0)
    high = _assembly(run, envelope, 2.0)
    assemblies = (low, tied_right, high, tied_left)
    ranked = physical_assembly_order(assemblies, (run,), _status(assemblies))
    tied = tuple(sorted((tied_left, tied_right), key=lambda item: item.id.bytes))
    assert ranked == (high, *tied, low)
    assert ranked[0] is high
    assert [item.id for item in ranked[1:3]] == [item.id for item in tied]
    assert "rank" not in high.content_mapping()
    assert high.id == content_id(high.id_inputs())


def test_contested_and_rejected_stay_and_invalidated_and_failed_are_omitted() -> None:
    envelope = _envelope()
    completed = _run(envelope)
    failed = _run(envelope, "failed")
    contested = _assembly(completed, envelope, 1.0)
    rejected = _assembly(completed, envelope, 2.0)
    invalidated = _assembly(completed, envelope, 5.0)
    failed_assembly = _assembly(failed, envelope, 9.0)
    stream = StatusStream()
    for assembly in (contested, rejected, invalidated, failed_assembly):
        stream.append(
            target_id=assembly.id,
            status="proposed",
            recorded_at=_RECORDED,
            actor="rank-test",
        )
    stream.append(
        target_id=contested.id,
        status="contested",
        recorded_at=_LATER,
        actor="rank-test",
    )
    stream.append(
        target_id=rejected.id,
        status="rejected",
        recorded_at=_LATER,
        actor="rank-test",
    )
    stream.append(
        target_id=invalidated.id,
        status="invalidated",
        recorded_at="2020-01-01T00:00:02Z",
        actor="rank-test",
    )
    ranked = physical_assembly_order(
        (invalidated, failed_assembly, contested, rejected),
        (completed, failed),
        stream,
    )
    assert ranked == (rejected, contested)
    assert ranked[0] is rejected
    assert ranked[1] is contested
    cancelled = _run(envelope, "cancelled")
    cancelled_assembly = _assembly(cancelled, envelope, 4.0)
    assert physical_assembly_order(
        (cancelled_assembly, contested),
        (cancelled, completed),
        _status((cancelled_assembly, contested)),
    ) == (contested,)


def test_missing_physical_score_is_omitted_and_rank_is_not_stored() -> None:
    envelope = _envelope()
    run = _run(envelope)
    scored = _assembly(run, envelope, 1.0)
    language_only = _assembly(
        run,
        envelope,
        9.0,
        scores=(_score(run, 9.0, channel="language"),),
    )
    join_score = _assembly(
        run,
        envelope,
        8.0,
        scores=(_score(run, 8.0, hypothesis_type="join"),),
    )
    before = scored.content_bytes()
    events = _status((scored, language_only, join_score))
    ranked = physical_assembly_order(
        (language_only, join_score, scored),
        (run,),
        events,
    )
    assert ranked == (scored,)
    assert ranked[0] is scored
    assert scored.content_bytes() == before
    assert not hasattr(scored, "rank")
    assert scored.id == content_id(scored.id_inputs())


def test_missing_status_event_is_refused() -> None:
    envelope = _envelope()
    run = _run(envelope)
    assembly = _assembly(run, envelope, 1.0)
    with pytest.raises(ValueError, match="status event"):
        physical_assembly_order((assembly,), (run,), StatusStream())


def test_a_join_in_the_list_is_refused() -> None:
    envelope = _envelope()
    run = _run(envelope)
    assembly = _assembly(run, envelope, 1.0)
    join = JoinHypothesis.create(
        run_id=run.id,
        fragment_a_id=uuid.uuid4(),
        edge_a_id=uuid.uuid4(),
        fragment_b_id=uuid.uuid4(),
        edge_b_id=uuid.uuid4(),
        transform_id=uuid.uuid4(),
        scores=(_score(run, 1.0, hypothesis_type="join"),),
        provenance_id=envelope.id,
    )
    with pytest.raises(ValueError, match="join or a reading"):
        physical_assembly_order((assembly, join), (run,), _status((assembly,)))
    assert physical_assembly_order((assembly,), (run,), _status((assembly,))) == (
        assembly,
    )


def test_an_assembly_that_cites_no_run_is_refused() -> None:
    envelope = _envelope()
    run = _run(envelope)
    assembly = AssemblyContent.create(
        page_frame_id=uuid.uuid4(),
        producer="human",
        scores=(_score(run, 1.0),),
    )
    assert assembly.run_id is None
    with pytest.raises(ValueError, match="cites its run"):
        physical_assembly_order((assembly,), (run,), _status((assembly,)))


def test_two_completed_runs_are_refused() -> None:
    first_envelope = _envelope()
    second_envelope = _envelope(b"other-source")
    first = _run(first_envelope)
    second = _run(second_envelope)
    left = _assembly(first, first_envelope, 1.0)
    right = _assembly(second, second_envelope, 2.0)
    with pytest.raises(ValueError, match="one run"):
        physical_assembly_order(
            (left, right),
            (first, second),
            _status((left, right)),
        )
