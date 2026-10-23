"""Placement error at a predeclared N against frozen synthetic placement labels.

See the placement-error section of ``docs/EVALUATION.md``
(``#placement-error``) and ``_place`` in ``src/prw/synthetic_tear.py``.
RMSE is the square root of the mean squared Euclidean distance, in page
millimetres, between landmarks placed by an assembly pose and the same
landmarks placed by a frozen ``kind: placement`` row. Both use the
``_place`` matrix. Positive rotation sends ``+x`` toward ``+y``. The new x
is ``x * cos(rotation) - y * sin(rotation)``. The new y is
``x * sin(rotation) + y * cos(rotation)``. The translation is added after
that. The local origin is the outline centroid. The predicted pose is not
aligned to the label before the error.

The reference is a frozen ``kind: placement`` row. The metric does not
measure warped or shrunken real parchment. The error includes the
difference between the page-origin rule recorded on the assembly envelope
and the generator's absolute rotation. ``Q-SCI-03``, ``Q-SCI-15``, and
``Q-SCI-20`` stay open.

N is the caller's integer. It is recorded before any label is treated as a
comparison target. This module has no function that chooses N from the
scored assemblies or from the errors. The first N assemblies are scored in
caller order. Assemblies past N are named as unscored. The report lists
every scored fragment's RMSE with its assembly id and fragment id. It does
not replace that list with a single best assembly, and it introduces no
pass threshold.

A caller-supplied correspondence maps a project fragment id to a fixture
fragment id. That correspondence is recorded in the report and is not
written into ``labels.json``. A fragment with no correspondence, a fragment
with no placement label, or an unplaced fragment is listed with no error
number. A polygon with no vertices refuses that fragment and writes no
error number for it. The module does not write 0 for those rows.

The report copies algorithm name ``rigid_assembly_search``, version ``1``,
the parameter hash, ``code_version``, ``model_hash`` ``absent``, the source
hashes, and the absence of ``random_seed`` from the cited assembly envelope.
It names the page-origin rule recorded on that envelope. It does not invent
a second envelope. The freeze identifier is the ``sha256:`` digest of the
label-file bytes. Join rows and page rows are not scored. The writer does
not open TIFF bytes and does not modify ``labels.json`` or ``provenance.json``.
"""

from __future__ import annotations

import json
import math
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from prw.identity import ABSENT, canonical_json_bytes, hash_value
from prw.joins import RigidTransform
from prw.provenance import AssemblyContent, ProvenanceEnvelope
from prw.synthetic_tear import _place, require_fixture_destination

_ALGORITHM_NAME = "rigid_assembly_search"
_ALGORITHM_VERSION = "1"
_NO_PREVIOUS = "No previous placement-error report exists."
_REPORT_DIRECTORY = "placement_error"
_REPORT_PREFIX = "placement-error-"
_DOES_NOT_MEASURE = "warped or shrunken real parchment"
_REFERENCE = "frozen kind: placement row"
_SCORED = "scored"
_NO_CORRESPONDENCE = "no_correspondence"
_NO_PLACEMENT_LABEL = "no_placement_label"
_UNPLACED = "unplaced"
_REFUSED = "refused"
_UNSCORED = "unscored"
_NO_ERROR_STATUSES = frozenset(
    {_NO_CORRESPONDENCE, _NO_PLACEMENT_LABEL, _UNPLACED, _REFUSED}
)
type Point = tuple[float, float]


