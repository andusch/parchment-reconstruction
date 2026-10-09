"""Synthetic locks for canonical JSON, sha256: digests, and UUIDv5 ids."""

import uuid

import pytest

from prw.identity import (
    ABSENT,
    URL_NAMESPACE,
    canonical_json_bytes,
    content_id,
    hash_value,
    require_hash,
)

_ABC_SHA256 = "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_canonical_json_sorts_keys_and_omits_null_fields() -> None:
    encoded = canonical_json_bytes(
        {"b": 1, "a": "é", "skipped": None, "nested": {"z": None, "m": True}}
    )
    assert encoded == '{"a":"é","b":1,"nested":{"m":true}}'.encode()
    with pytest.raises(ValueError, match="not stored as null"):
        canonical_json_bytes(["keep", None])


def test_hash_value_uses_sha256_prefix_or_absent() -> None:
    assert hash_value(b"abc") == _ABC_SHA256
    assert hash_value(None) == ABSENT
    assert require_hash(_ABC_SHA256) == _ABC_SHA256
    assert require_hash(ABSENT) == ABSENT
    with pytest.raises(ValueError, match="empty string"):
        require_hash("")
    with pytest.raises(ValueError, match="lowercase"):
        require_hash(_ABC_SHA256.upper())


def test_content_id_repeats_for_the_same_content() -> None:
    record = {"label": "leaf", "id": "ignore-me"}
    first = content_id(record)
    second = content_id({"id": "other", "label": "leaf"})
    assert first == second
    assert first.version == 5
    assert first.variant == uuid.RFC_4122
    assert first == uuid.uuid5(URL_NAMESPACE, '{"label":"leaf"}')
    assert uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8") == URL_NAMESPACE
    with_child = content_id({"label": "leaf", "child": {"id": "keep"}})
    assert with_child != content_id({"label": "leaf", "child": {"id": "drop"}})


def test_timestamp_change_does_not_change_an_id_that_excludes_it() -> None:
    earlier = content_id(
        {
            "label": "leaf",
            "started_at": "2020-01-01T00:00:00Z",
            "timestamp": "2020-01-01T00:00:00Z",
        }
    )
    later = content_id(
        {
            "label": "leaf",
            "started_at": "2024-06-01T12:00:00Z",
            "timestamp": "2024-06-01T12:00:00Z",
        }
    )
    assert earlier == later
    assert content_id({"label": "stem"}) != earlier


def test_ordered_inputs_keep_array_order_and_drop_nested_timestamps() -> None:
    name = ["completed", "joins", {"edge": "a", "created_at": "t1"}]
    repeated = content_id(["completed", "joins", {"created_at": "t2", "edge": "a"}])
    assert content_id(name) == repeated
    assert content_id(["joins", "completed", {"edge": "a"}]) != repeated
