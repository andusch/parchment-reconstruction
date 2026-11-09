"""Decode one classic lossless TIFF into 8-bit grayscale samples.

``Q-ENG-05`` is closed by ``docs/adr/0014-stdlib-lossless-tiff.md``. This
module is the decoder for a master that is not the synthetic fixture
layout. It uses the Python standard library (``struct`` and ``zlib``) and
adds no runtime dependency. It does not rewrite the presented bytes, does
not read tags 282 or 283 into ``pixels_per_mm``, and does not apply tag
274 (orientation), an ICC profile, or a transfer function.

``DECODER_NAME`` is ``lossless_tiff`` and ``DECODER_VERSION`` is ``1``.
The fixture writer layout still uses ``synthetic_uncompressed_tiff``
version ``1`` from ``prw.fixture_tiff``. Callers that need stable
provenance for that layout try the fixture reader first.

Accepted layout, when the bytes are a classic TIFF (magic ``II*\\x00`` or
``MM\\x00*``, version 42):

- The first IFD whose ``NewSubfileType`` is not a reduced-resolution image
  and not a transparency mask. A following IFD is not read.
- Strips or tiles, chunky or planar.
- Compression 1 (none), 32771 (old uncompressed), 5 (TIFF LZW), 8 and
  32946 (zlib deflate), and 32773 (PackBits). TIFF LZW is not GIF LZW.
- Predictor 1, and predictor 2 (horizontal differencing) at 8 or 16 bits.
- Photometric 0 (WhiteIsZero), 1 (BlackIsZero), 2 (RGB), and 3 (palette)
  at 1 or 8 bits. Palette samples are indexes into the colormap.
- Bits per sample 1, 8, or 16, unsigned. Extra samples are dropped.
  Associated alpha is not un-premultiplied.
- At most ``_MAX_EDGE`` pixels on a side and ``_MAX_PIXELS`` pixels.

The samples handed to the outline algorithm are 8-bit, row-major, and
BlackIsZero: 0 is black and 255 is white. 16-bit samples keep the high
byte. 1-bit samples expand to 0 or 255. RGB and palette use the integer
BT.601 weights ``(19595, 38470, 7471)`` with a rounding bias of 32768.
That reduction is part of this decoder. It is not a color measurement,
not a reading, and not a calibration.

Refused, as ``TiffDecodeFailure`` and not an outline:

- ``not_tiff``: the header is not classic TIFF and not BigTIFF.
- ``bigtiff``: version 43. ``prw verify`` still rejects that magic as
  ``UnsupportedMediaType`` before this decoder runs.
- ``jpeg_compression``: compression 6 or 7, including a lossless JPEG
  mode. There is no JPEG decoder in this module.
- ``unsupported_compression``: any other compression, including CCITT,
  JPEG 2000, and WebP.
- ``unsupported_photometric``: a photometric value other than 0, 1, 2,
  or 3, including CMYK and YCbCr.
- ``unsupported_bits``: a bit depth other than 1, 8, or 16; mixed depths;
  1-bit RGB; a 16-bit palette; or a sample format other than unsigned.
- ``oversized``: a dimension or pixel count above the caps above.
- ``inconsistent``: a truncated file, a missing required tag, a bad
  strip or tile, LSB fill order, or a codec that does not yield the
  expected sample count.

A layout failure has no polygon and no epistemic class.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from typing import Literal, NoReturn

DECODER_NAME = "lossless_tiff"
DECODER_VERSION = "1"
_MAX_EDGE = 200_000
_MAX_PIXELS = 400_000_000
_MAX_SAMPLES = 8
_MAX_TAGS = 1024
_MAX_VALUES = 2_000_000
_LZW_MAX_CODE = 4096

TiffDecodeFailureKind = Literal[
    "not_tiff",
    "bigtiff",
    "jpeg_compression",
    "unsupported_compression",
    "unsupported_photometric",
    "unsupported_bits",
    "oversized",
    "inconsistent",
]

_NUMERIC = {1: (1, "B"), 3: (2, "H"), 4: (4, "I")}
_COLOR_SAMPLES = {0: 1, 1: 1, 2: 3, 3: 1}
_SUPPORTED_COMPRESSION = frozenset({1, 5, 8, 32771, 32773, 32946})
_LUMA_RED = 19595
_LUMA_GREEN = 38470
_LUMA_BLUE = 7471
_LUMA_BIAS = 32768


class _Rejected(Exception):
    """Internal decode refusal. The public result is ``TiffDecodeFailure``."""

    def __init__(self, kind: TiffDecodeFailureKind) -> None:
        self.kind: TiffDecodeFailureKind = kind
        super().__init__(kind)


def _reject(kind: TiffDecodeFailureKind) -> NoReturn:
    raise _Rejected(kind)


@dataclass(frozen=True, slots=True)
class _Field:
    type_code: int
    count: int
    inline: bytes


@dataclass(frozen=True, slots=True)
class _Ifd:
    fields: dict[int, _Field]
    next_offset: int


@dataclass(frozen=True, slots=True)
class _Geometry:
    width: int
    height: int
    spp: int
    bits: int
    compression: int
    predictor: int
    planar: int
    photometric: int
    endian: str
    colormap: tuple[int, ...] | None


def read_lossless_tiff(
    payload: bytes | bytearray,
) -> DecodedRaster | TiffDecodeFailure:
    """Return grayscale samples, or a decode failure.

    ``payload`` is not modified. The result has no outline and no
    ``pixels_per_mm`` field.
    """
    if not isinstance(payload, bytes | bytearray):
        raise TypeError("The lossless TIFF decoder takes TIFF bytes.")
    data = bytes(payload) if isinstance(payload, bytearray) else payload
    try:
        return _decode(data)
    except _Rejected as rejected:
        return TiffDecodeFailure(kind=rejected.kind)


def _decode(data: bytes) -> DecodedRaster:
    endian = _endian(data)
    first = struct.unpack_from(endian + "I", data, 4)[0]
    ifd = _select_ifd(data, endian, first)
    geometry = _geometry(data, endian, ifd)
    samples, stored_bits = _stored_samples(data, ifd, geometry)
    gray = _grayscale(samples, geometry, stored_bits)
    return DecodedRaster(
        width=geometry.width,
        height=geometry.height,
        samples=gray,
        decoder_name=DECODER_NAME,
        decoder_version=DECODER_VERSION,
    )


def _endian(data: bytes) -> Literal["<", ">"]:
    if len(data) < 8:
        if data[:2] in {b"II", b"MM"}:
            _reject("inconsistent")
        _reject("not_tiff")
    if data[:2] == b"II":
        endian: Literal["<", ">"] = "<"
    elif data[:2] == b"MM":
        endian = ">"
    else:
        _reject("not_tiff")
    version = struct.unpack_from(endian + "H", data, 2)[0]
    if version == 43:
        _reject("bigtiff")
    if version != 42:
        _reject("not_tiff")
    return endian


def _select_ifd(data: bytes, endian: str, offset: int) -> _Ifd:
    seen: set[int] = set()
    for _ in range(64):
        if offset == 0 or offset in seen or offset > len(data) - 2:
            _reject("inconsistent")
        seen.add(offset)
        parsed = _parse_ifd(data, endian, offset)
        if _full_resolution(data, endian, parsed):
            return parsed
        offset = parsed.next_offset
    _reject("inconsistent")


def _parse_ifd(data: bytes, endian: str, offset: int) -> _Ifd:
    count = struct.unpack_from(endian + "H", data, offset)[0]
    end = offset + 2 + count * 12 + 4
    if count > _MAX_TAGS or end > len(data):
        _reject("inconsistent")
    fields: dict[int, _Field] = {}
    for index in range(count):
        start = offset + 2 + index * 12
        tag = struct.unpack_from(endian + "H", data, start)[0]
        if tag in fields:
            _reject("inconsistent")
        type_code = struct.unpack_from(endian + "H", data, start + 2)[0]
        value_count = struct.unpack_from(endian + "I", data, start + 4)[0]
        fields[tag] = _Field(type_code, value_count, data[start + 8 : start + 12])
    next_offset = struct.unpack_from(endian + "I", data, end - 4)[0]
    return _Ifd(fields, next_offset)


def _full_resolution(data: bytes, endian: str, ifd: _Ifd) -> bool:
    new_subfile = _maybe_one(data, endian, ifd, 254)
    if new_subfile is not None:
        reduced = (new_subfile & 1) != 0
        mask = (new_subfile & 4) != 0
        return not reduced and not mask
    old_subfile = _maybe_one(data, endian, ifd, 255)
    return old_subfile != 2


def _geometry(data: bytes, endian: str, ifd: _Ifd) -> _Geometry:
    width = _required_one(data, endian, ifd, 256)
    height = _required_one(data, endian, ifd, 257)
    if width < 1 or height < 1:
        _reject("inconsistent")
    if width > _MAX_EDGE or height > _MAX_EDGE or width * height > _MAX_PIXELS:
        _reject("oversized")
    spp = _optional_one(data, endian, ifd, 277, 1)
    if spp < 1 or spp > _MAX_SAMPLES:
        _reject("inconsistent")
    bits = _bits_per_sample(data, endian, ifd, spp)
    photometric = _required_one(data, endian, ifd, 262)
    if photometric not in _COLOR_SAMPLES:
        _reject("unsupported_photometric")
    if photometric == 2 and bits == 1:
        _reject("unsupported_bits")
    if photometric == 3 and bits == 16:
        _reject("unsupported_bits")
    color_count = _COLOR_SAMPLES[photometric]
    if spp < color_count:
        _reject("inconsistent")
    _check_extra_samples(data, endian, ifd, spp - color_count)
    _check_sample_format(data, endian, ifd, spp)
    _check_fill_order(data, endian, ifd)
    compression = _optional_one(data, endian, ifd, 259, 1)
    if compression in {6, 7}:
        _reject("jpeg_compression")
    if compression not in _SUPPORTED_COMPRESSION:
        _reject("unsupported_compression")
    if compression == 32771:
        compression = 1
    predictor = _optional_one(data, endian, ifd, 317, 1)
    if predictor not in {1, 2}:
        _reject("inconsistent")
    if predictor == 2 and bits not in {8, 16}:
        _reject("inconsistent")
    planar = _optional_one(data, endian, ifd, 284, 1)
    if planar not in {1, 2}:
        _reject("inconsistent")
    colormap = None
    if photometric == 3:
        colormap = _numbers(data, endian, _required_field(ifd, 320))
        if len(colormap) != 3 * (1 << bits):
            _reject("inconsistent")
    return _Geometry(
        width=width,
        height=height,
        spp=spp,
        bits=bits,
        compression=compression,
        predictor=predictor,
        planar=planar,
        photometric=photometric,
        endian=endian,
        colormap=colormap,
    )


def _bits_per_sample(data: bytes, endian: str, ifd: _Ifd, spp: int) -> int:
    field = ifd.fields.get(258)
    values = (1,) if field is None else _numbers(data, endian, field)
    uniform = len(values) == spp and all(item == values[0] for item in values)
    if len(values) == 1 or uniform:
        bits = values[0]
    else:
        _reject("inconsistent")
    if bits not in {1, 8, 16}:
        _reject("unsupported_bits")
    return bits


def _check_extra_samples(data: bytes, endian: str, ifd: _Ifd, extra: int) -> None:
    field = ifd.fields.get(338)
    if field is None:
        return
    if len(_numbers(data, endian, field)) != extra:
        _reject("inconsistent")


def _check_sample_format(data: bytes, endian: str, ifd: _Ifd, spp: int) -> None:
    field = ifd.fields.get(339)
    if field is None:
        return
    formats = _numbers(data, endian, field)
    if len(formats) not in {1, spp} or any(item != 1 for item in formats):
        _reject("unsupported_bits")


def _check_fill_order(data: bytes, endian: str, ifd: _Ifd) -> None:
    fill = _maybe_one(data, endian, ifd, 266)
    if fill not in {None, 1}:
        _reject("inconsistent")


def _stored_samples(data: bytes, ifd: _Ifd, geometry: _Geometry) -> tuple[bytes, int]:
    tile_width = _maybe_one(data, geometry.endian, ifd, 322)
    tile_length = _maybe_one(data, geometry.endian, ifd, 323)
    if tile_width is not None or tile_length is not None:
        if tile_width is None or tile_length is None:
            _reject("inconsistent")
        stored = _decode_tiles(data, ifd, geometry, tile_width, tile_length)
    else:
        stored = _decode_strips(data, ifd, geometry)
    stored_bits = 1 if geometry.bits == 1 else 8
    return stored, stored_bits


def _decode_strips(data: bytes, ifd: _Ifd, geometry: _Geometry) -> bytes:
    rows_per_strip = _optional_one(data, geometry.endian, ifd, 278, geometry.height)
    if rows_per_strip < 1:
        _reject("inconsistent")
    strip_count = (geometry.height + rows_per_strip - 1) // rows_per_strip
    separate = geometry.planar == 2 and geometry.spp > 1
    planes = geometry.spp if separate else 1
    offsets = _required_numbers(data, geometry.endian, ifd, 273)
    counts = _byte_counts(
        data, ifd, geometry, 279, strip_count * planes, rows_per_strip
    )
    if len(offsets) != strip_count * planes or len(counts) != strip_count * planes:
        _reject("inconsistent")
    if separate:
        return _planar_strips(
            data, geometry, offsets, counts, rows_per_strip, strip_count
        )
    return _chunky_strips(data, geometry, offsets, counts, rows_per_strip, strip_count)


def _chunky_strips(
    data: bytes,
    geometry: _Geometry,
    offsets: tuple[int, ...],
    counts: tuple[int, ...],
    rows_per_strip: int,
    strip_count: int,
) -> bytes:
    dest = bytearray(geometry.width * geometry.height * geometry.spp)
    for index in range(strip_count):
        start = index * rows_per_strip
        rows = min(rows_per_strip, geometry.height - start)
        tile = _expand_block(
            _compressed_bytes(data, offsets[index], counts[index]),
            geometry,
            geometry.width,
            rows,
            geometry.spp,
        )
        _place(
            dest,
            geometry.width,
            0,
            start,
            tile,
            geometry.width,
            geometry.width,
            rows,
            geometry.spp,
        )
    return bytes(dest)


def _planar_strips(
    data: bytes,
    geometry: _Geometry,
    offsets: tuple[int, ...],
    counts: tuple[int, ...],
    rows_per_strip: int,
    strip_count: int,
) -> bytes:
    planes = [bytearray(geometry.width * geometry.height) for _ in range(geometry.spp)]
    for plane in range(geometry.spp):
        for index in range(strip_count):
            start = index * rows_per_strip
            rows = min(rows_per_strip, geometry.height - start)
            slot = plane * strip_count + index
            tile = _expand_block(
                _compressed_bytes(data, offsets[slot], counts[slot]),
                geometry,
                geometry.width,
                rows,
                1,
            )
            _place(
                planes[plane],
                geometry.width,
                0,
                start,
                tile,
                geometry.width,
                geometry.width,
                rows,
                1,
            )
    return _interleave(planes, geometry.width, geometry.height)


def _decode_tiles(
    data: bytes,
    ifd: _Ifd,
    geometry: _Geometry,
    tile_width: int,
    tile_length: int,
) -> bytes:
    if tile_width < 1 or tile_length < 1:
        _reject("inconsistent")
    if (
        tile_width > _MAX_EDGE
        or tile_length > _MAX_EDGE
        or tile_width * tile_length > _MAX_PIXELS
    ):
        _reject("oversized")
    across = (geometry.width + tile_width - 1) // tile_width
    down = (geometry.height + tile_length - 1) // tile_length
    separate = geometry.planar == 2 and geometry.spp > 1
    planes = geometry.spp if separate else 1
    tile_count = across * down * planes
    offsets = _required_numbers(data, geometry.endian, ifd, 324)
    counts = _required_numbers(data, geometry.endian, ifd, 325)
    if len(offsets) != tile_count or len(counts) != tile_count:
        _reject("inconsistent")
    if separate:
        return _planar_tiles(
            data, geometry, offsets, counts, tile_width, tile_length, across, down
        )
    return _chunky_tiles(
        data, geometry, offsets, counts, tile_width, tile_length, across, down
    )


def _chunky_tiles(
    data: bytes,
    geometry: _Geometry,
    offsets: tuple[int, ...],
    counts: tuple[int, ...],
    tile_width: int,
    tile_length: int,
    across: int,
    down: int,
) -> bytes:
    dest = bytearray(geometry.width * geometry.height * geometry.spp)
    for tile_y in range(down):
        for tile_x in range(across):
            slot = tile_y * across + tile_x
            tile = _expand_block(
                _compressed_bytes(data, offsets[slot], counts[slot]),
                geometry,
                tile_width,
                tile_length,
                geometry.spp,
            )
            origin_x = tile_x * tile_width
            origin_y = tile_y * tile_length
            _place(
                dest,
                geometry.width,
                origin_x,
                origin_y,
                tile,
                tile_width,
                min(tile_width, geometry.width - origin_x),
                min(tile_length, geometry.height - origin_y),
                geometry.spp,
            )
    return bytes(dest)


def _planar_tiles(
    data: bytes,
    geometry: _Geometry,
    offsets: tuple[int, ...],
    counts: tuple[int, ...],
    tile_width: int,
    tile_length: int,
    across: int,
    down: int,
) -> bytes:
    per_plane = across * down
    planes = [bytearray(geometry.width * geometry.height) for _ in range(geometry.spp)]
    for plane in range(geometry.spp):
        for tile_y in range(down):
            for tile_x in range(across):
                slot = plane * per_plane + tile_y * across + tile_x
                tile = _expand_block(
                    _compressed_bytes(data, offsets[slot], counts[slot]),
                    geometry,
                    tile_width,
                    tile_length,
                    1,
                )
                origin_x = tile_x * tile_width
                origin_y = tile_y * tile_length
                _place(
                    planes[plane],
                    geometry.width,
                    origin_x,
                    origin_y,
                    tile,
                    tile_width,
                    min(tile_width, geometry.width - origin_x),
                    min(tile_length, geometry.height - origin_y),
                    1,
                )
    return _interleave(planes, geometry.width, geometry.height)


def _byte_counts(
    data: bytes,
    ifd: _Ifd,
    geometry: _Geometry,
    tag: int,
    blocks: int,
    rows_per_strip: int,
) -> tuple[int, ...]:
    field = ifd.fields.get(tag)
    if field is not None:
        return _numbers(data, geometry.endian, field)
    if geometry.compression != 1:
        _reject("inconsistent")
    separate = geometry.planar == 2 and geometry.spp > 1
    spp = 1 if separate else geometry.spp
    counts: list[int] = []
    for index in range(blocks):
        if separate:
            per_plane = (geometry.height + rows_per_strip - 1) // rows_per_strip
            strip_index = index % per_plane
        else:
            strip_index = index
        start = strip_index * rows_per_strip
        rows = min(rows_per_strip, geometry.height - start)
        counts.append(_raw_len(geometry.width, rows, spp, geometry.bits))
    return tuple(counts)


def _compressed_bytes(data: bytes, offset: int, count: int) -> bytes:
    if count < 0 or offset < 0 or count > len(data) or offset > len(data) - count:
        _reject("inconsistent")
    return data[offset : offset + count]


def _expand_block(
    blob: bytes,
    geometry: _Geometry,
    width: int,
    rows: int,
    spp: int,
) -> bytes:
    expected = _raw_len(width, rows, spp, geometry.bits)
    raw = _decompress(blob, geometry.compression, expected)
    return _to_stored_samples(raw, width, rows, spp, geometry)


def _raw_len(width: int, rows: int, spp: int, bits: int) -> int:
    if bits == 1:
        return rows * ((width * spp + 7) // 8)
    if bits == 8:
        return rows * width * spp
    if bits == 16:
        return rows * width * spp * 2
    _reject("unsupported_bits")


def _decompress(blob: bytes, compression: int, expected: int) -> bytes:
    if compression == 1:
        if len(blob) != expected:
            _reject("inconsistent")
        return blob
    if compression == 32773:
        return _packbits(blob, expected)
    if compression in {8, 32946}:
        return _inflate(blob, expected)
    if compression == 5:
        return _lzw(blob, expected)
    _reject("unsupported_compression")


def _packbits(blob: bytes, expected: int) -> bytes:
    out = bytearray()
    index = 0
    limit = len(blob)
    while len(out) < expected:
        if index >= limit:
            _reject("inconsistent")
        control = blob[index]
        index += 1
        if control >= 128:
            control -= 256
        if control == -128:
            continue
        if control >= 0:
            count = control + 1
            if index + count > limit:
                _reject("inconsistent")
            out += blob[index : index + count]
            index += count
        else:
            if index >= limit:
                _reject("inconsistent")
            out += bytes((blob[index],)) * (1 - control)
            index += 1
        if len(out) > expected:
            _reject("inconsistent")
    return bytes(out)


def _inflate(blob: bytes, expected: int) -> bytes:
    decoder = zlib.decompressobj()
    try:
        decoded = decoder.decompress(blob, expected + 1)
        if not decoder.eof:
            decoded += decoder.decompress(decoder.unconsumed_tail, 1)
    except zlib.error as exc:
        raise _Rejected("inconsistent") from exc
    if len(decoded) != expected or not decoder.eof:
        _reject("inconsistent")
    return decoded


class _Bits:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0
        self._acc = 0
        self._have = 0

    def read(self, width: int) -> int:
        while self._have < width:
            if self._pos >= len(self._data):
                _reject("inconsistent")
            self._acc = (self._acc << 8) | self._data[self._pos]
            self._pos += 1
            self._have += 8
        self._have -= width
        code = (self._acc >> self._have) & ((1 << width) - 1)
        if self._have:
            self._acc &= (1 << self._have) - 1
        else:
            self._acc = 0
        return code


def _lzw(blob: bytes, expected: int) -> bytes:
    """Decode TIFF LZW.

    Code width grows after codes 510, 1022, and 2046 are stored. That is
    the libtiff schedule: the next read uses the wider code. This is not
    GIF LZW.
    """
    bits = _Bits(blob)
    table = _lzw_table()
    width = 9
    next_code = 258
    out = bytearray()
    previous: bytes | None = None
    while True:
        code = bits.read(width)
        if code == 256:
            table = _lzw_table()
            width = 9
            next_code = 258
            previous = None
            continue
        if code == 257:
            break
        if code < 256:
            entry = table[code]
        elif code == next_code and previous is not None:
            entry = previous + previous[:1]
        elif 258 <= code < next_code:
            entry = table[code]
        else:
            _reject("inconsistent")
        if len(out) + len(entry) > expected:
            _reject("inconsistent")
        out += entry
        if previous is not None and next_code < _LZW_MAX_CODE:
            table.append(previous + entry[:1])
            next_code += 1
            if next_code == 511:
                width = 10
            elif next_code == 1023:
                width = 11
            elif next_code == 2047:
                width = 12
        previous = entry
    if len(out) != expected:
        _reject("inconsistent")
    return bytes(out)


def _lzw_table() -> list[bytes]:
    table = [bytes((index,)) for index in range(256)]
    table.append(b"")
    table.append(b"")
    return table


def _to_stored_samples(
    raw: bytes,
    width: int,
    rows: int,
    spp: int,
    geometry: _Geometry,
) -> bytes:
    if geometry.bits == 1:
        return _unpack_1(raw, width, rows, spp)
    if geometry.bits == 8:
        expected = rows * width * spp
        if len(raw) != expected:
            _reject("inconsistent")
        buf = bytearray(raw)
        if geometry.predictor == 2:
            _undo8(buf, width * spp, rows, spp)
        return bytes(buf)
    expected = rows * width * spp * 2
    if len(raw) != expected:
        _reject("inconsistent")
    buf = bytearray(raw)
    if geometry.predictor == 2:
        _undo16(buf, width * spp, rows, spp, geometry.endian)
    return _high_bytes(buf, geometry.endian)


def _unpack_1(raw: bytes, width: int, rows: int, spp: int) -> bytes:
    row_bytes = (width * spp + 7) // 8
    if len(raw) != rows * row_bytes:
        _reject("inconsistent")
    out = bytearray(rows * width * spp)
    cursor = 0
    for row in range(rows):
        base = row * row_bytes
        for sample_index in range(width * spp):
            byte = raw[base + (sample_index >> 3)]
            out[cursor] = (byte >> (7 - (sample_index & 7))) & 1
            cursor += 1
    return bytes(out)


def _undo8(buf: bytearray, row_samples: int, rows: int, stride: int) -> None:
    for row in range(rows):
        start = row * row_samples
        for index in range(stride, row_samples):
            pos = start + index
            buf[pos] = (buf[pos] + buf[pos - stride]) & 0xFF


def _undo16(
    buf: bytearray, row_samples: int, rows: int, stride: int, endian: str
) -> None:
    little = endian == "<"
    row_bytes = row_samples * 2
    for row in range(rows):
        base = row * row_bytes
        for index in range(stride, row_samples):
            pos = base + index * 2
            prev = pos - stride * 2
            if little:
                value = buf[pos] | (buf[pos + 1] << 8)
                prior = buf[prev] | (buf[prev + 1] << 8)
                value = (value + prior) & 0xFFFF
                buf[pos] = value & 0xFF
                buf[pos + 1] = value >> 8
            else:
                value = (buf[pos] << 8) | buf[pos + 1]
                prior = (buf[prev] << 8) | buf[prev + 1]
                value = (value + prior) & 0xFFFF
                buf[pos] = value >> 8
                buf[pos + 1] = value & 0xFF


def _high_bytes(raw: bytearray, endian: str) -> bytes:
    count = len(raw) // 2
    out = bytearray(count)
    shift = 1 if endian == "<" else 0
    for index in range(count):
        out[index] = raw[index * 2 + shift]
    return bytes(out)


def _place(
    dest: bytearray,
    dest_width: int,
    origin_x: int,
    origin_y: int,
    tile: bytes,
    tile_width: int,
    copy_width: int,
    copy_height: int,
    spp: int,
) -> None:
    for row in range(copy_height):
        src = (row * tile_width) * spp
        dst = ((origin_y + row) * dest_width + origin_x) * spp
        count = copy_width * spp
        dest[dst : dst + count] = tile[src : src + count]


def _interleave(planes: list[bytearray], width: int, height: int) -> bytes:
    if len(planes) == 1:
        return bytes(planes[0])
    count = width * height
    spp = len(planes)
    out = bytearray(count * spp)
    for sample in range(spp):
        plane = planes[sample]
        if len(plane) != count:
            _reject("inconsistent")
        for index, value in enumerate(plane):
            out[index * spp + sample] = value
    return bytes(out)


def _grayscale(samples: bytes, geometry: _Geometry, stored_bits: int) -> bytes:
    count = geometry.width * geometry.height
    if geometry.photometric in {0, 1}:
        channel = _channel(samples, count, geometry.spp, 0)
        return _scale_gray(channel, stored_bits, geometry.photometric == 0)
    if geometry.photometric == 2:
        return _rgb_luma(samples, count, geometry.spp)
    if geometry.photometric == 3:
        if geometry.colormap is None:
            _reject("inconsistent")
        return _palette_luma(
            _channel(samples, count, geometry.spp, 0),
            geometry.colormap,
            geometry.bits,
        )
    _reject("unsupported_photometric")


def _channel(samples: bytes, count: int, spp: int, which: int) -> bytes:
    if spp == 1:
        return samples
    return bytes(samples[index * spp + which] for index in range(count))


def _scale_gray(channel: bytes, stored_bits: int, white_is_zero: bool) -> bytes:
    if stored_bits == 1:
        if white_is_zero:
            return bytes(0 if sample else 255 for sample in channel)
        return bytes(255 if sample else 0 for sample in channel)
    if white_is_zero:
        return bytes(255 - sample for sample in channel)
    return channel


def _rgb_luma(samples: bytes, count: int, spp: int) -> bytes:
    out = bytearray(count)
    for index in range(count):
        base = index * spp
        out[index] = _luma(samples[base], samples[base + 1], samples[base + 2])
    return bytes(out)


def _palette_luma(indexes: bytes, colormap: tuple[int, ...], bits: int) -> bytes:
    entries = 1 << bits
    out = bytearray(len(indexes))
    for position, index in enumerate(indexes):
        if index >= entries:
            _reject("inconsistent")
        red = colormap[index] >> 8
        green = colormap[entries + index] >> 8
        blue = colormap[2 * entries + index] >> 8
        out[position] = _luma(red, green, blue)
    return bytes(out)


def _luma(red: int, green: int, blue: int) -> int:
    weighted = _LUMA_RED * red + _LUMA_GREEN * green + _LUMA_BLUE * blue
    return (weighted + _LUMA_BIAS) >> 16


def _required_field(ifd: _Ifd, tag: int) -> _Field:
    field = ifd.fields.get(tag)
    if field is None:
        _reject("inconsistent")
    return field


def _required_numbers(data: bytes, endian: str, ifd: _Ifd, tag: int) -> tuple[int, ...]:
    return _numbers(data, endian, _required_field(ifd, tag))


def _required_one(data: bytes, endian: str, ifd: _Ifd, tag: int) -> int:
    values = _required_numbers(data, endian, ifd, tag)
    if len(values) != 1:
        _reject("inconsistent")
    return values[0]


def _optional_one(data: bytes, endian: str, ifd: _Ifd, tag: int, default: int) -> int:
    found = _maybe_one(data, endian, ifd, tag)
    if found is None:
        return default
    return found


def _maybe_one(data: bytes, endian: str, ifd: _Ifd, tag: int) -> int | None:
    field = ifd.fields.get(tag)
    if field is None:
        return None
    values = _numbers(data, endian, field)
    if len(values) != 1:
        _reject("inconsistent")
    return values[0]


def _numbers(data: bytes, endian: str, field: _Field) -> tuple[int, ...]:
    spec = _NUMERIC.get(field.type_code)
    if spec is None or field.count < 0 or field.count > _MAX_VALUES:
        _reject("inconsistent")
    size, code = spec
    total = size * field.count
    if total <= 4:
        blob = field.inline[:total]
    else:
        offset = struct.unpack(endian + "I", field.inline)[0]
        if total > len(data) or offset > len(data) - total:
            _reject("inconsistent")
        blob = data[offset : offset + total]
    if len(blob) != total:
        _reject("inconsistent")
    if field.count == 0:
        return ()
    unpacked = struct.unpack(endian + (code * field.count), blob)
    return tuple(int(item) for item in unpacked)


@dataclass(frozen=True, slots=True)
class DecodedRaster:
    """Width, height, and row-major 8-bit BlackIsZero samples.

    ``decoder_name`` and ``decoder_version`` are ``lossless_tiff`` and
    ``1``. There is no ``pixels_per_mm`` field.
    """

    width: int
    height: int
    samples: bytes
    decoder_name: str
    decoder_version: str

    def __post_init__(self) -> None:
        if self.decoder_name != DECODER_NAME or self.decoder_version != DECODER_VERSION:
            raise ValueError("The decoder is lossless_tiff version 1.")
        if self.width < 1 or self.height < 1:
            raise ValueError("A decoded image has a positive width and height.")
        if len(self.samples) != self.width * self.height:
            raise ValueError("Grayscale samples are one byte per pixel.")


@dataclass(frozen=True, slots=True)
class TiffDecodeFailure:
    """A TIFF that this decoder will not turn into samples.

    Not an outline, not a hypothesis, and not an epistemic class. No polygon
    is produced. The presented bytes are not modified.
    """

    kind: TiffDecodeFailureKind

    def __post_init__(self) -> None:
        if self.kind not in {
            "not_tiff",
            "bigtiff",
            "jpeg_compression",
            "unsupported_compression",
            "unsupported_photometric",
            "unsupported_bits",
            "oversized",
            "inconsistent",
        }:
            raise ValueError(
                "A TIFF decode failure is not_tiff, bigtiff, jpeg_compression, "
                "unsupported_compression, unsupported_photometric, "
                "unsupported_bits, oversized, or inconsistent."
            )
