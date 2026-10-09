"""Synthetic leaf geometry for the evaluation fixture.

The synthetic-tear contract is the section of that name in
``docs/EVALUATION.md``. Fragment-local coordinates follow
``docs/adr/0011-frame-conventions.md``: the origin is the centroid of the
establishing outline, ``+x`` is right, ``+y`` is down, and the unit is
millimetres. Page placements use those same axes in ``page_global_mm``.

Erosion moves each vertex toward the fragment centroid by the named
fraction. It is a centroid offset, not a physical tear model. Lighting
variation is stored in the parameter blob and is not rasterized.

Joins, placements, and the generator page are written only under the
caller-supplied ``benchmarks/`` directory. Solver code must not read that
store. This module does not create a project database.
"""

from __future__ import annotations

import math
import random
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prw.frames import CoordinateFrame
from prw.identity import ABSENT, canonical_json_bytes, content_id
from prw.provenance import ProvenanceEnvelope

type Point = tuple[float, float]

ALGORITHM_NAME = "synthetic_tear"
ALGORITHM_VERSION = "1"
PAGE_WIDTH_MM = 100.0
PAGE_HEIGHT_MM = 140.0
MILLIMETRES_PER_PIXEL = 1.0
_PIECE_COUNT = 4
_CUT_JITTER_MM = 4.0


def erode_toward_centroid(
    vertices: Sequence[Point],
    fraction: float,
) -> tuple[Point, ...]:
    """Move each vertex toward the centroid by ``fraction`` of that offset.

    This is not a physical tear model and it does not use a geometry library.
    """
    _require_fraction("edge_erosion", fraction, upper_inclusive=False)
    points = tuple(vertices)
    if len(points) < 3:
        raise ValueError("A fragment polygon has at least three vertices.")
    centroid = _centroid(points)
    kept: list[Point] = []
    for x_coord, y_coord in points:
        kept.append(
            (
                x_coord + fraction * (centroid[0] - x_coord),
                y_coord + fraction * (centroid[1] - y_coord),
            )
        )
    return tuple(kept)


@dataclass(frozen=True, slots=True)
class CutCurve:
    """One straight cut in ``page_global_mm``."""

    id: uuid.UUID
    vertices: tuple[Point, Point]


@dataclass(frozen=True, slots=True)
class FragmentGeometry:
    """One emitted piece. ``local_polygon`` is fragment-local and eroded."""

    id: uuid.UUID
    outline_revision_id: uuid.UUID
    frame: CoordinateFrame
    page_polygon: tuple[Point, ...]
    local_polygon: tuple[Point, ...]
    page_centroid: Point


@dataclass(frozen=True, slots=True)
class JoinLabel:
    """A fixture join. This is a BenchmarkLabel, not a project hypothesis."""

    id: uuid.UUID
    fragment_ids: tuple[uuid.UUID, uuid.UUID]
    cut_curve_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class PlacementLabel:
    """A rigid placement in ``page_global_mm``."""

    id: uuid.UUID
    fragment_id: uuid.UUID
    rotation_radians: float
    translation_x: float
    translation_y: float


@dataclass(frozen=True, slots=True)
class PageLabel:
    """The generator page polygon in ``page_global_mm``."""

    id: uuid.UUID
    polygon: tuple[Point, ...]
    millimetres_per_pixel: float
    fragment_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True, slots=True)
class SyntheticLeaf:
    """Polygons, cuts, and labels for one seeded leaf."""

    page: PageLabel
    page_frame: CoordinateFrame
    cut_curves: tuple[CutCurve, ...]
    fragments: tuple[FragmentGeometry, ...]
    joins: tuple[JoinLabel, ...]
    placements: tuple[PlacementLabel, ...]
    envelope: ProvenanceEnvelope


def generate_synthetic_leaf(
    benchmarks_dir: Path,
    *,
    missing_fragment_percentage: float,
    edge_erosion: float,
    rotation: float,
    lighting_variation: float,
    random_seed: int,
    code_version: str,
) -> SyntheticLeaf:
    """Generate one leaf and write its BenchmarkLabel records.

    ``lighting_variation`` is copied into the parameter blob and does not
    change the polygons. ``random_seed`` chooses the cut jitter and which
    pieces the missing-fragment percentage omits.
    """
    _require_seed(random_seed)
    _require_fraction(
        "missing_fragment_percentage",
        missing_fragment_percentage,
        upper_inclusive=True,
    )
    _require_fraction("edge_erosion", edge_erosion, upper_inclusive=False)
    _require_finite("rotation", rotation)
    _require_finite("lighting_variation", lighting_variation)
    if not isinstance(code_version, str) or code_version == "":
        raise ValueError("code_version is required.")
    parameters = {
        "missing_fragment_percentage": missing_fragment_percentage,
        "edge_erosion": edge_erosion,
        "rotation": rotation,
        "lighting_variation": lighting_variation,
    }
    envelope = ProvenanceEnvelope.create(
        source_hashes=(),
        parameters=parameters,
        algorithm_name=ALGORITHM_NAME,
        algorithm_version=ALGORITHM_VERSION,
        code_version=code_version,
        decoder_name=ABSENT,
        decoder_version=ABSENT,
        model_hash=ABSENT,
        random_seed=random_seed,
    )
    leaf = _build_leaf(
        envelope=envelope,
        missing_fragment_percentage=missing_fragment_percentage,
        edge_erosion=edge_erosion,
        rotation=rotation,
        random_seed=random_seed,
    )
    _write_benchmark_store(benchmarks_dir, leaf)
    return leaf


