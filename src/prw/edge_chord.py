"""Build chord edge arcs from one millimetre outline.

Stage 4 in ``docs/ALGORITHM.md`` builds ``EdgeArc`` rows in
``fragment_local_mm``. The implemented algorithm is ``edge_chord`` version
``1``. Each polygon side, including the side that closes the ring, is a
chord: the ordered endpoints. The parameter blob records ``descriptor``
``chord`` and ``minimum_edge_length_mm``.

A non-millimetre outline is a failed run under its own id, including
``attempt_id``, and emits no edge. An outline with no usable side is a
completed run with no edges. The outline stays. This use case emits no join.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from prw.frames import CoordinateFrame
from prw.identity import content_id
from prw.joins import EdgeArc, EdgeArcLog
from prw.outlines import FragmentOutlineRevision
from prw.provenance import (
    AlgorithmRun,
    ProvenanceEnvelope,
    StatusEvent,
    StatusStream,
    run_id_inputs,
)

ALGORITHM_NAME = "edge_chord"
ALGORITHM_VERSION = "1"
DESCRIPTOR = "chord"
type Point = tuple[float, float]
type Chord = tuple[Point, Point]


def _require_text(value: str, label: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{label} is required.")
    return value


def _minimum(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("minimum_edge_length_mm is a finite number.")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError("minimum_edge_length_mm is zero or a positive finite number.")
    return number


def _chords(polygon: Sequence[Point], minimum: float) -> tuple[Chord, ...]:
    count = len(polygon)
    kept: list[Chord] = []
    for index, start in enumerate(polygon):
        end = polygon[(index + 1) % count]
        length = math.hypot(end[0] - start[0], end[1] - start[1])
        if length == 0.0 or length < minimum:
            continue
        kept.append((start, end))
    return tuple(kept)


def _envelope(
    outline_envelope: ProvenanceEnvelope,
    minimum: float,
    code_version: str,
) -> ProvenanceEnvelope:
    return ProvenanceEnvelope.create(
        source_hashes=outline_envelope.source_hashes,
        parameters={
            "descriptor": DESCRIPTOR,
            "minimum_edge_length_mm": minimum,
        },
        algorithm_name=ALGORITHM_NAME,
        algorithm_version=ALGORITHM_VERSION,
        code_version=code_version,
        decoder_name=outline_envelope.decoder_name,
        decoder_version=outline_envelope.decoder_version,
    )


def _require_machine_outline(
    outline: object,
    envelope: object,
) -> tuple[FragmentOutlineRevision, ProvenanceEnvelope]:
    if not isinstance(outline, FragmentOutlineRevision):
        raise TypeError("A chord run traces a FragmentOutlineRevision.")
    if not isinstance(envelope, ProvenanceEnvelope):
        raise TypeError("The outline envelope is a ProvenanceEnvelope.")
    if outline.producer != "machine" or outline.provenance_id != envelope.id:
        raise ValueError("A chord run traces a machine outline and its envelope.")
    if outline.epistemic_class != "interpretation":
        raise ValueError("A machine outline's epistemic class is interpretation.")
    return outline, envelope


@dataclass(frozen=True, slots=True)
class ChordEdges:
    """One completed ``edge_chord`` run and the edges it inserted.

    An empty ``edges`` tuple is a completed run whose outline had no usable
    side. See stage 4 in ``docs/ALGORITHM.md``.
    """

    run: AlgorithmRun
    outline: FragmentOutlineRevision
    frame: CoordinateFrame
    edges: tuple[EdgeArc, ...]
    proposed: tuple[StatusEvent, ...]

    def __post_init__(self) -> None:
        if self.run.status != "completed" or self.run.attempt_id is not None:
            raise ValueError("A completed edge run has no attempt_id.")
        if self.frame.kind != "fragment_local_mm":
            raise ValueError("A completed edge run is in fragment_local_mm.")
        if self.outline.frame_id != self.frame.id:
            raise ValueError("The outline cites the fragment_local_mm frame.")
        if len(self.proposed) != len(self.edges):
            raise ValueError("Each edge is inserted with proposed.")
        for edge, proposed in zip(self.edges, self.proposed, strict=True):
            cites_run = (
                edge.run_id == self.run.id
                and edge.provenance_id == self.run.provenance.id
            )
            if not cites_run:
                raise ValueError("The edge run_id is the completed run.")
            if edge.outline_revision_id != self.outline.id:
                raise ValueError("The edge is scoped to this outline revision.")
            if edge.frame_id != self.frame.id:
                raise ValueError("The edge frame is fragment_local_mm.")
            if edge.epistemic_class != "interpretation" or edge.producer != "machine":
                raise ValueError("A chord edge is a machine interpretation.")
            if proposed.status != "proposed" or proposed.target_id != edge.id:
                raise ValueError("Insert appends proposed on the edge.")
        if (
            self.run.join_ids
            or self.run.assembly_ids
            or self.run.reading_ids
            or self.run.line_ids
            or self.run.line_order_ids
        ):
            raise ValueError("An edge run emits no join.")


@dataclass(frozen=True, slots=True)
class FailedEdgeChord:
    """A failed run for a non-millimetre outline. No edge is stored.

    ``run.attempt_id`` is set. The run id is not the id a later completed
    run of the same inputs would take. See stage 4 in ``docs/ALGORITHM.md``.
    """

    run: AlgorithmRun
    outline: FragmentOutlineRevision

    def __post_init__(self) -> None:
        if self.run.status != "failed" or self.run.attempt_id is None:
            raise ValueError(
                "A non-millimetre outline stores a failed run and attempt_id."
            )
        completed = content_id(run_id_inputs(self.run.provenance, "completed", None))
        if self.run.id == completed:
            raise ValueError(
                "A failed run id is not the completed id of the same inputs."
            )
        if (
            self.run.join_ids
            or self.run.assembly_ids
            or self.run.reading_ids
            or self.run.line_ids
            or self.run.line_order_ids
        ):
            raise ValueError("A failed edge run emits no join.")


class EdgeChordLog:
    """In-memory chord runs. ``AlgorithmRun`` does not gain ``edge_ids``.

    A repeated completed run returns the stored edges. The edge ``run_id``
    groups those edges with the run.
    """

    def __init__(self) -> None:
        self._runs: list[AlgorithmRun] = []
        self._completed: dict[uuid.UUID, ChordEdges] = {}
        self._edges = EdgeArcLog()
        self._status = StatusStream()

    @property
    def runs(self) -> tuple[AlgorithmRun, ...]:
        return tuple(self._runs)

    @property
    def edges(self) -> tuple[EdgeArc, ...]:
        return self._edges.rows

    def build(
        self,
        outline: FragmentOutlineRevision,
        frame: CoordinateFrame,
        envelope: ProvenanceEnvelope,
        *,
        minimum_edge_length_mm: object,
        code_version: str,
        recorded_at: str,
    ) -> ChordEdges | FailedEdgeChord:
        """Trace ``outline`` into chord edges, or record a failed run.

        A frame other than ``fragment_local_mm`` fails the run and emits no
        edge. A side shorter than ``minimum_edge_length_mm`` is omitted, as
        is a side of length zero. The outline object is not modified.
        """
        stored_outline, stored_envelope = _require_machine_outline(outline, envelope)
        if not isinstance(frame, CoordinateFrame):
            raise TypeError("The outline frame is a CoordinateFrame.")
        minimum = _minimum(minimum_edge_length_mm)
        edge_envelope = _envelope(
            stored_envelope,
            minimum,
            _require_text(code_version, "code_version"),
        )
        completed_id = content_id(run_id_inputs(edge_envelope, "completed", None))
        stored = self._completed.get(completed_id)
        if stored is not None:
            return stored
        if frame.kind != "fragment_local_mm":
            return self._fail(edge_envelope, stored_outline, recorded_at)
        if stored_outline.frame_id != frame.id:
            raise ValueError("The outline cites the fragment_local_mm frame.")
        return self._succeed(
            edge_envelope,
            stored_outline,
            frame,
            _chords(stored_outline.polygon, minimum),
            recorded_at,
        )

    def _fail(
        self,
        envelope: ProvenanceEnvelope,
        outline: FragmentOutlineRevision,
        recorded_at: str,
    ) -> FailedEdgeChord:
        run = AlgorithmRun.create(envelope, status="failed", started_at=recorded_at)
        self._runs.append(run)
        return FailedEdgeChord(run=run, outline=outline)

    def _succeed(
        self,
        envelope: ProvenanceEnvelope,
        outline: FragmentOutlineRevision,
        frame: CoordinateFrame,
        chords: tuple[Chord, ...],
        recorded_at: str,
    ) -> ChordEdges:
        run = AlgorithmRun.create(envelope, status="completed", started_at=recorded_at)
        edges: list[EdgeArc] = []
        proposed: list[StatusEvent] = []
        for geometry in chords:
            edge = EdgeArc.create(
                outline_revision_id=outline.id,
                frame=frame,
                geometry=geometry,
                run_id=run.id,
                provenance_id=envelope.id,
            )
            event = self._edges.insert(
                self._status,
                edge,
                recorded_at=recorded_at,
                actor=str(run.id),
            )
            edges.append(edge)
            proposed.append(event)
        result = ChordEdges(
            run=run,
            outline=outline,
            frame=frame,
            edges=tuple(edges),
            proposed=tuple(proposed),
        )
        self._runs.append(run)
        self._completed[run.id] = result
        return result
