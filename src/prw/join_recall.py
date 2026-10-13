"""Join recall at a predeclared K against frozen synthetic join labels.

See the join-recall section of ``docs/EVALUATION.md`` (``#join-recall-at-k``).
Recall is the fraction of frozen ``kind: join`` rows whose unordered
fragment-id pair appears on at least one of the top K ranked joins. The
reference is a frozen ``kind: join`` row. The metric does not measure a
historical join on real parchment. ``Q-SCI-15`` stays open.

K is the caller's integer. It is recorded before any label is treated as a
comparison target. This module has no function that chooses K from the
scored joins. A caller-supplied correspondence maps a project fragment id
to a fixture fragment id. That correspondence is recorded in the report and
is not written into ``labels.json``. A hypothesis whose fragment id is
absent from the correspondence does not match a label. A known join counts
once when several top-K hypotheses share its fragment pair. The report
lists every known join as present or absent. It is not summarized by a
best score, and it introduces no pass threshold.

The report copies algorithm name ``pairwise_rigid_join``, version ``1``,
the parameter hash, ``code_version``, ``model_hash`` ``absent``, the source
hashes, and the absence of ``random_seed`` from the cited join envelope.
It does not invent a second envelope. The freeze identifier is the
``sha256:`` digest of the label-file bytes. Placement and page rows are
not scored. The writer does not open TIFF bytes and does not modify
``labels.json`` or ``provenance.json``.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from prw.identity import ABSENT, canonical_json_bytes, hash_value
from prw.joins import JoinHypothesis
from prw.provenance import ProvenanceEnvelope
from prw.synthetic_tear import require_fixture_destination

_ALGORITHM_NAME = "pairwise_rigid_join"
_ALGORITHM_VERSION = "1"
_NO_PREVIOUS = "No previous join-recall report exists."
_REPORT_DIRECTORY = "join_recall"
_REPORT_PREFIX = "join-recall-"
_DOES_NOT_MEASURE = "a historical join on real parchment"
_REFERENCE = "frozen kind: join row"


def write_join_recall(
    benchmarks_dir: Path,
    *,
    envelope: ProvenanceEnvelope,
    ranked_joins: Sequence[JoinHypothesis],
    k: int,
    correspondence: Mapping[uuid.UUID, uuid.UUID],
) -> Path:
    """Write one join-recall report under ``benchmarks_dir``.

    ``k`` is the caller's integer, greater than or equal to 1. ``ranked_joins``
    is the physical order from join rank: the top K rows are the prefix of
    that sequence. ``correspondence`` maps project fragment ids to fixture
    fragment ids. See the join-recall section of ``docs/EVALUATION.md``. The
    reference is a frozen ``kind: join`` row. The metric does not measure a
    historical join on real parchment. The first report states that no
    previous join-recall report exists. A later report names the previous
    file, copies that file's recall list, and leaves that file unchanged.
    """
    recorded_k = _require_k(k)
    _require_join_envelope(envelope)
    ranked = _ranked_joins(ranked_joins, envelope)
    mapped = _correspondence(correspondence)
    destination = _destination(benchmarks_dir)
    label_path = destination / "labels.json"
    label_bytes = _label_bytes(label_path)
    join_rows = _join_rows(label_bytes)
    present_pairs = _present_pairs(ranked[:recorded_k], mapped)
    recall_list = _recall_list(join_rows, present_pairs)
    present = sum(1 for entry in recall_list if entry["status"] == "present")
    report_dir = destination / _REPORT_DIRECTORY
    previous = _previous_report(report_dir)
    body: dict[str, Any] = {
        "algorithm_name": envelope.algorithm_name,
        "algorithm_version": envelope.algorithm_version,
        "parameter_hash": envelope.parameter_hash,
        "code_version": envelope.code_version,
        "model_hash": envelope.model_hash,
        "random_seed": ABSENT,
        "source_hashes": envelope.source_hashes,
        "k": recorded_k,
        "correspondence": [
            {
                "project_fragment_id": project_id,
                "fixture_fragment_id": fixture_id,
            }
            for project_id, fixture_id in mapped
        ],
        "reference": _REFERENCE,
        "metric": "join_recall_at_k",
        "unit": (
            "fraction of known synthetic joins in the top K of the physical channel"
        ),
        "label_file_hash": hash_value(label_bytes),
        "recall_list": recall_list,
        "recall": present / len(recall_list),
        "does_not_measure": _DOES_NOT_MEASURE,
        "limiting_questions": ["Q-SCI-15"],
        "previous_report": ABSENT if previous is None else previous.name,
        "previous_report_statement": (
            _NO_PREVIOUS
            if previous is None
            else f"The previous join-recall report is {previous.name}."
        ),
    }
    if previous is not None:
        body["previous_recall_list"] = _previous_recall_list(previous)
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / _report_name(_next_index(report_dir))
    if path.name == "labels.json":
        raise ValueError("Overwriting labels.json is refused.")
    if path.exists():
        raise ValueError("A join-recall report is a new file.")
    path.write_bytes(canonical_json_bytes(body))
    return path


def _require_k(k: int) -> int:
    if isinstance(k, bool) or not isinstance(k, int):
        raise TypeError("K is an integer greater than or equal to 1.")
    if k < 1:
        raise ValueError("K is an integer greater than or equal to 1.")
    return k


def _require_join_envelope(envelope: ProvenanceEnvelope) -> None:
    if not isinstance(envelope, ProvenanceEnvelope):
        raise TypeError("The report copies the cited join envelope.")
    copied = (
        envelope.algorithm_name == _ALGORITHM_NAME
        and envelope.algorithm_version == _ALGORITHM_VERSION
        and envelope.model_hash == ABSENT
        and envelope.random_seed is None
    )
    if not copied:
        raise ValueError("The report copies the pairwise_rigid_join envelope.")


def _ranked_joins(
    joins: Sequence[JoinHypothesis],
    envelope: ProvenanceEnvelope,
) -> tuple[JoinHypothesis, ...]:
    if isinstance(joins, str | bytes) or not isinstance(joins, Sequence):
        raise TypeError("Ranked joins are JoinHypothesis rows.")
    stored: list[JoinHypothesis] = []
    for join in joins:
        if not isinstance(join, JoinHypothesis):
            raise TypeError("Ranked joins are JoinHypothesis rows.")
        if join.provenance_id != envelope.id:
            raise ValueError("The report copies the cited join envelope.")
        stored.append(join)
    return tuple(stored)


def _correspondence(
    correspondence: Mapping[uuid.UUID, uuid.UUID],
) -> tuple[tuple[str, str], ...]:
    if not isinstance(correspondence, Mapping):
        raise TypeError(
            "The correspondence maps project fragment ids to fixture fragment ids."
        )
    pairs: list[tuple[str, str]] = []
    for project_id, fixture_id in correspondence.items():
        if not isinstance(project_id, uuid.UUID) or not isinstance(
            fixture_id, uuid.UUID
        ):
            raise TypeError(
                "The correspondence maps project fragment ids to fixture fragment ids."
            )
        pairs.append((str(project_id), str(fixture_id)))
    pairs.sort(key=lambda item: item[0])
    return tuple(pairs)


def _destination(path: Path) -> Path:
    if not isinstance(path, Path):
        raise TypeError("A join-recall report is written under a benchmarks directory.")
    if path.name == "labels.json":
        raise ValueError("Overwriting labels.json is refused.")
    destination = require_fixture_destination(path)
    if destination.is_file():
        raise ValueError(
            "A join-recall report is written under a benchmarks directory."
        )
    return destination


def _label_bytes(path: Path) -> bytes:
    if not path.is_file():
        raise ValueError("A label file with no join row is refused.")
    return path.read_bytes()


def _join_rows(label_bytes: bytes) -> tuple[dict[str, Any], ...]:
    try:
        loaded = json.loads(label_bytes)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("A label file with no join row is refused.") from exc
    if not isinstance(loaded, list):
        raise ValueError("A label file with no join row is refused.")
    rows: list[dict[str, Any]] = []
    for item in loaded:
        record = _record(item)
        if record.get("kind") != "join":
            continue
        rows.append(_join_row(record))
    if not rows:
        raise ValueError("A label file with no join row is refused.")
    return tuple(rows)


def _record(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("A label file lists BenchmarkLabel rows.")
    stored: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError("A label file lists BenchmarkLabel rows.")
        stored[key] = item
    return stored


def _join_row(record: Mapping[str, Any]) -> dict[str, Any]:
    raw_ids = record.get("fragment_ids")
    if isinstance(raw_ids, str | bytes) or not isinstance(raw_ids, list):
        raise ValueError("A join label cites two fragment ids.")
    if len(raw_ids) != 2:
        raise ValueError("A join label cites two fragment ids.")
    fragment_ids = (_uuid_text(raw_ids[0]), _uuid_text(raw_ids[1]))
    if fragment_ids[0] == fragment_ids[1]:
        raise ValueError("A join label cites two fragment ids.")
    row: dict[str, Any] = {"fragment_ids": fragment_ids}
    if "id" in record:
        row["id"] = _uuid_text(record["id"])
    return row


def _uuid_text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("A join label cites two fragment ids.")
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise ValueError("A join label cites two fragment ids.") from exc
    return str(parsed)


def _present_pairs(
    top: Sequence[JoinHypothesis],
    correspondence: Sequence[tuple[str, str]],
) -> set[frozenset[str]]:
    table = dict(correspondence)
    pairs: set[frozenset[str]] = set()
    for join in top:
        left = table.get(str(join.fragment_a_id))
        right = table.get(str(join.fragment_b_id))
        if left is None or right is None or left == right:
            continue
        pairs.add(frozenset((left, right)))
    return pairs


def _recall_list(
    join_rows: Sequence[Mapping[str, Any]],
    present_pairs: set[frozenset[str]],
) -> list[dict[str, Any]]:
    listed: list[dict[str, Any]] = []
    for row in join_rows:
        fragment_ids = row["fragment_ids"]
        if not isinstance(fragment_ids, tuple):
            raise ValueError("A join label cites two fragment ids.")
        status = "present" if frozenset(fragment_ids) in present_pairs else "absent"
        entry: dict[str, Any] = {
            "fragment_ids": list(fragment_ids),
            "status": status,
        }
        if "id" in row:
            entry["id"] = row["id"]
        listed.append(entry)
    return listed


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


def _previous_recall_list(path: Path) -> list[dict[str, Any]]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("A join-recall report lists every known join.")
    values = loaded.get("recall_list")
    if not isinstance(values, list) or len(values) == 0:
        raise ValueError("A join-recall report lists every known join.")
    copied: list[dict[str, Any]] = []
    for value in values:
        record = _record(value)
        fragment_ids = record.get("fragment_ids")
        status = record.get("status")
        if (
            isinstance(fragment_ids, str | bytes)
            or not isinstance(fragment_ids, list)
            or len(fragment_ids) != 2
            or any(not isinstance(item, str) for item in fragment_ids)
            or status not in {"present", "absent"}
        ):
            raise ValueError("A join-recall report lists every known join.")
        entry: dict[str, Any] = {
            "fragment_ids": list(fragment_ids),
            "status": status,
        }
        if "id" in record:
            if not isinstance(record["id"], str):
                raise ValueError("A join-recall report lists every known join.")
            entry["id"] = record["id"]
        copied.append(entry)
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
