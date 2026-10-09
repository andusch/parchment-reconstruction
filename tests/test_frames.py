"""Synthetic frames under the ADR-0011 axis convention."""

import dataclasses
import uuid

import pytest

from prw.frames import (
    AXIS_X_RIGHT,
    AXIS_Y_DOWN,
    ORIGIN_MINIMUM_PAGE_CORNER,
    ORIGIN_OUTLINE_CENTROID,
    ORIGIN_TOP_LEFT_PIXEL,
    CoordinateFrame,
    PageFrame,
    polygon_centroid,
)
from prw.identity import content_id

_SQUARE = ((0, 0), (2, 0), (2, 2), (0, 2))
_LARGER = ((0, 0), (4, 0), (4, 4), (0, 4))


def test_square_centroid_is_the_mean_of_its_vertices() -> None:
    assert polygon_centroid(_SQUARE) == (1.0, 1.0)


def test_each_kind_stores_the_adr_0011_origin_and_axes() -> None:
    source = uuid.uuid4()
    fragment = uuid.uuid4()
    project = uuid.uuid4()
    outline = uuid.uuid4()
    pixels = CoordinateFrame.source_pixels(owner_id=source)
    local = CoordinateFrame.fragment_local_mm(
        owner_id=fragment,
        establishing_outline_revision_id=outline,
        polygon=_SQUARE,
    )
    page = CoordinateFrame.page_global_mm(owner_id=project)
    assert pixels.kind == "source_pixels"
    assert pixels.unit == "px"
    assert pixels.origin_description == ORIGIN_TOP_LEFT_PIXEL
    assert pixels.origin == (0.0, 0.0)
    assert pixels.establishing_outline_revision_id is None
    assert local.kind == "fragment_local_mm"
    assert local.unit == "mm"
    assert local.origin_description == ORIGIN_OUTLINE_CENTROID
    assert local.origin == (1.0, 1.0)
    assert local.establishing_outline_revision_id == outline
    assert page.kind == "page_global_mm"
    assert page.unit == "mm"
    assert page.origin_description == ORIGIN_MINIMUM_PAGE_CORNER
    assert page.origin == (0.0, 0.0)
    for frame in (pixels, local, page):
        assert frame.axis_x_direction == AXIS_X_RIGHT
        assert frame.axis_y_direction == AXIS_Y_DOWN
        assert frame.id.version == 5
        assert frame.id == content_id(frame.content_mapping())
        names = {item.name for item in dataclasses.fields(frame)}
        assert "fragment_extent_id" not in names
        assert names.isdisjoint(
            {"rotation_radians", "translation_x", "translation_y", "uniform_scale"}
        )


def test_a_later_outline_does_not_move_the_fragment_origin() -> None:
    outline = uuid.uuid4()
    frame = CoordinateFrame.fragment_local_mm(
        owner_id=uuid.uuid4(),
        establishing_outline_revision_id=outline,
        polygon=_SQUARE,
    )
    later = frame.with_later_outline(uuid.uuid4(), _LARGER)
    assert later.establishing_outline_revision_id == outline
    assert later.origin == (1.0, 1.0)
    assert later.id == frame.id
    assert "establishing_outline_revision_id" in frame.content_mapping()
    pixels = CoordinateFrame.source_pixels(owner_id=uuid.uuid4())
    assert "establishing_outline_revision_id" not in pixels.content_mapping()


def test_page_ranges_do_not_move_the_origin() -> None:
    frame = CoordinateFrame.page_global_mm(owner_id=uuid.uuid4())
    page = PageFrame.create(
        frame,
        min_width_mm=10,
        max_width_mm=12,
        min_height_mm=20,
        max_height_mm=22,
    )
    replaced = page.replace_ranges(
        min_width_mm=1,
        max_width_mm=3,
        min_height_mm=4,
        max_height_mm=8,
    )
    assert frame.origin == (0.0, 0.0)
    assert page.frame_id == frame.id
    assert replaced.frame_id == frame.id
    assert replaced.id != page.id
    assert replaced.id == content_id(replaced.content_mapping())
    assert replaced.id.version == 5
    with pytest.raises(ValueError, match="page_global_mm"):
        PageFrame.create(
            CoordinateFrame.source_pixels(owner_id=uuid.uuid4()),
            min_width_mm=1,
            max_width_mm=2,
            min_height_mm=1,
            max_height_mm=2,
        )