def _build_leaf(
    *,
    envelope: ProvenanceEnvelope,
    missing_fragment_percentage: float,
    edge_erosion: float,
    rotation: float,
    random_seed: int,
) -> SyntheticLeaf:
    generator = random.Random(random_seed)
    cut_x = PAGE_WIDTH_MM / 2 + generator.uniform(-_CUT_JITTER_MM, _CUT_JITTER_MM)
    cut_y = PAGE_HEIGHT_MM / 2 + generator.uniform(-_CUT_JITTER_MM, _CUT_JITTER_MM)
    omit_count = math.floor(missing_fragment_percentage * _PIECE_COUNT + 1e-9)
    omitted = set(generator.sample(range(_PIECE_COUNT), k=omit_count))
    vertical = _cut_curve(((cut_x, 0.0), (cut_x, PAGE_HEIGHT_MM)))
    horizontal = _cut_curve(((0.0, cut_y), (PAGE_WIDTH_MM, cut_y)))
    pieces = _rectangles(cut_x, cut_y)
    fragments: list[FragmentGeometry] = []
    for index, page_polygon in enumerate(pieces):
        if index in omitted:
            continue
        fragments.append(_fragment(page_polygon, edge_erosion))
    joins = _joins(fragments, pieces, omitted, vertical, horizontal)
    placements = tuple(_placement(fragment, rotation) for fragment in fragments)
    page = _page_label(tuple(fragment.id for fragment in fragments))
    fixture_id = content_id(
        {
            "parameter_hash": envelope.parameter_hash,
            "random_seed": random_seed,
        }
    )
    return SyntheticLeaf(
        page=page,
        page_frame=CoordinateFrame.page_global_mm(owner_id=fixture_id),
        cut_curves=(vertical, horizontal),
        fragments=tuple(fragments),
        joins=joins,
        placements=placements,
        envelope=envelope,
    )


def _fragment(page_polygon: tuple[Point, ...], edge_erosion: float) -> FragmentGeometry:
    centroid = _centroid(page_polygon)
    uneroded_local = _to_local(page_polygon, centroid)
    eroded_page = erode_toward_centroid(page_polygon, edge_erosion)
    local_polygon = _to_local(eroded_page, centroid)
    fragment_id = content_id(
        {"kind": "fragment", "local_polygon": local_polygon, "page_centroid": centroid}
    )
    outline_revision_id = content_id(
        {"kind": "outline", "local_polygon": uneroded_local}
    )
    frame = CoordinateFrame.fragment_local_mm(
        owner_id=fragment_id,
        establishing_outline_revision_id=outline_revision_id,
        polygon=uneroded_local,
    )
    return FragmentGeometry(
        id=fragment_id,
        outline_revision_id=outline_revision_id,
        frame=frame,
        page_polygon=page_polygon,
        local_polygon=local_polygon,
        page_centroid=centroid,
    )


def _joins(
    fragments: Sequence[FragmentGeometry],
    pieces: Sequence[tuple[Point, ...]],
    omitted: set[int],
    vertical: CutCurve,
    horizontal: CutCurve,
) -> tuple[JoinLabel, ...]:
    by_polygon = {fragment.page_polygon: fragment for fragment in fragments}
    adjacent = (
        (0, 1, vertical.id),
        (2, 3, vertical.id),
        (0, 2, horizontal.id),
        (1, 3, horizontal.id),
    )
    labels: list[JoinLabel] = []
    for left, right, cut_id in adjacent:
        if left in omitted or right in omitted:
            continue
        first = by_polygon[pieces[left]]
        second = by_polygon[pieces[right]]
        earlier, later = sorted((first.id, second.id), key=str)
        ordered = (earlier, later)
        body = {
            "kind": "join",
            "fragment_ids": ordered,
            "cut_curve_id": cut_id,
        }
        labels.append(
            JoinLabel(
                id=content_id(body),
                fragment_ids=ordered,
                cut_curve_id=cut_id,
            )
        )
    return tuple(sorted(labels, key=lambda label: str(label.id)))


