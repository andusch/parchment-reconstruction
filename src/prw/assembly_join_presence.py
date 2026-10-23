"""End-to-end join presence at a predeclared N against frozen synthetic joins.

See the end-to-end section of ``docs/EVALUATION.md``
(``#end-to-end-join-presence``). A fixture is present when at least one
frozen ``kind: join`` row has its unordered fragment-id pair on a join
cited by one of the first N assemblies, after the caller-supplied
correspondence. The metric counts fixtures. The fraction of present
fixtures is that metric. The report also lists every known join as present
or absent inside that top N.

The reference is a frozen ``kind: join`` row. The metric does not measure
a historical join on real parchment. This module does not define which
assemblies are distinct. ``Q-SCI-08`` and ``Q-SCI-15`` stay open.

N is the caller's integer. It is recorded before any label is treated as a
comparison target. This module has no function that chooses N from the
assemblies or from the labels. The first N assemblies are the prefix of the
caller order. A known join counts once when several of those assemblies
cite it. A hypothesis whose fragment id is absent from the correspondence
does not match a label. A join id on an assembly that the caller did not
pass does not count as present. The report lists every fixture as present
or absent. It introduces no pass threshold.

A caller-supplied correspondence maps a project fragment id to a fixture
fragment id. That correspondence is recorded in the report and is not
written into ``labels.json``. Placement rows and page rows are not scored.

The report copies algorithm name ``rigid_assembly_search``, version ``1``,
the parameter hash, ``code_version``, ``model_hash`` ``absent``, the source
hashes, and the absence of ``random_seed`` from the cited assembly envelope.
It records the ``sha256:`` digest of each label file. It does not invent a
second envelope. The writer does not open TIFF bytes and does not modify
``labels.json`` or ``provenance.json``.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prw.identity import ABSENT, canonical_json_bytes, hash_value, require_hash
from prw.joins import JoinHypothesis
from prw.provenance import AssemblyContent, ProvenanceEnvelope
from prw.synthetic_tear import require_fixture_destination

_ALGORITHM_NAME = "rigid_assembly_search"
_ALGORITHM_VERSION = "1"
_NO_PREVIOUS = "No previous end-to-end join-presence report exists."
_REPORT_DIRECTORY = "assembly_join_presence"
_REPORT_PREFIX = "assembly-join-presence-"
_DOES_NOT_MEASURE = "a historical join on real parchment"
_REFERENCE = "frozen kind: join row"
_PRESENT = "present"
_ABSENT_STATUS = "absent"
_REPORT_DESTINATION = (
    "An end-to-end join-presence report is written under a benchmarks directory."
)


@dataclass(frozen=True, slots=True)
class AssemblyFixture:
    """One synthetic fixture and the assemblies the caller asks to score.

    ``label_file`` is that fixture's frozen BenchmarkLabel file.
    ``assemblies`` is the physical order. ``joins`` are the join rows those
    assemblies cite. ``correspondence`` maps project fragment ids to fixture
    fragment ids.
    """

    label_file: Path
    assemblies: Sequence[AssemblyContent]
    joins: Sequence[JoinHypothesis]
    correspondence: Mapping[uuid.UUID, uuid.UUID]


def write_assembly_join_presence(
    benchmarks_dir: Path,
    *,
    envelope: ProvenanceEnvelope,
    fixtures: Sequence[AssemblyFixture],
    n: int,
) -> Path:
    """Write one end-to-end join-presence report under ``benchmarks_dir``.

    ``n`` is the caller's integer, greater than or equal to 1. It is recorded
    before any label is treated as a comparison target. Each fixture supplies
    ranked assemblies, the join rows they cite, a correspondence, and a
    frozen label file. A fixture is present when at least one frozen join
    appears in that top N. See the end-to-end section of
    ``docs/EVALUATION.md``. The metric does not measure a historical join on
    real parchment. The first report states that no previous end-to-end
    join-presence report exists. A later report names the previous file,
    copies that file's fixture list, and leaves that file unchanged.
    """
    recorded_n = _require_n(n)
    _require_assembly_envelope(envelope)
    recorded = _fixtures(fixtures)
    destination = _destination(benchmarks_dir)
    fixture_list: list[dict[str, Any]] = []
    seen_labels: set[Path] = set()
    for fixture in recorded:
        resolved = fixture.label_file.resolve()
        if resolved in seen_labels:
            raise ValueError("A fixture is scored once.")
        seen_labels.add(resolved)
        fixture_list.append(_score_fixture(destination, fixture, envelope, recorded_n))
    present = sum(1 for entry in fixture_list if entry["status"] == _PRESENT)
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
        "n": recorded_n,
        "reference": _REFERENCE,
        "metric": "assembly_join_presence",
        "unit": (
            "fraction of synthetic fixtures for which a known join appears "
            "inside a predeclared top-N of assemblies"
        ),
        "fixture_list": fixture_list,
        "presence": present / len(fixture_list),
        "does_not_measure": _DOES_NOT_MEASURE,
        "limiting_questions": ["Q-SCI-08", "Q-SCI-15"],
        "previous_report": ABSENT if previous is None else previous.name,
        "previous_report_statement": (
            _NO_PREVIOUS
            if previous is None
            else f"The previous end-to-end join-presence report is {previous.name}."
        ),
    }
    if previous is not None:
        body["previous_fixture_list"] = _previous_fixture_list(previous)
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / _report_name(_next_index(report_dir))
    if path.name == "labels.json":
        raise ValueError("Overwriting labels.json is refused.")
    if path.exists():
        raise ValueError("An end-to-end join-presence report is a new file.")
    path.write_bytes(canonical_json_bytes(body))
    return path


def _require_n(n: int) -> int:
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError("N is an integer greater than or equal to 1.")
    if n < 1:
        raise ValueError("N is an integer greater than or equal to 1.")
    return n


def _require_assembly_envelope(envelope: ProvenanceEnvelope) -> None:
    if not isinstance(envelope, ProvenanceEnvelope):
        raise TypeError("The report copies the cited assembly envelope.")
    copied = (
        envelope.algorithm_name == _ALGORITHM_NAME
        and envelope.algorithm_version == _ALGORITHM_VERSION
        and envelope.model_hash == ABSENT
        and envelope.random_seed is None
    )
    if not copied:
        raise ValueError("The report copies the rigid_assembly_search envelope.")


def _fixtures(fixtures: Sequence[AssemblyFixture]) -> tuple[AssemblyFixture, ...]:
    if isinstance(fixtures, str | bytes) or not isinstance(fixtures, Sequence):
        raise TypeError("Join presence scores a caller list of fixtures.")
    stored: list[AssemblyFixture] = []
    for fixture in fixtures:
        if not isinstance(fixture, AssemblyFixture):
            raise TypeError("Join presence scores a caller list of fixtures.")
        stored.append(fixture)
    if not stored:
        raise ValueError("A caller list with no fixture is refused.")
    return tuple(stored)


def _destination(path: Path) -> Path:
    if not isinstance(path, Path):
        raise TypeError(_REPORT_DESTINATION)
    if path.name == "labels.json":
        raise ValueError("Overwriting labels.json is refused.")
    destination = require_fixture_destination(path)
    if destination.is_file():
        raise ValueError(_REPORT_DESTINATION)
    return destination


def _score_fixture(
    benchmarks_dir: Path,
    fixture: AssemblyFixture,
    envelope: ProvenanceEnvelope,
    n: int,
) -> dict[str, Any]:
    label_file = _label_file(benchmarks_dir, fixture.label_file)
    label_bytes = _label_bytes(fixture.label_file)
    join_rows = _join_rows(label_bytes)
    assemblies = _assemblies(fixture.assemblies, envelope)
    joins = _joins(fixture.joins)
    mapped = _correspondence(fixture.correspondence)
    pairs = _present_pairs(assemblies[:n], joins, dict(mapped))
    join_list = _join_list(join_rows, pairs)
    status = (
        _PRESENT
        if any(entry["status"] == _PRESENT for entry in join_list)
        else _ABSENT_STATUS
    )
    return {
        "label_file": label_file,
        "label_file_hash": hash_value(label_bytes),
        "correspondence": [
            {
                "project_fragment_id": project_id,
                "fixture_fragment_id": fixture_id,
            }
            for project_id, fixture_id in mapped
        ],
        "status": status,
        "join_list": join_list,
    }


def _label_file(benchmarks_dir: Path, label_file: Path) -> str:
    if not isinstance(label_file, Path):
        raise TypeError("A fixture label file is labels.json.")
    if label_file.name != "labels.json":
        raise ValueError("A fixture label file is labels.json.")
    try:
        relative = label_file.resolve().relative_to(benchmarks_dir.resolve())
    except ValueError as exc:
        raise ValueError(
            "A fixture label file stays under the benchmarks directory."
        ) from exc
    return relative.as_posix()


def _label_bytes(path: Path) -> bytes:
    if not path.is_file():
        raise ValueError("A label file with no join row is refused.")
    return path.read_bytes()


def _assemblies(
    assemblies: Sequence[AssemblyContent],
    envelope: ProvenanceEnvelope,
) -> tuple[AssemblyContent, ...]:
    if isinstance(assemblies, str | bytes) or not isinstance(assemblies, Sequence):
        raise TypeError("Ranked assemblies are AssemblyContent rows.")
    stored: list[AssemblyContent] = []
    for assembly in assemblies:
        if not isinstance(assembly, AssemblyContent):
            raise TypeError("Ranked assemblies are AssemblyContent rows.")
        if assembly.provenance_id != envelope.id:
            raise ValueError("The report copies the cited assembly envelope.")
        stored.append(assembly)
    return tuple(stored)


def _joins(joins: Sequence[JoinHypothesis]) -> tuple[JoinHypothesis, ...]:
    if isinstance(joins, str | bytes) or not isinstance(joins, Sequence):
        raise TypeError("Cited joins are JoinHypothesis rows.")
    stored: list[JoinHypothesis] = []
    for join in joins:
        if not isinstance(join, JoinHypothesis):
            raise TypeError("Cited joins are JoinHypothesis rows.")
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


def _present_pairs(
    assemblies: Sequence[AssemblyContent],
    joins: Sequence[JoinHypothesis],
    correspondence: Mapping[str, str],
) -> set[frozenset[str]]:
    by_id: dict[uuid.UUID, JoinHypothesis] = {}
    for join in joins:
        stored = by_id.get(join.id)
        if stored is not None and stored != join:
            raise ValueError("A cited join is supplied once.")
        by_id[join.id] = join
    pairs: set[frozenset[str]] = set()
    for assembly in assemblies:
        for join_id in assembly.join_ids:
            cited = by_id.get(join_id)
            if cited is None:
                continue
            left = correspondence.get(str(cited.fragment_a_id))
            right = correspondence.get(str(cited.fragment_b_id))
            if left is None or right is None or left == right:
                continue
            pairs.add(frozenset((left, right)))
    return pairs


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


def _join_list(
    join_rows: Sequence[Mapping[str, Any]],
    present_pairs: set[frozenset[str]],
) -> list[dict[str, Any]]:
    listed: list[dict[str, Any]] = []
    for row in join_rows:
        fragment_ids = row["fragment_ids"]
        if not isinstance(fragment_ids, tuple):
            raise ValueError("A join label cites two fragment ids.")
        status = (
            _PRESENT if frozenset(fragment_ids) in present_pairs else _ABSENT_STATUS
        )
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


def _previous_fixture_list(path: Path) -> list[dict[str, Any]]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("An end-to-end join-presence report lists every fixture.")
    values = loaded.get("fixture_list")
    if not isinstance(values, list) or len(values) == 0:
        raise ValueError("An end-to-end join-presence report lists every fixture.")
    return [_copied_fixture(value) for value in values]


def _copied_fixture(value: object) -> dict[str, Any]:
    record = _record(value)
    label_file = record.get("label_file")
    label_hash = record.get("label_file_hash")
    status = record.get("status")
    correspondence = record.get("correspondence")
    join_list = record.get("join_list")
    if (
        not isinstance(label_file, str)
        or label_file == ""
        or not isinstance(label_hash, str)
        or status not in {_PRESENT, _ABSENT_STATUS}
        or isinstance(correspondence, str | bytes)
        or not isinstance(correspondence, list)
        or isinstance(join_list, str | bytes)
        or not isinstance(join_list, list)
        or len(join_list) == 0
    ):
        raise ValueError("An end-to-end join-presence report lists every fixture.")
    try:
        checked_hash = require_hash(label_hash)
    except ValueError as exc:
        raise ValueError(
            "An end-to-end join-presence report lists every fixture."
        ) from exc
    if checked_hash == ABSENT:
        raise ValueError("An end-to-end join-presence report lists every fixture.")
    return {
        "label_file": label_file,
        "label_file_hash": checked_hash,
        "correspondence": [_copied_correspondence(item) for item in correspondence],
        "status": status,
        "join_list": [_copied_join(item) for item in join_list],
    }


def _copied_correspondence(value: object) -> dict[str, str]:
    record = _record(value)
    project_id = record.get("project_fragment_id")
    fixture_id = record.get("fixture_fragment_id")
    if not isinstance(project_id, str) or not isinstance(fixture_id, str):
        raise ValueError("An end-to-end join-presence report lists every fixture.")
    return {
        "project_fragment_id": project_id,
        "fixture_fragment_id": fixture_id,
    }


def _copied_join(value: object) -> dict[str, Any]:
    record = _record(value)
    fragment_ids = record.get("fragment_ids")
    status = record.get("status")
    if (
        isinstance(fragment_ids, str | bytes)
        or not isinstance(fragment_ids, list)
        or len(fragment_ids) != 2
        or any(not isinstance(item, str) for item in fragment_ids)
        or status not in {_PRESENT, _ABSENT_STATUS}
    ):
        raise ValueError("An end-to-end join-presence report lists every fixture.")
    entry: dict[str, Any] = {
        "fragment_ids": list(fragment_ids),
        "status": status,
    }
    if "id" in record:
        if not isinstance(record["id"], str):
            raise ValueError("An end-to-end join-presence report lists every fixture.")
        entry["id"] = record["id"]
    return entry


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
