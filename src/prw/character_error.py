"""Character error rate under the frozen Q-SCI-16 abbreviation policy.

See the character-error section of ``docs/EVALUATION.md``
(``#character-error-rate``). The reference is a frozen ``kind: line`` row
in the BenchmarkLabel store. A line whose ``script`` or ``language`` is
``nomen-sacrum``, ``abbreviation``, or ``mixed-script`` stays unscored and
is excluded from the set. Every other line is compared as written.
Abbreviations are not expanded. There is no expansion table in this module.

Storage stays Unicode NFC. Comparison copies the strings, decomposes to
NFD, drops nonspacing marks, maps final sigma to sigma, and recomposes.
The stored strings are not rewritten. The report lists every line. The
headline rate is the total edit distance divided by the total comparison
length of the scored lines. It is not a best line, and it introduces no
pass threshold.

The number is a synthetic-fixture result. It does not measure Ancient
Greek handwriting, scholarly acceptability, or the PP-OCRv6 medium model
card. ``Q-SCI-06``, ``Q-SCI-13``, and ``Q-SCI-15`` stay open. ``Q-SCI-15``
still blocks an accuracy claim on a real manuscript.

The writer reads ``labels.json`` and ``image_manifest.json``. It does not
modify them and does not write a project evidence database. Solver and
``recognize`` code paths do not import this module.
"""

from __future__ import annotations

import json
import unicodedata
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from prw.identity import ABSENT, canonical_json_bytes, content_id, hash_value
from prw.provenance import ProvenanceEnvelope
from prw.synthetic_line import EXCLUSION_TAGS, READER_NAME, READER_VERSION
from prw.synthetic_tear import require_fixture_destination

_HTR_NAME = "greek_line_htr"
_HTR_VERSION = "1"
_NO_PREVIOUS = "No previous character-error report exists."
_REPORT_DIRECTORY = "character_error"
_REPORT_PREFIX = "character-error-"
_REFERENCE = "frozen kind: line row"
_METRIC = "character_error_rate"
_DOES_NOT_MEASURE = (
    "Ancient Greek handwriting, scholarly acceptability, "
    "or the PP-OCRv6 medium model card"
)
_CLAIM = "synthetic-fixture result"
_MODEL_CARD = "citations only; not this synthetic-fixture result"
_LIMITS = ("Q-SCI-06", "Q-SCI-13", "Q-SCI-15")
_SCORED = "scored"
_UNSCORED = "unscored"
_EXCLUSIONS = frozenset(EXCLUSION_TAGS)


def comparison_text(text: str) -> str:
    """Return a comparison copy of NFC ``text``.

    Accents are stripped and final sigma is mapped to sigma. ``text`` is
    not modified. An input that is not Unicode NFC is refused, so this
    function does not become a storage normalizer.
    """
    stored = _require_nfc(text)
    decomposed = unicodedata.normalize("NFD", stored)
    stripped = "".join(
        char for char in decomposed if unicodedata.category(char) != "Mn"
    )
    mapped = stripped.replace("\u03c2", "\u03c3")
    return unicodedata.normalize("NFC", mapped)


def edit_distance(reference: str, hypothesis: str) -> int:
    """Return the Levenshtein distance between two strings.

    The strings are compared code point by code point. This function does
    not strip accents, map sigma, or expand abbreviations.
    """
    if not isinstance(reference, str) or not isinstance(hypothesis, str):
        raise TypeError("Edit distance compares two strings.")
    if reference == hypothesis:
        return 0
    previous = list(range(len(hypothesis) + 1))
    for index, left in enumerate(reference, start=1):
        current = [index]
        for column, right in enumerate(hypothesis, start=1):
            insert = current[column - 1] + 1
            delete = previous[column] + 1
            substitute = previous[column - 1] + (left != right)
            current.append(min(insert, delete, substitute))
        previous = current
    return previous[-1]


def exclusion_tag(script: str, language: str) -> str | None:
    """Return the operator exclusion tag, or ``None`` when the line is scored.

    The tag is ``nomen-sacrum``, ``abbreviation``, or ``mixed-script`` when
    that token is the line's ``script`` or ``language``. Two different
    exclusion tokens on one line are refused.
    """
    if not isinstance(script, str) or not isinstance(language, str):
        raise TypeError("A line tag is a string.")
    found: list[str] = []
    if script in _EXCLUSIONS:
        found.append(script)
    if language in _EXCLUSIONS and language not in found:
        found.append(language)
    if len(found) > 1:
        raise ValueError("A line has one exclusion tag.")
    if not found:
        return None
    return found[0]


