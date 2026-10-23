"""Search rigid non-overlapping page assemblies and keep the top N.

Stage 6 in ``docs/ALGORITHM.md`` places admitted pairwise joins in the one
shared ``page_global_mm`` frame. The implemented algorithm is
``rigid_assembly_search`` version ``1``. A kept assembly's ``physical``
score is ``join_score_sum_minus_range_penalty``: the sum of the member
joins' ``physical`` scores minus the millimetres by which the shifted
width or height falls outside the caller-supplied page ranges. That
penalty is a known limitation of the rigid model. The score does not
recover a historical page size.

The anchor fragment is the one with the least id bytes. Before the final
shift its page rotation is 0 and its translation is ``(0, 0)``. The join
pose maps fragment A's local frame onto fragment B's local frame, so a
page pose of B satisfies ``page_B ∘ join = page_A``. Overlap is positive
intersection area. Boundary contact stays. A dropped subset is not
inserted. Rank is the physical order from ``prw.assembly_rank`` and is
not stored on the assembly.

These records are internal. They are not a stable public API, and they
do not write a project directory.
"""

from __future__ import annotations

import itertools
import json
import math
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from prw.assemblies import AssemblyLog, placement_pose
from prw.assembly_rank import physical_assembly_order
from prw.frames import CoordinateFrame, PageFrame
from prw.identity import ABSENT, content_id
from prw.joins import JoinHypothesis, RigidTransform
from prw.outlines import Fragment, FragmentOutlineRevision
from prw.provenance import (
    AlgorithmRun,
    AssemblyContent,
    HypothesisStatus,
    Placement,
    ProvenanceEnvelope,
    Score,
    StatusEvent,
    StatusStream,
    run_id_inputs,
)
from prw.screening import ScreeningEvent, ScreeningLog

ALGORITHM_NAME = "rigid_assembly_search"
ALGORITHM_VERSION = "1"
SCORE_NAME = "join_score_sum_minus_range_penalty"
_POSITIVE_AREA_MM2 = 1e-8
_ADMITTED_STATUS = frozenset({"catalogued", "confirmed"})
_CONTESTED_JOIN = frozenset({"rejected", "rejected-via-ValidationDecision"})
type Point = tuple[float, float]
type Pose = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class FragmentOutline:
    """One fragment outline in its millimetre frame.

    ``frame`` is the outline's ``fragment_local_mm`` frame. A ``detected``
    fragment may be present so a join that cites it can be excluded.
    """

    fragment: Fragment
    frame: CoordinateFrame
    outline: FragmentOutlineRevision

    def __post_init__(self) -> None:
        if not isinstance(self.fragment, Fragment):
            raise TypeError("An outline pool entry cites a Fragment.")
        if not isinstance(self.frame, CoordinateFrame):
            raise TypeError("The outline frame is a CoordinateFrame.")
        if not isinstance(self.outline, FragmentOutlineRevision):
            raise TypeError("The outline is a FragmentOutlineRevision.")
        if self.outline.fragment_id != self.fragment.id:
            raise ValueError("The outline cites that fragment.")
        if self.frame.owner_id != self.fragment.id:
            raise ValueError("The fragment_local_mm frame is owned by that fragment.")
        if self.outline.frame_id != self.frame.id:
            raise ValueError("The outline cites its coordinate frame.")


@dataclass(frozen=True, slots=True)
class AssemblySearch:
    """One completed ``rigid_assembly_search`` run.

    ``assemblies`` is the first N kept candidates in physical order. An
    empty tuple is a completed run whose subsets were dropped or whose
    joins were excluded. No one-fragment assembly is stored. See stage 6
    in ``docs/ALGORITHM.md``.
    """

    run: AlgorithmRun
    assemblies: tuple[AssemblyContent, ...]
    poses: tuple[RigidTransform, ...]
    screening: tuple[ScreeningEvent, ...]
    proposed: tuple[StatusEvent, ...]
    contested: tuple[StatusEvent, ...]

    def __post_init__(self) -> None:
        provenance = self.run.provenance
        if self.run.status != "completed" or self.run.attempt_id is not None:
            raise ValueError("A completed assembly search has no attempt_id.")
        if provenance.algorithm_name != ALGORITHM_NAME:
            raise ValueError("The assembly algorithm is rigid_assembly_search.")
        if provenance.algorithm_version != ALGORITHM_VERSION:
            raise ValueError("The assembly algorithm version is 1.")
        if provenance.model_hash != ABSENT or provenance.random_seed is not None:
            raise ValueError("An assembly search omits a model and a random seed.")
        parameters = _blob(provenance)
        if parameters.get("score") != SCORE_NAME:
            raise ValueError(
                "The parameter blob names join_score_sum_minus_range_penalty."
            )
        if self.run.assembly_ids != tuple(item.id for item in self.assemblies):
            raise ValueError("The completed run lists the assembly ids in rank order.")
        if self.run.join_ids or self.run.reading_ids:
            raise ValueError("An assembly search emits assemblies.")
        if len(self.proposed) != len(self.assemblies):
            raise ValueError("Each inserted assembly is proposed.")


