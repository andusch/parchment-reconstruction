"""Decode lossless TIFF masters that are not the synthetic fixture layout."""

import dataclasses
import json
import struct
import subprocess
import sys
import uuid
import zlib
from pathlib import Path

from prw.fixture_tiff import FixtureSamples, UnsupportedFixtureLayout, read_fixture_tiff
from prw.ingest import VerifiedBytes, ingest_bytes
from prw.lossless_tiff import (
    DECODER_NAME,
    DECODER_VERSION,
    DecodedRaster,
    TiffDecodeFailure,
    read_lossless_tiff,
)
from prw.outlines import FragmentOutlineRevision
from prw.segment import FailedSegmentation, SegmentationLog, SegmentedOutline
from prw.synthetic_tear import generate_synthetic_leaf

_RECORDED = "2020-01-01T00:00:00Z"


class _Page:
    def __init__(
        self,
        width: int,
        height: int,
        blobs: tuple[bytes, ...],
        *,
        photometric: int = 1,
        compression: int = 1,
        bits: tuple[int, ...] = (8,),
        spp: int = 1,
        rows_per_strip: int | None = None,
        predictor: int | None = None,
        planar: int | None = None,
        extra: tuple[int, ...] | None = None,
        colormap: tuple[int, ...] | None = None,
        tiles: tuple[int, int] | None = None,
        reduced: bool = False,
        orientation: int | None = None,
        sample_format: tuple[int, ...] | None = None,
        fill_order: int | None = None,
        omit_byte_counts: bool = False,
        bad_rational: bool = False,
    ) -> None:
        self.width = width
        self.height = height
        self.blobs = blobs
        self.photometric = photometric
        self.compression = compression
        self.bits = bits
        self.spp = spp
        self.rows_per_strip = rows_per_strip
        self.predictor = predictor
        self.planar = planar
        self.extra = extra
        self.colormap = colormap
        self.tiles = tiles
        self.reduced = reduced
        self.orientation = orientation
        self.sample_format = sample_format
        self.fill_order = fill_order
        self.omit_byte_counts = omit_byte_counts
        self.bad_rational = bad_rational


def _numbers(endian: str, type_code: int, values: tuple[int, ...]) -> bytes:
    if type_code == 1:
        return bytes(values)
    code = "H" if type_code == 3 else "I"
    return struct.pack(endian + (code * len(values)), *values)


def _tag_map(
    page: _Page, blob_offsets: tuple[int, ...]
) -> dict[int, tuple[int, tuple[int, ...]]]:
    tags: dict[int, tuple[int, tuple[int, ...]]] = {
        256: (4, (page.width,)),
        257: (4, (page.height,)),
        258: (3, page.bits),
        259: (3, (page.compression,)),
        262: (3, (page.photometric,)),
        277: (3, (page.spp,)),
    }
    if page.tiles is None:
        rows = page.height if page.rows_per_strip is None else page.rows_per_strip
        tags[273] = (4, blob_offsets)
        tags[278] = (4, (rows,))
        if not page.omit_byte_counts:
            tags[279] = (4, tuple(len(blob) for blob in page.blobs))
    else:
        tags[322] = (4, (page.tiles[0],))
        tags[323] = (4, (page.tiles[1],))
        tags[324] = (4, blob_offsets)
        if not page.omit_byte_counts:
            tags[325] = (4, tuple(len(blob) for blob in page.blobs))
    if page.reduced:
        tags[254] = (4, (1,))
    if page.predictor is not None:
        tags[317] = (3, (page.predictor,))
    if page.planar is not None:
        tags[284] = (3, (page.planar,))
    if page.extra is not None:
        tags[338] = (3, page.extra)
    if page.colormap is not None:
        tags[320] = (3, page.colormap)
    if page.orientation is not None:
        tags[274] = (3, (page.orientation,))
    if page.sample_format is not None:
        tags[339] = (3, page.sample_format)
    if page.fill_order is not None:
        tags[266] = (3, (page.fill_order,))
    if page.bad_rational:
        tags[282] = (5, ())
    return tags


def _value_len(type_code: int, values: tuple[int, ...]) -> int:
    if type_code == 5:
        return 0
    size = {1: 1, 3: 2, 4: 4}[type_code]
    raw = size * len(values)
    return 0 if raw <= 4 else raw


