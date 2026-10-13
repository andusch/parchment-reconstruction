"""Derive join rank inside one run on the physical channel.

Rank is not a stored column. It is derived when a list is read. See the
rank paragraph under Score channels in ``docs/DATA_MODEL.md``. Inside one
``(run, hypothesis_type, channel)`` triple, a higher ``physical`` score
comes first. Equal scores are ordered by the content-derived hypothesis id,
ascending bytewise. Position in that sequence is the rank. Rank is not
written onto the join, and it is not an input to the join id.

A join whose latest status is ``rejected`` stays in the order. A join whose
latest status is ``invalidated`` is omitted. A join from a ``failed`` or
``cancelled`` run is omitted. A join with no ``physical`` score is omitted.
A join with no status event is refused. A list that also contains an
assembly or a reading is refused.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from prw.joins import JoinHypothesis
from prw.provenance import (
    AlgorithmRun,
    HypothesisStatus,
    Score,
    StatusEvent,
    StatusStream,
)

_OMITTED_RUN = frozenset({"failed", "cancelled"})


def _events(events: StatusStream | Sequence[StatusEvent]) -> tuple[StatusEvent, ...]:
    if isinstance(events, StatusStream):
        return events.events
    if isinstance(events, str | bytes) or not isinstance(events, Sequence):
        raise TypeError("Status events are a StatusStream or a sequence of events.")
    stored: list[StatusEvent] = []
    for event in events:
        if not isinstance(event, StatusEvent):
            raise TypeError("Status events are a StatusStream or a sequence of events.")
        stored.append(event)
    return tuple(stored)


def _latest_status(
    events: Sequence[StatusEvent],
) -> dict[uuid.UUID, HypothesisStatus]:
    latest: dict[uuid.UUID, HypothesisStatus] = {}
    for event in events:
        latest[event.target_id] = event.status
    return latest


def _runs(runs: Sequence[AlgorithmRun]) -> dict[uuid.UUID, AlgorithmRun]:
    if isinstance(runs, str | bytes) or not isinstance(runs, Sequence):
        raise TypeError("Runs are AlgorithmRun rows.")
    stored: dict[uuid.UUID, AlgorithmRun] = {}
    for run in runs:
        if not isinstance(run, AlgorithmRun):
            raise TypeError("Runs are AlgorithmRun rows.")
        stored[run.id] = run
    return stored


def _physical_score(join: JoinHypothesis) -> Score | None:
    found = [
        score
        for score in join.scores
        if score.channel == "physical" and score.hypothesis_type == "join"
    ]
    if not found:
        return None
    if len(found) != 1:
        raise ValueError("A join has one physical score.")
    return found[0]


def _joins(hypotheses: Sequence[object]) -> tuple[JoinHypothesis, ...]:
    if isinstance(hypotheses, str | bytes) or not isinstance(hypotheses, Sequence):
        raise TypeError("Rank reads a list of joins.")
    stored: list[JoinHypothesis] = []
    for item in hypotheses:
        if not isinstance(item, JoinHypothesis):
            raise ValueError(
                "Rank orders joins. An assembly or a reading is another list."
            )
        stored.append(item)
    return tuple(stored)


def physical_join_order(
    hypotheses: Sequence[object],
    runs: Sequence[AlgorithmRun],
    events: StatusStream | Sequence[StatusEvent],
) -> tuple[JoinHypothesis, ...]:
    """Return the physical order for joins in one completed run.

    See the rank paragraph under Score channels in ``docs/DATA_MODEL.md``.
    The returned objects are the joins that were passed in. Rank is the
    position in this sequence. A ``rejected`` join stays. An ``invalidated``
    join is omitted. The call writes nothing onto the join.
    """
    joins = _joins(hypotheses)
    by_run = _runs(runs)
    status = _latest_status(_events(events))
    eligible: list[tuple[float, JoinHypothesis]] = []
    for join in joins:
        if status.get(join.id) is None:
            raise ValueError("A join has a status event.")
        if status[join.id] == "invalidated":
            continue
        run = by_run.get(join.run_id)
        if run is None:
            raise ValueError("A join cites its run.")
        if run.status in _OMITTED_RUN:
            continue
        if run.status != "completed":
            raise ValueError("A join run is completed, failed, or cancelled.")
        score = _physical_score(join)
        if score is None:
            continue
        eligible.append((float(score.value), join))
    run_ids = {join.run_id for _, join in eligible}
    if len(run_ids) > 1:
        raise ValueError("Rank is inside one run.")
    eligible.sort(key=lambda item: (-item[0], item[1].id.bytes))
    return tuple(join for _, join in eligible)
