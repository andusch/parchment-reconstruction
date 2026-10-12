"""Propose pairwise rigid joins for an admitted fragment pool.

Stage 5 in ``docs/ALGORITHM.md`` proposes ``JoinHypothesis`` rows with a
rigid relative pose and a ``physical`` score. The implemented algorithm is
``pairwise_rigid_join`` version ``1``. The parameter blob records the score
``negative_absolute_length_difference``. That score is the negative of the
absolute chord-length difference. It is not a probability and does not mean
the edges meet.

``detected`` fragments are skipped. Fewer than two admitted fragments
(``catalogued`` or ``confirmed``) completes with an empty join list and no
pose. Each unordered pair of edges from two different admitted fragments
yields two ``proposed`` joins, one per endpoint pairing. Fragment A is the
lesser id string. The pose rotates chord A so its stored direction matches
the chosen direction of chord B, then translates midpoints, from A's
``fragment_local_mm`` frame into B's. The first pairing uses B's stored
direction and the second uses B reversed. There is no residual cutoff.

A missing calibration observation, or an edge frame other than
``fragment_local_mm``, fails the run under its own id and emits no pose.
Differing decoder names or versions fail the run. ``model_hash`` is
``absent`` and ``random_seed`` is omitted. This module does not read a
label file.
"""

from __future__ import annotations

import json
import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from prw.frames import CoordinateFrame
from prw.identity import ABSENT, content_id
from prw.joins import EdgeArc, JoinHypothesis, JoinHypothesisLog, RigidTransform
from prw.outlines import Fragment
from prw.provenance import (
    AlgorithmRun,
    ProvenanceEnvelope,
    Score,
    StatusEvent,
    StatusStream,
    run_id_inputs,
)
from prw.scale import CalibrationObservation, CalibrationTransform

ALGORITHM_NAME = "pairwise_rigid_join"
ALGORITHM_VERSION = "1"
SCORE_NAME = "negative_absolute_length_difference"
type Point = tuple[float, float]
type Chord = tuple[Point, Point]


def _require_text(value: str, label: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{label} is required.")
    return value


def _canonical(value: float) -> float:
    if value == 0.0:
        return 0.0
    return value


def _fragment_sort_key(item: FragmentChords) -> str:
    return str(item.fragment.id)


def _edge_sort_key(edge: EdgeArc) -> str:
    return str(edge.id)


def _admitted(fragment: Fragment) -> bool:
    return fragment.identification_status in {"catalogued", "confirmed"}


def _endpoints(edge: EdgeArc) -> Chord:
    if len(edge.geometry) != 2:
        raise ValueError("A pairwise chord has two endpoints.")
    start, end = edge.geometry
    if math.hypot(end[0] - start[0], end[1] - start[1]) == 0.0:
        raise ValueError("A pairwise chord has a positive length.")
    return start, end


def _length(chord: Chord) -> float:
    start, end = chord
    return math.hypot(end[0] - start[0], end[1] - start[1])


def _angle(chord: Chord) -> float:
    start, end = chord
    return math.atan2(end[1] - start[1], end[0] - start[0])


def _wrap(radians: float) -> float:
    return _canonical(math.atan2(math.sin(radians), math.cos(radians)))


def _midpoint(chord: Chord) -> Point:
    start, end = chord
    return ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)


def _length_score(chord_a: Chord, chord_b: Chord) -> float:
    difference = abs(_length(chord_a) - _length(chord_b))
    if difference == 0.0:
        return 0.0
    return -difference


def _pose(
    chord_a: Chord,
    chord_b: Chord,
    frame_a: CoordinateFrame,
    frame_b: CoordinateFrame,
    provenance_id: uuid.UUID,
) -> RigidTransform:
    rotation = _wrap(_angle(chord_b) - _angle(chord_a))
    mid_a = _midpoint(chord_a)
    mid_b = _midpoint(chord_b)
    cosine = math.cos(rotation)
    sine = math.sin(rotation)
    rotated_x = cosine * mid_a[0] - sine * mid_a[1]
    rotated_y = sine * mid_a[0] + cosine * mid_a[1]
    return RigidTransform.create(
        from_frame=frame_a,
        to_frame=frame_b,
        rotation_radians=rotation,
        translation_x=_canonical(mid_b[0] - rotated_x),
        translation_y=_canonical(mid_b[1] - rotated_y),
        provenance_id=provenance_id,
    )