def _build(pages: tuple[_Page, ...], endian: str = "<") -> bytes:
    cursor = 8
    plan_row = tuple[_Page, dict[int, tuple[int, tuple[int, ...]]], int, int, int]
    plans: list[plan_row] = []
    for page in pages:
        blob_offsets: list[int] = []
        for blob in page.blobs:
            blob_offsets.append(cursor)
            cursor += len(blob)
        tags = _tag_map(page, tuple(blob_offsets))
        overflow_at = cursor
        lengths = (_value_len(kind, values) for kind, values in tags.values())
        extra = sum(lengths)
        cursor += extra
        ifd_at = cursor
        cursor += 2 + 12 * len(tags) + 4
        plans.append((page, tags, overflow_at, ifd_at, cursor))
    out = bytearray(cursor)
    first_ifd = plans[0][3]
    if endian == "<":
        out[:8] = b"II*\x00" + struct.pack("<I", first_ifd)
    else:
        out[:8] = b"MM\x00*" + struct.pack(">I", first_ifd)
    for index, (page, tags, overflow_at, ifd_at, _end) in enumerate(plans):
        entries: list[bytes] = []
        overflow = overflow_at
        for tag in sorted(tags):
            type_code, values = tags[tag]
            if type_code == 5:
                entries.append(struct.pack(endian + "HHII", tag, 5, 1, 0xFFFFFFFF))
                continue
            raw = _numbers(endian, type_code, values)
            if len(raw) <= 4:
                inline = raw + bytes(4 - len(raw))
                entries.append(
                    struct.pack(endian + "HHI", tag, type_code, len(values)) + inline
                )
            else:
                out[overflow : overflow + len(raw)] = raw
                entries.append(
                    struct.pack(endian + "HHII", tag, type_code, len(values), overflow)
                )
                overflow += len(raw)
        next_ifd = plans[index + 1][3] if index + 1 < len(plans) else 0
        ifd = (
            struct.pack(endian + "H", len(entries))
            + b"".join(entries)
            + struct.pack(endian + "I", next_ifd)
        )
        out[ifd_at : ifd_at + len(ifd)] = ifd
        data_cursor = _data_start(plans, index)
        for blob in page.blobs:
            out[data_cursor : data_cursor + len(blob)] = blob
            data_cursor += len(blob)
    return bytes(out)


def _data_start(
    plans: list[tuple[_Page, dict[int, tuple[int, tuple[int, ...]]], int, int, int]],
    index: int,
) -> int:
    if index == 0:
        return 8
    return plans[index - 1][4]


def _gray(
    samples: bytes,
    width: int,
    height: int,
    *,
    endian: str = "<",
    **kwargs: object,
) -> bytes:
    page = _Page(width, height, (samples,))
    for key, value in kwargs.items():
        setattr(page, key, value)
    return _build((page,), endian)


def _read(payload: bytes) -> DecodedRaster:
    read = read_lossless_tiff(payload)
    assert isinstance(read, DecodedRaster)
    assert read.decoder_name == DECODER_NAME == "lossless_tiff"
    assert read.decoder_version == DECODER_VERSION == "1"
    assert "pixels_per_mm" not in {field.name for field in dataclasses.fields(read)}
    return read


def _assert_not_outline(failure: TiffDecodeFailure) -> None:
    assert not isinstance(failure, FragmentOutlineRevision)
    names = {field.name for field in dataclasses.fields(failure)}
    assert "polygon" not in names
    assert "epistemic_class" not in names
    assert "pixels_per_mm" not in names


def _difference8(samples: bytes, width: int, spp: int) -> bytes:
    row_samples = width * spp
    height = len(samples) // row_samples
    out = bytearray(len(samples))
    for row in range(height):
        start = row * row_samples
        for index in range(row_samples):
            if index < spp:
                out[start + index] = samples[start + index]
            else:
                out[start + index] = (
                    samples[start + index] - samples[start + index - spp]
                ) & 0xFF
    return bytes(out)