def write_character_error(
    benchmarks_dir: Path,
    *,
    images_dir: Path,
    envelope: ProvenanceEnvelope,
    hypotheses: Mapping[str, str],
) -> Path:
    """Write one character-error report under ``benchmarks_dir``.

    ``hypotheses`` maps an image name to the reader's stored NFC text.
    The reference text stays the frozen label. The first report states
    that no previous character-error report exists. A later report names
    the previous file, copies that file's line list, and leaves that file
    unchanged.
    """
    _require_envelope(envelope)
    stored_hypotheses = _hypotheses(hypotheses)
    benchmarks = _directory(benchmarks_dir, "benchmarks")
    images = _directory(images_dir, "images")
    if benchmarks.resolve() == images.resolve():
        raise ValueError(
            "Line images and the BenchmarkLabel store are different directories."
        )
    label_path = benchmarks / "labels.json"
    label_bytes = _read_file(label_path, "A label file with no line row is refused.")
    manifest_path = images / "image_manifest.json"
    manifest_bytes = _read_file(manifest_path, "An image manifest lists line images.")
    rows = _line_rows(label_bytes)
    manifest = _manifest_entries(manifest_bytes)
    _require_same_images(rows, manifest, stored_hypotheses, envelope)
    line_list = _line_list(rows, stored_hypotheses)
    totals = _totals(line_list)
    report_dir = benchmarks / _REPORT_DIRECTORY
    previous = _previous_report(report_dir)
    body: dict[str, Any] = {
        "algorithm_name": envelope.algorithm_name,
        "algorithm_version": envelope.algorithm_version,
        "parameter_blob": envelope.parameter_blob,
        "parameter_hash": envelope.parameter_hash,
        "code_version": envelope.code_version,
        "model_hash": envelope.model_hash,
        "random_seed": ABSENT,
        "decoder_name": envelope.decoder_name,
        "decoder_version": envelope.decoder_version,
        "source_hashes": envelope.source_hashes,
        "fixture_manifest_hash": hash_value(manifest_bytes),
        "fixture_manifest_hashes": manifest,
        "freeze_identifier": hash_value(label_bytes),
        "reference": _REFERENCE,
        "metric": _METRIC,
        "unit": ("edit distance divided by the comparison length of the scored lines"),
        "abbreviation_policy": "Q-SCI-16",
        "abbreviations_expanded": False,
        "storage": "nfc",
        "comparison": "strip accents and normalize final sigma",
        "claim": _CLAIM,
        "edit_distance": totals[0],
        "reference_length": totals[1],
        "character_error_rate": totals[2],
        "scored_line_count": totals[3],
        "unscored_line_count": totals[4],
        "line_list": line_list,
        "does_not_measure": _DOES_NOT_MEASURE,
        "model_card_figures": _MODEL_CARD,
        "limiting_questions": list(_LIMITS),
        "previous_report": ABSENT if previous is None else previous.name,
        "previous_report_statement": (
            _NO_PREVIOUS
            if previous is None
            else f"The previous character-error report is {previous.name}."
        ),
    }
    if previous is not None:
        body["previous_line_list"] = _previous_line_list(previous)
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / _report_name(_next_index(report_dir))
    if path.name == "labels.json":
        raise ValueError("Overwriting labels.json is refused.")
    if path.exists():
        raise ValueError("A character-error report is a new file.")
    path.write_bytes(canonical_json_bytes(body))
    if label_path.read_bytes() != label_bytes:
        raise ValueError("Overwriting labels.json is refused.")
    if manifest_path.read_bytes() != manifest_bytes:
        raise ValueError("Overwriting the image manifest is refused.")
    return path


def _require_nfc(text: object) -> str:
    if not isinstance(text, str):
        raise TypeError("Stored text is a string in Unicode NFC.")
    if unicodedata.normalize("NFC", text) != text:
        raise ValueError("Stored text is Unicode NFC.")
    return text


def _require_envelope(envelope: ProvenanceEnvelope) -> None:
    if not isinstance(envelope, ProvenanceEnvelope):
        raise TypeError("The report copies the cited reader envelope.")
    if envelope.random_seed is not None:
        raise ValueError("The character-error reader is deterministic.")
    synthetic = (
        envelope.algorithm_name == READER_NAME
        and envelope.algorithm_version == READER_VERSION
        and envelope.model_hash == ABSENT
    )
    model = (
        envelope.algorithm_name == _HTR_NAME
        and envelope.algorithm_version == _HTR_VERSION
        and envelope.model_hash.startswith("sha256:")
    )
    if synthetic or model:
        return
    raise ValueError("The report copies the synthetic line reader or greek_line_htr.")


