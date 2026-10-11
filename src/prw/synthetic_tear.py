"""Synthetic leaf geometry and fixture rasters for the evaluation fixture.

The synthetic-tear contract is the section of that name in
``docs/EVALUATION.md``. That section requires a manifest of SHA-256 digests
for every generated image. Fragment-local coordinates follow
``docs/adr/0011-frame-conventions.md``: the origin is the centroid of the
establishing outline, ``+x`` is right, ``+y`` is down, and the unit is
millimetres. Page placements use those same axes in ``page_global_mm``.

Erosion moves each vertex toward the fragment centroid by the named
fraction. It is a centroid offset, not a physical tear model.

``lighting_variation`` is a named parameter in the canonical parameter blob,
so it participates in the ``sha256:`` parameter hash. It is a per-fragment
gain on an 8-bit grayscale raster, not parchment color, ink, or warp.
Fragment ``i`` of ``n`` emitted pieces uses

``gain = 1 + lighting_variation * (2 * i / max(n - 1, 1) - 1)``

and the stored sample is ``round(128 * gain)`` clamped to 0..255.

Uncompressed little-endian TIFF layout, written with the standard library
and not an approved decoder for arbitrary scans (``Q-ENG-05`` stays open):

- Magic ``II*\\x00``, then the first IFD offset ``8`` as a little-endian
  unsigned long.
- Nine IFD entries in tag order, then a zero next-IFD offset. Image bytes
  follow the IFD. Samples are one 8-bit grayscale value per pixel, row
  major, with compression tag 259 equal to 1 (none).
- ``ImageWidth`` (tag 256) is a little-endian long at byte offset 18.
  ``ImageLength`` (tag 257) is a little-endian long at byte offset 30.
- The page image is ``PAGE_IMAGE_WIDTH`` by ``PAGE_IMAGE_HEIGHT`` pixels.
  Those counts are the page millimetres divided by ``MILLIMETRES_PER_PIXEL``.
  A fragment image is the axis-aligned bounds of the page pixels whose
  centers lie inside that fragment's placed polygon. The placement rotates
  the eroded local polygon about its centroid, then adds that centroid.
  Positive rotation sends ``+x`` toward ``+y``.

Joins, placements, and the generator page are written only under the
caller-supplied ``benchmarks/`` directory. The image manifest lists digests
and byte lengths. It does not copy those labels. Solver code must not read
the BenchmarkLabel store. This module does not create a project database
and does not write ``originals/`` or ``manifest.json``.
"""

from __future__ import annotations

import math
import random
import struct
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from prw.frames import CoordinateFrame, polygon_centroid
from prw.identity import ABSENT, canonical_json_bytes, content_id, hash_value
from prw.provenance import ProvenanceEnvelope

type Point = tuple[float, float]

ALGORITHM_NAME = "synthetic_tear"
ALGORITHM_VERSION = "1"
DECODER_NAME = "synthetic_uncompressed_tiff"
DECODER_VERSION = "1"
PAGE_WIDTH_MM = 100.0
PAGE_HEIGHT_MM = 140.0
MILLIMETRES_PER_PIXEL = 1.0
PAGE_IMAGE_WIDTH = 100
PAGE_IMAGE_HEIGHT = 140
TIFF_MAGIC = b"II*\x00"
TIFF_WIDTH_OFFSET = 18
TIFF_HEIGHT_OFFSET = 30
_BASE_LEVEL = 128
_PIECE_COUNT = 4
_CUT_JITTER_MM = 4.0
_IFD_ENTRY_COUNT = 9
_TIFF_IFD_OFFSET = 8
_TIFF_IMAGE_OFFSET = _TIFF_IFD_OFFSET + 2 + _IFD_ENTRY_COUNT * 12 + 4
_PROJECT_DIRECTORY_NAMES = frozenset(
    {"originals", "observations", "runs", "validations", "exports"}
)
ImageRole = Literal["page", "fragment"]


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
    """One emitted piece.

    ``local_polygon`` is the eroded mask in ``fragment_local_mm``.
    ``page_polygon`` is that mask after the recorded placement.
    """

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
class GeneratedImage:
    """One fixture TIFF named in the image manifest.

    The manifest entry is a digest and a byte length. It is not a
    BenchmarkLabel and it is not a project ``manifest.json``.
    """

    role: ImageRole
    name: str
    content_hash: str
    byte_length: int
    width: int
    height: int
    fragment_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class SyntheticLeaf:
    """Polygons, cuts, labels, and fixture images for one seeded leaf."""

    page: PageLabel
    page_frame: CoordinateFrame
    cut_curves: tuple[CutCurve, ...]
    fragments: tuple[FragmentGeometry, ...]
    joins: tuple[JoinLabel, ...]
    placements: tuple[PlacementLabel, ...]
    envelope: ProvenanceEnvelope
    images: tuple[GeneratedImage, ...] = ()


