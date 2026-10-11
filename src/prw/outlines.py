"""In-memory fragment identities and machine outline revisions.

``Fragment`` and ``FragmentOutlineRevision`` follow ``docs/DATA_MODEL.md``.
A detector outline is epistemic class ``interpretation`` with producer
``machine``. The outline id is a UUIDv5 over the run id and the polygon.
``operator_id`` and ``session_id`` are absent. Inserting a
``FragmentOutlineRevision`` appends one ``StatusEvent`` in the same write.
That event is ``proposed``, unless the same write is a machine rejection,
in which case the event is ``rejected``. The outline row has no status
column. A later polygon is a new row with ``supersedes_id``. The previous
row stays.

These records are internal. They are not a stable public API, and they do
not write a project directory.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from prw.identity import content_id
from prw.provenance import StatusEvent, StatusStream

type Point = tuple[float, float]


def _coordinate(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("A vertex coordinate is a finite number.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("A vertex coordinate is a finite number.")
    return number


def _point(value: object) -> Point:
    if isinstance(value, str | bytes) or not isinstance(value, Sequence):
        raise TypeError("A vertex is an x and a y.")
    if len(value) != 2:
        raise ValueError("A vertex is an x and a y.")
    x, y = value
    return (_coordinate(x), _coordinate(y))


def _polygon(vertices: Sequence[object]) -> tuple[Point, ...]:
    if isinstance(vertices, str | bytes):
        raise TypeError("A polygon is ordered vertices.")
    points = tuple(_point(vertex) for vertex in vertices)
    if len(points) < 3:
        raise ValueError("A polygon has at least three vertices.")
    return points


def _require_uuid(value: object, label: str) -> uuid.UUID:
    if not isinstance(value, uuid.UUID):
        raise TypeError(f"{label} is a UUID.")
    return value


def _require_label(value: object) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError("A fragment label is an opaque label.")
    return value


@dataclass(frozen=True, slots=True)
class Fragment:
    """Identity of one physical piece. The label is not a reconstruction.

    The id is a UUIDv5 over the caller-supplied project id and the opaque
    label. See ``Fragment`` in ``docs/DATA_MODEL.md``. A machine-proposed
    fragment has ``identification_status`` ``detected``.
    """

    project_id: uuid.UUID
    label: str
    identification_status: Literal["detected"]
    id: uuid.UUID

    @classmethod
    def create(cls, *, project_id: uuid.UUID, label: str) -> Fragment:
        """Build a machine-proposed fragment with status ``detected``."""
        stored_project = _require_uuid(project_id, "project_id")
        stored_label = _require_label(label)
        return cls(
            project_id=stored_project,
            label=stored_label,
            identification_status="detected",
            id=content_id([stored_project, stored_label]),
        )

    def id_inputs(self) -> list[Any]:
        """Project id, then the opaque label. Status is not an id input."""
        return [self.project_id, self.label]

    def __post_init__(self) -> None:
        _require_uuid(self.project_id, "project_id")
        _require_label(self.label)
        if self.identification_status != "detected":
            raise ValueError(
                "A machine-proposed fragment has identification_status detected."
            )
        if self.id != content_id(self.id_inputs()):
            raise ValueError("Fragment.id does not match the project id and label.")


@dataclass(frozen=True, slots=True)
class FragmentOutlineRevision:
    """One polygon revision in a named frame.

    See ``FragmentOutlineRevision`` in ``docs/DATA_MODEL.md``. The epistemic
    class is ``interpretation`` and the producer is ``machine``. ``run_id``
    is set. ``operator_id`` and ``session_id`` are absent. The id is a
    UUIDv5 over the run id and the polygon. The row has no status column.
    """

    fragment_id: uuid.UUID
    frame_id: uuid.UUID
    polygon: tuple[Point, ...]
    producer: Literal["machine"]
    run_id: uuid.UUID
    epistemic_class: Literal["interpretation"]
    provenance_id: uuid.UUID
    supersedes_id: uuid.UUID | None
    id: uuid.UUID

    @classmethod
    def create(
        cls,
        *,
        fragment_id: uuid.UUID,
        frame_id: uuid.UUID,
        polygon: Sequence[object],
        run_id: uuid.UUID,
        provenance_id: uuid.UUID,
        producer: str = "machine",
        epistemic_class: str = "interpretation",
        supersedes_id: uuid.UUID | None = None,
    ) -> FragmentOutlineRevision:
        """Build one immutable outline. A different class is rejected."""
        if epistemic_class != "interpretation":
            raise ValueError("A detector outline's epistemic class is interpretation.")
        if producer != "machine":
            raise ValueError("A detector outline has producer machine.")
        stored_fragment = _require_uuid(fragment_id, "fragment_id")
        stored_frame = _require_uuid(frame_id, "frame_id")
        stored_run = _require_uuid(run_id, "run_id")
        stored_provenance = _require_uuid(provenance_id, "provenance_id")
        stored_polygon = _polygon(polygon)
        stored_supersedes = (
            None
            if supersedes_id is None
            else _require_uuid(supersedes_id, "supersedes_id")
        )
        revision_id = content_id([stored_run, stored_polygon])
        if stored_supersedes == revision_id:
            raise ValueError("supersedes_id cites a previous outline revision.")
        return cls(
            fragment_id=stored_fragment,
            frame_id=stored_frame,
            polygon=stored_polygon,
            producer="machine",
            run_id=stored_run,
            epistemic_class="interpretation",
            provenance_id=stored_provenance,
            supersedes_id=stored_supersedes,
            id=revision_id,
        )

    def supersede(
        self,
        polygon: Sequence[object],
        *,
        run_id: uuid.UUID | None = None,
        provenance_id: uuid.UUID | None = None,
    ) -> FragmentOutlineRevision:
        """Return a new revision. This polygon stays as it was.

        The new row stores ``supersedes_id`` pointing at this id. See
        ``FragmentOutlineRevision`` in ``docs/DATA_MODEL.md``.
        """
        return FragmentOutlineRevision.create(
            fragment_id=self.fragment_id,
            frame_id=self.frame_id,
            polygon=polygon,
            run_id=self.run_id if run_id is None else run_id,
            provenance_id=(
                self.provenance_id if provenance_id is None else provenance_id
            ),
            supersedes_id=self.id,
        )

    def id_inputs(self) -> list[Any]:
        """Run id, then the polygon. The id is not the rest of the row."""
        return [self.run_id, self.polygon]

    def __post_init__(self) -> None:
        if self.epistemic_class != "interpretation":
            raise ValueError("A detector outline's epistemic class is interpretation.")
        if self.producer != "machine":
            raise ValueError("A detector outline has producer machine.")
        if self.supersedes_id == self.id:
            raise ValueError("supersedes_id cites a previous outline revision.")
        if self.id != content_id(self.id_inputs()):
            raise ValueError(
                "FragmentOutlineRevision.id does not match the run id and polygon."
            )


class OutlineRevisionLog:
    """Append-only ``FragmentOutlineRevision`` rows.

    ``insert`` appends the first ``StatusEvent`` in the same write. See the
    insert rule for ``FragmentOutlineRevision`` under ``StatusEvent`` in
    ``docs/DATA_MODEL.md``. The current status is that event stream. It is
    not a column on the outline.
    """

    def __init__(self) -> None:
        self._rows: list[FragmentOutlineRevision] = []

    @property
    def rows(self) -> tuple[FragmentOutlineRevision, ...]:
        return tuple(self._rows)

    def by_id(self, revision_id: uuid.UUID) -> FragmentOutlineRevision:
        """Return the stored revision. The polygon is the one that was inserted."""
        for row in self._rows:
            if row.id == revision_id:
                return row
        raise KeyError("No FragmentOutlineRevision has that id.")

    def insert(
        self,
        stream: StatusStream,
        outline: FragmentOutlineRevision,
        *,
        recorded_at: str,
        actor: str,
    ) -> StatusEvent:
        """Store ``outline`` and append ``proposed`` in the same write.

        This write is not a machine rejection, so the event is ``proposed``.
        See the ``FragmentOutlineRevision`` insert rule under ``StatusEvent``
        in ``docs/DATA_MODEL.md``. The outline object is not modified.
        """
        if not isinstance(outline, FragmentOutlineRevision):
            raise TypeError("insert stores a FragmentOutlineRevision.")
        if any(row.id == outline.id for row in self._rows):
            raise ValueError(
                "An outline revision is inserted once. A later polygon is a new row."
            )
        if outline.supersedes_id is not None and not any(
            row.id == outline.supersedes_id for row in self._rows
        ):
            raise ValueError("supersedes_id cites a stored outline revision.")
        if stream.current_status(outline.id) is not None:
            raise ValueError(
                "An outline revision is inserted once, with its first status event."
            )
        event = stream.append(
            target_id=outline.id,
            status="proposed",
            recorded_at=recorded_at,
            actor=actor,
        )
        self._rows.append(outline)
        return event
