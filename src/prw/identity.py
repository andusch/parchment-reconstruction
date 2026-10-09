"""Canonical JSON, ``sha256:`` digests, and content-derived UUIDv5 identifiers.

The id rules are the introduction of ``docs/DATA_MODEL.md``. Canonical JSON is
UTF-8, with sorted object keys and no insignificant whitespace. An omitted
field is absent from that JSON. It is not stored as null. A hash value is
``sha256:`` plus lowercase hexadecimal, or the token ``absent`` where a hash
does not apply. An empty string is not a hash value. A content-derived id is
a UUIDv5 as in RFC 4122, in the URL namespace
``6ba7b811-9dad-11d1-80b4-00c04fd430c8``. The name is canonical JSON of the
inputs that document names for the id. Timestamps are metadata and are never
an input to an id.

Ruling R7 in ``docs/reviewed_resolutions/R0-01.md`` requires the full
parameter blob in that canonical JSON, plus its SHA-256. Ruling R9 requires
content-derived hypothesis ids so a repeated run reproduces the same id.

These helpers are internal. They are not a stable public API.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

ABSENT = "absent"
URL_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")

_SHA256_VALUE = re.compile(r"sha256:[0-9a-f]{64}\Z")


def canonical_json(value: object) -> str:
    """Return canonical JSON text for ``value``.

    Object keys are sorted. Encoding is UTF-8 with no insignificant
    whitespace. A mapping entry whose value is ``None`` is omitted.
    """
    return canonical_json_bytes(value).decode("utf-8")


def canonical_json_bytes(value: object) -> bytes:
    """Return the UTF-8 bytes of :func:`canonical_json`."""
    text = json.dumps(
        _json_ready(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return text.encode("utf-8")


def hash_value(data: bytes | None) -> str:
    """Return a ``sha256:`` digest, or ``absent`` when no hash applies.

    ``data is None`` means the hash does not apply. Empty bytes still have
    a digest. The result is never an empty string.
    """
    if data is None:
        return ABSENT
    return "sha256:" + hashlib.sha256(data).hexdigest()


def require_hash(value: str) -> str:
    """Return ``value`` when it is ``absent`` or a lowercase ``sha256:`` digest.

    Raises:
        ValueError: ``value`` is empty or is not one of those two forms.
    """
    if value == ABSENT or _SHA256_VALUE.fullmatch(value):
        return value
    if value == "":
        raise ValueError("An empty string is not a hash value.")
    raise ValueError(
        "A hash value is 'sha256:' plus lowercase hexadecimal, or 'absent'."
    )


def content_id(inputs: Mapping[str, Any] | Sequence[Any]) -> uuid.UUID:
    """Return the UUIDv5 of the canonical JSON name for ``inputs``.

    A mapping is canonical content: the root ``id`` and every timestamp
    field are excluded, then serialized. A sequence is an ordered list of
    inputs and keeps that order. Timestamp fields inside objects are
    excluded in both forms. The same content returns the same id.
    """
    if isinstance(inputs, str | bytes | bytearray):
        raise TypeError("A content-derived id name is a JSON array or object.")
    if isinstance(inputs, Mapping):
        prepared = _without_id_inputs(inputs, drop_root_id=True)
    elif isinstance(inputs, Sequence):
        prepared = _without_id_inputs(inputs, drop_root_id=False)
    else:
        raise TypeError("A content-derived id name is a JSON array or object.")
    name = canonical_json(prepared)
    return uuid.uuid5(URL_NAMESPACE, name)


def _json_ready(value: object) -> Any:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Canonical JSON rejects non-finite numbers.")
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Mapping):
        ready: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"Object keys must be strings, got {type(key).__name__}."
                )
            if item is None:
                continue
            ready[key] = _json_ready(item)
        return ready
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return [_json_ready(item) for item in value]
    if value is None:
        raise ValueError("An omitted field is absent. It is not stored as null.")
    raise TypeError(f"Cannot encode {type(value).__name__} as canonical JSON.")


def _is_timestamp_field(key: str) -> bool:
    return key == "timestamp" or key.endswith("_at")


def _without_id_inputs(value: object, *, drop_root_id: bool) -> Any:
    if isinstance(value, Mapping):
        kept: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"Object keys must be strings, got {type(key).__name__}."
                )
            if (drop_root_id and key == "id") or _is_timestamp_field(key):
                continue
            kept[key] = _without_id_inputs(item, drop_root_id=False)
        return kept
    if isinstance(value, str | bytes | bytearray):
        return value
    if isinstance(value, Sequence):
        return [_without_id_inputs(item, drop_root_id=False) for item in value]
    return value
