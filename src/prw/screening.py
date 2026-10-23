"""In-memory screening events for a hypothesis a gate has seen.

``ScreeningEvent`` follows ``docs/DATA_MODEL.md``. The id is a UUIDv5 over
the array ``run_id``, ``hypothesis_id``, ``gate``, and ``outcome``, in that
order. ``gate`` is ``physical``, ``language``, or ``human``. ``outcome`` is
``admitted`` or ``excluded``. An exclusion is a stored outcome. A missing
event means the gate did not see that hypothesis. Admission is a stored
gate outcome. The event records no ``ValidationDecision`` and assigns no
epistemic class.

The row has no status column, no epistemic class, and no score. The log
does not rewrite the hypothesis the event cites. This module does not
decide which hypotheses a gate admits.

These records are internal. They are not a stable public API, and they
do not write a project directory.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from prw.identity import content_id

Gate = Literal["physical", "language", "human"]
Outcome = Literal["admitted", "excluded"]


def _require_uuid(value: object, label: str) -> uuid.UUID:
    if not isinstance(value, uuid.UUID):
        raise TypeError(f"{label} is a UUID.")
    return value


def _gate(value: object) -> Gate:
    if value == "physical" or value == "language" or value == "human":
        return value
    raise ValueError("gate is physical, language, or human.")


def _outcome(value: object) -> Outcome:
    if value == "admitted" or value == "excluded":
        return value
    raise ValueError("outcome is admitted or excluded.")


@dataclass(frozen=True, slots=True)
class ScreeningEvent:
    """One gate outcome for one hypothesis.

    See ``ScreeningEvent`` in ``docs/DATA_MODEL.md``. The id is a UUIDv5
    over ``run_id``, ``hypothesis_id``, ``gate``, and ``outcome``. An
    exclusion is a stored outcome. A missing event means the gate did not
    see that hypothesis. The row has no status column and no score.
    """

    run_id: uuid.UUID
    hypothesis_id: uuid.UUID
    gate: Gate
    outcome: Outcome
    id: uuid.UUID

    @classmethod
    def create(
        cls,
        *,
        run_id: uuid.UUID,
        hypothesis_id: uuid.UUID,
        gate: str,
        outcome: str,
    ) -> ScreeningEvent:
        """Build a screening event and its content-derived id."""
        stored_run = _require_uuid(run_id, "run_id")
        stored_hypothesis = _require_uuid(hypothesis_id, "hypothesis_id")
        stored_gate = _gate(gate)
        stored_outcome = _outcome(outcome)
        return cls(
            run_id=stored_run,
            hypothesis_id=stored_hypothesis,
            gate=stored_gate,
            outcome=stored_outcome,
            id=content_id([stored_run, stored_hypothesis, stored_gate, stored_outcome]),
        )

    def id_inputs(self) -> list[uuid.UUID | str]:
        """``run_id``, ``hypothesis_id``, ``gate``, then ``outcome``."""
        return [self.run_id, self.hypothesis_id, self.gate, self.outcome]

    def __post_init__(self) -> None:
        _require_uuid(self.run_id, "run_id")
        _require_uuid(self.hypothesis_id, "hypothesis_id")
        _gate(self.gate)
        _outcome(self.outcome)
        if self.id != content_id(self.id_inputs()):
            raise ValueError("ScreeningEvent.id does not match its id inputs.")


class ScreeningLog:
    """Append-only ``ScreeningEvent`` rows.

    A second event with the same id is refused. The log stores the event
    and leaves the cited hypothesis as it was. A missing event means the
    gate did not see that hypothesis.
    """

    def __init__(self) -> None:
        self._rows: list[ScreeningEvent] = []

    @property
    def rows(self) -> tuple[ScreeningEvent, ...]:
        return tuple(self._rows)

    def by_id(self, event_id: uuid.UUID) -> ScreeningEvent:
        """Return the stored event. A missing id was not recorded."""
        for row in self._rows:
            if row.id == event_id:
                return row
        raise KeyError("No ScreeningEvent has that id.")

    def append(self, event: ScreeningEvent) -> ScreeningEvent:
        """Store ``event``. A second append of the same id is refused."""
        if not isinstance(event, ScreeningEvent):
            raise TypeError("append stores a screening event.")
        if any(stored.id == event.id for stored in self._rows):
            raise ValueError("A screening event id is stored once.")
        self._rows.append(event)
        return event
