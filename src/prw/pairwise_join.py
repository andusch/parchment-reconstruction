"""Propose pairwise rigid joins for an admitted fragment pool.

Stage 5 in ``docs/ALGORITHM.md`` proposes ``JoinHypothesis`` rows with a
rigid relative pose and a ``physical`` score. The implemented algorithm is
``pairwise_rigid_join`` version ``1``. The parameter blob records the score
``negative_chord_gap_plus_curve_and_overlap``. The chord term is the absolute
length difference of the admitted chords. When both fragments carry an
outline, the curve term is the best rigid match of their minimum-area
rectangle sides, sampled at ``curve_samples`` equal steps, and the overlap
term is the intersection thickness of those rectangles under the stored
pose. The score is the negative of the sum. It is not a probability and does
not mean the edges meet.

``detected`` fragments are skipped. Fewer than two admitted fragments
(``catalogued`` or ``confirmed``) completes with an empty join list and no
pose. Each unordered pair of edges from two different admitted fragments
yields two ``proposed`` joins, one per endpoint pairing. Fragment A is the
lesser id string. A chord pose rotates chord A so its stored direction
matches the chosen direction of chord B, then translates midpoints, from A's
``fragment_local_mm`` frame into B's. The first pairing uses B's stored
direction and the second uses B reversed. There is no residual cutoff.

When both outlines have a minimum-area rectangle and the chord pose with the
smaller rectangle thickness still overlaps, that pairing's stored pose is
replaced. The replacement seats the best-matched rectangle sides so the
rectangles touch on the exterior without turning the fragment over, choosing
the seat whose translation is most opposed to that overlapping chord
alignment. The other pairing keeps its chord pose. A chord pose that already
has no rectangle overlap is kept.
The overlap term is the thickness under the pose that is stored.

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
SCORE_NAME = "negative_chord_gap_plus_curve_and_overlap"
POSE_NAME = "exterior_side"
CURVE_SAMPLES = 8
# A shared boundary leaves no measurable rectangle area.
_TOUCH_MM = 1e-6
type Point = tuple[float, float]
type Chord = tuple[Point, Point]
type Rectangle = tuple[Point, Point, Point, Point]


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


def _gap(chord_a: Chord, chord_b: Chord) -> float:
    return abs(_length(chord_a) - _length(chord_b))


def _rank_value(total: float) -> float:
    # A shared boundary leaves clip dust far below a millimetre.
    if abs(total) <= 1e-9:
        return 0.0
    return -total


def _motion(chord_a: Chord, chord_b: Chord) -> tuple[float, Point]:
    rotation = _wrap(_angle(chord_b) - _angle(chord_a))
    mid_a = _midpoint(chord_a)
    mid_b = _midpoint(chord_b)
    cosine = math.cos(rotation)
    sine = math.sin(rotation)
    rotated_x = cosine * mid_a[0] - sine * mid_a[1]
    rotated_y = sine * mid_a[0] + cosine * mid_a[1]
    return rotation, (
        _canonical(mid_b[0] - rotated_x),
        _canonical(mid_b[1] - rotated_y),
    )


def _transform(
    frame_a: CoordinateFrame,
    frame_b: CoordinateFrame,
    rotation: float,
    translation: Point,
    provenance_id: uuid.UUID,
) -> RigidTransform:
    return RigidTransform.create(
        from_frame=frame_a,
        to_frame=frame_b,
        rotation_radians=rotation,
        translation_x=translation[0],
        translation_y=translation[1],
        provenance_id=provenance_id,
    )


def _pose(
    chord_a: Chord,
    chord_b: Chord,
    frame_a: CoordinateFrame,
    frame_b: CoordinateFrame,
    provenance_id: uuid.UUID,
) -> RigidTransform:
    rotation, translation = _motion(chord_a, chord_b)
    return _transform(frame_a, frame_b, rotation, translation, provenance_id)


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
    parameters: dict[str, object] = {
        "curve_samples": CURVE_SAMPLES,
        "score": SCORE_NAME,
        "seat": POSE_NAME,
        "fragment_ids": sorted(_fragment_sort_key(item) for item in admitted),
        "frame_ids": sorted(str(item.frame.id) for item in admitted),
        "edge_ids": sorted(
            _edge_sort_key(edge) for item in admitted for edge in item.edges
        ),
    }
    outline_ids = sorted(
        str(content_id(item.outline)) for item in admitted if item.outline is not None
    )
    if outline_ids:
        parameters["outline_ids"] = outline_ids
    return parameters


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
    ``outline`` is the fragment polygon in ``fragment_local_mm``. It is
    omitted when the caller has no millimetre outline. A ``detected``
    fragment is still recorded here so the pool can skip it. See stage 5
    in ``docs/ALGORITHM.md``.
    """

    fragment: Fragment
    frame: CoordinateFrame
    edges: tuple[EdgeArc, ...]
    envelope: ProvenanceEnvelope
    observation: CalibrationObservation | None = None
    transform: CalibrationTransform | None = None
    outline: tuple[Point, ...] | None = None

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
        if self.outline is not None:
            _require_outline(self.outline)


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
                "The parameter blob names negative_chord_gap_plus_curve_and_overlap."
            )
        if parameters.get("curve_samples") != CURVE_SAMPLES:
            raise ValueError("The parameter blob records curve_samples.")
        if parameters.get("seat") != POSE_NAME:
            raise ValueError("The parameter blob names exterior_side.")
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


