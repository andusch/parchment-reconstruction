"""In-memory coordinate frames under the ADR-0011 axis convention.

``CoordinateFrame`` and ``PageFrame`` follow ``docs/DATA_MODEL.md`` and
``docs/adr/0011-frame-conventions.md``. Every kind stores ``+x`` right and
``+y`` down. ``source_pixels`` starts at the top-left pixel.
    ``fragment_local_mm`` starts at the area centroid of the polygon cited by
    ``establishing_outline_revision_id``. A repeated closing vertex is not a
    second vertex. That citation is the mask. It is not a
``FragmentExtent``, and a later outline does not move it. ``page_global_mm``
starts at the minimum corner, coordinate ``(0, 0)``. ``PageFrame`` width and
height are ranges measured from that origin. Transforms are not frame fields.

These records are internal. They are not a stable public API, and they do
not write a project directory.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from prw.identity import content_id

FrameKind = Literal["source_pixels", "fragment_local_mm", "page_global_mm"]
Unit = Literal["px", "mm"]
type Point = tuple[float, float]

AXIS_X_RIGHT = "+x right"
AXIS_Y_DOWN = "+y down"
ORIGIN_TOP_LEFT_PIXEL = "Top-left pixel"
ORIGIN_OUTLINE_CENTROID = "first-outline centroid"
ORIGIN_MINIMUM_PAGE_CORNER = "minimum page corner"

_UNIT_FOR_KIND: dict[FrameKind, Unit] = {
    "source_pixels": "px",
    "fragment_local_mm": "mm",
    "page_global_mm": "mm",
}
_ORIGIN_FOR_KIND: dict[FrameKind, str] = {
    "source_pixels": ORIGIN_TOP_LEFT_PIXEL,
    "fragment_local_mm": ORIGIN_OUTLINE_CENTROID,
    "page_global_mm": ORIGIN_MINIMUM_PAGE_CORNER,
}


def polygon_centroid(vertices: Sequence[object]) -> Point:
    """Return the area centroid of the polygon.

    The centroid is the shoelace centroid. A repeated closing vertex is not a
    second vertex, and consecutive duplicate vertices are dropped. No geometry
    library is used.
    """
    points = _open_ring(vertices)
    count = len(points)
    twice_area = 0.0
    centroid_x = 0.0
    centroid_y = 0.0
    for index, (x_coord, y_coord) in enumerate(points):
        next_x, next_y = points[(index + 1) % count]
        cross = x_coord * next_y - next_x * y_coord
        twice_area += cross
        centroid_x += (x_coord + next_x) * cross
        centroid_y += (y_coord + next_y) * cross
    if twice_area == 0.0:
        raise ValueError("A polygon has a non-zero area.")
    scale = 1.0 / (3.0 * twice_area)
    return (centroid_x * scale, centroid_y * scale)


def _open_ring(vertices: Sequence[object]) -> tuple[Point, ...]:
    if isinstance(vertices, str | bytes) or not isinstance(vertices, Sequence):
        raise TypeError("A polygon is a sequence of vertices.")
    points = [_point(vertex) for vertex in vertices]
    if len(points) >= 2 and points[0] == points[-1]:
        points = points[:-1]
    opened: list[Point] = []
    for point in points:
        if not opened or point != opened[-1]:
            opened.append(point)
    if len(opened) >= 2 and opened[0] == opened[-1]:
        opened = opened[:-1]
    if len(opened) < 3:
        raise ValueError("A polygon has at least three vertices.")
    return tuple(opened)


def _point(value: object) -> Point:
    if isinstance(value, str | bytes) or not isinstance(value, Sequence):
        raise TypeError("A vertex is an x and a y.")
    if len(value) != 2:
        raise ValueError("A vertex is an x and a y.")
    x, y = value
    return (_coordinate(x), _coordinate(y))


def _coordinate(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("A vertex coordinate is a finite number.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("A vertex coordinate is a finite number.")
    return number


def _millimetre(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{label} is a number of millimetres.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} is a finite number of millimetres.")
    return number


def _inclusive_range(lower: object, upper: object, label: str) -> tuple[float, float]:
    minimum = _millimetre(lower, f"min_{label}_mm")
    maximum = _millimetre(upper, f"max_{label}_mm")
    if minimum < 0 or maximum < minimum:
        raise ValueError(
            f"The {label} range is inclusive and is measured from the origin."
        )
    return minimum, maximum


@dataclass(frozen=True, slots=True)
class CoordinateFrame:
    """One named coordinate system. Axes and origin follow ADR-0011.

    ``origin`` is the origin coordinate: ``(0, 0)`` for ``source_pixels`` and
    ``page_global_mm``, and the establishing polygon's centroid for
    ``fragment_local_mm``. The id is a UUIDv5 over the canonical content.
    """

    kind: FrameKind
    origin_description: str
    axis_x_direction: str
    axis_y_direction: str
    unit: Unit
    owner_id: uuid.UUID
    origin: Point
    establishing_outline_revision_id: uuid.UUID | None
    id: uuid.UUID

    @classmethod
    def source_pixels(cls, *, owner_id: uuid.UUID) -> CoordinateFrame:
        """Build the pixel frame owned by one source image."""
        return cls._build(
            kind="source_pixels",
            owner_id=owner_id,
            origin=(0.0, 0.0),
            establishing_outline_revision_id=None,
        )

    @classmethod
    def fragment_local_mm(
        cls,
        *,
        owner_id: uuid.UUID,
        establishing_outline_revision_id: uuid.UUID,
        polygon: Sequence[object],
    ) -> CoordinateFrame:
        """Place the origin at the centroid of the cited polygon.

        ``owner_id`` is the fragment. The cited outline is the mask.
        """
        if not isinstance(establishing_outline_revision_id, uuid.UUID):
            raise TypeError("establishing_outline_revision_id is a UUID.")
        return cls._build(
            kind="fragment_local_mm",
            owner_id=owner_id,
            origin=polygon_centroid(polygon),
            establishing_outline_revision_id=establishing_outline_revision_id,
        )

    @classmethod
    def page_global_mm(cls, *, owner_id: uuid.UUID) -> CoordinateFrame:
        """Build the shared page frame. The minimum corner is ``(0, 0)``.

        ``owner_id`` is the project. ``PageFrame`` cites this frame.
        """
        return cls._build(
            kind="page_global_mm",
            owner_id=owner_id,
            origin=(0.0, 0.0),
            establishing_outline_revision_id=None,
        )

    def with_later_outline(
        self,
        outline_revision_id: uuid.UUID,
        polygon: Sequence[object],
    ) -> CoordinateFrame:
        """Accept a later outline as geometry in this frame.

        The establishing citation and the origin stay as they were. Superseding
        an outline does not move ``fragment_local_mm``.
        """
        if self.kind != "fragment_local_mm":
            raise ValueError(
                "A later outline is geometry in fragment_local_mm. "
                "It is not a new origin."
            )
        if not isinstance(outline_revision_id, uuid.UUID):
            raise TypeError("An outline revision id is a UUID.")
        polygon_centroid(polygon)
        return self

    def content_mapping(self) -> dict[str, Any]:
        """Stored fields except ``id``. An omitted outline citation is absent."""
        fields: dict[str, Any] = {
            "kind": self.kind,
            "origin_description": self.origin_description,
            "axis_x_direction": self.axis_x_direction,
            "axis_y_direction": self.axis_y_direction,
            "unit": self.unit,
            "owner_id": self.owner_id,
            "origin": self.origin,
        }
        if self.establishing_outline_revision_id is not None:
            fields["establishing_outline_revision_id"] = (
                self.establishing_outline_revision_id
            )
        return fields

    @classmethod
    def _build(
        cls,
        *,
        kind: FrameKind,
        owner_id: uuid.UUID,
        origin: Point,
        establishing_outline_revision_id: uuid.UUID | None,
    ) -> CoordinateFrame:
        if not isinstance(owner_id, uuid.UUID):
            raise TypeError("owner_id is a UUID.")
        fields: dict[str, Any] = {
            "kind": kind,
            "origin_description": _ORIGIN_FOR_KIND[kind],
            "axis_x_direction": AXIS_X_RIGHT,
            "axis_y_direction": AXIS_Y_DOWN,
            "unit": _UNIT_FOR_KIND[kind],
            "owner_id": owner_id,
            "origin": origin,
        }
        if establishing_outline_revision_id is not None:
            fields["establishing_outline_revision_id"] = (
                establishing_outline_revision_id
            )
        return cls(
            kind=kind,
            origin_description=fields["origin_description"],
            axis_x_direction=AXIS_X_RIGHT,
            axis_y_direction=AXIS_Y_DOWN,
            unit=fields["unit"],
            owner_id=owner_id,
            origin=origin,
            establishing_outline_revision_id=establishing_outline_revision_id,
            id=content_id(fields),
        )

    def __post_init__(self) -> None:
        if self.kind not in _UNIT_FOR_KIND:
            raise ValueError(
                "Frame kind is source_pixels, fragment_local_mm, or page_global_mm."
            )
        if self.unit != _UNIT_FOR_KIND[self.kind]:
            raise ValueError("The frame unit is px for source_pixels and mm otherwise.")
        if self.origin_description != _ORIGIN_FOR_KIND[self.kind]:
            raise ValueError("The origin description repeats ADR-0011.")
        if (
            self.axis_x_direction != AXIS_X_RIGHT
            or self.axis_y_direction != AXIS_Y_DOWN
        ):
            raise ValueError("Axes are +x right and +y down for every frame.")
        cited = self.establishing_outline_revision_id
        if self.kind == "fragment_local_mm":
            if not isinstance(cited, uuid.UUID):
                raise ValueError(
                    "fragment_local_mm cites the outline revision that establishes it."
                )
        elif cited is not None:
            raise ValueError(
                "establishing_outline_revision_id is set only for fragment_local_mm."
            )
        if self.kind == "fragment_local_mm":
            _point(self.origin)
        elif self.origin != (0.0, 0.0):
            raise ValueError("The pixel and page origins are coordinate (0, 0).")
        if self.id != content_id(self.content_mapping()):
            raise ValueError("CoordinateFrame.id does not match its content.")


@dataclass(frozen=True, slots=True)
class PageFrame:
    """Inclusive width and height ranges for the one shared page frame.

    Replacing the ranges writes a new ``PageFrame``. The cited
    ``page_global_mm`` frame, and its origin, stay put. How the range numbers
    are chosen remains open.
    """

    frame_id: uuid.UUID
    min_width_mm: float
    max_width_mm: float
    min_height_mm: float
    max_height_mm: float
    id: uuid.UUID

    @classmethod
    def create(
        cls,
        frame: CoordinateFrame,
        *,
        min_width_mm: object,
        max_width_mm: object,
        min_height_mm: object,
        max_height_mm: object,
    ) -> PageFrame:
        """Cite a ``page_global_mm`` frame and store ranges measured from its origin."""
        if frame.kind != "page_global_mm":
            raise ValueError("PageFrame cites the project's page_global_mm frame.")
        width = _inclusive_range(min_width_mm, max_width_mm, "width")
        height = _inclusive_range(min_height_mm, max_height_mm, "height")
        return cls._build(frame.id, width, height)

    def replace_ranges(
        self,
        *,
        min_width_mm: object,
        max_width_mm: object,
        min_height_mm: object,
        max_height_mm: object,
    ) -> PageFrame:
        """Return a new page record. ``frame_id`` is unchanged."""
        width = _inclusive_range(min_width_mm, max_width_mm, "width")
        height = _inclusive_range(min_height_mm, max_height_mm, "height")
        return self._build(self.frame_id, width, height)

    def content_mapping(self) -> dict[str, Any]:
        """Stored fields except ``id``."""
        return {
            "frame_id": self.frame_id,
            "min_width_mm": self.min_width_mm,
            "max_width_mm": self.max_width_mm,
            "min_height_mm": self.min_height_mm,
            "max_height_mm": self.max_height_mm,
        }

    @classmethod
    def _build(
        cls,
        frame_id: uuid.UUID,
        width: tuple[float, float],
        height: tuple[float, float],
    ) -> PageFrame:
        fields = {
            "frame_id": frame_id,
            "min_width_mm": width[0],
            "max_width_mm": width[1],
            "min_height_mm": height[0],
            "max_height_mm": height[1],
        }
        return cls(
            frame_id=frame_id,
            min_width_mm=width[0],
            max_width_mm=width[1],
            min_height_mm=height[0],
            max_height_mm=height[1],
            id=content_id(fields),
        )

    def __post_init__(self) -> None:
        _inclusive_range(self.min_width_mm, self.max_width_mm, "width")
        _inclusive_range(self.min_height_mm, self.max_height_mm, "height")
        if self.id != content_id(self.content_mapping()):
            raise ValueError("PageFrame.id does not match its content.")