def _placement(fragment: FragmentGeometry, rotation: float) -> PlacementLabel:
    body = {
        "kind": "placement",
        "fragment_id": fragment.id,
        "rotation_radians": rotation,
        "translation_x": fragment.page_centroid[0],
        "translation_y": fragment.page_centroid[1],
    }
    return PlacementLabel(
        id=content_id(body),
        fragment_id=fragment.id,
        rotation_radians=rotation,
        translation_x=fragment.page_centroid[0],
        translation_y=fragment.page_centroid[1],
    )


def _page_label(fragment_ids: tuple[uuid.UUID, ...]) -> PageLabel:
    polygon = (
        (0.0, 0.0),
        (PAGE_WIDTH_MM, 0.0),
        (PAGE_WIDTH_MM, PAGE_HEIGHT_MM),
        (0.0, PAGE_HEIGHT_MM),
    )
    body = {
        "kind": "page",
        "polygon": polygon,
        "millimetres_per_pixel": MILLIMETRES_PER_PIXEL,
        "fragment_ids": fragment_ids,
    }
    return PageLabel(
        id=content_id(body),
        polygon=polygon,
        millimetres_per_pixel=MILLIMETRES_PER_PIXEL,
        fragment_ids=fragment_ids,
    )


def _rectangles(cut_x: float, cut_y: float) -> tuple[tuple[Point, ...], ...]:
    width = PAGE_WIDTH_MM
    height = PAGE_HEIGHT_MM
    return (
        ((0.0, 0.0), (cut_x, 0.0), (cut_x, cut_y), (0.0, cut_y)),
        ((cut_x, 0.0), (width, 0.0), (width, cut_y), (cut_x, cut_y)),
        ((0.0, cut_y), (cut_x, cut_y), (cut_x, height), (0.0, height)),
        ((cut_x, cut_y), (width, cut_y), (width, height), (cut_x, height)),
    )


def _cut_curve(vertices: tuple[Point, Point]) -> CutCurve:
    curve_id = content_id({"kind": "cut", "vertices": vertices})
    return CutCurve(id=curve_id, vertices=vertices)


def _to_local(vertices: Sequence[Point], centroid: Point) -> tuple[Point, ...]:
    return tuple(
        (x_coord - centroid[0], y_coord - centroid[1]) for x_coord, y_coord in vertices
    )


def _write_benchmark_store(directory: Path, leaf: SyntheticLeaf) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    labels: list[dict[str, Any]] = [
        _with_id(_page_body(leaf.page), leaf.page.id),
    ]
    labels.extend(
        _with_id(_placement_body(label), label.id) for label in leaf.placements
    )
    labels.extend(_with_id(_join_body(label), label.id) for label in leaf.joins)
    _write_json(directory / "labels.json", labels)
    provenance = leaf.envelope.content_mapping()
    provenance["id"] = leaf.envelope.id
    _write_json(directory / "provenance.json", provenance)


def _page_body(page: PageLabel) -> dict[str, Any]:
    return {
        "kind": "page",
        "polygon": page.polygon,
        "millimetres_per_pixel": page.millimetres_per_pixel,
        "fragment_ids": page.fragment_ids,
    }


def _placement_body(label: PlacementLabel) -> dict[str, Any]:
    return {
        "kind": "placement",
        "fragment_id": label.fragment_id,
        "rotation_radians": label.rotation_radians,
        "translation_x": label.translation_x,
        "translation_y": label.translation_y,
    }


def _join_body(label: JoinLabel) -> dict[str, Any]:
    return {
        "kind": "join",
        "fragment_ids": label.fragment_ids,
        "cut_curve_id": label.cut_curve_id,
    }


def _with_id(body: dict[str, Any], label_id: uuid.UUID) -> dict[str, Any]:
    written = dict(body)
    written["id"] = label_id
    return written


def _write_json(path: Path, value: object) -> None:
    path.write_bytes(canonical_json_bytes(value))


def _centroid(vertices: Sequence[Point]) -> Point:
    count = len(vertices)
    return (
        sum(point[0] for point in vertices) / count,
        sum(point[1] for point in vertices) / count,
    )


def _require_seed(seed: int) -> None:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("random_seed is a JSON integer.")


def _require_finite(label: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{label} is a finite number.")
    if not math.isfinite(float(value)):
        raise ValueError(f"{label} is a finite number.")


def _require_fraction(label: str, value: float, *, upper_inclusive: bool) -> None:
    _require_finite(label, value)
    number = float(value)
    upper_ok = number <= 1.0 if upper_inclusive else number < 1.0
    if number < 0.0 or not upper_ok:
        raise ValueError(f"{label} is a fraction from 0 to 1.")