def _require_outline(outline: tuple[Point, ...]) -> None:
    if len(outline) < 3:
        raise ValueError("An outline polygon has at least three vertices.")
    for point in outline:
        if (
            isinstance(point, str | bytes)
            or not isinstance(point, tuple)
            or len(point) != 2
        ):
            raise TypeError("An outline vertex is an x and a y.")
        for coordinate in point:
            if isinstance(coordinate, bool) or not isinstance(coordinate, int | float):
                raise TypeError("An outline coordinate is a finite number.")
            if not math.isfinite(float(coordinate)):
                raise ValueError("An outline coordinate is a finite number.")


def _signed_area(polygon: Sequence[Point]) -> float:
    total = 0.0
    count = len(polygon)
    for index, point in enumerate(polygon):
        nxt = polygon[(index + 1) % count]
        total += point[0] * nxt[1] - nxt[0] * point[1]
    return total / 2.0


def _area(polygon: Sequence[Point]) -> float:
    return abs(_signed_area(polygon))


def _ccw(polygon: Sequence[Point]) -> tuple[Point, ...]:
    points = tuple(polygon)
    if _signed_area(points) < 0.0:
        return tuple(reversed(points))
    return points


def _orient(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _hull(points: Sequence[Point]) -> tuple[Point, ...]:
    ordered = sorted(set(points))
    if len(ordered) <= 1:
        return tuple(ordered)

    def build(vertices: Sequence[Point]) -> list[Point]:
        chain: list[Point] = []
        for point in vertices:
            while len(chain) >= 2 and _orient(chain[-2], chain[-1], point) <= 0.0:
                chain.pop()
            chain.append(point)
        return chain

    lower = build(ordered)
    upper = build(tuple(reversed(ordered)))
    return tuple(lower[:-1] + upper[:-1])


def _placed(
    origin: Point,
    along_x: float,
    along_y: float,
    across_x: float,
    across_y: float,
    along_at: float,
    across_at: float,
) -> Point:
    return (
        origin[0] + along_at * along_x + across_at * across_x,
        origin[1] + along_at * along_y + across_at * across_y,
    )


def _rectangle(outline: tuple[Point, ...] | None) -> Rectangle | None:
    """Return the minimum-area rectangle of ``outline``, or none.

    The rectangle is the rigid edge curve of the outline. Sides are sampled
    by the curve term. A polygon with no area has no rectangle.
    """
    if outline is None:
        return None
    hull = _hull(outline)
    if len(hull) < 3:
        return None
    best: tuple[float, float, Rectangle] | None = None
    count = len(hull)
    for index, start in enumerate(hull):
        end = hull[(index + 1) % count]
        dx_coord = end[0] - start[0]
        dy_coord = end[1] - start[1]
        length = math.hypot(dx_coord, dy_coord)
        if length == 0.0:
            continue
        along_x = dx_coord / length
        along_y = dy_coord / length
        across_x = -along_y
        across_y = along_x
        along = [
            (point[0] - start[0]) * along_x + (point[1] - start[1]) * along_y
            for point in hull
        ]
        across = [
            (point[0] - start[0]) * across_x + (point[1] - start[1]) * across_y
            for point in hull
        ]
        min_along, max_along = min(along), max(along)
        min_across, max_across = min(across), max(across)
        area = (max_along - min_along) * (max_across - min_across)
        angle = _angle((start, end))
        fitted = (
            _placed(start, along_x, along_y, across_x, across_y, min_along, min_across),
            _placed(start, along_x, along_y, across_x, across_y, max_along, min_across),
            _placed(start, along_x, along_y, across_x, across_y, max_along, max_across),
            _placed(start, along_x, along_y, across_x, across_y, min_along, max_across),
        )
        if best is None or area < best[0] or (area == best[0] and angle < best[1]):
            best = (area, angle, fitted)
    if best is None or best[0] == 0.0:
        return None
    ordered = _ccw(best[2])
    return (ordered[0], ordered[1], ordered[2], ordered[3])


def _samples(chord: Chord) -> tuple[Point, ...]:
    start, end = chord
    last = CURVE_SAMPLES - 1
    return tuple(
        (
            start[0] + (end[0] - start[0]) * index / last,
            start[1] + (end[1] - start[1]) * index / last,
        )
        for index in range(CURVE_SAMPLES)
    )


def _mean_distance(left: Sequence[Point], right: Sequence[Point]) -> float:
    return sum(
        math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(left, right, strict=True)
    ) / len(left)


def _map_point(rotation: float, translation: Point, point: Point) -> Point:
    cosine = math.cos(rotation)
    sine = math.sin(rotation)
    return (
        cosine * point[0] - sine * point[1] + translation[0],
        sine * point[0] + cosine * point[1] + translation[1],
    )


def _sides(rectangle: Rectangle) -> tuple[Chord, ...]:
    return tuple((rectangle[index], rectangle[(index + 1) % 4]) for index in range(4))


def _curve_penalty(left: Rectangle | None, right: Rectangle | None) -> float:
    """Best side-to-side length gap plus mean sample distance.

    Both directions of the right side are tried. The term is zero when
    either rectangle is absent.
    """
    if left is None or right is None:
        return 0.0
    best: float | None = None
    for side_a in _sides(left):
        for side_b in _sides(right):
            gap = _gap(side_a, side_b)
            for chord_b in (side_b, (side_b[1], side_b[0])):
                rotation = _wrap(_angle(chord_b) - _angle(side_a))
                mid_a = _midpoint(side_a)
                mid_b = _midpoint(chord_b)
                cosine = math.cos(rotation)
                sine = math.sin(rotation)
                rotated_x = cosine * mid_a[0] - sine * mid_a[1]
                rotated_y = sine * mid_a[0] + cosine * mid_a[1]
                translation = (mid_b[0] - rotated_x, mid_b[1] - rotated_y)
                moved = tuple(
                    _map_point(rotation, translation, point)
                    for point in _samples(side_a)
                )
                penalty = gap + _mean_distance(moved, _samples(chord_b))
                if best is None or penalty < best:
                    best = penalty
    if best is None or best == 0.0:
        return 0.0
    return best


def _line_hit(a: Point, b: Point, c: Point, d: Point) -> Point:
    denominator = (a[0] - b[0]) * (c[1] - d[1]) - (a[1] - b[1]) * (c[0] - d[0])
    if denominator == 0.0:
        return a
    scale = (
        (a[0] - c[0]) * (c[1] - d[1]) - (a[1] - c[1]) * (c[0] - d[0])
    ) / denominator
    return (a[0] + scale * (b[0] - a[0]), a[1] + scale * (b[1] - a[1]))


def _clip(subject: Sequence[Point], clip: Sequence[Point]) -> tuple[Point, ...]:
    output = list(subject)
    count = len(clip)
    for index, start in enumerate(clip):
        if not output:
            return ()
        end = clip[(index + 1) % count]
        incoming = output
        output = []
        previous = incoming[-1]
        for current in incoming:
            current_inside = _orient(start, end, current) >= -1e-12
            previous_inside = _orient(start, end, previous) >= -1e-12
            if current_inside:
                if not previous_inside:
                    output.append(_line_hit(previous, current, start, end))
                output.append(current)
            elif previous_inside:
                output.append(_line_hit(previous, current, start, end))
            previous = current
    return tuple(output)


def _overlap_thickness(
    left: Rectangle | None,
    right: Rectangle | None,
    rotation: float,
    translation: Point,
) -> float:
    """Intersection area over the square root of the smaller rectangle.

    The unit is millimetres. Boundary contact is zero area. The term is
    zero when either rectangle is absent.
    """
    if left is None or right is None:
        return 0.0
    moved = _ccw(tuple(_map_point(rotation, translation, point) for point in left))
    other = _ccw(right)
    shared = _area(_clip(moved, other))
    base = math.sqrt(min(_area(moved), _area(other)))
    if base == 0.0 or shared == 0.0:
        return 0.0
    return shared / base


def _physical_value(
    chord_gap: float,
    curve_penalty: float,
    thickness: float,
) -> float:
    return _rank_value(chord_gap + curve_penalty + thickness)


def _unit(translation: Point) -> Point:
    length = math.hypot(translation[0], translation[1])
    if length == 0.0:
        return (0.0, 0.0)
    return (translation[0] / length, translation[1] / length)


def _exterior_seats(
    left: Rectangle, right: Rectangle
) -> tuple[tuple[float, Point], ...]:
    """Exterior seats of the best-matched rectangle sides.

    A seat aligns one side of ``left`` with one directed side of ``right``.
    The penalty is that side pair's length gap plus the mean sample distance.
    Only seats of the minimum penalty whose rectangles do not overlap are
    returned.
    """
    found: list[tuple[float, float, float, Point]] = []
    best: float | None = None
    for side_a in _sides(left):
        for side_b in _sides(right):
            gap = _gap(side_a, side_b)
            for directed in (side_b, (side_b[1], side_b[0])):
                rotation, translation = _motion(side_a, directed)
                moved = tuple(
                    _map_point(rotation, translation, point)
                    for point in _samples(side_a)
                )
                penalty = gap + _mean_distance(moved, _samples(directed))
                thickness = _overlap_thickness(left, right, rotation, translation)
                if best is None or penalty < best:
                    best = penalty
                found.append((penalty, thickness, rotation, translation))
    if best is None:
        return ()
    return tuple(
        (rotation, translation)
        for penalty, thickness, rotation, translation in found
        if penalty <= best + 1e-9 and thickness <= _TOUCH_MM
    )


def _opposed_seat(
    seats: tuple[tuple[float, Point], ...],
    chord_translation: Point,
) -> tuple[float, Point] | None:
    """Return an exterior seat opposed to ``chord_translation``.

    Seats that turn the fragment over are dropped when an unturned seat
    exists. The chord alignment of a long flat points through the fragment.
    The opposite unturned seat puts the contact on the other side of that
    alignment. Equal opposite sides of a rectangle remain a tie the flat
    cannot break.
    """
    if not seats:
        return None
    nearest = min(abs(rotation) for rotation, _translation in seats)
    unturned = tuple(seat for seat in seats if abs(abs(seat[0]) - nearest) <= 1e-3)
    reference = _unit(chord_translation)

    def sort_key(seat: tuple[float, Point]) -> tuple[float, float, float]:
        _rotation, translation = seat
        direction = _unit(translation)
        dot = direction[0] * reference[0] + direction[1] * reference[1]
        return (dot, translation[0], translation[1])

    return min(unturned, key=sort_key)


def _candidates(
    admitted: Sequence[FragmentChords],
    envelope: ProvenanceEnvelope,
) -> tuple[tuple[JoinHypothesis, ...], tuple[RigidTransform, ...]]:
    run_id = content_id(run_id_inputs(envelope, "completed", None))
    rectangles = {item.fragment.id: _rectangle(item.outline) for item in admitted}
    joins: list[JoinHypothesis] = []
    transforms: list[RigidTransform] = []
    for index, left in enumerate(admitted):
        for right in admitted[index + 1 :]:
            curve_penalty = _curve_penalty(
                rectangles[left.fragment.id],
                rectangles[right.fragment.id],
            )
            for edge_a in sorted(left.edges, key=_edge_sort_key):
                chord_a = _endpoints(edge_a)
                for edge_b in sorted(right.edges, key=_edge_sort_key):
                    forward = _endpoints(edge_b)
                    pairings = (forward, (forward[1], forward[0]))
                    chord_gap = _gap(chord_a, forward)
                    motions = tuple(_motion(chord_a, chord_b) for chord_b in pairings)
                    rect_a = rectangles[left.fragment.id]
                    rect_b = rectangles[right.fragment.id]
                    thicknesses = tuple(
                        _overlap_thickness(rect_a, rect_b, rotation, translation)
                        for rotation, translation in motions
                    )
                    seated = min(
                        range(len(pairings)),
                        key=lambda item: (thicknesses[item], item),
                    )
                    seats = (
                        _exterior_seats(rect_a, rect_b)
                        if rect_a is not None and rect_b is not None
                        else ()
                    )
                    for pairing_index, _chord_b in enumerate(pairings):
                        rotation, translation = motions[pairing_index]
                        thickness = thicknesses[pairing_index]
                        if pairing_index == seated and thickness > _TOUCH_MM and seats:
                            opposed = _opposed_seat(seats, translation)
                            if opposed is not None:
                                rotation, translation = opposed
                                thickness = _overlap_thickness(
                                    rect_a, rect_b, rotation, translation
                                )
                        transform = _transform(
                            left.frame,
                            right.frame,
                            rotation,
                            translation,
                            envelope.id,
                        )
                        score = Score(
                            value=_physical_value(chord_gap, curve_penalty, thickness),
                            run_id=run_id,
                            channel="physical",
                            hypothesis_type="join",
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
