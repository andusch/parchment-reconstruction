"""Frozen synthetic line images and the slot reader that decodes them.

The images are uncompressed fixture TIFFs. Each column stores one Unicode
scalar as two bytes: the high byte on row 0 and the low byte on row 1.
That encoding is a code, not ink and not a letter shape. It does not
measure Ancient Greek handwriting.

The generator writes those images, an image manifest, and ``kind: line``
BenchmarkLabel rows. The transcription on a label is the frozen reference.
The pixels are the observation. The reader decodes pixels and does not
read the label file. It uses no model, so ``model_hash`` is ``absent``.
It is deterministic, so the envelope omits ``random_seed``.

Ground truth is written only under the caller-supplied benchmarks
directory. This module does not create a project database and does not
write ``originals/`` or ``manifest.json``.
"""

from __future__ import annotations

import json
import unicodedata
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prw.fixture_tiff import (
    DECODER_NAME,
    DECODER_VERSION,
    FixtureSamples,
    read_fixture_tiff,
    write_fixture_tiff,
)
from prw.identity import ABSENT, canonical_json_bytes, content_id, hash_value
from prw.provenance import ProvenanceEnvelope
from prw.synthetic_tear import require_fixture_destination

ALGORITHM_NAME = "synthetic_line_fixture"
ALGORITHM_VERSION = "1"
READER_NAME = "synthetic_line_slots"
READER_VERSION = "1"
ENCODING = "codepoint_bytes"
BYTE_ORDER = "big"
ROWS = 2
_LINE_ROLE = "line"

# Operator tags that exclude a line from the character-error set.
# A line is excluded when ``script`` or ``language`` is one of these.
EXCLUSION_TAGS = ("nomen-sacrum", "abbreviation", "mixed-script")


@dataclass(frozen=True, slots=True)
class SyntheticLineSpec:
    """One frozen line: the label text and the text painted into the image.

    ``reference_text`` is the BenchmarkLabel transcription, stored in
    Unicode NFC. ``painted_text`` is what the pixels encode. The two may
    differ. The difference is a constructed slot difference, not a
    handwriting error.
    """

    image_name: str
    reference_text: str
    painted_text: str
    script: str
    language: str


# The fixture is frozen. Adding a line or changing a transcription changes
# the ground-truth bytes and is a new fixture, not a silent edit.
FROZEN_LINES: tuple[SyntheticLineSpec, ...] = (
    SyntheticLineSpec(
        image_name="line-exact.tif",
        reference_text="\u03bb\u03bf\u03b3\u03bf\u03c2",
        painted_text="\u03bb\u03bf\u03b3\u03bf\u03c2",
        script="Grek",
        language="grc",
    ),
    SyntheticLineSpec(
        image_name="line-accent.tif",
        reference_text="\u03bb\u03cc\u03b3\u03bf\u03c2",
        painted_text="\u03bb\u03bf\u03b3\u03bf\u03c2",
        script="Grek",
        language="grc",
    ),
    SyntheticLineSpec(
        image_name="line-final-sigma.tif",
        reference_text="\u03bb\u03bf\u03b3\u03bf\u03c3",
        painted_text="\u03bb\u03bf\u03b3\u03bf\u03c2",
        script="Grek",
        language="grc",
    ),
    SyntheticLineSpec(
        image_name="line-substitution.tif",
        reference_text="\u03bb\u03bf\u03b3\u03bf\u03c2",
        painted_text="\u03bb\u03bf\u03b3\u03bf\u03be",
        script="Grek",
        language="grc",
    ),
    SyntheticLineSpec(
        image_name="line-as-written.tif",
        reference_text="\u03ba\u03c2",
        painted_text="\u03ba\u03c2",
        script="Grek",
        language="grc",
    ),
    SyntheticLineSpec(
        image_name="line-nomen-sacrum.tif",
        reference_text="\u03ba\u03c2",
        painted_text="\u03ba\u03c5",
        script="nomen-sacrum",
        language="grc",
    ),
    SyntheticLineSpec(
        image_name="line-abbreviation.tif",
        reference_text="\u03ba\u03c2",
        painted_text="\u03ba\u03cd\u03c1\u03b9\u03bf\u03c2",
        script="Grek",
        language="abbreviation",
    ),
    SyntheticLineSpec(
        image_name="line-mixed-script.tif",
        reference_text="ab\u03bb\u03bf\u03b3",
        painted_text="xxxx",
        script="mixed-script",
        language="grc",
    ),
)


@dataclass(frozen=True, slots=True)
class SyntheticLineImage:
    """One line TIFF named in the image manifest."""

    name: str
    content_hash: str
    byte_length: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class SyntheticLineFixture:
    """Images, labels, and the generator envelope for the frozen lines."""

    envelope: ProvenanceEnvelope
    images: tuple[SyntheticLineImage, ...]
    label_ids: tuple[uuid.UUID, ...]