def _lzw_encode(data: bytes) -> bytes:
    table = {bytes((index,)): index for index in range(256)}
    next_code = 258
    width = 9
    bits: list[int] = []

    def write(code: int, size: int) -> None:
        for shift in range(size - 1, -1, -1):
            bits.append((code >> shift) & 1)

    write(256, 9)
    if data:
        current = bytes((data[0],))
        for value in data[1:]:
            nxt = bytes((value,))
            joined = current + nxt
            if joined in table:
                current = joined
                continue
            write(table[current], width)
            if next_code < 4096:
                table[joined] = next_code
                next_code += 1
                if next_code == 512:
                    width = 10
                elif next_code == 1024:
                    width = 11
                elif next_code == 2048:
                    width = 12
            current = nxt
        write(table[current], width)
        # The final code consumes a table slot. EOI uses the width after that.
        next_code += 1
        if next_code == 512:
            width = 10
        elif next_code == 1024:
            width = 11
        elif next_code == 2048:
            width = 12
    write(257, width)
    out = bytearray()
    acc = 0
    have = 0
    for bit in bits:
        acc = (acc << 1) | bit
        have += 1
        if have == 8:
            out.append(acc)
            acc = 0
            have = 0
    if have:
        out.append(acc << (8 - have))
    return bytes(out)


def _packbits(data: bytes) -> bytes:
    out = bytearray()
    index = 0
    while index < len(data):
        if index + 1 < len(data) and data[index] == data[index + 1]:
            value = data[index]
            end = index + 1
            while end < len(data) and end - index < 128 and data[end] == value:
                end += 1
            out.append(256 - (end - index - 1))
            out.append(value)
            index = end
            continue
        end = index + 1
        while (
            end < len(data)
            and end - index < 128
            and not (end + 1 < len(data) and data[end] == data[end + 1])
        ):
            end += 1
        literal = data[index:end]
        out.append(len(literal) - 1)
        out += literal
        index = end
    return bytes(out)


def _tiles(
    samples: bytes, width: int, height: int, spp: int, tile_w: int, tile_h: int
) -> tuple[bytes, ...]:
    across = (width + tile_w - 1) // tile_w
    down = (height + tile_h - 1) // tile_h
    blobs: list[bytes] = []
    for tile_y in range(down):
        for tile_x in range(across):
            blob = bytearray(tile_w * tile_h * spp)
            for row in range(tile_h):
                for col in range(tile_w):
                    y_coord = tile_y * tile_h + row
                    x_coord = tile_x * tile_w + col
                    dest = (row * tile_w + col) * spp
                    if y_coord < height and x_coord < width:
                        src = (y_coord * width + x_coord) * spp
                        blob[dest : dest + spp] = samples[src : src + spp]
                    else:
                        blob[dest : dest + spp] = b"\xff" * spp
            blobs.append(bytes(blob))
    return tuple(blobs)


def test_lzw_encoder_matches_a_hand_built_clear_literal() -> None:
    assert _lzw_encode(b"\x41") == bytes((0x80, 0x10, 0x60, 0x20))


def test_fixture_page_matches_and_keeps_its_own_decoder_name(tmp_path: Path) -> None:
    images = tmp_path / "images"
    generate_synthetic_leaf(
        tmp_path / "benchmarks",
        images_dir=images,
        missing_fragment_percentage=0.0,
        edge_erosion=0.0,
        rotation=0.0,
        lighting_variation=0.0,
        random_seed=3,
        code_version="test-code",
    )
    page = (images / "page.tif").read_bytes()
    fixture = read_fixture_tiff(page)
    general = _read(page)
    assert isinstance(fixture, FixtureSamples)
    assert general.samples == fixture.samples
    assert (general.width, general.height) == (fixture.width, fixture.height)
    segmented = SegmentationLog().segment(
        page,
        project_id=uuid.uuid4(),
        label="page",
        foreground_threshold=1,
        code_version="test-code",
        recorded_at=_RECORDED,
    )
    assert isinstance(segmented, SegmentedOutline | FailedSegmentation)
    assert segmented.run.provenance.decoder_name == "synthetic_uncompressed_tiff"


def test_big_endian_grayscale_is_not_the_fixture_layout_and_segments() -> None:
    samples = bytes([200]) * 16
    payload = bytearray(_gray(samples, 4, 4, endian=">"))
    before = bytes(payload)
    assert isinstance(read_fixture_tiff(payload), UnsupportedFixtureLayout)
    read = _read(payload)
    assert read.samples == samples
    assert bytes(payload) == before
    verified = ingest_bytes(payload)
    assert isinstance(verified, VerifiedBytes)
    segmented = SegmentationLog().segment(
        payload,
        project_id=uuid.uuid4(),
        label="shelf-1",
        foreground_threshold=1,
        code_version="test-code",
        recorded_at=_RECORDED,
    )
    assert isinstance(segmented, SegmentedOutline)
    assert segmented.outline.epistemic_class == "interpretation"
    assert segmented.outline.producer == "machine"
    assert segmented.run.provenance.decoder_name == "lossless_tiff"
    assert segmented.run.provenance.decoder_version == "1"
    assert segmented.run.provenance.random_seed is None
    assert len(segmented.outline.polygon) >= 3


