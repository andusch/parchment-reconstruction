"""Round-trip the fixture writer's TIFF layout and refuse every other one."""

import dataclasses
import struct
from pathlib import Path

from prw.fixture_tiff import (
    FixtureSamples,
    UnsupportedFixtureLayout,
    read_fixture_tiff,
)
from prw.outlines import FragmentOutlineRevision
from prw.synthetic_tear import (
    DECODER_NAME,
    DECODER_VERSION,
    PAGE_IMAGE_HEIGHT,
    PAGE_IMAGE_WIDTH,
    TIFF_HEIGHT_OFFSET,
    TIFF_MAGIC,
    TIFF_WIDTH_OFFSET,
    generate_synthetic_leaf,
)

_ENTRY_STRIDE = 12


def _generate(directory: Path) -> Path:
    images = directory.parent / f"{directory.name}-images"
    generate_synthetic_leaf(
        directory,
        images_dir=images,
        missing_fragment_percentage=0.0,
        edge_erosion=0.0,
        rotation=0.2,
        lighting_variation=0.0,
        random_seed=7,
        code_version="test-code",
    )
    return images


def _value_offset(entry_index: int) -> int:
    return TIFF_WIDTH_OFFSET + entry_index * _ENTRY_STRIDE


def _strip_samples(payload: bytes) -> bytes:
    width = struct.unpack_from("<I", payload, TIFF_WIDTH_OFFSET)[0]
    height = struct.unpack_from("<I", payload, TIFF_HEIGHT_OFFSET)[0]
    strip_offset = struct.unpack_from("<I", payload, _value_offset(5))[0]
    byte_count = struct.unpack_from("<I", payload, _value_offset(8))[0]
    assert byte_count == width * height
    return payload[strip_offset : strip_offset + byte_count]


def _assert_not_an_outline(failure: UnsupportedFixtureLayout) -> None:
    assert not isinstance(failure, FragmentOutlineRevision)
    names = {field.name for field in dataclasses.fields(failure)}
    assert "polygon" not in names
    assert "epistemic_class" not in names
    assert "pixels_per_mm" not in names
    assert not hasattr(failure, "polygon")


def test_generated_tiff_round_trips_width_height_and_samples(tmp_path: Path) -> None:
    images = _generate(tmp_path / "benchmarks")
    page = (images / "page.tif").read_bytes()
    read = read_fixture_tiff(page)
    assert isinstance(read, FixtureSamples)
    assert (read.width, read.height) == (PAGE_IMAGE_WIDTH, PAGE_IMAGE_HEIGHT)
    assert read.samples == _strip_samples(page)
    assert read.decoder_name == "synthetic_uncompressed_tiff"
    assert read.decoder_name == DECODER_NAME
    assert read.decoder_version == "1"
    assert read.decoder_version == DECODER_VERSION
    names = {field.name for field in dataclasses.fields(read)}
    assert "pixels_per_mm" not in names
    fragment_name = next(path.name for path in images.glob("fragment-*.tif"))
    fragment = (images / fragment_name).read_bytes()
    fragment_read = read_fixture_tiff(fragment)
    assert isinstance(fragment_read, FixtureSamples)
    assert fragment_read.samples == _strip_samples(fragment)
    assert len(fragment_read.samples) == fragment_read.width * fragment_read.height
    assert (fragment_read.width, fragment_read.height) != (
        read.width,
        read.height,
    )


def test_other_layouts_fail_without_an_outline(tmp_path: Path) -> None:
    images = _generate(tmp_path / "benchmarks")
    page = bytearray((images / "page.tif").read_bytes())
    assert page.startswith(TIFF_MAGIC)

    rewritten = bytearray(page)
    struct.pack_into("<I", rewritten, 4, 16)
    different_ifd = read_fixture_tiff(rewritten)
    assert isinstance(different_ifd, UnsupportedFixtureLayout)
    assert different_ifd.kind == "different_ifd"
    _assert_not_an_outline(different_ifd)

    compressed = bytearray(page)
    struct.pack_into("<H", compressed, _value_offset(3), 5)
    compressed_strip = read_fixture_tiff(compressed)
    assert isinstance(compressed_strip, UnsupportedFixtureLayout)
    assert compressed_strip.kind == "compressed_strip"
    _assert_not_an_outline(compressed_strip)

    rgb = bytearray(page)
    struct.pack_into("<H", rgb, _value_offset(4), 2)
    not_grayscale = read_fixture_tiff(rgb)
    assert isinstance(not_grayscale, UnsupportedFixtureLayout)
    assert not_grayscale.kind == "not_grayscale"
    _assert_not_an_outline(not_grayscale)

    other = read_fixture_tiff(b"MM\x00*" + bytes(32))
    assert isinstance(other, UnsupportedFixtureLayout)
    assert other.kind == "other_layout"
    _assert_not_an_outline(other)