def reader_parameters() -> dict[str, Any]:
    """Parameter blob for the deterministic slot reader."""
    return {
        "byte_order": BYTE_ORDER,
        "encoding": ENCODING,
        "rows": ROWS,
    }


def reader_envelope(
    *,
    source_hashes: Sequence[str],
    code_version: str,
) -> ProvenanceEnvelope:
    """Envelope for one deterministic read of the line images.

    The algorithm uses no model and no randomness.
    """
    return ProvenanceEnvelope.create(
        source_hashes=source_hashes,
        parameters=reader_parameters(),
        algorithm_name=READER_NAME,
        algorithm_version=READER_VERSION,
        code_version=code_version,
        decoder_name=DECODER_NAME,
        decoder_version=DECODER_VERSION,
        model_hash=ABSENT,
    )


def read_synthetic_line(payload: bytes | bytearray) -> str:
    """Decode one synthetic line image to Unicode NFC text.

    The function reads pixels. It does not open a BenchmarkLabel file and
    it does not expand an abbreviation.
    """
    if not isinstance(payload, bytes | bytearray):
        raise TypeError("A synthetic line image is TIFF bytes.")
    raster = read_fixture_tiff(bytes(payload))
    if not isinstance(raster, FixtureSamples):
        raise ValueError("A synthetic line image is the fixture TIFF layout.")
    if raster.height != ROWS:
        raise ValueError("A synthetic line image has two code-point rows.")
    return _decode_rows(raster.samples, raster.width)


def generate_synthetic_lines(
    benchmarks_dir: Path,
    *,
    images_dir: Path,
    code_version: str,
) -> SyntheticLineFixture:
    """Write the frozen line fixture once.

    The same call writes the same TIFF bytes. There is no seed: the
    generator does not use randomness. A destination that already holds
    ``labels.json`` or a line image is refused, so a later call cannot
    edit the frozen transcriptions.
    """
    _require_distinct_dirs(benchmarks_dir, images_dir)
    if not isinstance(code_version, str) or code_version == "":
        raise ValueError("code_version is required.")
    _require_frozen_lines()
    labels = tuple(_label_row(spec) for spec in FROZEN_LINES)
    payloads = tuple(_line_payload(spec.painted_text) for spec in FROZEN_LINES)
    _require_absent(benchmarks_dir, images_dir, labels)
    images = tuple(
        _image_record(spec.image_name, payload)
        for spec, payload in zip(FROZEN_LINES, payloads, strict=True)
    )
    envelope = ProvenanceEnvelope.create(
        source_hashes=(),
        parameters={
            "byte_order": BYTE_ORDER,
            "encoding": ENCODING,
            "fixture": READER_NAME,
            "line_count": len(FROZEN_LINES),
            "rows": ROWS,
        },
        algorithm_name=ALGORITHM_NAME,
        algorithm_version=ALGORITHM_VERSION,
        code_version=code_version,
        decoder_name=DECODER_NAME,
        decoder_version=DECODER_VERSION,
        model_hash=ABSENT,
    )
    images_dir.mkdir(parents=True, exist_ok=True)
    benchmarks_dir.mkdir(parents=True, exist_ok=True)
    for spec, payload in zip(FROZEN_LINES, payloads, strict=True):
        (images_dir / spec.image_name).write_bytes(payload)
    _write_json(
        images_dir / "image_manifest.json",
        {"images": [_manifest_entry(image) for image in images]},
    )
    _write_json(benchmarks_dir / "labels.json", list(labels))
    provenance = envelope.content_mapping()
    provenance["id"] = envelope.id
    _write_json(benchmarks_dir / "provenance.json", provenance)
    return SyntheticLineFixture(
        envelope=envelope,
        images=images,
        label_ids=tuple(uuid.UUID(row["id"]) for row in labels),
    )


def _require_frozen_lines() -> None:
    names = [spec.image_name for spec in FROZEN_LINES]
    if len(names) != len(set(names)):
        raise ValueError("A synthetic line image name is unique.")
    for spec in FROZEN_LINES:
        _require_nfc_text(spec.reference_text, "reference")
        _require_nfc_text(spec.painted_text, "painted")
        if spec.image_name != Path(spec.image_name).name:
            raise ValueError("A synthetic line image name is a file name.")
        if not spec.image_name.endswith(".tif"):
            raise ValueError("A synthetic line image name is a TIFF file name.")


def _require_nfc_text(text: str, label: str) -> None:
    if text == "" or unicodedata.normalize("NFC", text) != text:
        raise ValueError(f"A frozen line {label} is non-empty Unicode NFC.")
    for char in text:
        if ord(char) > 0xFFFF or 0xD800 <= ord(char) <= 0xDFFF:
            raise ValueError("A frozen line uses a Basic Multilingual Plane scalar.")