@dataclass(frozen=True, slots=True)
class FailedAssemblySearch:
    """A failed assembly search. No assembly and no screening event are stored.

    ``run.attempt_id`` is set. The run id is not the id a later completed
    run of the same inputs would take. See stage 6 in ``docs/ALGORITHM.md``.
    """

    run: AlgorithmRun

    def __post_init__(self) -> None:
        if self.run.status != "failed" or self.run.attempt_id is None:
            raise ValueError("A failed assembly search stores attempt_id.")
        completed = content_id(run_id_inputs(self.run.provenance, "completed", None))
        if self.run.id == completed:
            raise ValueError(
                "A failed run id is not the completed id of the same inputs."
            )
        if self.run.assembly_ids or self.run.join_ids or self.run.reading_ids:
            raise ValueError("A failed assembly search emits no assembly.")
        provenance = self.run.provenance
        if provenance.model_hash != ABSENT or provenance.random_seed is not None:
            raise ValueError("An assembly search omits a model and a random seed.")
        if provenance.algorithm_name != ALGORITHM_NAME:
            raise ValueError("The assembly algorithm is rigid_assembly_search.")


@dataclass(frozen=True, slots=True)
class _Kept:
    assembly: AssemblyContent
    poses: tuple[RigidTransform, ...]
    joins: tuple[JoinHypothesis, ...]


class AssemblySearchLog:
    """In-memory rigid assembly searches.

    A repeated completed run returns the stored assemblies. Screening
    events stay on this log. The search does not read a benchmark label.
    """

    def __init__(self) -> None:
        self._runs: list[AlgorithmRun] = []
        self._completed: dict[uuid.UUID, AssemblySearch] = {}
        self._assemblies = AssemblyLog()
        self._screening = ScreeningLog()
        self._status = StatusStream()

    @property
    def runs(self) -> tuple[AlgorithmRun, ...]:
        return tuple(self._runs)

    @property
    def assemblies(self) -> tuple[AssemblyContent, ...]:
        return self._assemblies.rows

    @property
    def screening(self) -> tuple[ScreeningEvent, ...]:
        return self._screening.rows

    def search(
        self,
        joins: Sequence[object],
        transforms: Sequence[object],
        runs: Sequence[object],
        events: StatusStream | Sequence[StatusEvent],
        outlines: Sequence[object],
        page: object,
        page_frame: object,
        *,
        n: object,
        translation_tolerance_mm: object,
        rotation_tolerance_radians: object,
        code_version: str,
        recorded_at: str,
    ) -> AssemblySearch | FailedAssemblySearch:
        """Search admitted joins and keep at most ``n`` assemblies.

        A missing ``n`` or tolerance, a negative tolerance, a missing page
        frame, a frame other than ``page_global_mm``, an outline that is
        not ``fragment_local_mm``, disagreeing decoder names or versions,
        a join with no status event, or a join that cites no run fails
        this run and emits no assembly and no screening event.
        """
        version = _require_text(code_version, "code_version")
        prepared = _prepare(
            joins,
            transforms,
            runs,
            events,
            outlines,
            page,
            page_frame,
            n=n,
            translation_tolerance_mm=translation_tolerance_mm,
            rotation_tolerance_radians=rotation_tolerance_radians,
            code_version=version,
        )
        if isinstance(prepared, ProvenanceEnvelope):
            return self._fail(prepared, recorded_at)
        completed_id = content_id(run_id_inputs(prepared.envelope, "completed", None))
        stored = self._completed.get(completed_id)
        if stored is not None:
            return stored
        AlgorithmRun.create(
            prepared.envelope, status="completed", started_at=recorded_at
        )
        screening = tuple(
            self._screening.append(event)
            for event in _screening_events(prepared, completed_id)
        )
        kept = _kept_assemblies(prepared, completed_id)
        ordered = _rank(kept, prepared.envelope, recorded_at)
        chosen = ordered[: prepared.n]
        run = AlgorithmRun.create(
            prepared.envelope,
            status="completed",
            started_at=recorded_at,
            assembly_ids=tuple(item.assembly.id for item in chosen),
        )
        proposed: list[StatusEvent] = []
        contested: list[StatusEvent] = []
        poses: list[RigidTransform] = []
        for item in chosen:
            proposed.append(
                self._assemblies.insert(
                    self._status,
                    item.assembly,
                    recorded_at=recorded_at,
                    actor=str(run.id),
                )
            )
            poses.extend(item.poses)
            if _contested(item.joins, prepared.status):
                contested.append(
                    self._status.append(
                        target_id=item.assembly.id,
                        status="contested",
                        recorded_at=recorded_at,
                        actor=str(run.id),
                    )
                )
        result = AssemblySearch(
            run=run,
            assemblies=tuple(item.assembly for item in chosen),
            poses=tuple(poses),
            screening=screening,
            proposed=tuple(proposed),
            contested=tuple(contested),
        )
        self._runs.append(run)
        self._completed[run.id] = result
        return result

    def _fail(
        self, envelope: ProvenanceEnvelope, recorded_at: str
    ) -> FailedAssemblySearch:
        run = AlgorithmRun.create(envelope, status="failed", started_at=recorded_at)
        self._runs.append(run)
        return FailedAssemblySearch(run=run)


