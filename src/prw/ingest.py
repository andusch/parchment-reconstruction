"""Ingest caller-supplied bytes.

``SourceImage`` and ``IntegrityFailure`` are defined in
``docs/DATA_MODEL.md#sourceimage``. Ingest accepts a lossless TIFF only and
records that media type. Any other media type is rejected. Recognition is
the 4-byte magic ``II*\\x00`` or ``MM\\x00*``. A checksum mismatch is an
``IntegrityFailure``: a protocol event with a random UUID, the presented
hash, the expected hash, and a UTC timestamp. It is not observed evidence,
it is not a hypothesis, and it has no epistemic class. The presented bytes
are not modified.

This module does not parse an IFD, read header PPI, create a calibration,
or write a project directory. Decoder name and version wait until a TIFF
decoder is approved.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from prw.identity import (
    ABSENT,
    URL_NAMESPACE,
    canonical_json,
    hash_value,
    require_hash,
)

TIFF_MEDIA_TYPE: Literal["image/tiff"] = "image/tiff"
_LITTLE_ENDIAN_TIFF = b"II*\x00"
_BIG_ENDIAN_TIFF = b"MM\x00*"


def content_hash_id(content_hash: str) -> uuid.UUID:
    """Return the UUIDv5 of a ``SourceImage`` content hash.

    The id input is that hash alone, as canonical JSON. Byte length and
    media type are stored on a verified record and are not part of the id.
    """
    checked = require_hash(content_hash)
    if checked == ABSENT:
        raise ValueError("A content hash is a sha256: digest.")
    return uuid.uuid5(URL_NAMESPACE, canonical_json(checked))


def ingest_bytes(
    presented: bytes | bytearray,
    *,
    expected_hash: str | None = None,
) -> VerifiedBytes | IntegrityFailure | UnsupportedMediaType:
    """Hash ``presented`` and accept it only when it is a TIFF master.

    When ``expected_hash`` is supplied and differs, the result is an
    ``IntegrityFailure`` and not a hypothesis. A non-TIFF prefix is an
    unsupported media type and not a hypothesis. ``presented`` is left
    unchanged.
    """
    if not isinstance(presented, bytes | bytearray):
        raise TypeError("Ingest reads caller-supplied bytes.")
    payload = bytes(presented)
    presented_hash = hash_value(payload)
    if not _is_tiff(payload):
        return UnsupportedMediaType(
            presented_hash=presented_hash,
            byte_length=len(payload),
        )
    if expected_hash is not None:
        recorded = require_hash(expected_hash)
        if recorded == ABSENT:
            raise ValueError("An expected hash is a sha256: digest.")
        if recorded != presented_hash:
            return IntegrityFailure(
                id=uuid.uuid4(),
                source_image_id=content_hash_id(recorded),
                presented_hash=presented_hash,
                expected_hash=recorded,
                timestamp=_utc_now(),
            )
    return VerifiedBytes(
        id=content_hash_id(presented_hash),
        content_hash=presented_hash,
        byte_length=len(payload),
        media_type=TIFF_MEDIA_TYPE,
    )


def _is_tiff(presented: bytes) -> bool:
    prefix = presented[:4]
    return prefix in (_LITTLE_ENDIAN_TIFF, _BIG_ENDIAN_TIFF)


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_utc(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("A timestamp is UTC ISO-8601.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("A timestamp is UTC ISO-8601.")
    return value


@dataclass(frozen=True, slots=True)
class VerifiedBytes:
    """Hash record for TIFF bytes. This is the start of an observed source.

    Pixel width, pixel height, ``fragment_id``, face, and ``storage_path``
    are absent. Header PPI is not read, and no calibration is created.
    """

    id: uuid.UUID
    content_hash: str
    byte_length: int
    media_type: Literal["image/tiff"]

    def __post_init__(self) -> None:
        if self.media_type != TIFF_MEDIA_TYPE:
            raise ValueError("The media type is the lossless TIFF type image/tiff.")
        if self.byte_length < 0:
            raise ValueError("byte_length is the number of presented bytes.")
        if self.id != content_hash_id(self.content_hash):
            raise ValueError("VerifiedBytes.id does not match its content hash.")


@dataclass(frozen=True, slots=True)
class IntegrityFailure:
    """Protocol event for a checksum mismatch.

    Not observed evidence, not a hypothesis, and not an epistemic class.
    The bytes are not repaired.
    """

    id: uuid.UUID
    source_image_id: uuid.UUID
    presented_hash: str
    expected_hash: str
    timestamp: str

    def __post_init__(self) -> None:
        if self.id.version != 4:
            raise ValueError("An IntegrityFailure id is a random UUID.")
        presented = require_hash(self.presented_hash)
        expected = require_hash(self.expected_hash)
        if presented == ABSENT or expected == ABSENT:
            raise ValueError("A checksum comparison uses sha256: digests.")
        if presented == expected:
            raise ValueError("An IntegrityFailure records hashes that differ.")
        if self.source_image_id != content_hash_id(expected):
            raise ValueError(
                "source_image_id is the recorded source the failure qualifies."
            )
        _require_utc(self.timestamp)


@dataclass(frozen=True, slots=True)
class UnsupportedMediaType:
    """Rejected non-TIFF bytes.

    Not a hypothesis, not observed evidence, and not an ``IntegrityFailure``.
    """

    presented_hash: str
    byte_length: int

    def __post_init__(self) -> None:
        checked = require_hash(self.presented_hash)
        if checked == ABSENT:
            raise ValueError("A presented hash is a sha256: digest.")
        if self.byte_length < 0:
            raise ValueError("byte_length is the number of presented bytes.")