def write_placement_error(
    benchmarks_dir: Path,
    *,
    envelope: ProvenanceEnvelope,
    ranked_assemblies: Sequence[AssemblyContent],
    poses: Sequence[RigidTransform],
    polygons: Mapping[uuid.UUID, Sequence[object]],
    n: int,
    correspondence: Mapping[uuid.UUID, uuid.UUID],
) -> Path:
    """Write one placement-error report under ``benchmarks_dir``.

    ``n`` is the caller's integer, greater than or equal to 1. It is recorded
    before any label is treated as a comparison target. ``ranked_assemblies``
    is the physical order from assembly rank. The first N rows are scored in
    that order. Assemblies past N are named as unscored. ``poses`` are the
    assembly placement transforms. ``polygons`` maps a project fragment id to
    local vertices in polygon order. ``correspondence`` maps project fragment
    ids to fixture fragment ids.

    See the placement-error section of ``docs/EVALUATION.md`` and ``_place``
    in ``src/prw/synthetic_tear.py``. The reference is a frozen
    ``kind: placement`` row. The metric does not measure warped or shrunken
    real parchment. The first report states that no previous placement-error
    report exists. A later report names the previous file, copies that file's
    error list, and leaves that file unchanged.
    """
    recorded_n = _require_n(n)
    _require_assembly_envelope(envelope)
    ranked = _ranked_assemblies(ranked_assemblies, envelope)
    pose_table = _pose_table(poses, envelope)
    local_polygons = _polygons(polygons)
    mapped = _correspondence(correspondence)
    page_origin = _page_origin(envelope)
    destination = _destination(benchmarks_dir)
    label_path = destination / "labels.json"
    label_bytes = _label_bytes(label_path)
    placement_rows = _placement_rows(label_bytes)
    error_list = _error_list(
        ranked[:recorded_n],
        pose_table,
        local_polygons,
        dict(mapped),
        placement_rows,
    )
    unscored = _unscored(ranked[recorded_n:])
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
        "page_origin": page_origin,
        "correspondence": [
            {
                "project_fragment_id": project_id,
                "fixture_fragment_id": fixture_id,
            }
            for project_id, fixture_id in mapped
        ],
        "reference": _REFERENCE,
        "metric": "placement_error",
        "unit": "root-mean-square error in page millimetres",
        "freeze_identifier": hash_value(label_bytes),
        "error_list": error_list,
        "unscored_assemblies": unscored,
        "error_includes": (
            "The error includes the difference between the page-origin rule "
            f"{page_origin} and the generator's absolute rotation."
        ),
        "does_not_measure": _DOES_NOT_MEASURE,
        "limiting_questions": ["Q-SCI-03", "Q-SCI-15", "Q-SCI-20"],
        "previous_report": ABSENT if previous is None else previous.name,
        "previous_report_statement": (
            _NO_PREVIOUS
            if previous is None
            else f"The previous placement-error report is {previous.name}."
        ),
    }
    if previous is not None:
        body["previous_error_list"] = _previous_error_list(previous)
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / _report_name(_next_index(report_dir))
    if path.name == "labels.json":
        raise ValueError("Overwriting labels.json is refused.")
    if path.exists():
        raise ValueError("A placement-error report is a new file.")
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


