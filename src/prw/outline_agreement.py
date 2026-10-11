"""Intersection-over-union for polygons already in one named frame.

The metric is the outline-agreement section of ``docs/EVALUATION.md``.
The unit is intersection-over-union between a predicted polygon and a
reference polygon. The reference is a generator polygon supplied by the
caller. A human outline is not a reference. ``Q-SCI-17`` stays open.

Both polygons are already in the named frame. This module does not convert
pixels to millimetres. It does not open BenchmarkLabel join, placement, or
page rows, and it does not invent a provenance envelope. The report copies
algorithm name ``fragment_outline``, version ``1``, the parameter hash,
``code_version``, ``model_hash`` ``absent``, and the absence of
``random_seed`` from the segmentation envelope the caller passes in.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from prw.frames import FrameKind
from prw.identity import ABSENT, canonical_json_bytes, require_hash
from prw.provenance import ProvenanceEnvelope
from prw.synthetic_tear import require_fixture_destination

_ALGORITHM_NAME = "fragment_outline"
_ALGORITHM_VERSION = "1"
_NO_PREVIOUS = "No previous outline-agreement report exists."
_REPORT_DIRECTORY = "outline_agreement"
_REPORT_PREFIX = "outline-agreement-"
_FRAMES = ("source_pixels", "fragment_local_mm", "page_global_mm")

type Point = tuple[float, float]
type Polygon = tuple[Point, ...]


def polygon_iou(
    predicted: Sequence[object],
    reference: Sequence[object],
    *,
    predicted_frame: str,
    reference_frame: str,
) -> float:
    """Return intersection-over-union for two polygons in one named frame.

    See the outline-agreement section of ``docs/EVALUATION.md``. ``reference``
    is a generator polygon supplied by the caller. Mixed frames are refused.
    Coordinates are not converted, and BenchmarkLabel rows are not opened.
    """
    frame = _require_frame(predicted_frame)
    other = _require_frame(reference_frame)
    if frame != other:
        raise ValueError("Outline agreement uses one named frame.")
    predicted_ring = _ring(predicted)
    reference_ring = _ring(reference)
    predicted_area = abs(_signed_area(predicted_ring))
    reference_area = abs(_signed_area(reference_ring))
    intersection = _intersection_area(predicted_ring, reference_ring)
    union = predicted_area + reference_area - intersection
    if union == 0:
        raise ValueError("A polygon has a non-zero area.")
    return intersection / union


def write_outline_agreement(
    benchmarks_dir: Path,
    *,
    envelope: ProvenanceEnvelope,
    frame: str,
    pairs: Sequence[tuple[Sequence[object], Sequence[object]]],
    fixture_image_hashes: Sequence[str],
) -> Path:
    """Write one outline-agreement report under ``benchmarks_dir``.

    Each pair is a predicted polygon and a generator polygon supplied by the
    caller, both in ``frame``. The report lists every intersection-over-union
    value. See the outline-agreement section of ``docs/EVALUATION.md``. The
    first report states that no previous outline-agreement report exists. A
    later report names the previous file and leaves that file unchanged.
    """
    named_frame = _require_frame(frame)
    _require_segmentation_envelope(envelope)
    if not isinstance(pairs, Sequence) or isinstance(pairs, str | bytes):
        raise TypeError("Outline agreement scores caller-supplied polygon pairs.")
    if len(pairs) == 0:
        raise ValueError("Outline agreement scores at least one polygon pair.")
    hashes = _fixture_hashes(fixture_image_hashes)
    ious = [
        polygon_iou(
            predicted,
            reference,
            predicted_frame=named_frame,
            reference_frame=named_frame,
        )
        for predicted, reference in pairs
    ]
    destination = require_fixture_destination(benchmarks_dir)
    report_dir = destination / _REPORT_DIRECTORY
    previous = _previous_report(report_dir)
    body: dict[str, Any] = {
        "algorithm_name": envelope.algorithm_name,
        "algorithm_version": envelope.algorithm_version,
        "parameter_hash": envelope.parameter_hash,
        "code_version": envelope.code_version,
        "model_hash": envelope.model_hash,
        "random_seed": ABSENT,
        "fixture_image_hashes": hashes,
        "frame": named_frame,
        "reference": "generator polygon supplied by the caller",
        "metric": "outline_agreement",
        "unit": "intersection_over_union",
        "ious": ious,
        "limiting_questions": ["Q-SCI-17"],
        "previous_report": ABSENT if previous is None else previous.name,
        "previous_report_statement": (
            _NO_PREVIOUS
            if previous is None
            else f"The previous outline-agreement report is {previous.name}."
        ),
    }
    if previous is not None:
        body["previous_ious"] = _previous_ious(previous)
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / _report_name(_next_index(report_dir))
    if path.exists():
        raise ValueError("An outline-agreement report is a new file.")
    path.write_bytes(canonical_json_bytes(body))
    return path


def _require_frame(value: str) -> FrameKind:
    if value in _FRAMES:
        return cast(FrameKind, value)
    raise ValueError(
        "The frame is source_pixels, fragment_local_mm, or page_global_mm."
    )


def _require_segmentation_envelope(envelope: ProvenanceEnvelope) -> None:
    if not isinstance(envelope, ProvenanceEnvelope):
        raise TypeError("The report copies the segmentation envelope.")
    copied = (
        envelope.algorithm_name == _ALGORITHM_NAME
        and envelope.algorithm_version == _ALGORITHM_VERSION
        and envelope.model_hash == ABSENT
        and envelope.random_seed is None
    )
    if not copied:
        raise ValueError(
            "The report copies the fragment_outline segmentation envelope."
        )


def _fixture_hashes(values: Sequence[str]) -> tuple[str, ...]:
    if not isinstance(values, Sequence) or isinstance(values, str | bytes):
        raise TypeError("Fixture image hashes are sha256 digests.")
    if len(values) == 0:
        raise ValueError("The report records the fixture image hashes.")
    hashes = tuple(require_hash(value) for value in values)
    if any(value == ABSENT for value in hashes):
        raise ValueError("A fixture image hash is a sha256 digest.")
    return hashes


def _previous_report(report_dir: Path) -> Path | None:
    if not report_dir.is_dir():
        return None
    reports = sorted(
        path
        for path in report_dir.iterdir()
        if path.is_file() and _report_index(path.name) is not None
    )
    if not reports:
        return None
    return reports[-1]


def _previous_ious(path: Path) -> list[float]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("An outline-agreement report lists every IoU.")
    values = loaded.get("ious")
    if not isinstance(values, list) or len(values) == 0:
        raise ValueError("An outline-agreement report lists every IoU.")
    ious: list[float] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError("An outline-agreement report lists every IoU.")
        ious.append(float(value))
    return ious


def _report_index(name: str) -> int | None:
    if not name.startswith(_REPORT_PREFIX) or not name.endswith(".json"):
        return None
    suffix = name[len(_REPORT_PREFIX) : -len(".json")]
    if len(suffix) != 4 or not suffix.isdecimal():
        return None
    return int(suffix)


def _next_index(report_dir: Path) -> int:
    if not report_dir.is_dir():
        return 1
    indexes = [
        index
        for path in report_dir.iterdir()
        if (index := _report_index(path.name)) is not None
    ]
    if not indexes:
        return 1
    return max(indexes) + 1


def _report_name(index: int) -> str:
    return f"{_REPORT_PREFIX}{index:04d}.json"


def _ring(vertices: Sequence[object]) -> Polygon:
    if isinstance(vertices, str | bytes) or not isinstance(vertices, Sequence):
        raise TypeError("A polygon is a sequence of vertices.")
    points = [_point(vertex) for vertex in vertices]
    if len(points) >= 2 and points[0] == points[-1]:
        points = points[:-1]
    deduped: list[Point] = []
    for point in points:
        if not deduped or point != deduped[-1]:
            deduped.append(point)
    if len(deduped) < 3 or _signed_area(deduped) == 0:
        raise ValueError("A polygon has at least three vertices and a non-zero area.")
    return tuple(deduped)


def _point(value: object) -> Point:
    if isinstance(value, str | bytes) or not isinstance(value, Sequence):
        raise TypeError("A vertex is an x and a y.")
    if len(value) != 2:
        raise ValueError("A vertex is an x and a y.")
    return (_coordinate(value[0]), _coordinate(value[1]))


def _coordinate(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("A vertex coordinate is a finite number.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("A vertex coordinate is a finite number.")
    return number


def _signed_area(vertices: Sequence[Point]) -> float:
    total = 0.0
    count = len(vertices)
    for index, (x_coord, y_coord) in enumerate(vertices):
        next_x, next_y = vertices[(index + 1) % count]
        total += x_coord * next_y - next_x * y_coord
    return total / 2


def _intersection_area(predicted: Polygon, reference: Polygon) -> float:
    predicted_ccw = _ccw(predicted)
    reference_ccw = _ccw(reference)
    subjects = (
        (predicted_ccw,) if _is_convex(predicted_ccw) else _triangulate(predicted_ccw)
    )
    clips = (
        (reference_ccw,) if _is_convex(reference_ccw) else _triangulate(reference_ccw)
    )
    return sum(
        abs(_signed_area(_clip(subject, clip)))
        for subject in subjects
        for clip in clips
    )


def _ccw(vertices: Polygon) -> Polygon:
    if _signed_area(vertices) < 0:
        return tuple(reversed(vertices))
    return vertices


def _is_convex(vertices: Polygon) -> bool:
    count = len(vertices)
    return all(_turn(vertices, index) >= 0 for index in range(count))


def _turn(vertices: Polygon, index: int) -> float:
    count = len(vertices)
    return _cross(
        vertices[index],
        vertices[(index + 1) % count],
        vertices[(index + 2) % count],
    )


def _triangulate(vertices: Polygon) -> tuple[Polygon, ...]:
    remaining = list(vertices)
    triangles: list[Polygon] = []
    while len(remaining) > 3:
        count = len(remaining)
        ear = _ear_index(remaining)
        if ear is None:
            raise ValueError("Outline agreement scores a simple polygon.")
        previous = remaining[(ear - 1) % count]
        current = remaining[ear]
        nxt = remaining[(ear + 1) % count]
        triangles.append((previous, current, nxt))
        del remaining[ear]
    triangles.append((remaining[0], remaining[1], remaining[2]))
    return tuple(triangles)


def _ear_index(vertices: Sequence[Point]) -> int | None:
    count = len(vertices)
    for index in range(count):
        previous = vertices[(index - 1) % count]
        current = vertices[index]
        nxt = vertices[(index + 1) % count]
        if _cross(previous, current, nxt) <= 0:
            continue
        if any(
            _strictly_inside(vertices[other], previous, current, nxt)
            for other in range(count)
            if other not in {(index - 1) % count, index, (index + 1) % count}
        ):
            continue
        return index
    return None


def _strictly_inside(point: Point, a: Point, b: Point, c: Point) -> bool:
    first = _cross(a, b, point)
    second = _cross(b, c, point)
    third = _cross(c, a, point)
    return first > 0 and second > 0 and third > 0


def _cross(origin: Point, first: Point, second: Point) -> float:
    return (first[0] - origin[0]) * (second[1] - origin[1]) - (first[1] - origin[1]) * (
        second[0] - origin[0]
    )


def _clip(subject: Polygon, clip: Polygon) -> Polygon:
    output = list(subject)
    for index, start in enumerate(clip):
        if not output:
            return ()
        end = clip[(index + 1) % len(clip)]
        incoming = output
        output = []
        previous = incoming[-1]
        for current in incoming:
            current_inside = _cross(start, end, current) >= 0
            previous_inside = _cross(start, end, previous) >= 0
            if current_inside:
                if not previous_inside:
                    output.append(_edge_intersection(previous, current, start, end))
                output.append(current)
            elif previous_inside:
                output.append(_edge_intersection(previous, current, start, end))
            previous = current
    return _positive_area(output)


def _positive_area(points: Sequence[Point]) -> Polygon:
    ring = list(points)
    if len(ring) >= 2 and ring[0] == ring[-1]:
        ring = ring[:-1]
    deduped: list[Point] = []
    for point in ring:
        if not deduped or point != deduped[-1]:
            deduped.append(point)
    if len(deduped) < 3 or _signed_area(deduped) == 0:
        return ()
    return tuple(deduped)


def _edge_intersection(
    start: Point, end: Point, edge_start: Point, edge_end: Point
) -> Point:
    denominator = _cross(start, end, edge_end) - _cross(start, end, edge_start)
    if denominator == 0:
        raise ValueError("Outline agreement scores a simple polygon.")
    offset = _cross(start, edge_start, edge_end)
    fraction = offset / denominator
    return (
        start[0] + fraction * (end[0] - start[0]),
        start[1] + fraction * (end[1] - start[1]),
    )