def require_fixture_destination(path: Path) -> Path:
    """Return ``path`` when fixture files may be written there.

    A project evidence database is refused: ``originals/`` and the other
    directory names in the ADR-0007 sketch, and any destination already
    inside a directory that holds ``manifest.json``. This refusal does not
    accept a project format. Q-ENG-01 stays open.
    """
    if not isinstance(path, Path):
        raise TypeError("A fixture destination is a path.")
    if any(part in _PROJECT_DIRECTORY_NAMES for part in path.parts):
        raise ValueError(
            "Fixture files are not written into a project evidence database."
        )
    for parent in (path, *path.parents):
        if (parent / "manifest.json").is_file():
            raise ValueError("That destination is inside a project evidence database.")
    return path


def generate_synthetic_leaf(
    benchmarks_dir: Path,
    *,
    images_dir: Path,
    missing_fragment_percentage: float,
    edge_erosion: float,
    rotation: float,
    lighting_variation: float,
    random_seed: int,
    code_version: str,
) -> SyntheticLeaf:
    """Generate one leaf, its TIFF bytes, and its BenchmarkLabel records.

    ``lighting_variation`` changes the per-fragment raster gain and the
    parameter hash. It does not change the polygons. ``rotation`` changes the
    painted page polygon and the TIFF bytes. It does not change
    ``local_polygon``. ``random_seed`` chooses the cut jitter and which
    pieces the missing-fragment percentage omits. The same seed and
    parameters reproduce the same TIFF bytes.
    """
    require_fixture_destination(benchmarks_dir)
    require_fixture_destination(images_dir)
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
    _require_page_pixels()
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
        decoder_name=DECODER_NAME,
        decoder_version=DECODER_VERSION,
        model_hash=ABSENT,
        random_seed=random_seed,
    )
    draft = _build_leaf(
        envelope=envelope,
        missing_fragment_percentage=missing_fragment_percentage,
        edge_erosion=edge_erosion,
        rotation=rotation,
        random_seed=random_seed,
    )
    images = _write_fixture_images(images_dir, draft, lighting_variation)
    leaf = replace(draft, images=images)
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
    indexed: dict[int, FragmentGeometry] = {}
    for index, cut_polygon in enumerate(pieces):
        if index in omitted:
            continue
        indexed[index] = _fragment(cut_polygon, edge_erosion, rotation)
    fragments = tuple(indexed[index] for index in sorted(indexed))
    joins = _joins(indexed, omitted, vertical, horizontal)
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


def _fragment(
    cut_polygon: tuple[Point, ...],
    edge_erosion: float,
    rotation: float,
) -> FragmentGeometry:
    eroded_page = erode_toward_centroid(cut_polygon, edge_erosion)
    centroid = _centroid(eroded_page)
    local_polygon = _to_local(eroded_page, centroid)
    page_polygon = _place(local_polygon, rotation, centroid)
    fragment_id = content_id(
        {"kind": "fragment", "local_polygon": local_polygon, "page_centroid": centroid}
    )
    outline_revision_id = content_id(
        {"kind": "outline", "local_polygon": local_polygon}
    )
    frame = CoordinateFrame.fragment_local_mm(
        owner_id=fragment_id,
        establishing_outline_revision_id=outline_revision_id,
        polygon=local_polygon,
    )
    return FragmentGeometry(
        id=fragment_id,
        outline_revision_id=outline_revision_id,
        frame=frame,
        page_polygon=page_polygon,
        local_polygon=local_polygon,
        page_centroid=centroid,
    )


def _place(
    local_polygon: Sequence[Point],
    rotation: float,
    centroid: Point,
) -> tuple[Point, ...]:
    """Rotate about the local origin, then add the page centroid.

    Positive rotation sends ``+x`` toward ``+y``.
    """
    cosine = math.cos(rotation)
    sine = math.sin(rotation)
    origin_x, origin_y = centroid
    return tuple(
        (
            x_coord * cosine - y_coord * sine + origin_x,
            x_coord * sine + y_coord * cosine + origin_y,
        )
        for x_coord, y_coord in local_polygon
    )


