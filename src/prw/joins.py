"""In-memory edge arcs, rigid poses, and pairwise joins.

``EdgeArc``, ``RigidTransform``, and ``JoinHypothesis`` follow
``docs/DATA_MODEL.md``. A machine edge is epistemic class ``interpretation``
with producer ``machine``. Its frame is ``fragment_local_mm``. A machine pose
and a pairwise join are epistemic class ``hypothesis``. The pose stores
rotation and translation. The join cites two fragments, two edges, that pose,
and one ``physical`` score for hypothesis type ``join``. The score is an
uncalibrated ranking feature. See the score channels in ``docs/DATA_MODEL.md``
and ``docs/adr/0009-separate-score-channels.md``. Status is an append-only
``StatusEvent`` under ``docs/adr/0006-append-only-hypotheses.md``. The content
rows have no status column.

These records are internal. They are not a stable public API, and they do
not write a project directory.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from prw.frames import CoordinateFrame
from prw.identity import canonical_json_bytes, content_id
from prw.provenance import HypothesisStatus, Score, StatusEvent, StatusStream

type Point = tuple[float, float]


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


def _point(value: object) -> Point:
    if isinstance(value, str | bytes) or not isinstance(value, Sequence):
        raise TypeError("A vertex is an x and a y.")
    if len(value) != 2:
        raise ValueError("A vertex is an x and a y.")
    x_coord, y_coord = value
    return (
        _finite(x_coord, "A vertex coordinate"),
        _finite(y_coord, "A vertex coordinate"),
    )


def _geometry(vertices: Sequence[object]) -> tuple[Point, ...]:
    if isinstance(vertices, str | bytes):
        raise TypeError("An edge geometry is ordered vertices.")
    points = tuple(_point(vertex) for vertex in vertices)
    if len(points) < 2:
        raise ValueError("An edge geometry has at least two vertices.")
    return points


def _local_frame(frame: object, label: str) -> CoordinateFrame:
    if not isinstance(frame, CoordinateFrame):
        raise TypeError(f"{label} is a coordinate frame.")
    if frame.kind != "fragment_local_mm":
        raise ValueError(f"{label} is fragment_local_mm.")
    return frame


def _machine_producer(producer: str, label: str) -> Literal["machine"]:
    if producer != "machine":
        raise ValueError(f"{label} has producer machine.")
    return "machine"


@dataclass(frozen=True, slots=True)
class EdgeArc:
    """One edge on an outline revision. Geometry is in ``fragment_local_mm``.

    See ``EdgeArc`` in ``docs/DATA_MODEL.md``. The id is a UUIDv5 over the
    run id, the outline revision id, and the edge geometry. ``operator_id``
    and ``session_id`` are absent. The row has no status column.
    """

    outline_revision_id: uuid.UUID
    frame_id: uuid.UUID
    geometry: tuple[Point, ...]
    producer: Literal["machine"]
    run_id: uuid.UUID
    epistemic_class: Literal["interpretation"]
    provenance_id: uuid.UUID
    id: uuid.UUID

    @classmethod
    def create(
        cls,
        *,
        outline_revision_id: uuid.UUID,
        frame: CoordinateFrame,
        geometry: Sequence[object],
        run_id: uuid.UUID,
        provenance_id: uuid.UUID,
        producer: str = "machine",
        epistemic_class: str = "interpretation",
    ) -> EdgeArc:
        """Build a machine edge. A class other than ``interpretation`` is rejected."""
        if epistemic_class != "interpretation":
            raise ValueError("An edge's epistemic class is interpretation.")
        stored_outline = _require_uuid(outline_revision_id, "outline_revision_id")
        stored_frame = _local_frame(frame, "An edge frame")
        stored_geometry = _geometry(geometry)
        stored_run = _require_uuid(run_id, "run_id")
        stored_provenance = _require_uuid(provenance_id, "provenance_id")
        return cls(
            outline_revision_id=stored_outline,
            frame_id=stored_frame.id,
            geometry=stored_geometry,
            producer=_machine_producer(producer, "A machine edge"),
            run_id=stored_run,
            epistemic_class="interpretation",
            provenance_id=stored_provenance,
            id=content_id([stored_run, stored_outline, stored_geometry]),
        )

    def id_inputs(self) -> list[Any]:
        """Run id, outline revision id, then the edge geometry."""
        return [self.run_id, self.outline_revision_id, self.geometry]

    def __post_init__(self) -> None:
        _require_uuid(self.outline_revision_id, "outline_revision_id")
        _require_uuid(self.frame_id, "frame_id")
        _require_uuid(self.run_id, "run_id")
        _require_uuid(self.provenance_id, "provenance_id")
        if self.epistemic_class != "interpretation":
            raise ValueError("An edge's epistemic class is interpretation.")
        if self.producer != "machine":
            raise ValueError("A machine edge has producer machine.")
        _geometry(self.geometry)
        if self.id != content_id(self.id_inputs()):
            raise ValueError("EdgeArc.id does not match its id inputs.")


@dataclass(frozen=True, slots=True)
class RigidTransform:
    """A join pose: rotation and translation between two fragment frames.

    See ``RigidTransform`` in ``docs/DATA_MODEL.md``. Both frames are
    ``fragment_local_mm``. Uniform scale lives on ``CalibrationTransform``.
    The id is a UUIDv5 over the canonical content of this record. The row
    has no status column.
    """

    from_frame_id: uuid.UUID
    to_frame_id: uuid.UUID
    rotation_radians: float
    translation_x: float
    translation_y: float
    producer: Literal["machine"]
    epistemic_class: Literal["hypothesis"]
    provenance_id: uuid.UUID
    id: uuid.UUID

    @classmethod
    def create(
        cls,
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
        """Build a machine join pose.

        A frame other than ``fragment_local_mm`` is rejected.
        """
        if epistemic_class != "hypothesis":
            raise ValueError("A rigid pose's epistemic class is hypothesis.")
        stored_from = _local_frame(from_frame, "A join pose frame")
        stored_to = _local_frame(to_frame, "The destination frame")
        stored_rotation = _finite(rotation_radians, "rotation_radians")
        stored_x = _finite(translation_x, "translation_x")
        stored_y = _finite(translation_y, "translation_y")
        stored_provenance = _require_uuid(provenance_id, "provenance_id")
        stored_producer = _machine_producer(producer, "A machine pose")
        content = {
            "from_frame_id": stored_from.id,
            "to_frame_id": stored_to.id,
            "rotation_radians": stored_rotation,
            "translation_x": stored_x,
            "translation_y": stored_y,
            "producer": stored_producer,
            "epistemic_class": "hypothesis",
            "provenance_id": stored_provenance,
        }
        return cls(
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

    def content_mapping(self) -> dict[str, Any]:
        """Canonical content. ``id`` is not an input."""
        return {
            "from_frame_id": self.from_frame_id,
            "to_frame_id": self.to_frame_id,
            "rotation_radians": self.rotation_radians,
            "translation_x": self.translation_x,
            "translation_y": self.translation_y,
            "producer": self.producer,
            "epistemic_class": self.epistemic_class,
            "provenance_id": self.provenance_id,
        }

    def __post_init__(self) -> None:
        _require_uuid(self.from_frame_id, "from_frame_id")
        _require_uuid(self.to_frame_id, "to_frame_id")
        _require_uuid(self.provenance_id, "provenance_id")
        _finite(self.rotation_radians, "rotation_radians")
        _finite(self.translation_x, "translation_x")
        _finite(self.translation_y, "translation_y")
        if self.epistemic_class != "hypothesis":
            raise ValueError("A rigid pose's epistemic class is hypothesis.")
        if self.producer != "machine":
            raise ValueError("A machine pose has producer machine.")
        if self.id != content_id(self.content_mapping()):
            raise ValueError("RigidTransform.id does not match its content.")


@dataclass(frozen=True, slots=True)
class JoinHypothesis:
    """A pairwise join candidate. The row has no status column.

    See ``JoinHypothesis`` in ``docs/DATA_MODEL.md``. The epistemic class is
    ``hypothesis``. The id is a UUIDv5 over the run id and the hypothesis
    content when ``run_id`` is set. The score channel is ``physical``.
    """

    run_id: uuid.UUID
    fragment_a_id: uuid.UUID
    edge_a_id: uuid.UUID
    fragment_b_id: uuid.UUID
    edge_b_id: uuid.UUID
    transform_id: uuid.UUID
    producer: Literal["machine"]
    scores: tuple[Score, ...]
    provenance_id: uuid.UUID
    epistemic_class: Literal["hypothesis"]
    id: uuid.UUID

    @classmethod
    def create(
        cls,
        *,
        run_id: uuid.UUID,
        fragment_a_id: uuid.UUID,
        edge_a_id: uuid.UUID,
        fragment_b_id: uuid.UUID,
        edge_b_id: uuid.UUID,
        transform_id: uuid.UUID,
        scores: Sequence[Score],
        provenance_id: uuid.UUID,
        producer: str = "machine",
        epistemic_class: str = "hypothesis",
    ) -> JoinHypothesis:
        """Build a machine pairwise join. A third fragment id has no field."""
        if epistemic_class != "hypothesis":
            raise ValueError("A join's epistemic class is hypothesis.")
        stored_run = _require_uuid(run_id, "run_id")
        stored_fragment_a = _require_uuid(fragment_a_id, "fragment_a_id")
        stored_edge_a = _require_uuid(edge_a_id, "edge_a_id")
        stored_fragment_b = _require_uuid(fragment_b_id, "fragment_b_id")
        stored_edge_b = _require_uuid(edge_b_id, "edge_b_id")
        stored_transform = _require_uuid(transform_id, "transform_id")
        stored_provenance = _require_uuid(provenance_id, "provenance_id")
        if stored_fragment_a == stored_fragment_b:
            raise ValueError("A join cites two distinct fragment ids.")
        if stored_edge_a == stored_edge_b:
            raise ValueError("A join cites two distinct edge ids.")
        stored_scores = _one_physical_score(scores, stored_run)
        stored_producer = _machine_producer(producer, "A machine join")
        content = _join_content(
            fragment_a_id=stored_fragment_a,
            edge_a_id=stored_edge_a,
            fragment_b_id=stored_fragment_b,
            edge_b_id=stored_edge_b,
            transform_id=stored_transform,
            producer=stored_producer,
            scores=stored_scores,
            provenance_id=stored_provenance,
        )
        return cls(
            run_id=stored_run,
            fragment_a_id=stored_fragment_a,
            edge_a_id=stored_edge_a,
            fragment_b_id=stored_fragment_b,
            edge_b_id=stored_edge_b,
            transform_id=stored_transform,
            producer=stored_producer,
            scores=stored_scores,
            provenance_id=stored_provenance,
            epistemic_class="hypothesis",
            id=content_id([stored_run, content]),
        )

    def content_mapping(self) -> dict[str, Any]:
        """Hypothesis content. ``id`` and ``run_id`` are not in this object."""
        return _join_content(
            fragment_a_id=self.fragment_a_id,
            edge_a_id=self.edge_a_id,
            fragment_b_id=self.fragment_b_id,
            edge_b_id=self.edge_b_id,
            transform_id=self.transform_id,
            producer=self.producer,
            scores=self.scores,
            provenance_id=self.provenance_id,
        )

    def id_inputs(self) -> list[Any]:
        """Run id, then the hypothesis content."""
        return [self.run_id, self.content_mapping()]

    def content_bytes(self) -> bytes:
        """Canonical bytes of the hypothesis content."""
        return canonical_json_bytes(self.content_mapping())

    def __post_init__(self) -> None:
        _require_uuid(self.run_id, "run_id")
        _require_uuid(self.fragment_a_id, "fragment_a_id")
        _require_uuid(self.edge_a_id, "edge_a_id")
        _require_uuid(self.fragment_b_id, "fragment_b_id")
        _require_uuid(self.edge_b_id, "edge_b_id")
        _require_uuid(self.transform_id, "transform_id")
        _require_uuid(self.provenance_id, "provenance_id")
        if self.fragment_a_id == self.fragment_b_id:
            raise ValueError("A join cites two distinct fragment ids.")
        if self.edge_a_id == self.edge_b_id:
            raise ValueError("A join cites two distinct edge ids.")
        if self.epistemic_class != "hypothesis":
            raise ValueError("A join's epistemic class is hypothesis.")
        if self.producer != "machine":
            raise ValueError("A machine join has producer machine.")
        _one_physical_score(self.scores, self.run_id)
        if self.id != content_id(self.id_inputs()):
            raise ValueError("JoinHypothesis.id does not match its content.")


def _one_physical_score(
    scores: Sequence[object], run_id: uuid.UUID
) -> tuple[Score, ...]:
    if isinstance(scores, str | bytes):
        raise TypeError("scores entries are Score records.")
    stored = tuple(scores)
    if len(stored) != 1 or not isinstance(stored[0], Score):
        raise ValueError(
            "A join stores one score, with channel physical and hypothesis type join."
        )
    score = stored[0]
    if score.channel != "physical" or score.hypothesis_type != "join":
        raise ValueError(
            "A join stores one score, with channel physical and hypothesis type join."
        )
    if score.run_id != run_id:
        raise ValueError("A join score cites the join run.")
    return (score,)


def _join_content(
    *,
    fragment_a_id: uuid.UUID,
    edge_a_id: uuid.UUID,
    fragment_b_id: uuid.UUID,
    edge_b_id: uuid.UUID,
    transform_id: uuid.UUID,
    producer: Literal["machine"],
    scores: tuple[Score, ...],
    provenance_id: uuid.UUID,
) -> dict[str, Any]:
    return {
        "fragment_a_id": fragment_a_id,
        "edge_a_id": edge_a_id,
        "fragment_b_id": fragment_b_id,
        "edge_b_id": edge_b_id,
        "transform_id": transform_id,
        "producer": producer,
        "epistemic_class": "hypothesis",
        "scores": [
            {
                "value": item.value,
                "run_id": item.run_id,
                "channel": item.channel,
                "hypothesis_type": item.hypothesis_type,
            }
            for item in scores
        ],
        "provenance_id": provenance_id,
    }


class EdgeArcLog:
    """Append-only ``EdgeArc`` rows.

    ``insert`` appends the first ``StatusEvent`` in the same write. See the
    insert rule for ``EdgeArc`` under ``StatusEvent`` in ``docs/DATA_MODEL.md``.
    """

    def __init__(self) -> None:
        self._rows: list[EdgeArc] = []

    @property
    def rows(self) -> tuple[EdgeArc, ...]:
        return tuple(self._rows)

    def by_id(self, edge_id: uuid.UUID) -> EdgeArc:
        """Return the stored edge. The geometry is the one that was inserted."""
        for row in self._rows:
            if row.id == edge_id:
                return row
        raise KeyError("No EdgeArc has that id.")

    def insert(
        self,
        stream: StatusStream,
        edge: EdgeArc,
        *,
        recorded_at: str,
        actor: str,
        machine_rejection: bool = False,
    ) -> StatusEvent:
        """Store ``edge`` and append its first status event in the same write.

        The event is ``proposed``, or ``rejected`` when this write is a machine
        rejection. The edge object is not modified.
        """
        return _insert(
            self._rows,
            stream,
            edge,
            recorded_at=recorded_at,
            actor=actor,
            machine_rejection=machine_rejection,
            record_name="edge",
        )


class JoinHypothesisLog:
    """Append-only ``JoinHypothesis`` rows.

    ``insert`` appends the first ``StatusEvent`` in the same write. See the
    insert rule for ``JoinHypothesis`` under ``StatusEvent`` in
    ``docs/DATA_MODEL.md``.
    """

    def __init__(self) -> None:
        self._rows: list[JoinHypothesis] = []

    @property
    def rows(self) -> tuple[JoinHypothesis, ...]:
        return tuple(self._rows)

    def by_id(self, join_id: uuid.UUID) -> JoinHypothesis:
        """Return the stored join. The content is the content that was inserted."""
        for row in self._rows:
            if row.id == join_id:
                return row
        raise KeyError("No JoinHypothesis has that id.")

    def insert(
        self,
        stream: StatusStream,
        join: JoinHypothesis,
        *,
        recorded_at: str,
        actor: str,
        machine_rejection: bool = False,
    ) -> StatusEvent:
        """Store ``join`` and append its first status event in the same write.

        The event is ``proposed``, or ``rejected`` when this write is a machine
        rejection. The join object is not modified.
        """
        return _insert(
            self._rows,
            stream,
            join,
            recorded_at=recorded_at,
            actor=actor,
            machine_rejection=machine_rejection,
            record_name="join",
        )


def _insert[RowT: (EdgeArc, JoinHypothesis)](
    rows: list[RowT],
    stream: StatusStream,
    row: RowT,
    *,
    recorded_at: str,
    actor: str,
    machine_rejection: bool,
    record_name: str,
) -> StatusEvent:
    if not isinstance(row, EdgeArc | JoinHypothesis):
        raise TypeError(f"insert stores an {record_name}.")
    if any(stored.id == row.id for stored in rows):
        raise ValueError(f"A {record_name} is inserted once.")
    if stream.current_status(row.id) is not None:
        raise ValueError(
            f"A {record_name} is inserted once, with its first status event."
        )
    initial: HypothesisStatus = "rejected" if machine_rejection else "proposed"
    event = stream.append(
        target_id=row.id,
        status=initial,
        recorded_at=recorded_at,
        actor=actor,
    )
    rows.append(row)
    return event