def _require_distinct_dirs(benchmarks_dir: Path, images_dir: Path) -> None:
    benchmarks = require_fixture_destination(benchmarks_dir)
    images = require_fixture_destination(images_dir)
    if not isinstance(benchmarks, Path) or not isinstance(images, Path):
        raise TypeError("A fixture destination is a path.")
    if benchmarks.resolve() == images.resolve():
        raise ValueError(
            "Line images and the BenchmarkLabel store are different directories."
        )


def _require_absent(
    benchmarks_dir: Path,
    images_dir: Path,
    labels: Sequence[Mapping[str, Any]],
) -> None:
    if (benchmarks_dir / "labels.json").exists():
        raise ValueError("A synthetic line fixture is written once.")
    if (benchmarks_dir / "provenance.json").exists():
        raise ValueError("A synthetic line fixture is written once.")
    for row in labels:
        name = row["image_name"]
        if not isinstance(name, str):
            raise ValueError("A synthetic line image name is a file name.")
        if (images_dir / name).exists():
            raise ValueError("A synthetic line fixture is written once.")
    if (images_dir / "image_manifest.json").exists():
        raise ValueError("A synthetic line fixture is written once.")


def _label_row(spec: SyntheticLineSpec) -> dict[str, Any]:
    body: dict[str, Any] = {
        "kind": "line",
        "image_name": spec.image_name,
        "text": spec.reference_text,
        "script": spec.script,
        "language": spec.language,
    }
    row = dict(body)
    row["id"] = str(content_id(body))
    return row


def _line_payload(text: str) -> bytes:
    samples, width = _encode_rows(text)
    return write_fixture_tiff(width, ROWS, samples)


def _encode_rows(text: str) -> tuple[bytes, int]:
    width = len(text)
    high = bytearray(width)
    low = bytearray(width)
    for index, char in enumerate(text):
        code = ord(char)
        high[index] = code >> 8
        low[index] = code & 0xFF
    return bytes(high + low), width


def _decode_rows(samples: bytes, width: int) -> str:
    if width < 1 or len(samples) != width * ROWS:
        raise ValueError("A synthetic line image has two code-point rows.")
    chars: list[str] = []
    for index in range(width):
        code = (samples[index] << 8) | samples[width + index]
        if 0xD800 <= code <= 0xDFFF:
            raise ValueError("A synthetic line image stores a Unicode scalar.")
        chars.append(chr(code))
    text = "".join(chars)
    if unicodedata.normalize("NFC", text) != text:
        raise ValueError("A synthetic line image decodes to Unicode NFC.")
    return text


def _image_record(name: str, payload: bytes) -> SyntheticLineImage:
    raster = read_fixture_tiff(payload)
    if not isinstance(raster, FixtureSamples):
        raise ValueError("A synthetic line image is the fixture TIFF layout.")
    return SyntheticLineImage(
        name=name,
        content_hash=hash_value(payload),
        byte_length=len(payload),
        width=raster.width,
        height=raster.height,
    )


def _manifest_entry(image: SyntheticLineImage) -> dict[str, Any]:
    return {
        "role": _LINE_ROLE,
        "name": image.name,
        "content_hash": image.content_hash,
        "byte_length": image.byte_length,
        "width": image.width,
        "height": image.height,
    }


def _write_json(path: Path, value: object) -> None:
    path.write_bytes(canonical_json_bytes(value))


def load_image_manifest(path: Path) -> tuple[dict[str, Any], ...]:
    """Return the line entries in a fixture image manifest.

    The caller uses this to hash the same file the report cites. This
    function does not open ``labels.json``.
    """
    try:
        loaded = json.loads(path.read_bytes())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("An image manifest is JSON.") from exc
    images = loaded.get("images") if isinstance(loaded, dict) else None
    if not isinstance(images, list) or not images:
        raise ValueError("An image manifest lists line images.")
    entries: list[dict[str, Any]] = []
    for item in images:
        if not isinstance(item, dict):
            raise ValueError("An image manifest lists line images.")
        name = item.get("name")
        digest = item.get("content_hash")
        length = item.get("byte_length")
        role = item.get("role")
        if (
            role != _LINE_ROLE
            or not isinstance(name, str)
            or name != Path(name).name
            or not isinstance(digest, str)
            or not digest.startswith("sha256:")
            or isinstance(length, bool)
            or not isinstance(length, int)
            or length < 1
        ):
            raise ValueError("An image manifest lists line images.")
        entries.append(
            {
                "name": name,
                "content_hash": digest,
                "byte_length": length,
            }
        )
    return tuple(entries)