def _joins(
    fragments: dict[int, FragmentGeometry],
    omitted: set[int],
    vertical: CutCurve,
    horizontal: CutCurve,
) -> tuple[JoinLabel, ...]:
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
        first = fragments[left]
        second = fragments[right]
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


def _write_fixture_images(
    directory: Path,
    leaf: SyntheticLeaf,
    lighting_variation: float,
) -> tuple[GeneratedImage, ...]:
    """Write uncompressed TIFF bytes and the digest manifest.

    The manifest is the list required by the synthetic-tear section of
    ``docs/EVALUATION.md``. Each entry has a ``sha256:`` digest and a byte
    length. Ground-truth joins, placements, and the page label are not
    copied into it.
    """
    directory.mkdir(parents=True, exist_ok=True)
    page_samples = _page_samples(leaf.fragments, lighting_variation)
    images = [
        _store_image(
            directory,
            role="page",
            name="page.tif",
            samples=page_samples,
            width=PAGE_IMAGE_WIDTH,
            height=PAGE_IMAGE_HEIGHT,
            fragment_id=None,
        )
    ]
    count = len(leaf.fragments)
    for index, fragment in enumerate(leaf.fragments):
        samples, width, height = _fragment_samples(
            fragment,
            index,
            count,
            lighting_variation,
        )
        images.append(
            _store_image(
                directory,
                role="fragment",
                name=f"fragment-{fragment.id}.tif",
                samples=samples,
                width=width,
                height=height,
                fragment_id=fragment.id,
            )
        )
    _write_json(
        directory / "image_manifest.json",
        {"images": [_manifest_entry(image) for image in images]},
    )
    return tuple(images)


def _store_image(
    directory: Path,
    *,
    role: ImageRole,
    name: str,
    samples: bytes,
    width: int,
    height: int,
    fragment_id: uuid.UUID | None,
) -> GeneratedImage:
    payload = _uncompressed_grayscale_tiff(width, height, samples)
    (directory / name).write_bytes(payload)
    return GeneratedImage(
        role=role,
        name=name,
        content_hash=hash_value(payload),
        byte_length=len(payload),
        width=width,
        height=height,
        fragment_id=fragment_id,
    )


def _manifest_entry(image: GeneratedImage) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "role": image.role,
        "name": image.name,
        "content_hash": image.content_hash,
        "byte_length": image.byte_length,
        "width": image.width,
        "height": image.height,
    }
    if image.fragment_id is not None:
        entry["fragment_id"] = image.fragment_id
    return entry


def _page_samples(
    fragments: Sequence[FragmentGeometry],
    lighting_variation: float,
) -> bytes:
    count = len(fragments)
    samples = bytearray(PAGE_IMAGE_WIDTH * PAGE_IMAGE_HEIGHT)
    for index, fragment in enumerate(fragments):
        level = _fragment_level(index, count, lighting_variation)
        _paint(samples, PAGE_IMAGE_WIDTH, fragment, level, 0, 0)
    return bytes(samples)


def fragment_polygon_in_source_pixels(
    page_polygon: Sequence[Point],
) -> tuple[Point, ...]:
    """Map a painted page polygon into that fragment crop's ``source_pixels``.

    A pixel center is ``(column + 0.5, row + 0.5)`` millimetres. The crop
    origin is the minimum column and row of page pixels whose centers lie
    inside the polygon, the same origin the fragment TIFF uses.
    """
    _covered, origin_x, origin_y = _crop(page_polygon)
    return tuple(
        (
            x_mm / MILLIMETRES_PER_PIXEL - 0.5 - origin_x,
            y_mm / MILLIMETRES_PER_PIXEL - 0.5 - origin_y,
        )
        for x_mm, y_mm in page_polygon
    )


def _fragment_samples(
    fragment: FragmentGeometry,
    index: int,
    count: int,
    lighting_variation: float,
) -> tuple[bytes, int, int]:
    covered, origin_x, origin_y = _crop(fragment.page_polygon)
    width = max(pixel[0] for pixel in covered) - origin_x + 1
    height = max(pixel[1] for pixel in covered) - origin_y + 1
    samples = bytearray(width * height)
    level = _fragment_level(index, count, lighting_variation)
    for column, row in covered:
        samples[(row - origin_y) * width + (column - origin_x)] = level
    return bytes(samples), width, height


