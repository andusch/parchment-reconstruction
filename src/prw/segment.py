"""Segment one fragment raster into a source-pixel outline.

Stage 3 in ``docs/ALGORITHM.md`` takes a verified source image and can write
a ``FragmentOutlineRevision``. This use case keeps a single 4-connected
foreground component and traces its outer boundary in ``source_pixels``.
A sample is foreground when it is greater than or equal to
``foreground_threshold``. Vertices start at the topmost, then leftmost,
boundary sample and follow that outer boundary.

A failed segmentation is a failed run, not an empty success. The failed
run is stored under its own id, including ``attempt_id``, and no polygon
is inserted. A page of several components fails. That failure does not set
``group_scan``. ``Q-PRD-04`` stays open.

The algorithm name ``fragment_outline`` and version ``1`` are provenance
labels. They are not a public CLI contract. ``random_seed`` is omitted.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from prw.fixture_tiff import (
    FixtureSamples,
    UnsupportedFixtureLayout,
    read_fixture_tiff,
)
from prw.frames import CoordinateFrame
from prw.identity import content_id
from prw.ingest import (
    IntegrityFailure,
    UnsupportedMediaType,
    VerifiedBytes,
    ingest_bytes,
)
from prw.outlines import Fragment, FragmentOutlineRevision, OutlineRevisionLog
from prw.provenance import (
    AlgorithmRun,
    ProvenanceEnvelope,
    StatusEvent,
    StatusStream,
    run_id_inputs,
)
from prw.synthetic_tear import DECODER_NAME, DECODER_VERSION

ALGORITHM_NAME = "fragment_outline"
ALGORITHM_VERSION = "1"

SegmentationFailureKind = Literal[
    "no_foreground",
    "multiple_components",
    "hole",
    "degenerate_boundary",
]
_NEIGHBORS_4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
# Clockwise Moore neighborhood, starting at north. +x is right and +y is down.
_MOORE = (
    (0, -1),
    (1, -1),
    (1, 0),
    (1, 1),
    (0, 1),
    (-1, 1),
    (-1, 0),
    (-1, -1),
)


def _require_threshold(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("foreground_threshold is an integer from 0 through 255.")
    if value < 0 or value > 255:
        raise ValueError("foreground_threshold is an integer from 0 through 255.")
    return value


def _mask(samples: bytes, threshold: int) -> bytearray:
    return bytearray(1 if sample >= threshold else 0 for sample in samples)


def _component_count(mask: bytearray, width: int, height: int) -> int:
    seen = bytearray(width * height)
    count = 0
    for index, value in enumerate(mask):
        if value == 0 or seen[index]:
            continue
        count += 1
        stack = [index]
        seen[index] = 1
        while stack:
            current = stack.pop()
            x_coord = current % width
            y_coord = current // width
            for dx_coord, dy_coord in _NEIGHBORS_4:
                next_x = x_coord + dx_coord
                next_y = y_coord + dy_coord
                if next_x < 0 or next_y < 0 or next_x >= width or next_y >= height:
                    continue
                next_index = next_y * width + next_x
                if mask[next_index] and not seen[next_index]:
                    seen[next_index] = 1
                    stack.append(next_index)
    return count


def _has_hole(mask: bytearray, width: int, height: int) -> bool:
    """Return whether a 4-connected background region misses the image border."""
    seen = bytearray(width * height)
    stack: list[int] = []
    for x_coord in range(width):
        for y_coord in (0, height - 1):
            index = y_coord * width + x_coord
            if mask[index] == 0:
                stack.append(index)
    for y_coord in range(height):
        for x_coord in (0, width - 1):
            index = y_coord * width + x_coord
            if mask[index] == 0:
                stack.append(index)
    while stack:
        current = stack.pop()
        if seen[current] or mask[current]:
            continue
        seen[current] = 1
        x_coord = current % width
        y_coord = current // width
        for dx_coord, dy_coord in _NEIGHBORS_4:
            next_x = x_coord + dx_coord
            next_y = y_coord + dy_coord
            if next_x < 0 or next_y < 0 or next_x >= width or next_y >= height:
                continue
            next_index = next_y * width + next_x
            if mask[next_index] == 0 and not seen[next_index]:
                stack.append(next_index)
    return any(value == 0 and not seen[index] for index, value in enumerate(mask))


def _on_mask(
    mask: bytearray, width: int, height: int, x_coord: int, y_coord: int
) -> bool:
    return (
        0 <= x_coord < width
        and 0 <= y_coord < height
        and mask[y_coord * width + x_coord] == 1
    )


def _outer_boundary(
    mask: bytearray, width: int, height: int
) -> tuple[tuple[int, int], ...] | None:
    """Trace direction changes on the outer boundary.

    The walk starts at the topmost, then leftmost, foreground sample and
    moves clockwise through the Moore neighborhood. ``None`` means the
    boundary does not yield a polygon.
    """
    start: tuple[int, int] | None = None
    for y_coord in range(height):
        for x_coord in range(width):
            if mask[y_coord * width + x_coord]:
                start = (x_coord, y_coord)
                break
        if start is not None:
            break
    if start is None:
        return None
    boundary = _moore_boundary(mask, width, height, start)
    corners = _direction_changes(boundary)
    if len(corners) < 3 or corners[0] != start:
        return None
    return corners


def _moore_boundary(
    mask: bytearray,
    width: int,
    height: int,
    start: tuple[int, int],
) -> tuple[tuple[int, int], ...]:
    start_x, start_y = start
    boundary = [start]
    x_coord, y_coord = start
    # Enter from the north, then take the next clockwise neighbor.
    direction = 1
    examined = 0
    limit = width * height * 8
    steps = 0
    while steps < limit:
        steps += 1
        dx_coord, dy_coord = _MOORE[direction]
        next_x = x_coord + dx_coord
        next_y = y_coord + dy_coord
        if (next_x, next_y) == (start_x, start_y) and len(boundary) > 1:
            return tuple(boundary)
        if _on_mask(mask, width, height, next_x, next_y):
            boundary.append((next_x, next_y))
            x_coord, y_coord = next_x, next_y
            direction = ((direction + 4) % 8 + 1) % 8
            examined = 0
            continue
        direction = (direction + 1) % 8
        examined += 1
        if examined >= 8:
            return tuple(boundary)
    raise RuntimeError("The outer-boundary trace did not close.")


def _direction_changes(
    boundary: tuple[tuple[int, int], ...],
) -> tuple[tuple[int, int], ...]:
    count = len(boundary)
    if count < 3:
        return boundary
    kept: list[tuple[int, int]] = []
    for index, current in enumerate(boundary):
        previous = boundary[(index - 1) % count]
        nxt = boundary[(index + 1) % count]
        incoming = (current[0] - previous[0], current[1] - previous[1])
        outgoing = (nxt[0] - current[0], nxt[1] - current[1])
        if incoming != outgoing:
            kept.append(current)
    return tuple(kept)


def _envelope(
    content_hash: str,
    threshold: int,
    code_version: str,
) -> ProvenanceEnvelope:
    return ProvenanceEnvelope.create(
        source_hashes=(content_hash,),
        parameters={"foreground_threshold": threshold},
        algorithm_name=ALGORITHM_NAME,
        algorithm_version=ALGORITHM_VERSION,
        code_version=code_version,
        decoder_name=DECODER_NAME,
        decoder_version=DECODER_VERSION,
    )


@dataclass(frozen=True, slots=True)
class SegmentedOutline:
    """One completed segmentation. The outline is an interpretation."""

    run: AlgorithmRun
    fragment: Fragment
    frame: CoordinateFrame
    outline: FragmentOutlineRevision
    proposed: StatusEvent

    def __post_init__(self) -> None:
        if self.run.status != "completed" or self.run.attempt_id is not None:
            raise ValueError("A completed outline run has no attempt_id.")
        if self.outline.run_id != self.run.id:
            raise ValueError("The outline run_id is the completed run.")
        if self.outline.epistemic_class != "interpretation":
            raise ValueError("A segmented outline's epistemic class is interpretation.")
        if self.outline.producer != "machine":
            raise ValueError("A segmented outline has producer machine.")
        if self.frame.kind != "source_pixels":
            raise ValueError("The segmented outline is in source_pixels.")
        if self.outline.frame_id != self.frame.id:
            raise ValueError("The outline cites its source_pixels frame.")
        proposed_on_outline = (
            self.proposed.status == "proposed"
            and self.proposed.target_id == self.outline.id
        )
        if not proposed_on_outline:
            raise ValueError("Insert appends proposed on the outline.")
        if self.run.join_ids or self.run.assembly_ids or self.run.reading_ids:
            raise ValueError("This run does not record joins, assemblies, or readings.")
        if self.run.line_ids or self.run.line_order_ids:
            raise ValueError("This run does not record text lines.")


@dataclass(frozen=True, slots=True)
class FailedSegmentation:
    """A failed run with no outline.

    This is not an empty success. ``run.attempt_id`` is set, and the run id
    is not the id a later completed run of the same inputs would take.
    """

    run: AlgorithmRun
    kind: SegmentationFailureKind

    def __post_init__(self) -> None:
        if self.run.status != "failed" or self.run.attempt_id is None:
            raise ValueError(
                "A failed segmentation stores a failed run and attempt_id."
            )
        if self.kind not in {
            "no_foreground",
            "multiple_components",
            "hole",
            "degenerate_boundary",
        }:
            raise ValueError(
                "A segmentation failure is no foreground, multiple components, "
                "a hole, or a boundary that is not a polygon."
            )
        completed = content_id(run_id_inputs(self.run.provenance, "completed", None))
        if self.run.id == completed:
            raise ValueError(
                "A failed run id is not the completed id of the same inputs."
            )


SegmentResult = (
    IntegrityFailure
    | UnsupportedMediaType
    | UnsupportedFixtureLayout
    | FailedSegmentation
    | SegmentedOutline
)


class SegmentationLog:
    """In-memory runs and the outlines those completed runs inserted.

    A repeated completed segmentation returns the stored row and does not
    insert another. ``AlgorithmRun`` has no ``outline_ids``. The outline's
    ``run_id`` groups it with the run.
    """

    def __init__(self) -> None:
        self._runs: list[AlgorithmRun] = []
        self._completed: dict[uuid.UUID, SegmentedOutline] = {}
        self._outlines = OutlineRevisionLog()
        self._status = StatusStream()

    @property
    def runs(self) -> tuple[AlgorithmRun, ...]:
        return tuple(self._runs)

    @property
    def outlines(self) -> tuple[FragmentOutlineRevision, ...]:
        return self._outlines.rows

    def segment(
        self,
        presented: bytes | bytearray,
        *,
        project_id: uuid.UUID,
        label: str,
        foreground_threshold: int,
        code_version: str,
        recorded_at: str,
        expected_hash: str | None = None,
    ) -> SegmentResult:
        """Segment ``presented`` or return the existing ingest or layout failure.

        ``presented`` is not modified. The fragment label is the caller's
        opaque label. This method does not read a manifest or ``benchmarks/``.
        """
        if not isinstance(presented, bytes | bytearray):
            raise TypeError("Segmentation reads caller-supplied bytes.")
        threshold = _require_threshold(foreground_threshold)
        ingested = ingest_bytes(presented, expected_hash=expected_hash)
        if not isinstance(ingested, VerifiedBytes):
            return ingested
        raster = read_fixture_tiff(presented)
        if not isinstance(raster, FixtureSamples):
            return raster
        envelope = _envelope(ingested.content_hash, threshold, code_version)
        completed_id = content_id(run_id_inputs(envelope, "completed", None))
        stored = self._completed.get(completed_id)
        if stored is not None:
            return stored
        kind = _failure_kind(raster, threshold)
        if kind is not None:
            return self._fail(envelope, recorded_at, kind)
        return self._succeed(
            envelope,
            raster,
            threshold,
            project_id=project_id,
            label=label,
            source_id=ingested.id,
            recorded_at=recorded_at,
        )

    def _fail(
        self,
        envelope: ProvenanceEnvelope,
        recorded_at: str,
        kind: SegmentationFailureKind,
    ) -> FailedSegmentation:
        run = AlgorithmRun.create(envelope, status="failed", started_at=recorded_at)
        self._runs.append(run)
        return FailedSegmentation(run=run, kind=kind)

    def _succeed(
        self,
        envelope: ProvenanceEnvelope,
        raster: FixtureSamples,
        threshold: int,
        *,
        project_id: uuid.UUID,
        label: str,
        source_id: uuid.UUID,
        recorded_at: str,
    ) -> SegmentedOutline | FailedSegmentation:
        mask = _mask(raster.samples, threshold)
        corners = _outer_boundary(mask, raster.width, raster.height)
        if corners is None:
            return self._fail(envelope, recorded_at, "degenerate_boundary")
        run = AlgorithmRun.create(envelope, status="completed", started_at=recorded_at)
        fragment = Fragment.create(project_id=project_id, label=label)
        frame = CoordinateFrame.source_pixels(owner_id=source_id)
        outline = FragmentOutlineRevision.create(
            fragment_id=fragment.id,
            frame_id=frame.id,
            polygon=corners,
            run_id=run.id,
            provenance_id=envelope.id,
        )
        proposed = self._outlines.insert(
            self._status,
            outline,
            recorded_at=recorded_at,
            actor=str(run.id),
        )
        self._runs.append(run)
        result = SegmentedOutline(
            run=run,
            fragment=fragment,
            frame=frame,
            outline=outline,
            proposed=proposed,
        )
        self._completed[run.id] = result
        return result


def _failure_kind(
    raster: FixtureSamples, threshold: int
) -> SegmentationFailureKind | None:
    mask = _mask(raster.samples, threshold)
    if not any(mask):
        return "no_foreground"
    if _component_count(mask, raster.width, raster.height) != 1:
        return "multiple_components"
    if _has_hole(mask, raster.width, raster.height):
        return "hole"
    return None