def _hypotheses(hypotheses: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(hypotheses, Mapping):
        raise TypeError("Hypotheses map an image name to stored text.")
    stored: dict[str, str] = {}
    for name, text in hypotheses.items():
        if not isinstance(name, str) or name == "" or name != Path(name).name:
            raise TypeError("Hypotheses map an image name to stored text.")
        stored[name] = _require_nfc(text)
    if not stored:
        raise ValueError("A character-error report lists every line.")
    return stored


def _directory(path: Path, label: str) -> Path:
    if not isinstance(path, Path):
        raise TypeError(
            "A character-error report is written under a benchmarks directory."
        )
    if path.name == "labels.json":
        raise ValueError("Overwriting labels.json is refused.")
    destination = require_fixture_destination(path)
    if destination.is_file():
        raise ValueError(
            "A character-error report is written under a benchmarks directory."
        )
    if label == "images" and not (destination / "image_manifest.json").is_file():
        raise ValueError("An image manifest lists line images.")
    return destination


def _read_file(path: Path, message: str) -> bytes:
    if not path.is_file():
        raise ValueError(message)
    return path.read_bytes()


def _line_rows(label_bytes: bytes) -> tuple[dict[str, Any], ...]:
    try:
        loaded = json.loads(label_bytes)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("A label file with no line row is refused.") from exc
    if not isinstance(loaded, list):
        raise ValueError("A label file with no line row is refused.")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in loaded:
        record = _record(item)
        if record.get("kind") != "line":
            continue
        row = _line_row(record)
        if row["image_name"] in seen:
            raise ValueError("A line label names one image.")
        seen.add(row["image_name"])
        rows.append(row)
    if not rows:
        raise ValueError("A label file with no line row is refused.")
    rows.sort(key=lambda item: str(item["image_name"]))
    return tuple(rows)


def _line_row(record: Mapping[str, Any]) -> dict[str, Any]:
    image_name = record.get("image_name")
    text = record.get("text")
    script = record.get("script")
    language = record.get("language")
    label_id = record.get("id")
    if (
        not isinstance(image_name, str)
        or image_name != Path(image_name).name
        or not isinstance(script, str)
        or script == ""
        or not isinstance(language, str)
        or language == ""
        or not isinstance(label_id, str)
    ):
        raise ValueError("A line label cites an image, a text, and tags.")
    stored_text = _require_nfc(text)
    body = {
        "kind": "line",
        "image_name": image_name,
        "text": stored_text,
        "script": script,
        "language": language,
    }
    try:
        parsed = uuid.UUID(label_id)
    except ValueError as exc:
        raise ValueError("A line label cites an image, a text, and tags.") from exc
    if str(content_id(body)) != str(parsed):
        raise ValueError("A line label id does not match its content.")
    return {
        "id": str(parsed),
        "image_name": image_name,
        "text": stored_text,
        "script": script,
        "language": language,
    }


def _manifest_entries(manifest_bytes: bytes) -> list[dict[str, Any]]:
    try:
        loaded = json.loads(manifest_bytes)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("An image manifest lists line images.") from exc
    images = loaded.get("images") if isinstance(loaded, dict) else None
    if not isinstance(images, list) or not images:
        raise ValueError("An image manifest lists line images.")
    entries: list[dict[str, Any]] = []
    for item in images:
        record = _record(item)
        name = record.get("name")
        digest = record.get("content_hash")
        length = record.get("byte_length")
        if (
            record.get("role") != "line"
            or not isinstance(name, str)
            or not isinstance(digest, str)
            or not digest.startswith("sha256:")
            or isinstance(length, bool)
            or not isinstance(length, int)
        ):
            raise ValueError("An image manifest lists line images.")
        entries.append({"name": name, "content_hash": digest, "byte_length": length})
    return entries


def _require_same_images(
    rows: Sequence[Mapping[str, Any]],
    manifest: Sequence[Mapping[str, Any]],
    hypotheses: Mapping[str, str],
    envelope: ProvenanceEnvelope,
) -> None:
    label_names = [str(row["image_name"]) for row in rows]
    manifest_names = [str(item["name"]) for item in manifest]
    if label_names != sorted(manifest_names) or len(label_names) != len(
        set(label_names)
    ):
        raise ValueError("A character-error report lists every line.")
    if set(hypotheses) != set(label_names):
        raise ValueError("A character-error report lists every line.")
    hashes = tuple(str(item["content_hash"]) for item in manifest)
    if tuple(envelope.source_hashes) != hashes:
        raise ValueError("The report copies the cited reader envelope.")


def _line_list(
    rows: Sequence[Mapping[str, Any]],
    hypotheses: Mapping[str, str],
) -> list[dict[str, Any]]:
    listed: list[dict[str, Any]] = []
    for row in rows:
        image_name = str(row["image_name"])
        reference = str(row["text"])
        hypothesis = hypotheses[image_name]
        script = str(row["script"])
        language = str(row["language"])
        tag = exclusion_tag(script, language)
        entry: dict[str, Any] = {
            "image_name": image_name,
            "line_id": row["id"],
            "status": _UNSCORED if tag is not None else _SCORED,
            "exclusion": ABSENT if tag is None else tag,
            "script": script,
            "language": language,
            "reference_text": reference,
            "hypothesis_text": hypothesis,
        }
        if tag is None:
            scored = _score(reference, hypothesis)
            entry["reference_comparison"] = scored[0]
            entry["hypothesis_comparison"] = scored[1]
            entry["edit_distance"] = scored[2]
            entry["reference_length"] = scored[3]
            entry["character_error_rate"] = scored[4]
        else:
            entry["character_error_rate"] = ABSENT
        listed.append(entry)
    return listed


def _score(reference: str, hypothesis: str) -> tuple[str, str, int, int, float]:
    compared_reference = comparison_text(reference)
    compared_hypothesis = comparison_text(hypothesis)
    if compared_reference == "":
        raise ValueError("A scored line has a non-empty reference.")
    distance = edit_distance(compared_reference, compared_hypothesis)
    length = len(compared_reference)
    return (
        compared_reference,
        compared_hypothesis,
        distance,
        length,
        distance / length,
    )


def _totals(line_list: Sequence[Mapping[str, Any]]) -> tuple[int, int, float, int, int]:
    distance = 0
    length = 0
    scored = 0
    unscored = 0
    for entry in line_list:
        if entry["status"] == _UNSCORED:
            unscored += 1
            continue
        if entry["status"] != _SCORED:
            raise ValueError("A character-error report lists every line.")
        scored += 1
        distance += int(entry["edit_distance"])
        length += int(entry["reference_length"])
    if scored == 0 or length == 0:
        raise ValueError("A character-error report scores at least one line.")
    return distance, length, distance / length, scored, unscored


def _record(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("A label file lists BenchmarkLabel rows.")
    stored: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError("A label file lists BenchmarkLabel rows.")
        stored[key] = item
    return stored


def _previous_report(report_dir: Path) -> Path | None:
    if not report_dir.is_dir():
        return None
    reports = sorted(
        path
        for path in report_dir.iterdir()
        if path.is_file() and _report_index(path.name) is not None
    )
    if not reports:
        return None
    return reports[-1]


def _previous_line_list(path: Path) -> list[dict[str, Any]]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("A character-error report lists every line.")
    values = loaded.get("line_list")
    if not isinstance(values, list) or len(values) == 0:
        raise ValueError("A character-error report lists every line.")
    copied: list[dict[str, Any]] = []
    for value in values:
        record = _record(value)
        status = record.get("status")
        if status not in {_SCORED, _UNSCORED}:
            raise ValueError("A character-error report lists every line.")
        if not isinstance(record.get("image_name"), str):
            raise ValueError("A character-error report lists every line.")
        if not isinstance(record.get("reference_text"), str):
            raise ValueError("A character-error report lists every line.")
        if not isinstance(record.get("hypothesis_text"), str):
            raise ValueError("A character-error report lists every line.")
        copied.append(dict(record))
    return copied


def _report_index(name: str) -> int | None:
    if not name.startswith(_REPORT_PREFIX) or not name.endswith(".json"):
        return None
    suffix = name[len(_REPORT_PREFIX) : -len(".json")]
    if len(suffix) != 4 or not suffix.isdecimal():
        return None
    return int(suffix)


def _next_index(report_dir: Path) -> int:
    if not report_dir.is_dir():
        return 1
    indexes = [
        index
        for path in report_dir.iterdir()
        if (index := _report_index(path.name)) is not None
    ]
    if not indexes:
        return 1
    return max(indexes) + 1


def _report_name(index: int) -> str:
    return f"{_REPORT_PREFIX}{index:04d}.json"
