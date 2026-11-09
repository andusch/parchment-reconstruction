"""In-memory review of ranked pairwise joins.

The rank order is ``physical_join_order``. This module does not score joins
and does not read ``benchmarks/``. A join stays epistemic class ``hypothesis``.
A validation decision is appended. It does not rewrite the join and it does
not drop another join from the list. The session is not a project directory.
``Q-ENG-01`` stays open.

The actor string ``local-operator`` is one local operator. ``Q-PRD-01`` stays
open, and the session does not store a person's name.
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from prw.edge_chord import EdgeChordLog, FailedEdgeChord
from prw.ingest import IntegrityFailure, UnsupportedMediaType
from prw.join_rank import physical_join_order
from prw.joins import JoinHypothesis, RigidTransform
from prw.lossless_tiff import TiffDecodeFailure
from prw.outlines import Fragment
from prw.pairwise_join import FailedPairwiseJoin, FragmentChords, PairwiseJoinLog
from prw.provenance import AlgorithmRun, HypothesisStatus, StatusEvent, StatusStream
from prw.scale import CallerScale, ScaledOutline, ScaleLog
from prw.segment import (
    FailedSegmentation,
    SegmentationLog,
    SegmentedOutline,
    pool_project_id,
)

type Point = tuple[float, float]
type DecisionWord = Literal["accept", "reject", "defer"]

LOCAL_OPERATOR = "local-operator"
REVIEW_BANNER = (
    "These joins are hypotheses. Each row is a hypothesis. Rank 1 is the "
    "first row of the physical score sort. It is not a historical join and "
    "it is not the answer."
)
PLACEMENT_CAPTION = (
    "Placement sketch of this hypothesis in fragment-local millimetres. "
    "The moved outline follows the stored pose. This is not a page and not "
    "a historical join."
)
DECISION_NOTE = (
    "A validation decision does not delete other hypotheses and does not "
    "change epistemic class."
)
EMPTY_JOINS = "No join hypothesis was proposed."


@dataclass(frozen=True, slots=True)
class PoolImage:
    """One labeled image path. The label is not a reconstruction."""

    label: str
    path: Path

    def __post_init__(self) -> None:
        if self.label == "":
            raise ValueError("A fragment label is required.")
        object.__setattr__(self, "path", Path(self.path))


@dataclass(frozen=True, slots=True)
class RankRequest:
    """Inputs for one rank, matching the headless pool flags."""

    images: tuple[PoolImage, ...]
    foreground_threshold: int
    pixels_per_mm: float
    uncertainty: float
    minimum_edge_length_mm: float
    code_version: str
    recorded_at: str


@dataclass(frozen=True, slots=True)
class ReviewFailure:
    """A pipeline failure. It is not a join and it has no epistemic class."""

    record: str
    detail: str


@dataclass(frozen=True, slots=True)
class ReviewFragment:
    """One millimetre outline shown beside the joins."""

    label: str
    fragment_id: uuid.UUID
    polygon: tuple[Point, ...]
    epistemic_class: Literal["interpretation"]
    producer: Literal["machine"]


@dataclass(frozen=True, slots=True)
class ReviewEdge:
    """One chord in ``fragment_local_mm``. The class is ``interpretation``."""

    edge_id: uuid.UUID
    fragment_id: uuid.UUID
    geometry: tuple[Point, ...]
    epistemic_class: Literal["interpretation"]


@dataclass(frozen=True, slots=True)
class ReviewJoinRow:
    """One ranked hypothesis a reviewer can read."""

    rank: int
    join_id: uuid.UUID
    epistemic_class: Literal["hypothesis"]
    fragment_a_label: str
    fragment_b_label: str
    score: float
    channel: Literal["physical"]
    status: HypothesisStatus
    decision: DecisionWord | None

    def __post_init__(self) -> None:
        if self.rank < 1:
            raise ValueError("Rank is a position starting at 1.")
        if self.epistemic_class != "hypothesis":
            raise ValueError("A join's epistemic class is hypothesis.")
        if self.channel != "physical":
            raise ValueError("This review sorts the physical channel.")


@dataclass(frozen=True, slots=True)
class PlacementSketch:
    """Two outlines in the destination fragment's local millimetres.

    The pose maps fragment A into fragment B. The sketch is still a hypothesis.
    """

    caption: str
    frame: Literal["fragment_local_mm"]
    epistemic_class: Literal["hypothesis"]
    anchor_label: str
    moved_label: str
    anchor_polygon: tuple[Point, ...]
    moved_polygon: tuple[Point, ...]
    anchor_edge: tuple[Point, ...]
    moved_edge: tuple[Point, ...]


@dataclass(frozen=True, slots=True)
class ValidationDecision:
    """Append-only decision. The id is a random UUID.

    See ``ValidationDecision`` in ``docs/DATA_MODEL.md``. Accept does not
    re-type the target.
    """

    id: uuid.UUID
    target_hypothesis_id: uuid.UUID
    actor: str
    decided_at: str
    decision: DecisionWord
    comment: str | None = None

    def __post_init__(self) -> None:
        if self.id.version != 4:
            raise ValueError("A validation decision id is a random UUID.")
        if self.decision not in {"accept", "reject", "defer"}:
            raise ValueError("A validation decision is accept, reject, or defer.")
        if self.actor == "":
            raise ValueError("actor is required.")
        _require_utc(self.decided_at)
        if self.comment is not None and self.comment == "":
            raise ValueError("An empty comment is omitted.")


class ReviewSession:
    """Ranked joins plus an append-only decision log.

    Join objects stay as they were inserted. Rank is derived on read.
    """

    def __init__(
        self,
        *,
        fragments: tuple[ReviewFragment, ...],
        edges: tuple[ReviewEdge, ...],
        joins: tuple[JoinHypothesis, ...],
        transforms: tuple[RigidTransform, ...],
        run: AlgorithmRun,
        proposed: tuple[StatusEvent, ...],
    ) -> None:
        self._fragments = {item.fragment_id: item for item in fragments}
        self._edges = {item.edge_id: item for item in edges}
        self._joins = joins
        self._transforms = {item.id: item for item in transforms}
        self._run = run
        self._status = StatusStream()
        for event in proposed:
            self._status.replay(event)
        self._decisions: list[ValidationDecision] = []

    def banner(self) -> str:
        """The sentence shown above every ranked list."""
        return REVIEW_BANNER

    def decision_note(self) -> str:
        """The sentence shown beside the decision buttons."""
        return DECISION_NOTE

    def fragments(self) -> tuple[ReviewFragment, ...]:
        """Loaded outlines, in pool order."""
        return tuple(self._fragments.values())

    def outline_line(self) -> str:
        """One line naming the loaded outlines and their epistemic class."""
        labels = ", ".join(item.label for item in self.fragments())
        if labels == "":
            return "No outline was loaded."
        return f"Loaded outlines, epistemic class interpretation: {labels}."

    def hypothesis_ids(self) -> tuple[uuid.UUID, ...]:
        """Every join id stored for this run, including a rejected one."""
        return tuple(join.id for join in self._joins)

    def content_bytes(self, join_id: uuid.UUID) -> bytes:
        """Canonical join content. A decision does not change these bytes."""
        return self._require_join(join_id).content_bytes()

    def rows(self) -> tuple[ReviewJoinRow, ...]:
        """Physical order. A rejected join stays. Rank is the position."""
        ordered = physical_join_order(self._joins, (self._run,), self._status)
        latest: dict[uuid.UUID, DecisionWord] = {}
        for decision in self._decisions:
            latest[decision.target_hypothesis_id] = decision.decision
        built: list[ReviewJoinRow] = []
        for position, join in enumerate(ordered, start=1):
            status = self._status.current_status(join.id)
            if status is None:
                raise ValueError("A join has a status event.")
            channel = join.scores[0].channel
            if channel != "physical":
                raise ValueError("This review sorts the physical channel.")
            built.append(
                ReviewJoinRow(
                    rank=position,
                    join_id=join.id,
                    epistemic_class=join.epistemic_class,
                    fragment_a_label=self._fragments[join.fragment_a_id].label,
                    fragment_b_label=self._fragments[join.fragment_b_id].label,
                    score=float(join.scores[0].value),
                    channel=channel,
                    status=status,
                    decision=latest.get(join.id),
                )
            )
        return tuple(built)

    def placement(self, join_id: uuid.UUID) -> PlacementSketch:
        """Draw fragment A into fragment B's local millimetres."""
        join = self._require_join(join_id)
        transform = self._transforms[join.transform_id]
        anchor = self._fragments[join.fragment_b_id]
        moved = self._fragments[join.fragment_a_id]
        return PlacementSketch(
            caption=PLACEMENT_CAPTION,
            frame="fragment_local_mm",
            epistemic_class="hypothesis",
            anchor_label=anchor.label,
            moved_label=moved.label,
            anchor_polygon=anchor.polygon,
            moved_polygon=tuple(_apply(point, transform) for point in moved.polygon),
            anchor_edge=self._edges[join.edge_b_id].geometry,
            moved_edge=tuple(
                _apply(point, transform)
                for point in self._edges[join.edge_a_id].geometry
            ),
        )

    def decide(
        self,
        join_id: uuid.UUID,
        decision: DecisionWord,
        *,
        actor: str,
        decided_at: str,
        comment: str | None = None,
    ) -> ValidationDecision:
        """Append a decision. Reject also appends a status event.

        The join row is not replaced. Other joins stay in ``hypothesis_ids``.
        Accept and defer do not change status and do not change epistemic class.
        """
        join = self._require_join(join_id)
        if decision not in {"accept", "reject", "defer"}:
            raise ValueError("A validation decision is accept, reject, or defer.")
        stored_comment = None if comment in (None, "") else comment
        record = ValidationDecision(
            id=uuid.uuid4(),
            target_hypothesis_id=join.id,
            actor=actor,
            decided_at=decided_at,
            decision=decision,
            comment=stored_comment,
        )
        if decision == "reject":
            self._status.append(
                target_id=join.id,
                status="rejected-via-ValidationDecision",
                recorded_at=decided_at,
                actor=actor,
            )
        self._decisions.append(record)
        return record

    def decisions(self) -> tuple[ValidationDecision, ...]:
        """Decisions in append order."""
        return tuple(self._decisions)

    def _require_join(self, join_id: uuid.UUID) -> JoinHypothesis:
        for join in self._joins:
            if join.id == join_id:
                return join
        raise ValueError("No join hypothesis has that id.")