def _paint(
    samples: bytearray,
    width: int,
    fragment: FragmentGeometry,
    level: int,
    origin_x: int,
    origin_y: int,
) -> None:
    for column, row in _covered_pixels(fragment.page_polygon):
        samples[(row - origin_y) * width + (column - origin_x)] = level


def _crop(polygon: Sequence[Point]) -> tuple[tuple[tuple[int, int], ...], int, int]:
    covered = _covered_pixels(polygon)
    if not covered:
        raise ValueError("The painted polygon covers no pixel.")
    origin_x = min(pixel[0] for pixel in covered)
    origin_y = min(pixel[1] for pixel in covered)
    return covered, origin_x, origin_y


def _covered_pixels(polygon: Sequence[Point]) -> tuple[tuple[int, int], ...]:
    covered: list[tuple[int, int]] = []
    for row in range(PAGE_IMAGE_HEIGHT):
        for column in range(PAGE_IMAGE_WIDTH):
            x_mm = (column + 0.5) * MILLIMETRES_PER_PIXEL
            y_mm = (row + 0.5) * MILLIMETRES_PER_PIXEL
            if _contains(x_mm, y_mm, polygon):
                covered.append((column, row))
    return tuple(covered)


def _contains(x_mm: float, y_mm: float, polygon: Sequence[Point]) -> bool:
    inside = False
    previous = len(polygon) - 1
    for index, (x_coord, y_coord) in enumerate(polygon):
        other_x, other_y = polygon[previous]
        crosses = (y_coord > y_mm) != (other_y > y_mm)
        if crosses:
            intersect_x = (other_x - x_coord) * (y_mm - y_coord) / (
                other_y - y_coord
            ) + x_coord
            if x_mm < intersect_x:
                inside = not inside
        previous = index
    return inside


def _fragment_level(index: int, count: int, lighting_variation: float) -> int:
    span = max(count - 1, 1)
    gain = 1.0 + lighting_variation * (2.0 * index / span - 1.0)
    level = round(_BASE_LEVEL * gain)
    if level < 0:
        return 0
    if level > 255:
        return 255
    return level


def _uncompressed_grayscale_tiff(width: int, height: int, samples: bytes) -> bytes:
    """Return one uncompressed 8-bit grayscale TIFF in this writer's layout.

    This is the fixture writer. It is not a decoder for arbitrary scans.
    """
    if width < 1 or height < 1:
        raise ValueError("A fixture image has a positive width and height.")
    if len(samples) != width * height:
        raise ValueError("Uncompressed grayscale samples are one byte per pixel.")
    entries = b"".join(
        (
            _tiff_long(256, width),
            _tiff_long(257, height),
            _tiff_short(258, 8),
            _tiff_short(259, 1),
            _tiff_short(262, 1),
            _tiff_long(273, _TIFF_IMAGE_OFFSET),
            _tiff_short(277, 1),
            _tiff_long(278, height),
            _tiff_long(279, width * height),
        )
    )
    ifd = struct.pack("<H", _IFD_ENTRY_COUNT) + entries + struct.pack("<I", 0)
    payload = TIFF_MAGIC + struct.pack("<I", _TIFF_IFD_OFFSET) + ifd + samples
    stored_width = struct.unpack_from("<I", payload, TIFF_WIDTH_OFFSET)[0]
    stored_height = struct.unpack_from("<I", payload, TIFF_HEIGHT_OFFSET)[0]
    if (stored_width, stored_height) != (width, height):
        raise ValueError(
            "The TIFF width and height were not stored at the documented offsets."
        )
    return payload


def _tiff_long(tag: int, value: int) -> bytes:
    return struct.pack("<HHII", tag, 4, 1, value)


def _tiff_short(tag: int, value: int) -> bytes:
    return struct.pack("<HHIHH", tag, 3, 1, value, 0)


def _require_page_pixels() -> None:
    width = PAGE_WIDTH_MM / MILLIMETRES_PER_PIXEL
    height = PAGE_HEIGHT_MM / MILLIMETRES_PER_PIXEL
    if width != PAGE_IMAGE_WIDTH or height != PAGE_IMAGE_HEIGHT:
        raise ValueError("Page size is a positive whole number of pixels.")


def _centroid(vertices: Sequence[Point]) -> Point:
    return polygon_centroid(vertices)


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