def _ranked_assemblies(
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


def _pose_table(
    poses: Sequence[RigidTransform],
    envelope: ProvenanceEnvelope,
) -> dict[uuid.UUID, RigidTransform]:
    if isinstance(poses, str | bytes) or not isinstance(poses, Sequence):
        raise TypeError("Assembly poses are RigidTransform rows.")
    table: dict[uuid.UUID, RigidTransform] = {}
    for pose in poses:
        if not isinstance(pose, RigidTransform):
            raise TypeError("Assembly poses are RigidTransform rows.")
        if pose.provenance_id != envelope.id:
            raise ValueError("The report copies the cited assembly envelope.")
        stored = table.get(pose.id)
        if stored is not None and stored != pose:
            raise ValueError("An assembly pose is supplied once.")
        table[pose.id] = pose
    return table


def _polygons(
    polygons: Mapping[uuid.UUID, Sequence[object]],
) -> dict[str, tuple[Point, ...]]:
    if not isinstance(polygons, Mapping):
        raise TypeError("Local polygons map a project fragment id to vertices.")
    stored: dict[str, tuple[Point, ...]] = {}
    for fragment_id, vertices in polygons.items():
        if not isinstance(fragment_id, uuid.UUID):
            raise TypeError("Local polygons map a project fragment id to vertices.")
        if isinstance(vertices, str | bytes) or not isinstance(vertices, Sequence):
            raise TypeError("A polygon is a sequence of vertices.")
        points = tuple(_point(vertex) for vertex in vertices)
        stored[str(fragment_id)] = points
    return stored


def _point(value: object) -> Point:
    if (
        isinstance(value, str | bytes)
        or not isinstance(value, Sequence)
        or len(value) != 2
    ):
        raise TypeError("A polygon vertex is a pair of finite numbers.")
    return (
        _finite(value[0], "A polygon vertex is a pair of finite numbers."),
        _finite(value[1], "A polygon vertex is a pair of finite numbers."),
    )


def _finite(value: object, message: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(message)
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(message)
    return number


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


def _page_origin(envelope: ProvenanceEnvelope) -> str:
    parsed = json.loads(envelope.parameter_blob)
    if not isinstance(parsed, dict):
        raise ValueError(
            "The report names the page-origin rule on the assembly envelope."
        )
    origin = parsed.get("page_origin")
    if not isinstance(origin, str) or origin == "":
        raise ValueError(
            "The report names the page-origin rule on the assembly envelope."
        )
    return origin


def _destination(path: Path) -> Path:
    if not isinstance(path, Path):
        raise TypeError(
            "A placement-error report is written under a benchmarks directory."
        )
    if path.name == "labels.json":
        raise ValueError("Overwriting labels.json is refused.")
    destination = require_fixture_destination(path)
    if destination.is_file():
        raise ValueError(
            "A placement-error report is written under a benchmarks directory."
        )
    return destination


def _label_bytes(path: Path) -> bytes:
    if not path.is_file():
        raise ValueError("A label file with no placement row is refused.")
    return path.read_bytes()


def _placement_rows(label_bytes: bytes) -> dict[str, dict[str, float]]:
    try:
        loaded = json.loads(label_bytes)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("A label file with no placement row is refused.") from exc
    if not isinstance(loaded, list):
        raise ValueError("A label file with no placement row is refused.")
    rows: dict[str, dict[str, float]] = {}
    for item in loaded:
        record = _record(item)
        if record.get("kind") != "placement":
            continue
        fragment_id = _uuid_text(record.get("fragment_id"))
        if fragment_id in rows:
            raise ValueError("A placement label cites one fragment.")
        rows[fragment_id] = {
            "rotation_radians": _label_number(record.get("rotation_radians")),
            "translation_x": _label_number(record.get("translation_x")),
            "translation_y": _label_number(record.get("translation_y")),
        }
    if not rows:
        raise ValueError("A label file with no placement row is refused.")
    return rows


def _record(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("A label file lists BenchmarkLabel rows.")
    stored: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError("A label file lists BenchmarkLabel rows.")
        stored[key] = item
    return stored


def _label_number(value: object) -> float:
    message = "A placement label records rotation and translation."
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(message)
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(message)
    return number


def _uuid_text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("A placement label cites one fragment.")
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise ValueError("A placement label cites one fragment.") from exc
    return str(parsed)


def _error_list(
    ranked: Sequence[AssemblyContent],
    poses: Mapping[uuid.UUID, RigidTransform],
    polygons: Mapping[str, tuple[Point, ...]],
    correspondence: Mapping[str, str],
    placement_rows: Mapping[str, Mapping[str, float]],
) -> list[dict[str, Any]]:
    listed: list[dict[str, Any]] = []
    for assembly in ranked:
        placed: set[uuid.UUID] = set()
        for placement in assembly.placements:
            listed.append(
                _fragment_error(
                    assembly.id,
                    placement.fragment_id,
                    placement.transform_id,
                    poses,
                    polygons,
                    correspondence,
                    placement_rows,
                    unplaced=False,
                )
            )
            placed.add(placement.fragment_id)
        for fragment_id in assembly.unplaced_fragment_ids:
            if fragment_id in placed:
                continue
            listed.append(
                _fragment_error(
                    assembly.id,
                    fragment_id,
                    None,
                    poses,
                    polygons,
                    correspondence,
                    placement_rows,
                    unplaced=True,
                )
            )
    return listed


def _fragment_error(
    assembly_id: uuid.UUID,
    fragment_id: uuid.UUID,
    transform_id: uuid.UUID | None,
    poses: Mapping[uuid.UUID, RigidTransform],
    polygons: Mapping[str, tuple[Point, ...]],
    correspondence: Mapping[str, str],
    placement_rows: Mapping[str, Mapping[str, float]],
    *,
    unplaced: bool,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "assembly_id": str(assembly_id),
        "fragment_id": str(fragment_id),
    }
    if unplaced:
        entry["status"] = _UNPLACED
        return entry
    vertices = polygons.get(str(fragment_id), ())
    if len(vertices) == 0:
        entry["status"] = _REFUSED
        return entry
    fixture_id = correspondence.get(str(fragment_id))
    if fixture_id is None:
        entry["status"] = _NO_CORRESPONDENCE
        return entry
    label = placement_rows.get(fixture_id)
    if label is None:
        entry["status"] = _NO_PLACEMENT_LABEL
        return entry
    if transform_id is None or transform_id not in poses:
        raise ValueError("A placed fragment cites its assembly pose.")
    pose = poses[transform_id]
    predicted = _place(
        vertices,
        pose.rotation_radians,
        (pose.translation_x, pose.translation_y),
    )
    reference = _place(
        vertices,
        label["rotation_radians"],
        (label["translation_x"], label["translation_y"]),
    )
    entry["status"] = _SCORED
    entry["rmse_mm"] = _rmse(predicted, reference)
    return entry


def _rmse(predicted: Sequence[Point], reference: Sequence[Point]) -> float:
    if len(predicted) == 0 or len(predicted) != len(reference):
        raise ValueError("RMSE pairs the caller-supplied vertices.")
    total = 0.0
    for (left_x, left_y), (right_x, right_y) in zip(predicted, reference, strict=True):
        total += (left_x - right_x) ** 2 + (left_y - right_y) ** 2
    return math.sqrt(total / len(predicted))


def _unscored(ranked: Sequence[AssemblyContent]) -> list[dict[str, str]]:
    return [
        {"assembly_id": str(assembly.id), "status": _UNSCORED} for assembly in ranked
    ]


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


def _previous_error_list(path: Path) -> list[dict[str, Any]]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("A placement-error report lists every scored fragment.")
    values = loaded.get("error_list")
    if not isinstance(values, list):
        raise ValueError("A placement-error report lists every scored fragment.")
    return [_copied_error(value) for value in values]


def _copied_error(value: object) -> dict[str, Any]:
    record = _record(value)
    assembly_id = record.get("assembly_id")
    fragment_id = record.get("fragment_id")
    status = record.get("status")
    if (
        not isinstance(assembly_id, str)
        or not isinstance(fragment_id, str)
        or status not in {_SCORED, *_NO_ERROR_STATUSES}
    ):
        raise ValueError("A placement-error report lists every scored fragment.")
    entry: dict[str, Any] = {
        "assembly_id": assembly_id,
        "fragment_id": fragment_id,
        "status": status,
    }
    if status == _SCORED:
        rmse = record.get("rmse_mm")
        if isinstance(rmse, bool) or not isinstance(rmse, int | float):
            raise ValueError("A placement-error report lists every scored fragment.")
        if isinstance(rmse, float) and not math.isfinite(rmse):
            raise ValueError("A placement-error report lists every scored fragment.")
        entry["rmse_mm"] = float(rmse)
        return entry
    if "rmse_mm" in record:
        raise ValueError("A placement-error report lists every scored fragment.")
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