def row_line(row: ReviewJoinRow) -> str:
    """One list line. Rank 1 uses the same hypothesis word as every other row."""
    decision = "" if row.decision is None else f"  validation {row.decision}"
    return (
        f"Rank {row.rank} hypothesis  {row.fragment_a_label} + "
        f"{row.fragment_b_label}  physical score {row.score}  "
        f"status {row.status}{decision}"
    )


def hypothesis_lines(session: ReviewSession) -> tuple[str, ...]:
    """Lines the review list shows for this session."""
    rows = session.rows()
    if not rows:
        return (EMPTY_JOINS,)
    return tuple(row_line(row) for row in rows)


def failure_line(failure: ReviewFailure) -> str:
    """One status line for a pipeline failure."""
    return f"{failure.record}: {failure.detail}"


def load_ranked_joins(request: RankRequest) -> ReviewSession | ReviewFailure:
    """Segment, scale, trace, and rank one pool.

    Detected fragments are confirmed before pairing, which is the same
    admission rule the headless rank command uses. Ground-truth label files
    are refused before any join is proposed.
    """
    _validate_request(request)
    scale = CallerScale(
        pixels_per_mm=request.pixels_per_mm,
        uncertainty=request.uncertainty,
        producer="human",
    )
    fragments: list[ReviewFragment] = []
    edges: list[ReviewEdge] = []
    chords: list[FragmentChords] = []
    for image in request.images:
        presented = image.path.read_bytes()
        segmented = SegmentationLog().segment(
            presented,
            project_id=pool_project_id(image.label),
            label=image.label,
            foreground_threshold=request.foreground_threshold,
            code_version=request.code_version,
            recorded_at=request.recorded_at,
        )
        failure = _segment_failure(segmented)
        if failure is not None:
            return failure
        if not isinstance(segmented, SegmentedOutline):
            raise TypeError("Segmentation returned an unknown record.")
        scaled = ScaleLog().apply(
            segmented.outline,
            segmented.frame,
            scale,
            source_hashes=segmented.run.provenance.source_hashes,
            code_version=segmented.run.provenance.code_version,
            decoder_name=segmented.run.provenance.decoder_name,
            decoder_version=segmented.run.provenance.decoder_version,
            recorded_at=request.recorded_at,
        )
        if not isinstance(scaled, ScaledOutline):
            raise ValueError("A supplied scale stores a millimetre outline.")
        traced = EdgeChordLog().build(
            scaled.outline,
            scaled.frame,
            scaled.run.provenance,
            minimum_edge_length_mm=request.minimum_edge_length_mm,
            code_version=request.code_version,
            recorded_at=request.recorded_at,
        )
        if isinstance(traced, FailedEdgeChord):
            return ReviewFailure("FailedEdgeChord", "no edge")
        fragment = segmented.fragment.confirm()
        fragments.append(_fragment(fragment, scaled))
        for edge in traced.edges:
            edges.append(
                ReviewEdge(
                    edge_id=edge.id,
                    fragment_id=fragment.id,
                    geometry=edge.geometry,
                    epistemic_class=edge.epistemic_class,
                )
            )
        chords.append(
            FragmentChords(
                fragment=fragment,
                frame=traced.frame,
                edges=traced.edges,
                envelope=traced.run.provenance,
                observation=scaled.observation,
                transform=scaled.transform,
            )
        )
    proposed = PairwiseJoinLog().propose(
        chords,
        code_version=request.code_version,
        recorded_at=request.recorded_at,
    )
    if isinstance(proposed, FailedPairwiseJoin):
        return ReviewFailure("FailedPairwiseJoin", "no pose")
    return ReviewSession(
        fragments=tuple(fragments),
        edges=tuple(edges),
        joins=proposed.joins,
        transforms=proposed.transforms,
        run=proposed.run,
        proposed=proposed.proposed,
    )