def _require_pool(pool: object) -> tuple[FragmentChords, ...]:
    if isinstance(pool, str | bytes) or not isinstance(pool, Sequence):
        raise TypeError("A join pool is fragment chords.")
    stored: list[FragmentChords] = []
    seen: set[uuid.UUID] = set()
    for item in pool:
        if not isinstance(item, FragmentChords):
            raise TypeError("A join pool entry is FragmentChords.")
        if item.fragment.id in seen:
            raise ValueError("A fragment appears once in the pool.")
        seen.add(item.fragment.id)
        stored.append(item)
    return tuple(stored)


def _parameters(admitted: Sequence[FragmentChords]) -> dict[str, object]:
    return {
        "score": SCORE_NAME,
        "fragment_ids": sorted(_fragment_sort_key(item) for item in admitted),
        "frame_ids": sorted(str(item.frame.id) for item in admitted),
        "edge_ids": sorted(
            _edge_sort_key(edge) for item in admitted for edge in item.edges
        ),
    }


def _envelope(
    admitted: Sequence[FragmentChords],
    code_version: str,
) -> tuple[ProvenanceEnvelope, bool]:
    hashes = sorted(
        {digest for item in admitted for digest in item.envelope.source_hashes}
    )
    decoders = {
        (item.envelope.decoder_name, item.envelope.decoder_version) for item in admitted
    }
    if not decoders:
        decoder_name, decoder_version = ABSENT, ABSENT
        agreed = True
    else:
        decoder_name, decoder_version = min(decoders)
        agreed = len(decoders) == 1
    envelope = ProvenanceEnvelope.create(
        source_hashes=hashes,
        parameters=_parameters(admitted),
        algorithm_name=ALGORITHM_NAME,
        algorithm_version=ALGORITHM_VERSION,
        code_version=code_version,
        decoder_name=decoder_name,
        decoder_version=decoder_version,
    )
    return envelope, agreed


def _established(item: FragmentChords) -> bool:
    observation = item.observation
    transform = item.transform
    if observation is None or transform is None:
        return False
    if not isinstance(observation, CalibrationObservation):
        raise TypeError("The calibration observation is a CalibrationObservation.")
    if not isinstance(transform, CalibrationTransform):
        raise TypeError("The calibration transform is a CalibrationTransform.")
    return (
        observation.transform_id == transform.id
        and transform.to_frame_id == item.frame.id
    )


def _millimetre_ready(item: FragmentChords) -> bool:
    if item.frame.kind != "fragment_local_mm":
        return False
    if item.frame.owner_id != item.fragment.id:
        raise ValueError("The fragment_local_mm frame is owned by that fragment.")
    for edge in item.edges:
        if edge.frame_id != item.frame.id:
            raise ValueError("The edge cites the fragment_local_mm frame.")
    return _established(item)


@dataclass(frozen=True, slots=True)
class FragmentChords:
    """Edges of one fragment and the calibration that established their frame.

    ``observation`` and ``transform`` are omitted when calibration is missing.
    A ``detected`` fragment is still recorded here so the pool can skip it.
    See stage 5 in ``docs/ALGORITHM.md``.
    """

    fragment: Fragment
    frame: CoordinateFrame
    edges: tuple[EdgeArc, ...]
    envelope: ProvenanceEnvelope
    observation: CalibrationObservation | None = None
    transform: CalibrationTransform | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.fragment, Fragment):
            raise TypeError("A join pool entry cites a Fragment.")
        if not isinstance(self.frame, CoordinateFrame):
            raise TypeError("The edge frame is a CoordinateFrame.")
        if not isinstance(self.envelope, ProvenanceEnvelope):
            raise TypeError("The edge envelope is a ProvenanceEnvelope.")
        if isinstance(self.edges, str | bytes) or not isinstance(self.edges, tuple):
            raise TypeError("Edges are EdgeArc rows.")
        for edge in self.edges:
            if not isinstance(edge, EdgeArc):
                raise TypeError("Edges are EdgeArc rows.")
            if edge.provenance_id != self.envelope.id:
                raise ValueError("An edge cites its envelope.")
        if self.observation is not None and not isinstance(
            self.observation, CalibrationObservation
        ):
            raise TypeError("The calibration observation is a CalibrationObservation.")
        if self.transform is not None and not isinstance(
            self.transform, CalibrationTransform
        ):
            raise TypeError("The calibration transform is a CalibrationTransform.")


