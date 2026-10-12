"""Headless console for ingest, frames, provenance, and fixture generation.

The use cases are ``prw.ingest``, ``prw.frames``, ``prw.provenance``,
``prw.synthetic_tear``, ``prw.segment``, ``prw.scale``, and
``prw.outline_agreement``. Command names and flags are unfrozen. They are
not a stable interface. The project format is still Q-ENG-01 in
``docs/OPEN_QUESTIONS.md``. This module does not import Qt, does not open a
network connection, does not start a worker, and does not write
``manifest.json`` or ``originals/``. An absent ``fragment-<integer>.tif`` is
the fragment at that index in the sibling ``image_manifest.json``. An
existing file is read as given.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from prw.fixture_tiff import UnsupportedFixtureLayout
from prw.frames import CoordinateFrame
from prw.identity import ABSENT, canonical_json, content_id
from prw.ingest import (
    IntegrityFailure,
    UnsupportedMediaType,
    VerifiedBytes,
    ingest_bytes,
)
from prw.outline_agreement import write_outline_agreement
from prw.outlines import FragmentOutlineRevision
from prw.provenance import ProvenanceEnvelope
from prw.scale import CallerScale, ScaledOutline, ScaleLog
from prw.segment import FailedSegmentation, SegmentationLog, SegmentedOutline
from prw.synthetic_tear import generate_synthetic_leaf


def main(argv: Sequence[str] | None = None) -> int:
    """Run one unfrozen command and return a process status."""
    parser = _parser()
    args = parser.parse_args(None if argv is None else list(argv))
    try:
        return int(_COMMANDS[args.command](args))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prw",
        description=(
            "Headless calls for ingest, frames, provenance, the synthetic "
            "fixture generator, segmentation, caller-supplied scale, and "
            "outline agreement. Command names are unfrozen and are not a "
            "stable interface. The project format is still Q-ENG-01."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    verify = commands.add_parser(
        "verify",
        help="Hash a TIFF and print the content hash or an IntegrityFailure.",
    )
    verify.add_argument("path", type=Path)
    verify.add_argument("--expected", default=None)

    frame = commands.add_parser(
        "frame",
        help="Print a fragment_local_mm frame for a polygon.",
    )
    frame.add_argument("--polygon", nargs="+", required=True, metavar="X,Y")

    provenance = commands.add_parser(
        "provenance",
        help="Print one provenance envelope. Omit --random-seed when deterministic.",
    )
    provenance.add_argument("--algorithm-name", required=True)
    provenance.add_argument("--algorithm-version", required=True)
    provenance.add_argument("--code-version", required=True)
    provenance.add_argument("--parameter", action="append", default=[])
    provenance.add_argument("--decoder-name", default=ABSENT)
    provenance.add_argument("--decoder-version", default=ABSENT)
    provenance.add_argument("--random-seed", type=int, default=None)

    generate = commands.add_parser(
        "generate",
        help="Write fixture images, the image manifest, and BenchmarkLabel rows.",
    )
    generate.add_argument("--benchmarks", type=Path, required=True)
    generate.add_argument("--images", type=Path, required=True)
    generate.add_argument("--missing-fragment-percentage", type=float, required=True)
    generate.add_argument("--edge-erosion", type=float, required=True)
    generate.add_argument("--rotation", type=float, required=True)
    generate.add_argument("--lighting-variation", type=float, required=True)
    generate.add_argument("--random-seed", type=int, required=True)
    generate.add_argument("--code-version", required=True)

    segment = commands.add_parser(
        "segment",
        help="Print one fragment outline. Unfrozen; not a stable interface.",
    )
    _add_segment_arguments(segment)
    segment.add_argument("--pixels-per-mm", type=float, default=None)
    segment.add_argument("--uncertainty", type=float, default=None)

    agree = commands.add_parser(
        "agree",
        help=("Score the segmented outline against a caller polygon. Unfrozen."),
    )
    agree.add_argument("--benchmarks", type=Path, required=True)
    agree.add_argument(
        "--reference",
        action="append",
        required=True,
        metavar="X,Y",
        help="One vertex of the reference polygon. Repeat for each vertex.",
    )
    agree.add_argument("--frame", required=True)
    _add_segment_arguments(agree)
    return parser


def _add_segment_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", type=Path)
    parser.add_argument("--expected", default=None)
    parser.add_argument("--label", required=True)
    parser.add_argument("--foreground-threshold", type=int, required=True)
    parser.add_argument("--code-version", required=True)


def _presented_bytes(path: Path) -> bytes:
    """Read one fixture image.

    An existing file is read as given. ``fragment-<integer>.tif`` is the
    fragment at that index in the sibling ``image_manifest.json`` when that
    file is absent. The caller receives bytes. Segmentation does not open
    the manifest or a BenchmarkLabel file.
    """
    resolved = _resolve_image(path)
    try:
        return resolved.read_bytes()
    except OSError as exc:
        raise ValueError(_missing_image_message(path)) from exc


def _resolve_image(path: Path) -> Path:
    if path.is_file():
        return path
    index = _ordinal_fragment_index(path.name)
    manifest_path = path.parent / "image_manifest.json"
    if index is None or not manifest_path.is_file():
        return path
    names = _manifest_fragment_names(manifest_path)
    if index >= len(names):
        raise ValueError(_missing_image_message(path, names))
    return path.parent / names[index]


def _ordinal_fragment_index(name: str) -> int | None:
    stem, separator, suffix = name.rpartition(".")
    if separator != "." or suffix != "tif" or not stem.startswith("fragment-"):
        return None
    digits = stem.removeprefix("fragment-")
    if digits == "" or not digits.isdecimal():
        return None
    return int(digits)


def _manifest_fragment_names(path: Path) -> list[str]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("An image manifest is JSON.") from exc
    images = loaded.get("images") if isinstance(loaded, dict) else None
    if not isinstance(images, list):
        raise ValueError("An image manifest lists images.")
    names: list[str] = []
    for entry in images:
        if not isinstance(entry, dict):
            raise ValueError("An image manifest lists images.")
        if entry.get("role") != "fragment":
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not _is_fragment_file_name(name):
            raise ValueError("An image manifest names each fragment file.")
        names.append(name)
    return names


def _is_fragment_file_name(name: str) -> bool:
    return (
        name == Path(name).name
        and name.startswith("fragment-")
        and name.endswith(".tif")
        and name != "fragment-.tif"
    )


def _fragment_names(directory: Path) -> list[str]:
    manifest_path = directory / "image_manifest.json"
    if manifest_path.is_file():
        return _manifest_fragment_names(manifest_path)
    if not directory.is_dir():
        return []
    return sorted(
        path.name
        for path in directory.iterdir()
        if path.is_file() and _is_fragment_file_name(path.name)
    )


def _missing_image_message(path: Path, names: Sequence[str] | None = None) -> str:
    present = list(names) if names is not None else _fragment_names(path.parent)
    if not present:
        return f"{path} is not a fixture image."
    listed = ", ".join(present)
    return f"{path} is not a fixture image. Fragment files: {listed}."


def _cmd_verify(args: argparse.Namespace) -> int:
    presented = _presented_bytes(args.path)
    result = ingest_bytes(presented, expected_hash=args.expected)
    if isinstance(result, VerifiedBytes):
        _print_record(
            {
                "record": "VerifiedBytes",
                "content_hash": result.content_hash,
                "byte_length": result.byte_length,
                "media_type": result.media_type,
                "id": result.id,
            }
        )
        return 0
    if isinstance(result, IntegrityFailure):
        _print_record(
            {
                "record": "IntegrityFailure",
                "id": result.id,
                "source_image_id": result.source_image_id,
                "presented_hash": result.presented_hash,
                "expected_hash": result.expected_hash,
                "timestamp": result.timestamp,
            }
        )
        return 1
    if isinstance(result, UnsupportedMediaType):
        _print_record(
            {
                "record": "UnsupportedMediaType",
                "presented_hash": result.presented_hash,
                "byte_length": result.byte_length,
            }
        )
        return 1
    raise ValueError("Ingest returned an unknown record.")


def _cmd_frame(args: argparse.Namespace) -> int:
    polygon = tuple(_parse_point(item) for item in args.polygon)
    if len(polygon) < 3:
        raise ValueError("A fragment polygon has at least three vertices.")
    owner_id = content_id({"kind": "cli-fragment", "polygon": polygon})
    outline_id = content_id({"kind": "cli-outline", "polygon": polygon})
    frame = CoordinateFrame.fragment_local_mm(
        owner_id=owner_id,
        establishing_outline_revision_id=outline_id,
        polygon=polygon,
    )
    payload = frame.content_mapping()
    payload["id"] = frame.id
    _print_record(payload)
    return 0


def _cmd_provenance(args: argparse.Namespace) -> int:
    envelope = ProvenanceEnvelope.create(
        source_hashes=(),
        parameters=_parse_parameters(args.parameter),
        algorithm_name=args.algorithm_name,
        algorithm_version=args.algorithm_version,
        code_version=args.code_version,
        decoder_name=args.decoder_name,
        decoder_version=args.decoder_version,
        model_hash=ABSENT,
        random_seed=args.random_seed,
    )
    _print_envelope(envelope)
    return 0


def _cmd_segment(args: argparse.Namespace) -> int:
    presented = _presented_bytes(args.path)
    segmented = _segment_presented(args, presented)
    if not isinstance(segmented, SegmentedOutline):
        _print_failure(segmented)
        return 1
    if args.pixels_per_mm is None and args.uncertainty is None:
        _print_outline(
            segmented.outline,
            frame=segmented.frame.kind,
            envelope=segmented.run.provenance,
        )
        return 0
    if args.pixels_per_mm is None or args.uncertainty is None:
        raise ValueError("pixels_per_mm and uncertainty are supplied together.")
    scaled = ScaleLog().apply(
        segmented.outline,
        segmented.frame,
        CallerScale(
            pixels_per_mm=args.pixels_per_mm,
            uncertainty=args.uncertainty,
            producer="human",
        ),
        source_hashes=segmented.run.provenance.source_hashes,
        code_version=segmented.run.provenance.code_version,
        decoder_name=segmented.run.provenance.decoder_name,
        decoder_version=segmented.run.provenance.decoder_version,
        recorded_at=_utc_now(),
    )
    if not isinstance(scaled, ScaledOutline):
        raise ValueError("A supplied scale stores a millimetre outline.")
    _print_outline(
        scaled.outline,
        frame=scaled.frame.kind,
        envelope=scaled.run.provenance,
    )
    return 0


def _cmd_agree(args: argparse.Namespace) -> int:
    _refuse_benchmark_label_join(args.benchmarks)
    presented = _presented_bytes(args.path)
    segmented = _segment_presented(args, presented)
    if not isinstance(segmented, SegmentedOutline):
        _print_failure(segmented)
        return 1
    if args.frame != segmented.frame.kind:
        raise ValueError("Outline agreement uses the segmented outline's frame.")
    report = write_outline_agreement(
        args.benchmarks,
        envelope=segmented.run.provenance,
        frame=segmented.frame.kind,
        pairs=[(segmented.outline.polygon, _polygon_arg(args.reference))],
        fixture_image_hashes=segmented.run.provenance.source_hashes,
    )
    _print_record(json.loads(report.read_text(encoding="utf-8")))
    return 0


def _segment_presented(args: argparse.Namespace, presented: bytes) -> Any:
    return SegmentationLog().segment(
        presented,
        project_id=content_id(["cli-segment", args.label]),
        label=args.label,
        foreground_threshold=args.foreground_threshold,
        code_version=args.code_version,
        recorded_at=_utc_now(),
        expected_hash=args.expected,
    )


def _print_outline(
    outline: FragmentOutlineRevision,
    *,
    frame: str,
    envelope: ProvenanceEnvelope,
) -> None:
    _print_record(
        {
            "record": "FragmentOutlineRevision",
            "epistemic_class": outline.epistemic_class,
            "producer": outline.producer,
            "frame": frame,
            "polygon": outline.polygon,
            "id": outline.id,
            "envelope": _envelope_payload(envelope),
        }
    )


def _print_failure(result: object) -> None:
    if isinstance(result, IntegrityFailure):
        _print_record(
            {
                "record": "IntegrityFailure",
                "id": result.id,
                "source_image_id": result.source_image_id,
                "presented_hash": result.presented_hash,
                "expected_hash": result.expected_hash,
                "timestamp": result.timestamp,
            }
        )
        return
    if isinstance(result, UnsupportedMediaType):
        _print_record(
            {
                "record": "UnsupportedMediaType",
                "presented_hash": result.presented_hash,
                "byte_length": result.byte_length,
            }
        )
        return
    if isinstance(result, UnsupportedFixtureLayout):
        _print_record({"record": "UnsupportedFixtureLayout", "kind": result.kind})
        return
    if isinstance(result, FailedSegmentation):
        _print_record(
            {
                "record": "FailedSegmentation",
                "kind": result.kind,
                "run_id": result.run.id,
            }
        )
        return
    raise ValueError("Segmentation returned an unknown record.")


def _refuse_benchmark_label_join(path: Path) -> None:
    if not path.is_file():
        return
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            "An outline-agreement path is a benchmarks directory."
        ) from exc
    if _contains_join_label(loaded):
        raise ValueError("A BenchmarkLabel join file is not an outline-agreement path.")
    raise ValueError("An outline-agreement path is a benchmarks directory.")


def _contains_join_label(value: object) -> bool:
    if isinstance(value, dict):
        return value.get("kind") == "join"
    if isinstance(value, list):
        return any(
            isinstance(item, dict) and item.get("kind") == "join" for item in value
        )
    return False


def _polygon_arg(values: Sequence[str]) -> tuple[tuple[float, float], ...]:
    polygon = tuple(_parse_point(item) for item in values)
    if len(polygon) < 3:
        raise ValueError("A polygon has at least three vertices.")
    return polygon


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cmd_generate(args: argparse.Namespace) -> int:
    leaf = generate_synthetic_leaf(
        args.benchmarks,
        images_dir=args.images,
        missing_fragment_percentage=args.missing_fragment_percentage,
        edge_erosion=args.edge_erosion,
        rotation=args.rotation,
        lighting_variation=args.lighting_variation,
        random_seed=args.random_seed,
        code_version=args.code_version,
    )
    provenance = leaf.envelope.content_mapping()
    provenance["id"] = leaf.envelope.id
    _print_record(
        {
            "provenance": provenance,
            "images": [
                {
                    "name": image.name,
                    "role": image.role,
                    "content_hash": image.content_hash,
                    "byte_length": image.byte_length,
                }
                for image in leaf.images
            ],
        }
    )
    return 0


def _print_envelope(envelope: ProvenanceEnvelope) -> None:
    _print_record(_envelope_payload(envelope))


def _envelope_payload(envelope: ProvenanceEnvelope) -> dict[str, Any]:
    payload = envelope.content_mapping()
    payload["id"] = envelope.id
    return payload


def _print_record(payload: dict[str, Any]) -> None:
    print(canonical_json(payload))


def _parse_parameters(pairs: Sequence[str]) -> dict[str, Any]:
    parameters: dict[str, Any] = {}
    for pair in pairs:
        name, separator, raw = pair.partition("=")
        if separator != "=" or name == "":
            raise ValueError("A parameter is name=json.")
        if name in parameters:
            raise ValueError("A parameter name is given once.")
        try:
            parameters[name] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("A parameter value is JSON.") from exc
    return parameters


def _parse_point(text: str) -> tuple[float, float]:
    left, separator, right = text.partition(",")
    if separator != "," or left == "" or right == "":
        raise ValueError("A polygon vertex is x,y.")
    try:
        return (float(left), float(right))
    except ValueError as exc:
        raise ValueError("A polygon vertex is x,y.") from exc


_COMMANDS = {
    "verify": _cmd_verify,
    "frame": _cmd_frame,
    "provenance": _cmd_provenance,
    "generate": _cmd_generate,
    "segment": _cmd_segment,
    "agree": _cmd_agree,
}


if __name__ == "__main__":
    raise SystemExit(main())