def _fragment(fragment: Fragment, scaled: ScaledOutline) -> ReviewFragment:
    outline = scaled.outline
    if outline.producer != "machine":
        raise ValueError("A segmented outline has producer machine.")
    return ReviewFragment(
        label=fragment.label,
        fragment_id=fragment.id,
        polygon=outline.polygon,
        epistemic_class=outline.epistemic_class,
        producer=outline.producer,
    )


def _validate_request(request: RankRequest) -> None:
    if not isinstance(request, RankRequest):
        raise TypeError("Rank reads a RankRequest.")
    if isinstance(request.images, str | bytes) or not isinstance(request.images, tuple):
        raise TypeError("A pool is a tuple of images.")
    if not request.images:
        raise ValueError("A pool image is one label and one existing path.")
    if request.code_version == "":
        raise ValueError("code_version is required.")
    if isinstance(request.foreground_threshold, bool):
        raise TypeError("foreground_threshold is an integer from 0 through 255.")
    _require_utc(request.recorded_at)
    seen: set[str] = set()
    for image in request.images:
        if not isinstance(image, PoolImage):
            raise TypeError("A pool image is a label and a path.")
        if image.label in seen:
            raise ValueError("A fragment label is given once.")
        seen.add(image.label)
        if not image.path.is_file():
            raise ValueError(f"{image.path} is not a fixture image.")
        _refuse_join_label(image.path)


