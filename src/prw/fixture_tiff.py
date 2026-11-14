"""Read samples from the synthetic uncompressed TIFF layout only.

The layout is the one written in ``src/prw/synthetic_tear.py``: magic
``II*\\x00``, first IFD at offset 8, nine entries in tag order, a zero
next-IFD offset, then one 8-bit grayscale sample per pixel. ``ImageWidth``
is the little-endian long at ``TIFF_WIDTH_OFFSET`` and ``ImageLength`` is
the little-endian long at ``TIFF_HEIGHT_OFFSET``. Compression tag 259 is 1
and photometric tag 262 is 1 (BlackIsZero).

``DECODER_NAME`` is ``synthetic_uncompressed_tiff`` and ``DECODER_VERSION``
is ``1``. This module defines those strings, ``TIFF_MAGIC``, and the width
and height offsets. The writer imports them.

This reader is the synthetic layout only. Arbitrary lossless masters are
``prw.lossless_tiff``, under ``docs/adr/0014-stdlib-lossless-tiff.md``.
Tags 282 and 283 are not read. A header resolution does not become
``pixels_per_mm``. A layout failure is a protocol result with no outline,
no hypothesis, and no epistemic class. Pixel commands try the lossless
decoder after this failure and do not surface it.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Literal

DECODER_NAME = "synthetic_uncompressed_tiff"
DECODER_VERSION = "1"
TIFF_MAGIC = b"II*\x00"
TIFF_WIDTH_OFFSET = 18
TIFF_HEIGHT_OFFSET = 30

LayoutFailureKind = Literal[
    "different_ifd",
    "compressed_strip",
    "not_grayscale",
    "other_layout",
]

_IFD_OFFSET = 8
_ENTRY_COUNT = 9
_ENTRY_LENGTH = 12
_HEADER_LENGTH = _IFD_OFFSET + 2 + _ENTRY_COUNT * _ENTRY_LENGTH + 4
_TYPE_SHORT = 3
_TYPE_LONG = 4
_UNCOMPRESSED = 1
_BLACK_IS_ZERO = 1
_GRAYSCALE_PHOTOMETRIC = frozenset({0, _BLACK_IS_ZERO})
_ENTRIES: tuple[tuple[int, int, int], ...] = (
    (256, _TYPE_LONG, 1),
    (257, _TYPE_LONG, 1),
    (258, _TYPE_SHORT, 1),
    (259, _TYPE_SHORT, 1),
    (262, _TYPE_SHORT, 1),
    (273, _TYPE_LONG, 1),
    (277, _TYPE_SHORT, 1),
    (278, _TYPE_LONG, 1),
    (279, _TYPE_LONG, 1),
)


def _value_offset(index: int) -> int:
    return _IFD_OFFSET + 2 + index * _ENTRY_LENGTH + 8


def write_fixture_tiff(width: int, height: int, samples: bytes) -> bytes:
    """Return one uncompressed 8-bit grayscale TIFF in this reader's layout.

    The layout is the synthetic fixture writer: magic, one IFD, photometric
    BlackIsZero, and no compression. This is not a writer for arbitrary scans.
    """
    if isinstance(width, bool) or not isinstance(width, int) or width < 1:
        raise ValueError("A fixture image has a positive width and height.")
    if isinstance(height, bool) or not isinstance(height, int) or height < 1:
        raise ValueError("A fixture image has a positive width and height.")
    if not isinstance(samples, bytes) or len(samples) != width * height:
        raise ValueError("Uncompressed grayscale samples are one byte per pixel.")
    entries = b"".join(
        (
            _tiff_long(256, width),
            _tiff_long(257, height),
            _tiff_short(258, 8),
            _tiff_short(259, _UNCOMPRESSED),
            _tiff_short(262, _BLACK_IS_ZERO),
            _tiff_long(273, _HEADER_LENGTH),
            _tiff_short(277, 1),
            _tiff_long(278, height),
            _tiff_long(279, width * height),
        )
    )
    ifd = struct.pack("<H", _ENTRY_COUNT) + entries + struct.pack("<I", 0)
    payload = TIFF_MAGIC + struct.pack("<I", _IFD_OFFSET) + ifd + samples
    stored_width = _long_at(payload, TIFF_WIDTH_OFFSET)
    stored_height = _long_at(payload, TIFF_HEIGHT_OFFSET)
    if (stored_width, stored_height) != (width, height):
        raise ValueError(
            "The TIFF width and height were not stored at the documented offsets."
        )
    return payload


def _tiff_long(tag: int, value: int) -> bytes:
    return struct.pack("<HHII", tag, 4, 1, value)


def _tiff_short(tag: int, value: int) -> bytes:
    return struct.pack("<HHIHH", tag, 3, 1, value, 0)


def read_fixture_tiff(
    payload: bytes | bytearray,
) -> FixtureSamples | UnsupportedFixtureLayout:
    """Return width, height, and samples, or a layout failure.

    The decoder name and version are the writer's ``synthetic_uncompressed_tiff``
    and ``1``. The result has no outline.
    """
    if not isinstance(payload, bytes | bytearray):
        raise TypeError("The fixture reader takes TIFF bytes.")
    data = bytes(payload)
    kind = _layout_kind(data)
    if kind is not None:
        return UnsupportedFixtureLayout(kind=kind)
    width = _long_at(data, TIFF_WIDTH_OFFSET)
    height = _long_at(data, TIFF_HEIGHT_OFFSET)
    return FixtureSamples(
        width=width,
        height=height,
        samples=data[_HEADER_LENGTH:],
        decoder_name=DECODER_NAME,
        decoder_version=DECODER_VERSION,
    )


def _layout_kind(payload: bytes) -> LayoutFailureKind | None:
    if _value_offset(0) != TIFF_WIDTH_OFFSET or _value_offset(1) != TIFF_HEIGHT_OFFSET:
        raise RuntimeError(
            "The fixture width and height offsets do not match the writer layout."
        )
    if not payload.startswith(TIFF_MAGIC):
        return "other_layout"
    if not _ifd_skeleton_matches(payload):
        return "different_ifd"
    if _short_at(payload, _value_offset(3)) != _UNCOMPRESSED:
        return "compressed_strip"
    photometric = _short_at(payload, _value_offset(4))
    if photometric not in _GRAYSCALE_PHOTOMETRIC:
        return "not_grayscale"
    if not _values_match(payload):
        return "different_ifd"
    return None


def _ifd_skeleton_matches(payload: bytes) -> bool:
    if len(payload) < _HEADER_LENGTH:
        return False
    ifd_offset = _long_at(payload, 4)
    count = struct.unpack_from("<H", payload, _IFD_OFFSET)[0]
    next_ifd = _long_at(payload, _HEADER_LENGTH - 4)
    if ifd_offset != _IFD_OFFSET or count != _ENTRY_COUNT or next_ifd != 0:
        return False
    for index, (tag, kind, count_value) in enumerate(_ENTRIES):
        start = _IFD_OFFSET + 2 + index * _ENTRY_LENGTH
        stored_tag, stored_type, stored_count = struct.unpack_from(
            "<HHI", payload, start
        )
        if (stored_tag, stored_type, stored_count) != (tag, kind, count_value):
            return False
        pad = _short_pad(payload, _value_offset(index))
        if stored_type == _TYPE_SHORT and pad != 0:
            return False
    return True


def _values_match(payload: bytes) -> bool:
    width = _long_at(payload, TIFF_WIDTH_OFFSET)
    height = _long_at(payload, TIFF_HEIGHT_OFFSET)
    remaining = len(payload) - _HEADER_LENGTH
    if width < 1 or height < 1 or width > remaining or height > remaining:
        return False
    sample_count = width * height
    if sample_count != remaining:
        return False
    if _short_at(payload, _value_offset(2)) != 8:
        return False
    if _short_at(payload, _value_offset(4)) != _BLACK_IS_ZERO:
        return False
    if _long_at(payload, _value_offset(5)) != _HEADER_LENGTH:
        return False
    if _short_at(payload, _value_offset(6)) != 1:
        return False
    if _long_at(payload, _value_offset(7)) != height:
        return False
    return _long_at(payload, _value_offset(8)) == sample_count


def _long_at(payload: bytes, offset: int) -> int:
    return int(struct.unpack_from("<I", payload, offset)[0])


def _short_at(payload: bytes, offset: int) -> int:
    return int(struct.unpack_from("<H", payload, offset)[0])


def _short_pad(payload: bytes, offset: int) -> int:
    return int(struct.unpack_from("<H", payload, offset + 2)[0])


@dataclass(frozen=True, slots=True)
class FixtureSamples:
    """Width, height, and row-major grayscale samples from one fixture TIFF.

    ``decoder_name`` and ``decoder_version`` match the writer. There is no
    ``pixels_per_mm`` field.
    """

    width: int
    height: int
    samples: bytes
    decoder_name: str
    decoder_version: str

    def __post_init__(self) -> None:
        if self.decoder_name != DECODER_NAME or self.decoder_version != DECODER_VERSION:
            raise ValueError("The decoder is synthetic_uncompressed_tiff version 1.")
        if self.width < 1 or self.height < 1:
            raise ValueError("A fixture image has a positive width and height.")
        if len(self.samples) != self.width * self.height:
            raise ValueError("Uncompressed grayscale samples are one byte per pixel.")


@dataclass(frozen=True, slots=True)
class UnsupportedFixtureLayout:
    """A byte string that is not the fixture writer's TIFF layout.

    Not an outline, not a hypothesis, and not an epistemic class. No polygon
    is produced.
    """

    kind: LayoutFailureKind

    def __post_init__(self) -> None:
        if self.kind not in {
            "different_ifd",
            "compressed_strip",
            "not_grayscale",
            "other_layout",
        }:
            raise ValueError(
                "A layout failure is a different IFD, a compressed strip, "
                "a non-grayscale photometric tag, or another layout."
            )