@dataclass(frozen=True, slots=True)
class _Prepared:
    joins: tuple[JoinHypothesis, ...]
    transforms: Mapping[uuid.UUID, RigidTransform]
    runs: Mapping[uuid.UUID, AlgorithmRun]
    status: Mapping[uuid.UUID, HypothesisStatus]
    outlines: Mapping[uuid.UUID, FragmentOutline]
    page: PageFrame
    page_frame: CoordinateFrame
    n: int
    translation_tolerance_mm: float
    rotation_tolerance_radians: float
    envelope: ProvenanceEnvelope

    @property
    def admitted(self) -> tuple[JoinHypothesis, ...]:
        return tuple(join for join in self.joins if _admit(join, self) is None)


def _require_text(value: str, label: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{label} is required.")
    return value


def _blob(provenance: ProvenanceEnvelope) -> dict[str, Any]:
    parsed = json.loads(provenance.parameter_blob)
    if not isinstance(parsed, dict):
        raise ValueError("parameter_blob is a JSON object.")
    return parsed


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


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


def _latest(events: Sequence[StatusEvent]) -> dict[uuid.UUID, HypothesisStatus]:
    found: dict[uuid.UUID, HypothesisStatus] = {}
    for event in events:
        found[event.target_id] = event.status
    return found


def _sequence(value: object, label: str) -> tuple[object, ...]:
    if isinstance(value, str | bytes) or not isinstance(value, Sequence):
        raise TypeError(label)
    return tuple(value)


def _prepare(
    joins: Sequence[object],
    transforms: Sequence[object],
    runs: Sequence[object],
    events: StatusStream | Sequence[StatusEvent],
    outlines: Sequence[object],
    page: object,
    page_frame: object,
    *,
    n: object,
    translation_tolerance_mm: object,
    rotation_tolerance_radians: object,
    code_version: str,
) -> _Prepared | ProvenanceEnvelope:
    stored_joins = _joins(_sequence(joins, "Joins are JoinHypothesis rows."))
    stored_transforms = _transforms(
        _sequence(transforms, "Transforms are RigidTransform rows.")
    )
    stored_runs = _runs(_sequence(runs, "Runs are AlgorithmRun rows."))
    status = _latest(_events(events))
    stored_outlines = _outlines(
        _sequence(outlines, "Outlines are FragmentOutline rows.")
    )
    stored_n = _optional_int(n)
    stored_translation = _optional_float(translation_tolerance_mm)
    stored_rotation = _optional_float(rotation_tolerance_radians)
    stored_page = page if isinstance(page, PageFrame) else None
    stored_frame = page_frame if isinstance(page_frame, CoordinateFrame) else None
    fatal = not _parameters_ok(stored_n, stored_translation, stored_rotation)
    if stored_page is None or stored_frame is None:
        fatal = True
    else:
        frame_mismatch = (
            stored_frame.kind != "page_global_mm"
            or stored_frame.id != stored_page.frame_id
        )
        if frame_mismatch:
            fatal = True
    if any(item.frame.kind != "fragment_local_mm" for item in stored_outlines.values()):
        fatal = True
    if any(join.run_id not in stored_runs for join in stored_joins):
        fatal = True
    if any(status.get(join.id) is None for join in stored_joins):
        fatal = True
    if any(join.transform_id not in stored_transforms for join in stored_joins):
        fatal = True
    envelopes = _cited_envelopes(stored_joins, stored_runs)
    decoders_agree, decoder_name, decoder_version = _decoders(envelopes)
    if not decoders_agree:
        fatal = True
    envelope = _envelope(
        envelopes,
        stored_joins,
        status,
        stored_outlines,
        stored_page,
        stored_n,
        stored_translation,
        stored_rotation,
        decoder_name,
        decoder_version,
        code_version,
    )
    if (
        fatal
        or stored_page is None
        or stored_frame is None
        or stored_n is None
        or stored_translation is None
        or stored_rotation is None
    ):
        return envelope
    return _Prepared(
        joins=stored_joins,
        transforms=stored_transforms,
        runs=stored_runs,
        status=status,
        outlines=stored_outlines,
        page=stored_page,
        page_frame=stored_frame,
        n=stored_n,
        translation_tolerance_mm=stored_translation,
        rotation_tolerance_radians=stored_rotation,
        envelope=envelope,
    )


def _parameters_ok(
    n: int | None,
    translation: float | None,
    rotation: float | None,
) -> bool:
    if n is None or n < 1:
        return False
    if translation is None or translation < 0.0:
        return False
    return rotation is not None and rotation >= 0.0


def _joins(items: Sequence[object]) -> tuple[JoinHypothesis, ...]:
    stored: list[JoinHypothesis] = []
    seen: set[uuid.UUID] = set()
    for item in items:
        if not isinstance(item, JoinHypothesis):
            raise TypeError("Joins are JoinHypothesis rows.")
        if item.id in seen:
            raise ValueError("A join appears once.")
        seen.add(item.id)
        stored.append(item)
    stored.sort(key=lambda join: join.id.bytes)
    return tuple(stored)


def _transforms(items: Sequence[object]) -> dict[uuid.UUID, RigidTransform]:
    stored: dict[uuid.UUID, RigidTransform] = {}
    for item in items:
        if not isinstance(item, RigidTransform):
            raise TypeError("Transforms are RigidTransform rows.")
        stored.setdefault(item.id, item)
    return stored


def _runs(items: Sequence[object]) -> dict[uuid.UUID, AlgorithmRun]:
    stored: dict[uuid.UUID, AlgorithmRun] = {}
    for item in items:
        if not isinstance(item, AlgorithmRun):
            raise TypeError("Runs are AlgorithmRun rows.")
        stored[item.id] = item
    return stored


def _outlines(items: Sequence[object]) -> dict[uuid.UUID, FragmentOutline]:
    stored: dict[uuid.UUID, FragmentOutline] = {}
    for item in items:
        if not isinstance(item, FragmentOutline):
            raise TypeError("Outlines are FragmentOutline rows.")
        if item.fragment.id in stored:
            raise ValueError("A fragment appears once in the outline pool.")
        stored[item.fragment.id] = item
    return stored


def _cited_envelopes(
    joins: Sequence[JoinHypothesis],
    runs: Mapping[uuid.UUID, AlgorithmRun],
) -> tuple[ProvenanceEnvelope, ...]:
    found: list[ProvenanceEnvelope] = []
    seen: set[uuid.UUID] = set()
    for join in joins:
        run = runs.get(join.run_id)
        if run is None or run.provenance.id in seen:
            continue
        seen.add(run.provenance.id)
        found.append(run.provenance)
    return tuple(found)


def _decoders(
    envelopes: Sequence[ProvenanceEnvelope],
) -> tuple[bool, str, str]:
    names = {(item.decoder_name, item.decoder_version) for item in envelopes}
    if not names:
        return True, ABSENT, ABSENT
    if len(names) == 1:
        name, version = next(iter(names))
        return True, name, version
    name, version = min(names)
    return False, name, version


def _envelope(
    envelopes: Sequence[ProvenanceEnvelope],
    joins: Sequence[JoinHypothesis],
    status: Mapping[uuid.UUID, HypothesisStatus],
    outlines: Mapping[uuid.UUID, FragmentOutline],
    page: PageFrame | None,
    n: int | None,
    translation: float | None,
    rotation: float | None,
    decoder_name: str,
    decoder_version: str,
    code_version: str,
) -> ProvenanceEnvelope:
    hashes = sorted({digest for item in envelopes for digest in item.source_hashes})
    parameters: dict[str, Any] = {
        "anchor": "least_fragment_id_bytes",
        "anchor_rotation_radians": 0,
        "join_ids": [str(join.id) for join in joins],
        "join_status": [
            {"join_id": str(join.id), "status": status.get(join.id, "absent")}
            for join in joins
        ],
        "outlines": [
            {
                "fragment_id": str(item.fragment.id),
                "frame_id": str(item.frame.id),
                "identification_status": item.fragment.identification_status,
                "outline_revision_id": str(item.outline.id),
            }
            for item in sorted(outlines.values(), key=lambda row: row.fragment.id.bytes)
        ],
        "page_origin": "minimum_corner",
        "score": SCORE_NAME,
    }
    if n is not None:
        parameters["n"] = n
    if translation is not None:
        parameters["translation_tolerance_mm"] = translation
    if rotation is not None:
        parameters["rotation_tolerance_radians"] = rotation
    if page is not None:
        parameters["page_frame_id"] = page.id
        parameters["min_width_mm"] = page.min_width_mm
        parameters["max_width_mm"] = page.max_width_mm
        parameters["min_height_mm"] = page.min_height_mm
        parameters["max_height_mm"] = page.max_height_mm
    return ProvenanceEnvelope.create(
        source_hashes=hashes,
        parameters=parameters,
        algorithm_name=ALGORITHM_NAME,
        algorithm_version=ALGORITHM_VERSION,
        code_version=code_version,
        decoder_name=decoder_name,
        decoder_version=decoder_version,
    )


def _admit(join: JoinHypothesis, prepared: _Prepared) -> str | None:
    """Return an exclusion reason, or None when the join is admitted."""
    if prepared.status[join.id] == "invalidated":
        return "invalidated"
    run = prepared.runs[join.run_id]
    if run.status in {"failed", "cancelled"}:
        return "run"
    left = prepared.outlines.get(join.fragment_a_id)
    right = prepared.outlines.get(join.fragment_b_id)
    if left is None or right is None:
        return "absent"
    if (
        left.fragment.identification_status not in _ADMITTED_STATUS
        or right.fragment.identification_status not in _ADMITTED_STATUS
    ):
        return "fragment"
    scores = [
        score
        for score in join.scores
        if score.channel == "physical" and score.hypothesis_type == "join"
    ]
    if len(scores) != 1:
        return "score"
    return None


def _screening_events(
    prepared: _Prepared, run_id: uuid.UUID
) -> tuple[ScreeningEvent, ...]:
    events: list[ScreeningEvent] = []
    for join in prepared.joins:
        outcome = "admitted" if _admit(join, prepared) is None else "excluded"
        events.append(
            ScreeningEvent.create(
                run_id=run_id,
                hypothesis_id=join.id,
                gate="physical",
                outcome=outcome,
            )
        )
    return tuple(events)


def _subsets(
    joins: Sequence[JoinHypothesis],
) -> tuple[tuple[JoinHypothesis, ...], ...]:
    ordered = tuple(sorted(joins, key=lambda join: join.id.bytes))
    groups: list[tuple[JoinHypothesis, ...]] = []
    for size in range(1, len(ordered) + 1):
        groups.extend(itertools.combinations(ordered, size))
    groups.sort(key=lambda group: tuple(join.id.bytes for join in group))
    return tuple(groups)


def _pose_of(transform: RigidTransform) -> Pose:
    return (
        transform.rotation_radians,
        transform.translation_x,
        transform.translation_y,
    )


def _wrap(radians: float) -> float:
    return math.atan2(math.sin(radians), math.cos(radians))


def _invert(pose: Pose) -> Pose:
    rotation, tx, ty = pose
    cosine = math.cos(rotation)
    sine = math.sin(rotation)
    return (_wrap(-rotation), -(cosine * tx + sine * ty), -(-sine * tx + cosine * ty))


def _compose(left: Pose, right: Pose) -> Pose:
    """Return ``left ∘ right``: apply ``right`` first."""
    left_rotation, left_x, left_y = left
    right_rotation, right_x, right_y = right
    cosine = math.cos(left_rotation)
    sine = math.sin(left_rotation)
    return (
        _wrap(left_rotation + right_rotation),
        cosine * right_x - sine * right_y + left_x,
        sine * right_x + cosine * right_y + left_y,
    )


def _apply(pose: Pose, point: Point) -> Point:
    rotation, tx, ty = pose
    cosine = math.cos(rotation)
    sine = math.sin(rotation)
    return (
        cosine * point[0] - sine * point[1] + tx,
        sine * point[0] + cosine * point[1] + ty,
    )


def _agrees(
    pose_a: Pose,
    pose_b: Pose,
    join_pose: Pose,
    translation_tolerance_mm: float,
    rotation_tolerance_radians: float,
) -> bool:
    implied = _compose(_invert(pose_b), pose_a)
    rotation_gap = abs(_wrap(implied[0] - join_pose[0]))
    translation_gap = math.hypot(implied[1] - join_pose[1], implied[2] - join_pose[2])
    return (
        rotation_gap <= rotation_tolerance_radians
        and translation_gap <= translation_tolerance_mm
    )


def _place_subset(
    subset: Sequence[JoinHypothesis],
    prepared: _Prepared,
) -> dict[uuid.UUID, Pose] | None:
    fragment_ids = {
        fragment_id
        for join in subset
        for fragment_id in (join.fragment_a_id, join.fragment_b_id)
    }
    anchor = min(fragment_ids, key=lambda fragment_id: fragment_id.bytes)
    poses: dict[uuid.UUID, Pose] = {anchor: (0.0, 0.0, 0.0)}
    pending = list(subset)
    progressed = True
    while progressed:
        progressed = False
        waiting: list[JoinHypothesis] = []
        for join in pending:
            pose = _pose_of(prepared.transforms[join.transform_id])
            placed_a = join.fragment_a_id in poses
            placed_b = join.fragment_b_id in poses
            if placed_a and placed_b:
                if not _agrees(
                    poses[join.fragment_a_id],
                    poses[join.fragment_b_id],
                    pose,
                    prepared.translation_tolerance_mm,
                    prepared.rotation_tolerance_radians,
                ):
                    return None
                continue
            if placed_a == placed_b:
                waiting.append(join)
                continue
            if placed_a:
                poses[join.fragment_b_id] = _compose(
                    poses[join.fragment_a_id], _invert(pose)
                )
            else:
                poses[join.fragment_a_id] = _compose(poses[join.fragment_b_id], pose)
            progressed = True
        pending = waiting
    if len(poses) != len(fragment_ids) or pending:
        return None
    return poses


def _shift(
    poses: dict[uuid.UUID, Pose],
    polygons: Mapping[uuid.UUID, tuple[Point, ...]],
) -> dict[uuid.UUID, Pose]:
    placed = [
        _apply(poses[fragment_id], point)
        for fragment_id, polygon in polygons.items()
        for point in polygon
    ]
    min_x = min(point[0] for point in placed)
    min_y = min(point[1] for point in placed)
    return {
        fragment_id: (rotation, tx - min_x, ty - min_y)
        for fragment_id, (rotation, tx, ty) in poses.items()
    }


def _polygons(
    poses: Mapping[uuid.UUID, Pose],
    outlines: Mapping[uuid.UUID, FragmentOutline],
) -> dict[uuid.UUID, tuple[Point, ...]]:
    return {
        fragment_id: tuple(
            _apply(pose, point) for point in outlines[fragment_id].outline.polygon
        )
        for fragment_id, pose in poses.items()
    }


def _overlaps(polygons: Mapping[uuid.UUID, tuple[Point, ...]]) -> bool:
    placed = list(polygons.values())
    for index, left in enumerate(placed):
        for right in placed[index + 1 :]:
            if _positive_overlap(left, right):
                return True
    return False


def _positive_overlap(left: Sequence[Point], right: Sequence[Point]) -> bool:
    left_ccw = _ccw(left)
    right_ccw = _ccw(right)
    if _convex(left_ccw) and _convex(right_ccw):
        return _area(_clip(left_ccw, right_ccw)) > _POSITIVE_AREA_MM2
    return _general_overlap(left_ccw, right_ccw)


def _ccw(polygon: Sequence[Point]) -> tuple[Point, ...]:
    points = tuple(polygon)
    if _signed_area(points) < 0.0:
        return tuple(reversed(points))
    return points


def _signed_area(polygon: Sequence[Point]) -> float:
    total = 0.0
    count = len(polygon)
    for index, point in enumerate(polygon):
        nxt = polygon[(index + 1) % count]
        total += point[0] * nxt[1] - nxt[0] * point[1]
    return total / 2.0


def _area(polygon: Sequence[Point]) -> float:
    return abs(_signed_area(polygon))


def _convex(polygon: Sequence[Point]) -> bool:
    turns: list[float] = []
    count = len(polygon)
    for index, point in enumerate(polygon):
        nxt = polygon[(index + 1) % count]
        after = polygon[(index + 2) % count]
        turn = _orient(point, nxt, after)
        if turn != 0.0:
            turns.append(turn)
    return all(turn > 0.0 for turn in turns) or all(turn < 0.0 for turn in turns)


def _orient(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


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


def _line_hit(a: Point, b: Point, c: Point, d: Point) -> Point:
    denominator = (a[0] - b[0]) * (c[1] - d[1]) - (a[1] - b[1]) * (c[0] - d[0])
    if denominator == 0.0:
        return a
    scale = (
        (a[0] - c[0]) * (c[1] - d[1]) - (a[1] - c[1]) * (c[0] - d[0])
    ) / denominator
    return (a[0] + scale * (b[0] - a[0]), a[1] + scale * (b[1] - a[1]))


def _general_overlap(left: Sequence[Point], right: Sequence[Point]) -> bool:
    if _edges_cross(left, right):
        return True
    return _sample_inside(left, right) or _sample_inside(right, left)


def _edges_cross(left: Sequence[Point], right: Sequence[Point]) -> bool:
    for start, end in _edges(left):
        for other_start, other_end in _edges(right):
            if _proper_cross(start, end, other_start, other_end):
                return True
    return False


def _edges(polygon: Sequence[Point]) -> tuple[tuple[Point, Point], ...]:
    count = len(polygon)
    return tuple(
        (polygon[index], polygon[(index + 1) % count]) for index in range(count)
    )


def _proper_cross(a: Point, b: Point, c: Point, d: Point) -> bool:
    first = _orient(a, b, c)
    second = _orient(a, b, d)
    third = _orient(c, d, a)
    fourth = _orient(c, d, b)
    return first * second < 0.0 and third * fourth < 0.0


def _sample_inside(source: Sequence[Point], target: Sequence[Point]) -> bool:
    for point in source:
        if _strictly_inside(point, target):
            return True
    count = len(source)
    for index, start in enumerate(source):
        end = source[(index + 1) % count]
        midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        if _strictly_inside(midpoint, target):
            return True
    return False


def _strictly_inside(point: Point, polygon: Sequence[Point]) -> bool:
    if _on_boundary(point, polygon):
        return False
    crossings = 0
    count = len(polygon)
    for index, start in enumerate(polygon):
        end = polygon[(index + 1) % count]
        if (start[1] > point[1]) == (end[1] > point[1]):
            continue
        crossing_x = start[0] + (end[0] - start[0]) * (point[1] - start[1]) / (
            end[1] - start[1]
        )
        if crossing_x > point[0]:
            crossings += 1
    return crossings % 2 == 1


def _on_boundary(point: Point, polygon: Sequence[Point]) -> bool:
    for start, end in _edges(polygon):
        if _orient(start, end, point) != 0.0:
            continue
        within_x = (
            min(start[0], end[0]) - 1e-12 <= point[0] <= max(start[0], end[0]) + 1e-12
        )
        within_y = (
            min(start[1], end[1]) - 1e-12 <= point[1] <= max(start[1], end[1]) + 1e-12
        )
        if within_x and within_y:
            return True
    return False


def _range_penalty(width: float, height: float, page: PageFrame) -> float:
    return _axis_penalty(width, page.min_width_mm, page.max_width_mm) + _axis_penalty(
        height, page.min_height_mm, page.max_height_mm
    )


def _axis_penalty(measure: float, low: float, high: float) -> float:
    if measure < low:
        return low - measure
    if measure > high:
        return measure - high
    return 0.0


def _extent(polygons: Mapping[uuid.UUID, tuple[Point, ...]]) -> tuple[float, float]:
    points = [point for polygon in polygons.values() for point in polygon]
    width = max(point[0] for point in points) - min(point[0] for point in points)
    height = max(point[1] for point in points) - min(point[1] for point in points)
    return width, height


def _kept_assemblies(prepared: _Prepared, run_id: uuid.UUID) -> tuple[_Kept, ...]:
    admitted_fragments = tuple(
        sorted(
            (
                item.fragment.id
                for item in prepared.outlines.values()
                if item.fragment.identification_status in _ADMITTED_STATUS
            ),
            key=lambda fragment_id: fragment_id.bytes,
        )
    )
    kept: list[_Kept] = []
    for subset in _subsets(prepared.admitted):
        placed = _place_subset(subset, prepared)
        if placed is None:
            continue
        shifted = _shift(
            placed,
            {
                fragment_id: prepared.outlines[fragment_id].outline.polygon
                for fragment_id in placed
            },
        )
        polygons = _polygons(shifted, prepared.outlines)
        if _overlaps(polygons):
            continue
        kept.append(_assembly(prepared, subset, shifted, admitted_fragments, run_id))
    return tuple(kept)


def _assembly(
    prepared: _Prepared,
    subset: Sequence[JoinHypothesis],
    poses: Mapping[uuid.UUID, Pose],
    admitted_fragments: Sequence[uuid.UUID],
    run_id: uuid.UUID,
) -> _Kept:
    ordered_joins = tuple(sorted(subset, key=lambda join: join.id.bytes))
    score_value = sum(_physical_value(join) for join in ordered_joins)
    width, height = _extent(_polygons(poses, prepared.outlines))
    score_value -= _range_penalty(width, height, prepared.page)
    built: list[tuple[uuid.UUID, RigidTransform]] = []
    for fragment_id in sorted(poses, key=lambda item: item.bytes):
        outline = prepared.outlines[fragment_id]
        rotation, tx, ty = poses[fragment_id]
        built.append(
            (
                fragment_id,
                placement_pose(
                    from_frame=outline.frame,
                    to_frame=prepared.page_frame,
                    rotation_radians=rotation,
                    translation_x=tx,
                    translation_y=ty,
                    provenance_id=prepared.envelope.id,
                ),
            )
        )
    placements = tuple(
        Placement(
            fragment_id=fragment_id,
            outline_revision_id=prepared.outlines[fragment_id].outline.id,
            transform_id=pose.id,
        )
        for fragment_id, pose in built
    )
    placed_ids = {fragment_id for fragment_id, _pose in built}
    unplaced = tuple(
        fragment_id
        for fragment_id in admitted_fragments
        if fragment_id not in placed_ids
    )
    assembly = AssemblyContent.create(
        page_frame_id=prepared.page.id,
        producer="machine",
        join_ids=tuple(join.id for join in ordered_joins),
        placements=placements,
        unplaced_fragment_ids=unplaced,
        scores=(
            Score(
                value=score_value,
                run_id=run_id,
                channel="physical",
                hypothesis_type="assembly",
            ),
        ),
        provenance_id=prepared.envelope.id,
        run_id=run_id,
    )
    return _Kept(
        assembly=assembly,
        poses=tuple(pose for _fragment_id, pose in built),
        joins=ordered_joins,
    )


def _physical_value(join: JoinHypothesis) -> float:
    score = next(
        item
        for item in join.scores
        if item.channel == "physical" and item.hypothesis_type == "join"
    )
    return float(score.value)


def _rank(
    kept: Sequence[_Kept], envelope: ProvenanceEnvelope, recorded_at: str
) -> tuple[_Kept, ...]:
    if not kept:
        return ()
    by_id = {item.assembly.id: item for item in kept}
    ranking_run = AlgorithmRun.create(
        envelope, status="completed", started_at=recorded_at
    )
    stream = StatusStream()
    for item in kept:
        stream.append(
            target_id=item.assembly.id,
            status="proposed",
            recorded_at=recorded_at,
            actor=str(ranking_run.id),
        )
    ordered = physical_assembly_order(
        tuple(item.assembly for item in kept),
        (ranking_run,),
        stream,
    )
    return tuple(by_id[assembly.id] for assembly in ordered)


def _contested(
    joins: Sequence[JoinHypothesis],
    status: Mapping[uuid.UUID, HypothesisStatus],
) -> bool:
    return any(status[join.id] in _CONTESTED_JOIN for join in joins)