@dataclass(frozen=True, slots=True)
class PairwiseJoins:
    """One completed ``pairwise_rigid_join`` run and the joins it inserted.

    An empty ``joins`` tuple is a completed run with fewer than two admitted
    fragments, or with no edge pair. No pose is stored. See stage 5 in
    ``docs/ALGORITHM.md``.
    """

    run: AlgorithmRun
    joins: tuple[JoinHypothesis, ...]
    transforms: tuple[RigidTransform, ...]
    proposed: tuple[StatusEvent, ...]

    def __post_init__(self) -> None:
        provenance = self.run.provenance
        if self.run.status != "completed" or self.run.attempt_id is not None:
            raise ValueError("A completed join run has no attempt_id.")
        if provenance.algorithm_name != ALGORITHM_NAME:
            raise ValueError("The join algorithm is pairwise_rigid_join.")
        if provenance.algorithm_version != ALGORITHM_VERSION:
            raise ValueError("The join algorithm version is 1.")
        if provenance.model_hash != ABSENT or provenance.random_seed is not None:
            raise ValueError("A join run omits a model and a random seed.")
        parameters = json.loads(provenance.parameter_blob)
        if parameters.get("score") != SCORE_NAME:
            raise ValueError(
                "The parameter blob names negative_absolute_length_difference."
            )
        if self.run.join_ids != tuple(join.id for join in self.joins):
            raise ValueError("The completed run lists the join ids.")
        if len(self.transforms) != len(self.joins) or len(self.proposed) != len(
            self.joins
        ):
            raise ValueError("Each join is inserted with one pose and proposed.")
        for join, transform, proposed in zip(
            self.joins, self.transforms, self.proposed, strict=True
        ):
            if join.run_id != self.run.id or join.provenance_id != provenance.id:
                raise ValueError("The join cites the completed run.")
            if join.transform_id != transform.id:
                raise ValueError("The join cites its rigid pose.")
            if join.epistemic_class != "hypothesis" or join.producer != "machine":
                raise ValueError("A pairwise join is a machine hypothesis.")
            if transform.epistemic_class != "hypothesis":
                raise ValueError("A join pose is a hypothesis.")
            if proposed.status != "proposed" or proposed.target_id != join.id:
                raise ValueError("Insert appends proposed on the join.")
            score = join.scores[0]
            if score.channel != "physical" or score.value > 0.0:
                raise ValueError("The physical score is a non-positive length rank.")
        if (
            self.run.assembly_ids
            or self.run.reading_ids
            or self.run.line_ids
            or self.run.line_order_ids
        ):
            raise ValueError("A join run emits pairwise joins.")


@dataclass(frozen=True, slots=True)
class FailedPairwiseJoin:
    """A failed join run. No pose is stored.

    ``run.attempt_id`` is set. The run id is not the id a later completed
    run of the same inputs would take. See stage 5 in ``docs/ALGORITHM.md``.
    """

    run: AlgorithmRun

    def __post_init__(self) -> None:
        if self.run.status != "failed" or self.run.attempt_id is None:
            raise ValueError("A failed join run stores attempt_id.")
        completed = content_id(run_id_inputs(self.run.provenance, "completed", None))
        if self.run.id == completed:
            raise ValueError(
                "A failed run id is not the completed id of the same inputs."
            )
        if self.run.join_ids or self.run.assembly_ids or self.run.reading_ids:
            raise ValueError("A failed join run emits no pose.")
        if self.run.provenance.model_hash != ABSENT or (
            self.run.provenance.random_seed is not None
        ):
            raise ValueError("A join run omits a model and a random seed.")


