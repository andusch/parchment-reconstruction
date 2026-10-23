"""Derive assembly rank inside one run on the physical channel.

Rank is not a stored column. It is derived when a list is read. See the
rank paragraph under Score channels in ``docs/DATA_MODEL.md``. Inside one
``(run, hypothesis_type, channel)`` triple, a higher ``physical`` score
comes first. Equal scores are ordered by the content-derived hypothesis id,
ascending bytewise. Position in that sequence is the rank. Rank is a
reading order. It is not written onto the assembly, and it is not an input
to the assembly id.

An assembly whose latest status is ``rejected`` or ``contested`` stays in
the order. An assembly whose latest status is ``invalidated`` is omitted.
An assembly from a ``failed`` or ``cancelled`` run is omitted. An assembly
with no ``physical`` score of type ``assembly`` is omitted. An assembly
with no status event is refused. An assembly that cites no run is refused.
A list that contains a join or a reading is refused. Assemblies from more
than one run are refused.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from prw.provenance import (
    AlgorithmRun,
    AssemblyContent,
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


def _physical_score(assembly: AssemblyContent) -> Score | None:
    found = [
        score
        for score in assembly.scores
        if score.channel == "physical" and score.hypothesis_type == "assembly"
    ]
    if not found:
        return None
    if len(found) != 1:
        raise ValueError("An assembly has one physical score.")
    return found[0]


def _assemblies(hypotheses: Sequence[object]) -> tuple[AssemblyContent, ...]:
    if isinstance(hypotheses, str | bytes) or not isinstance(hypotheses, Sequence):
        raise TypeError("Rank reads a list of assemblies.")
    stored: list[AssemblyContent] = []
    for item in hypotheses:
        if not isinstance(item, AssemblyContent):
            raise ValueError(
                "Rank orders assemblies. A join or a reading is another list."
            )
        stored.append(item)
    return tuple(stored)


def physical_assembly_order(
    hypotheses: Sequence[object],
    runs: Sequence[AlgorithmRun],
    events: StatusStream | Sequence[StatusEvent],
) -> tuple[AssemblyContent, ...]:
    """Return the physical order for assemblies in one completed run.

    See the rank paragraph under Score channels in ``docs/DATA_MODEL.md``.
    The returned objects are the assemblies that were passed in. Rank is
    the position in this sequence. A ``rejected`` or ``contested`` assembly
    stays. An ``invalidated`` assembly is omitted. The call writes nothing
    onto the assembly.
    """
    assemblies = _assemblies(hypotheses)
    by_run = _runs(runs)
    status = _latest_status(_events(events))
    eligible: list[tuple[float, AssemblyContent]] = []
    for assembly in assemblies:
        if status.get(assembly.id) is None:
            raise ValueError("An assembly has a status event.")
        if status[assembly.id] == "invalidated":
            continue
        if assembly.run_id is None:
            raise ValueError("An assembly cites its run.")
        run = by_run.get(assembly.run_id)
        if run is None:
            raise ValueError("An assembly cites its run.")
        if run.status in _OMITTED_RUN:
            continue
        if run.status != "completed":
            raise ValueError("An assembly run is completed, failed, or cancelled.")
        score = _physical_score(assembly)
        if score is None:
            continue
        eligible.append((float(score.value), assembly))
    run_ids = {assembly.run_id for _, assembly in eligible}
    if len(run_ids) > 1:
        raise ValueError("Rank is inside one run.")
    eligible.sort(key=lambda item: (-item[0], item[1].id.bytes))
    return tuple(assembly for _, assembly in eligible)
