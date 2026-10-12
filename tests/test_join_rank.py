"""Synthetic in-memory joins with caller-supplied physical scores."""

import uuid

import pytest

from prw.identity import hash_value
from prw.join_rank import physical_join_order
from prw.joins import JoinHypothesis
from prw.provenance import (
    AlgorithmRun,
    AssemblyContent,
    ProvenanceEnvelope,
    Score,
    StatusStream,
)

_RECORDED = "2020-01-01T00:00:00Z"


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


def _run(envelope: ProvenanceEnvelope, status: str = "completed") -> AlgorithmRun:
    return AlgorithmRun.create(
        envelope,
        status=status,  # type: ignore[arg-type]
        started_at=_RECORDED,
    )


def _join(
    run: AlgorithmRun,
    envelope: ProvenanceEnvelope,
    value: float,
) -> JoinHypothesis:
    return JoinHypothesis.create(
        run_id=run.id,
        fragment_a_id=uuid.uuid4(),
        edge_a_id=uuid.uuid4(),
        fragment_b_id=uuid.uuid4(),
        edge_b_id=uuid.uuid4(),
        transform_id=uuid.uuid4(),
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


def _status(
    joins: tuple[JoinHypothesis, ...],
    status: str = "proposed",
) -> StatusStream:
    stream = StatusStream()
    for join in joins:
        stream.append(
            target_id=join.id,
            status="proposed",
            recorded_at=_RECORDED,
            actor="rank-test",
        )
        if status != "proposed":
            stream.append(
                target_id=join.id,
                status=status,  # type: ignore[arg-type]
                recorded_at="2020-01-01T00:00:01Z",
                actor="rank-test",
            )
    return stream


def test_higher_score_precedes_and_equal_scores_follow_id_bytes() -> None:
    envelope = _envelope()
    run = _run(envelope)
    low = _join(run, envelope, -5.0)
    tied_left = _join(run, envelope, -1.0)
    tied_right = _join(run, envelope, -1.0)
    high = _join(run, envelope, -0.25)
    joins = (low, tied_right, high, tied_left)
    ranked = physical_join_order(joins, (run,), _status(joins))
    tied = tuple(sorted((tied_left, tied_right), key=lambda join: join.id.bytes))
    assert ranked == (high, *tied, low)
    assert ranked[0] is high
    assert [join.id for join in ranked[1:3]] == [join.id for join in tied]


def test_invalidated_and_failed_runs_are_omitted_and_rejected_stays() -> None:
    envelope = _envelope()
    completed = _run(envelope)
    failed = _run(envelope, "failed")
    kept = _join(completed, envelope, -2.0)
    rejected = _join(completed, envelope, -0.5)
    invalidated = _join(completed, envelope, 3.0)
    failed_join = _join(failed, envelope, 9.0)
    stream = StatusStream()
    for join in (kept, rejected, invalidated, failed_join):
        stream.append(
            target_id=join.id,
            status="proposed",
            recorded_at=_RECORDED,
            actor="rank-test",
        )
    stream.append(
        target_id=rejected.id,
        status="rejected",
        recorded_at="2020-01-01T00:00:01Z",
        actor="rank-test",
    )
    stream.append(
        target_id=invalidated.id,
        status="invalidated",
        recorded_at="2020-01-01T00:00:02Z",
        actor="rank-test",
    )
    ranked = physical_join_order(
        (invalidated, failed_join, kept, rejected),
        (completed, failed),
        stream,
    )
    assert ranked == (rejected, kept)
    cancelled = _run(envelope, "cancelled")
    cancelled_join = _join(cancelled, envelope, 4.0)
    cancelled_events = _status((cancelled_join, kept))
    assert physical_join_order(
        (cancelled_join, kept),
        (cancelled, completed),
        cancelled_events,
    ) == (kept,)


def test_missing_physical_score_is_omitted_and_rank_is_not_stored() -> None:
    envelope = _envelope()
    run = _run(envelope)
    scored = _join(run, envelope, 1.0)
    unscored = _join(run, envelope, 2.0)
    object.__setattr__(unscored, "scores", ())
    before = scored.id
    events = _status((unscored, scored))
    ranked = physical_join_order((unscored, scored), (run,), events)
    assert ranked == (scored,)
    assert ranked[0] is scored
    assert scored.id == before
    assert not hasattr(scored, "rank")
    repeated = physical_join_order((unscored, scored), (run,), events)
    assert [join.id for join in repeated] == [before]


def test_missing_status_event_is_refused() -> None:
    envelope = _envelope()
    run = _run(envelope)
    join = _join(run, envelope, 1.0)
    with pytest.raises(ValueError, match="status event"):
        physical_join_order((join,), (run,), StatusStream())


def test_mixed_hypothesis_types_are_refused() -> None:
    envelope = _envelope()
    run = _run(envelope)
    join = _join(run, envelope, 1.0)
    assembly = AssemblyContent.create(page_frame_id=uuid.uuid4(), producer="machine")
    with pytest.raises(ValueError, match="assembly or a reading"):
        physical_join_order((join, assembly), (run,), _status((join,)))
    assert join.id == physical_join_order((join,), (run,), _status((join,)))[0].id


def test_two_completed_runs_are_refused() -> None:
    first_envelope = _envelope()
    second_envelope = ProvenanceEnvelope.create(
        source_hashes=(hash_value(b"other-source"),),
        parameters={"clearance": 0.2},
        algorithm_name="joins",
        algorithm_version="1",
        code_version="abc123",
        decoder_name="tiff",
        decoder_version="1",
    )
    first = _run(first_envelope)
    second = _run(second_envelope)
    left = _join(first, first_envelope, 1.0)
    right = _join(second, second_envelope, 2.0)
    with pytest.raises(ValueError, match="one run"):
        physical_join_order((left, right), (first, second), _status((left, right)))