def test_empty_big_endian_master_fails_segmentation_after_decode() -> None:
    payload = _gray(bytes(4), 2, 2, endian=">")
    assert isinstance(read_fixture_tiff(payload), UnsupportedFixtureLayout)
    segmented = SegmentationLog().segment(
        payload,
        project_id=uuid.uuid4(),
        label="shelf-1",
        foreground_threshold=1,
        code_version="test-code",
        recorded_at=_RECORDED,
    )
    assert isinstance(segmented, FailedSegmentation)
    assert segmented.kind == "no_foreground"
    assert segmented.run.provenance.decoder_name == "lossless_tiff"
    assert not hasattr(segmented, "polygon")


def test_photometric_rgb_palette_white_is_zero_and_alpha() -> None:
    rgb = bytes((255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 255))
    decoded = _read(_gray(rgb, 2, 2, photometric=2, bits=(8, 8, 8), spp=3))
    assert decoded.samples == bytes((76, 150, 29, 255))
    white_zero = _read(_gray(bytes((0, 255, 10)), 3, 1, photometric=0))
    assert white_zero.samples == bytes((255, 0, 245))
    rgba = bytes((255, 0, 0, 128))
    assert _read(_gray(rgba, 1, 1, photometric=2, spp=4, extra=(2,))).samples == bytes(
        (76,)
    )
    colormap = tuple([0, 65535] + [0] * 254 + [0] * 256 + [0] * 256)
    palette = _read(_gray(bytes((0, 1)), 2, 1, photometric=3, colormap=colormap))
    assert palette.samples == bytes((0, 76))


def test_one_bit_sixteen_bit_and_predictor() -> None:
    bilevel = _read(_gray(bytes((0xA0,)), 4, 1, bits=(1,)))
    assert bilevel.samples == bytes((255, 0, 255, 0))
    white_bits = _read(_gray(bytes((0xA0,)), 4, 1, bits=(1,), photometric=0))
    assert white_bits.samples == bytes((0, 255, 0, 255))
    raw = bytes((0x02, 0x01, 0x00, 0xAB))
    assert _read(_gray(raw, 2, 1, bits=(16,))).samples == bytes((0x01, 0xAB))
    big = _gray(bytes((0x01, 0x02, 0xAB, 0x00)), 2, 1, bits=(16,), endian=">")
    assert _read(big).samples == bytes((0x01, 0xAB))
    original = bytes((10, 13, 13, 40, 40, 41))
    differed = _difference8(original, 3, 1)
    packed = zlib.compress(differed)
    predicted = _read(_gray(packed, 3, 2, compression=8, predictor=2))
    assert predicted.samples == original


def test_strips_tiles_planar_packbits_deflate_and_lzw() -> None:
    strips = (bytes((1, 2, 3, 4)), bytes((5, 6, 7, 8)), bytes((9, 10)))
    page = _Page(2, 5, strips, rows_per_strip=2)
    assert _read(_build((page,))).samples == b"".join(strips)
    omitted = _Page(2, 2, (bytes((4, 5, 6, 7)),), omit_byte_counts=True)
    assert _read(_build((omitted,))).samples == bytes((4, 5, 6, 7))
    tiled = bytes(index % 256 for index in range(6 * 5))
    tiles = _tiles(tiled, 6, 5, 1, 4, 4)
    tiled_page = _Page(6, 5, tiles, tiles=(4, 4))
    assert _read(_build((tiled_page,))).samples == tiled
    packed = _packbits(bytes((5, 5, 5, 1, 2, 3)))
    assert _read(_gray(packed, 6, 1, compression=32773)).samples == bytes(
        (5, 5, 5, 1, 2, 3)
    )
    raw = bytes(range(64))
    assert _read(_gray(zlib.compress(raw), 8, 8, compression=8)).samples == raw
    assert _read(_gray(zlib.compress(raw), 8, 8, compression=32946)).samples == raw
    encoded = _lzw_encode(b"\x41")
    assert _read(_gray(encoded, 1, 1, compression=5)).samples == b"\x41"
    longer = bytes(range(256)) + bytes(range(256))
    assert _read(_gray(_lzw_encode(longer), 32, 16, compression=5)).samples == longer
    differed = _difference8(longer, 32, 1)
    assert (
        _read(_gray(_lzw_encode(differed), 32, 16, compression=5, predictor=2)).samples
        == longer
    )
    planes = (bytes((255, 0)), bytes((0, 255)), bytes((0, 0)))
    planar = _Page(2, 1, planes, photometric=2, spp=3, bits=(8, 8, 8), planar=2)
    assert _read(_build((planar,))).samples == bytes((76, 150))


