"""Synthetic ingest: TIFF magic, a matching hash, and a checksum mismatch."""

import dataclasses
import uuid
from datetime import datetime, timedelta

from prw.identity import URL_NAMESPACE, canonical_json, hash_value
from prw.ingest import (
    TIFF_MEDIA_TYPE,
    IntegrityFailure,
    UnsupportedMediaType,
    VerifiedBytes,
    content_hash_id,
    ingest_bytes,
)

_LITTLE = b"II*\x00synthetic"
_BIG = b"MM\x00*synthetic"
_PNG = b"\x89PNG\r\n\x1a\n"


def _field_names(record: object) -> set[str]:
    return {item.name for item in dataclasses.fields(record)}  # type: ignore[arg-type]


def test_matching_tiff_returns_a_content_hash_record() -> None:
    digest = hash_value(_LITTLE)
    verified = ingest_bytes(_LITTLE, expected_hash=digest)
    repeated = ingest_bytes(_BIG)
    assert isinstance(verified, VerifiedBytes)
    assert isinstance(repeated, VerifiedBytes)
    assert verified.content_hash == digest
    assert verified.byte_length == len(_LITTLE)
    assert verified.media_type == TIFF_MEDIA_TYPE
    assert verified.id == content_hash_id(digest)
    assert verified.id == uuid.uuid5(URL_NAMESPACE, canonical_json(digest))
    assert verified.id.version == 5
    absent = {
        "pixel_width",
        "pixel_height",
        "fragment_id",
        "face",
        "storage_path",
        "claimed_resolution_ppi",
        "epistemic_class",
    }
    assert _field_names(verified).isdisjoint(absent)
    assert repeated.media_type == TIFF_MEDIA_TYPE


def test_checksum_mismatch_is_an_integrity_failure_and_not_a_hypothesis() -> None:
    presented = bytearray(_LITTLE)
    snapshot = bytes(presented)
    expected = hash_value(_BIG)
    failure = ingest_bytes(presented, expected_hash=expected)
    assert bytes(presented) == snapshot
    assert isinstance(failure, IntegrityFailure)
    assert failure.presented_hash == hash_value(snapshot)
    assert failure.expected_hash == expected
    assert failure.source_image_id == content_hash_id(expected)
    assert failure.id.version == 4
    parsed = datetime.fromisoformat(failure.timestamp)
    assert parsed.utcoffset() == timedelta(0)
    names = _field_names(failure)
    assert "epistemic_class" not in names
    assert names.isdisjoint({"hypothesis", "pixel_width", "claimed_resolution_ppi"})


def test_non_tiff_bytes_are_an_unsupported_media_type() -> None:
    rejected = ingest_bytes(_PNG, expected_hash=hash_value(_PNG))
    assert isinstance(rejected, UnsupportedMediaType)
    assert not isinstance(rejected, VerifiedBytes | IntegrityFailure)
    assert rejected.presented_hash == hash_value(_PNG)
    assert rejected.byte_length == len(_PNG)
    assert "epistemic_class" not in _field_names(rejected)
    short = ingest_bytes(b"II*")
    assert isinstance(short, UnsupportedMediaType)
