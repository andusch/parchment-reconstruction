"""In-memory page placements and assembly hypotheses.

``placement_pose`` returns a ``RigidTransform`` whose source is
``fragment_local_mm`` and whose destination is ``page_global_mm``. See
``RigidTransform`` and ``AssemblyHypothesis`` in ``docs/DATA_MODEL.md``.
The pose stores rotation and translation. Its epistemic class is
``hypothesis`` and its producer is ``machine``. The id is a UUIDv5 over
that content. The caller supplies ``provenance_id``. ``RigidTransform.create``
remains the join-pose rule and still accepts only two fragment-local frames.

``AssemblyLog`` stores an ``AssemblyContent`` row and appends its first
``StatusEvent`` in the same write. The content row has no status column.
The event is ``proposed``, or ``rejected`` when the write is a machine
rejection.

These records are internal. They are not a stable public API, and they
do not write a project directory. No assembly is searched.
"""

from __future__ import annotations

import math
import uuid
from typing import Any, Literal

from prw.frames import CoordinateFrame
from prw.identity import content_id
from prw.joins import RigidTransform
from prw.provenance import (
    AssemblyContent,
    StatusEvent,
    StatusStream,
    insert_hypothesis,
)


def _require_uuid(value: object, label: str) -> uuid.UUID:
    if not isinstance(value, uuid.UUID):
        raise TypeError(f"{label} is a UUID.")
    return value


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{label} is a finite number.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} is a finite number.")
    return number


def _source_frame(frame: object) -> CoordinateFrame:
    if not isinstance(frame, CoordinateFrame):
        raise TypeError("A placement source is a coordinate frame.")
    if frame.kind != "fragment_local_mm":
        raise ValueError("A placement source is fragment_local_mm.")
    return frame


def _page_frame(frame: object) -> CoordinateFrame:
    if not isinstance(frame, CoordinateFrame):
        raise TypeError("A placement destination is a coordinate frame.")
    if frame.kind != "page_global_mm":
        raise ValueError("A placement destination is page_global_mm.")
    return frame


def placement_pose(
    *,
    from_frame: CoordinateFrame,
    to_frame: CoordinateFrame,
    rotation_radians: object,
    translation_x: object,
    translation_y: object,
    provenance_id: uuid.UUID,
    producer: str = "machine",
    epistemic_class: str = "hypothesis",
) -> RigidTransform:
    """Build a machine placement from a fragment frame into the page frame.

    The source kind is ``fragment_local_mm``. The destination kind is
    ``page_global_mm``. A pixel frame, a fragment-local destination, or a
    page-frame source is rejected. A class other than ``hypothesis`` is
    rejected. A producer other than ``machine`` is rejected. The pose has
    no scale field.
    """
    if epistemic_class != "hypothesis":
        raise ValueError("A placement pose's epistemic class is hypothesis.")
    if producer != "machine":
        raise ValueError("A machine placement has producer machine.")
    stored_from = _source_frame(from_frame)
    stored_to = _page_frame(to_frame)
    stored_rotation = _finite(rotation_radians, "rotation_radians")
    stored_x = _finite(translation_x, "translation_x")
    stored_y = _finite(translation_y, "translation_y")
    stored_provenance = _require_uuid(provenance_id, "provenance_id")
    stored_producer: Literal["machine"] = "machine"
    content: dict[str, Any] = {
        "from_frame_id": stored_from.id,
        "to_frame_id": stored_to.id,
        "rotation_radians": stored_rotation,
        "translation_x": stored_x,
        "translation_y": stored_y,
        "producer": stored_producer,
        "epistemic_class": "hypothesis",
        "provenance_id": stored_provenance,
    }
    return RigidTransform(
        from_frame_id=stored_from.id,
        to_frame_id=stored_to.id,
        rotation_radians=stored_rotation,
        translation_x=stored_x,
        translation_y=stored_y,
        producer=stored_producer,
        epistemic_class="hypothesis",
        provenance_id=stored_provenance,
        id=content_id(content),
    )


class AssemblyLog:
    """Append-only ``AssemblyContent`` rows for a page hypothesis.

    ``insert`` appends the first ``StatusEvent`` in the same write. See
    ``AssemblyHypothesis`` and the insert rule under ``StatusEvent`` in
    ``docs/DATA_MODEL.md``. The content row has no status column.
    """

    def __init__(self) -> None:
        self._rows: list[AssemblyContent] = []

    @property
    def rows(self) -> tuple[AssemblyContent, ...]:
        return tuple(self._rows)

    def by_id(self, assembly_id: uuid.UUID) -> AssemblyContent:
        """Return the stored assembly. The content is the content that was inserted."""
        for row in self._rows:
            if row.id == assembly_id:
                return row
        raise KeyError("No AssemblyContent has that id.")

    def insert(
        self,
        stream: StatusStream,
        assembly: AssemblyContent,
        *,
        recorded_at: str,
        actor: str,
        machine_rejection: bool = False,
    ) -> StatusEvent:
        """Store ``assembly`` and append its first status event in the same write.

        The event is ``proposed``, or ``rejected`` when this write is a machine
        rejection. A second insert of the same id is refused. The assembly
        object is not modified.
        """
        if not isinstance(assembly, AssemblyContent):
            raise TypeError("insert stores an assembly.")
        if any(stored.id == assembly.id for stored in self._rows):
            raise ValueError("An assembly is inserted once.")
        event = insert_hypothesis(
            stream,
            assembly,
            recorded_at=recorded_at,
            actor=actor,
            machine_rejection=machine_rejection,
        )
        self._rows.append(assembly)
        return event