class PairwiseJoinLog:
    """In-memory pairwise join runs. ``AlgorithmRun`` does not gain ``edge_ids``.

    A repeated completed run returns the stored joins. Join ids are the
    content-derived ids of those hypotheses.
    """

    def __init__(self) -> None:
        self._runs: list[AlgorithmRun] = []
        self._completed: dict[uuid.UUID, PairwiseJoins] = {}
        self._joins = JoinHypothesisLog()
        self._status = StatusStream()

    @property
    def runs(self) -> tuple[AlgorithmRun, ...]:
        return tuple(self._runs)

    @property
    def joins(self) -> tuple[JoinHypothesis, ...]:
        return self._joins.rows

    def propose(
        self,
        pool: Sequence[FragmentChords],
        *,
        code_version: str,
        recorded_at: str,
    ) -> PairwiseJoins | FailedPairwiseJoin:
        """Propose pairwise joins, or record a failed run.

        ``detected`` fragments are not paired. Fewer than two admitted
        fragments completes with no joins and no pose. A missing calibration
        observation, a frame other than ``fragment_local_mm``, or disagreeing
        decoder names or versions fails the run and emits no pose.
        """
        contributions = _require_pool(pool)
        admitted = tuple(
            sorted(
                (item for item in contributions if _admitted(item.fragment)),
                key=_fragment_sort_key,
            )
        )
        version = _require_text(code_version, "code_version")
        envelope, decoders_agree = _envelope(admitted, version)
        if len(admitted) < 2:
            return self._complete(envelope, (), (), recorded_at)
        if not decoders_agree or any(not _millimetre_ready(item) for item in admitted):
            return self._fail(envelope, recorded_at)
        joins, transforms = _candidates(admitted, envelope)
        return self._complete(envelope, joins, transforms, recorded_at)

    def _fail(
        self,
        envelope: ProvenanceEnvelope,
        recorded_at: str,
    ) -> FailedPairwiseJoin:
        run = AlgorithmRun.create(envelope, status="failed", started_at=recorded_at)
        self._runs.append(run)
        return FailedPairwiseJoin(run=run)

    def _complete(
        self,
        envelope: ProvenanceEnvelope,
        joins: tuple[JoinHypothesis, ...],
        transforms: tuple[RigidTransform, ...],
        recorded_at: str,
    ) -> PairwiseJoins:
        completed_id = content_id(run_id_inputs(envelope, "completed", None))
        stored = self._completed.get(completed_id)
        if stored is not None:
            return stored
        run = AlgorithmRun.create(
            envelope,
            status="completed",
            started_at=recorded_at,
            join_ids=tuple(join.id for join in joins),
        )
        if run.id != completed_id:
            raise ValueError("The completed join run id is the provenance id.")
        proposed: list[StatusEvent] = []
        for join in joins:
            proposed.append(
                self._joins.insert(
                    self._status,
                    join,
                    recorded_at=recorded_at,
                    actor=str(run.id),
                )
            )
        result = PairwiseJoins(
            run=run,
            joins=joins,
            transforms=transforms,
            proposed=tuple(proposed),
        )
        self._runs.append(run)
        self._completed[run.id] = result
        return result


def _candidates(
    admitted: Sequence[FragmentChords],
    envelope: ProvenanceEnvelope,
) -> tuple[tuple[JoinHypothesis, ...], tuple[RigidTransform, ...]]:
    run_id = content_id(run_id_inputs(envelope, "completed", None))
    joins: list[JoinHypothesis] = []
    transforms: list[RigidTransform] = []
    for index, left in enumerate(admitted):
        for right in admitted[index + 1 :]:
            for edge_a in sorted(left.edges, key=_edge_sort_key):
                chord_a = _endpoints(edge_a)
                for edge_b in sorted(right.edges, key=_edge_sort_key):
                    forward = _endpoints(edge_b)
                    pairings = (forward, (forward[1], forward[0]))
                    score = Score(
                        value=_length_score(chord_a, forward),
                        run_id=run_id,
                        channel="physical",
                        hypothesis_type="join",
                    )
                    for chord_b in pairings:
                        transform = _pose(
                            chord_a,
                            chord_b,
                            left.frame,
                            right.frame,
                            envelope.id,
                        )
                        join = JoinHypothesis.create(
                            run_id=run_id,
                            fragment_a_id=left.fragment.id,
                            edge_a_id=edge_a.id,
                            fragment_b_id=right.fragment.id,
                            edge_b_id=edge_b.id,
                            transform_id=transform.id,
                            scores=(score,),
                            provenance_id=envelope.id,
                        )
                        transforms.append(transform)
                        joins.append(join)
    return tuple(joins), tuple(transforms)