def _refuse_join_label(path: Path) -> None:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return
    if _contains_join_label(loaded):
        raise ValueError("A BenchmarkLabel join file is not a rank path.")


def _contains_join_label(value: object) -> bool:
    if isinstance(value, dict):
        return value.get("kind") == "join"
    if isinstance(value, list):
        return any(
            isinstance(item, dict) and item.get("kind") == "join" for item in value
        )
    return False


def _segment_failure(result: object) -> ReviewFailure | None:
    if isinstance(result, SegmentedOutline):
        return None
    if isinstance(result, IntegrityFailure):
        return ReviewFailure(
            "IntegrityFailure",
            f"presented {result.presented_hash} expected {result.expected_hash}",
        )
    if isinstance(result, UnsupportedMediaType):
        return ReviewFailure(
            "UnsupportedMediaType",
            f"byte_length {result.byte_length}",
        )
    if isinstance(result, TiffDecodeFailure):
        return ReviewFailure("TiffDecodeFailure", result.kind)
    if isinstance(result, FailedSegmentation):
        return ReviewFailure("FailedSegmentation", result.kind)
    return None


def _apply(point: Point, transform: RigidTransform) -> Point:
    cosine = math.cos(transform.rotation_radians)
    sine = math.sin(transform.rotation_radians)
    x_coord, y_coord = point
    return (
        cosine * x_coord - sine * y_coord + transform.translation_x,
        sine * x_coord + cosine * y_coord + transform.translation_y,
    )


def _require_utc(value: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError("A timestamp is UTC ISO-8601.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("A timestamp is UTC ISO-8601.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("A timestamp is UTC ISO-8601.")
    return value