def test_reduced_ifd_orientation_and_ignored_resolution() -> None:
    full = bytes((9, 8, 7, 6))
    thumb = _Page(1, 1, (b"\x00",), reduced=True)
    image = _Page(2, 2, (full,))
    assert _read(_build((thumb, image))).samples == full
    turned = _Page(2, 2, (full,), orientation=2)
    plain = _Page(2, 2, (full,))
    assert _read(_build((turned,))).samples == _read(_build((plain,))).samples
    tagged = _Page(2, 2, (full,), bad_rational=True)
    assert _read(_build((tagged,))).samples == full


def test_refused_layouts_have_no_outline() -> None:
    cases = (
        (b"hello", "not_tiff"),
        (b"II+\x00" + struct.pack("<I", 8), "bigtiff"),
        (b"MM\x00*", "inconsistent"),
        (_gray(b"\x00", 1, 1, compression=7), "jpeg_compression"),
        (_gray(b"\x00", 1, 1, compression=4), "unsupported_compression"),
        (_gray(b"\x00", 1, 1, photometric=5), "unsupported_photometric"),
        (_gray(b"\x00", 1, 1, bits=(4,)), "unsupported_bits"),
        (_gray(b"\x00\x00", 1, 1, bits=(16,), sample_format=(3,)), "unsupported_bits"),
        (_gray(b"\x00", 1, 1, fill_order=2), "inconsistent"),
        (_gray(b"\x00", 200_001, 1), "oversized"),
        (_gray(b"\xff", 1, 1, compression=5), "inconsistent"),
    )
    for payload, kind in cases:
        failure = read_lossless_tiff(payload)
        assert isinstance(failure, TiffDecodeFailure)
        assert failure.kind == kind
        _assert_not_outline(failure)


def test_segment_and_rank_accept_a_non_fixture_master(tmp_path: Path) -> None:
    samples = bytes([210, 210, 0, 0, 210, 210, 0, 0])
    payload = _gray(samples, 4, 2, endian=">")
    assert isinstance(read_fixture_tiff(payload), UnsupportedFixtureLayout)
    path = tmp_path / "master.tif"
    path.write_bytes(payload)
    other = tmp_path / "other.tif"
    other.write_bytes(_gray(bytes([180]) * 8, 4, 2, endian=">"))
    segmented = _cli(
        "segment",
        str(path),
        "--label",
        "shelf-1",
        "--foreground-threshold",
        "1",
        "--code-version",
        "test-code",
    )
    assert segmented.returncode == 0, segmented.stderr
    outline = json.loads(segmented.stdout)
    assert outline["record"] == "FragmentOutlineRevision"
    assert outline["epistemic_class"] == "interpretation"
    assert outline["producer"] == "machine"
    assert outline["frame"] == "source_pixels"
    assert outline["envelope"]["decoder_name"] == "lossless_tiff"
    assert outline["envelope"]["decoder_version"] == "1"
    assert "random_seed" not in outline["envelope"]
    assert "UnsupportedFixtureLayout" not in segmented.stdout
    assert path.read_bytes() == payload
    ranked = _cli(
        "rank",
        "--image",
        "shelf-1",
        str(path),
        "--image",
        "shelf-2",
        str(other),
        "--foreground-threshold",
        "1",
        "--code-version",
        "test-code",
        "--pixels-per-mm",
        "10",
        "--uncertainty",
        "0.1",
    )
    assert ranked.returncode == 0, ranked.stderr
    body = json.loads(ranked.stdout)
    assert body["record"] == "physical_join_order"
    assert body["envelope"]["decoder_name"] == "lossless_tiff"
    assert "UnsupportedFixtureLayout" not in ranked.stdout
    for join in body["joins"]:
        assert join["epistemic_class"] == "hypothesis"
        assert join["channel"] == "physical"


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "prw.cli", *args],
        capture_output=True,
        text=True,
        check=False,
    )
