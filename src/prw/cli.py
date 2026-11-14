"""Headless console for ingest, frames, provenance, and fixture generation.

The use cases are ``prw.ingest``, ``prw.frames``, ``prw.provenance``,
``prw.synthetic_tear``, ``prw.segment``, ``prw.scale``,
``prw.outline_agreement``, ``prw.edge_chord``, ``prw.pairwise_join``,
``prw.join_rank``, ``prw.join_recall``, ``prw.assembly_search``,
``prw.assembly_rank``, ``prw.placement_error``,
``prw.assembly_join_presence``, and ``prw.recognize``. Command names and
flags are unfrozen. They are not a stable interface. The project format
is still Q-ENG-01 in ``docs/OPEN_QUESTIONS.md``. This module does not
import Qt, does not open a network connection, does not start a worker,
and does not write ``manifest.json`` or ``originals/``. A pool image is
one repeated flag with a label and an existing path. A missing path is
an error that lists the fragment names in the sibling
``image_manifest.json``. The recognizer reads one operator-supplied line
image and a local ``medium.safetensors`` file. It does not download
weights.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from prw.assembly_join_presence import AssemblyFixture, write_assembly_join_presence
from prw.assembly_rank import physical_assembly_order
from prw.assembly_search import (
    AssemblySearch,
    AssemblySearchLog,
    FailedAssemblySearch,
    FragmentOutline,
)
from prw.edge_chord import ChordEdges, EdgeChordLog, FailedEdgeChord
from prw.frames import CoordinateFrame, PageFrame
from prw.identity import ABSENT, canonical_json, content_id
from prw.ingest import (
    IntegrityFailure,
    UnsupportedMediaType,
    VerifiedBytes,
    ingest_bytes,
)
from prw.join_rank import physical_join_order
from prw.join_recall import write_join_recall
from prw.joins import JoinHypothesis
from prw.lossless_tiff import TiffDecodeFailure
from prw.outline_agreement import write_outline_agreement
from prw.outlines import Fragment, FragmentOutlineRevision
from prw.pairwise_join import (
    FailedPairwiseJoin,
    FragmentChords,
    PairwiseJoinLog,
    PairwiseJoins,
)
from prw.placement_error import write_placement_error
from prw.provenance import (
    AlgorithmRun,
    AssemblyContent,
    ProvenanceEnvelope,
    StatusEvent,
    StatusStream,
)
from prw.recognize import (
    FailedLineRecognition,
    HtrGroupMissing,
    LineRecognition,
    LineRecognitionLog,
    PreparedLine,
    predict_line_text,
    prepare_line_image,
    require_htr_group,
    require_weight_path,
)
from prw.scale import (
    CallerScale,
    ClaimedResolution,
    ScaledOutline,
    ScaleLog,
    record_claimed_resolution,
)
from prw.segment import (
    FILL_WITHOUT_4_INTERIOR,
    NOT_ABOVE_FRAME_SPLIT,
    FailedSegmentation,
    SegmentationLog,
    SegmentedOutline,
    pool_project_id,
)
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
            "fixture generator, segmentation, caller-supplied scale, outline "
            "agreement, chord edges, pairwise joins, join recall, assembly "
            "search, assembly rank, placement error, end-to-end join "
            "presence, and line recognition. Command names are unfrozen "
            "and are not a stable interface. The project format is still "
            "Q-ENG-01."
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
    _add_scale_arguments(segment)

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

    edge = commands.add_parser(
        "edge",
        help="Print chord edges for one outline. Unfrozen; not a stable interface.",
    )
    _add_segment_arguments(edge)
    _add_scale_arguments(edge)
    edge.add_argument("--minimum-edge-length-mm", type=float, default=0.0)

    rank = commands.add_parser(
        "rank",
        help="Print pairwise joins in physical order. Unfrozen.",
    )
    _add_pool_arguments(rank)

    recall = commands.add_parser(
        "recall",
        help="Write join recall at K. Unfrozen; not a stable interface.",
    )
    _add_pool_arguments(recall)
    recall.add_argument("--benchmarks", type=Path, required=True)
    recall.add_argument("--k", type=int, required=True)
    recall.add_argument("--correspondence", action="append", default=None)

    assemble = commands.add_parser(
        "assemble",
        help="Print rigid assembly search. Unfrozen; not a stable interface.",
    )
    _add_assembly_arguments(assemble)

    assembly_rank = commands.add_parser(
        "assembly-rank",
        help="Print assemblies in physical order. Unfrozen; not a stable interface.",
    )
    _add_assembly_arguments(assembly_rank)

    placement = commands.add_parser(
        "placement-error",
        help="Write a placement-error report. Unfrozen; not a stable interface.",
    )
    _add_assembly_arguments(placement)
    _add_report_arguments(placement)

    presence = commands.add_parser(
        "join-presence",
        help=(
            "Write an end-to-end join-presence report. "
            "Unfrozen; not a stable interface."
        ),
    )
    _add_assembly_arguments(presence)
    _add_report_arguments(presence)

    recognize = commands.add_parser(
        "recognize",
        help=(
            "Recognize one operator-supplied line image. "
            "Unfrozen; not a stable interface."
        ),
    )
    recognize.add_argument("path", type=Path)
    recognize.add_argument("--model", type=Path, required=True)
    recognize.add_argument("--label", required=True)
    recognize.add_argument("--code-version", required=True)
    recognize.add_argument("--script", default="Grek")
    recognize.add_argument("--language", default="grc")
    recognize.add_argument("--expected", default=None)
    return parser


def _add_scale_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--pixels-per-mm", type=float, default=None)
    parser.add_argument("--uncertainty", type=float, default=None)
    parser.add_argument(
        "--claimed-ppi",
        type=float,
        default=None,
        help=(
            "Operator-supplied claimed resolution in pixels per inch. "
            "Not a measured pixels_per_mm, and not read from the file header."
        ),
    )


def _add_assembly_arguments(parser: argparse.ArgumentParser) -> None:
    _add_pool_arguments(parser)
    parser.add_argument("--n", type=int, default=None)
    parser.add_argument("--translation-tolerance-mm", type=float, default=None)
    parser.add_argument("--rotation-tolerance-radians", type=float, default=None)
    parser.add_argument("--min-width-mm", type=float, default=None)
    parser.add_argument("--max-width-mm", type=float, default=None)
    parser.add_argument("--min-height-mm", type=float, default=None)
    parser.add_argument("--max-height-mm", type=float, default=None)


def _add_report_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--benchmarks", type=Path, required=True)
    parser.add_argument("--correspondence", action="append", default=None)


def _add_pool_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--image",
        action="append",
        nargs=2,
        required=True,
        metavar=("LABEL", "PATH"),
        dest="images",
        help=("One pool image: a label and an existing path. Repeat for each image."),
    )
    parser.add_argument("--foreground-threshold", type=int, required=True)
    parser.add_argument("--code-version", required=True)
    _add_enclosed_background_argument(parser)
    _add_border_mount_argument(parser)
    _add_scale_arguments(parser)
    parser.add_argument("--minimum-edge-length-mm", type=float, default=0.0)


def _add_border_mount_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--border-mount-treatment",
        default=None,
        choices=(NOT_ABOVE_FRAME_SPLIT,),
        help=(
            "Reclassify the border-connected darker side of the frame's "
            "Otsu split as background. Omit to leave the threshold mask "
            "unchanged."
        ),
    )


def _add_enclosed_background_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--enclosed-background-treatment",
        default=None,
        choices=(FILL_WITHOUT_4_INTERIOR,),
        help=(
            "Fill enclosed background that does not contain a 4-interior "
            "pixel. Omit to leave the hole check unchanged."
        ),
    )


def _add_segment_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", type=Path)
    parser.add_argument("--expected", default=None)
    parser.add_argument("--label", required=True)
    parser.add_argument("--foreground-threshold", type=int, required=True)
    parser.add_argument("--code-version", required=True)
    _add_enclosed_background_argument(parser)
    _add_border_mount_argument(parser)


def _presented_bytes(path: Path) -> bytes:
    """Read one fixture image that exists on disk.

    A missing path is an error that lists the fragment names in the sibling
    image manifest. This reader does not open a BenchmarkLabel file.
    """
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ValueError(_missing_image_message(path)) from exc


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


def _cmd_recognize(args: argparse.Namespace) -> int:
    weight_path = require_weight_path(args.model)
    try:
        runtime_version = require_htr_group()
    except HtrGroupMissing as exc:
        raise ValueError(str(exc)) from exc
    presented = _line_image_bytes(args.path)
    prepared = prepare_line_image(presented, expected_hash=args.expected)
    if not isinstance(prepared, PreparedLine):
        _print_failure(prepared)
        return 1
    weight_bytes = weight_path.read_bytes()
    try:
        prediction = predict_line_text(presented, weight_path)
    except Exception as exc:
        failed = LineRecognitionLog().fail(
            prepared,
            weight_bytes=weight_bytes,
            label=args.label,
            script=args.script,
            language=args.language,
            code_version=args.code_version,
            runtime_version=runtime_version,
            recorded_at=_utc_now(),
            detail=f"{type(exc).__name__}: {exc}",
        )
        _print_failed_recognition(failed)
        return 1
    stored = LineRecognitionLog().store(
        prepared,
        weight_bytes=weight_bytes,
        prediction=prediction,
        label=args.label,
        script=args.script,
        language=args.language,
        code_version=args.code_version,
        runtime_version=runtime_version,
        recorded_at=_utc_now(),
    )
    _print_recognition(stored)
    return 0


def _line_image_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ValueError(f"{path} is not a line image.") from exc


def _print_recognition(result: LineRecognition) -> None:
    _print_record(
        {
            "record": "ReadingHypothesis",
            "epistemic_class": result.reading.epistemic_class,
            "producer": result.reading.producer,
            "script": result.reading.script,
            "language": result.reading.language,
            "text": result.reading.text,
            "anchor_id": result.reading.anchor_id,
            "graphemes": [
                {
                    "text": item.text,
                    "text_status": item.text_status,
                    "epistemic_class": item.epistemic_class,
                    "producer": item.producer,
                }
                for item in result.graphemes
            ],
            "id": result.reading.id,
            "envelope": _envelope_payload(result.run.provenance),
        }
    )


def _print_failed_recognition(result: FailedLineRecognition) -> None:
    _print_record(
        {
            "record": "FailedLineRecognition",
            "status": "failed",
            "run_id": result.run.id,
            "detail": result.detail,
            "envelope": _envelope_payload(result.run.provenance),
        }
    )


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
    _require_scale_choice(args)
    presented = _presented_bytes(args.path)
    segmented = _segment_presented(args, presented)
    if not isinstance(segmented, SegmentedOutline):
        _print_failure(segmented, args)
        return 1
    claim = _claim_for_provenance(args, segmented.run.provenance)
    if args.pixels_per_mm is None:
        _print_outline(
            segmented.outline,
            frame=segmented.frame.kind,
            envelope=segmented.run.provenance,
            claim=claim,
        )
        return 0
    scaled = _apply_scale(segmented, args)
    _print_outline(
        scaled.outline,
        frame=scaled.frame.kind,
        envelope=scaled.run.provenance,
    )
    return 0


def _cmd_edge(args: argparse.Namespace) -> int:
    _require_scale_choice(args)
    presented = _presented_bytes(args.path)
    segmented = _segment_presented(args, presented)
    if not isinstance(segmented, SegmentedOutline):
        _print_failure(segmented, args)
        return 1
    claim = _claim_for_provenance(args, segmented.run.provenance)
    if args.pixels_per_mm is None:
        traced = _trace(
            segmented.outline,
            segmented.frame,
            segmented.run.provenance,
            args,
        )
    else:
        scaled = _apply_scale(segmented, args)
        traced = _trace(scaled.outline, scaled.frame, scaled.run.provenance, args)
    if isinstance(traced, FailedEdgeChord):
        _print_run_failure("FailedEdgeChord", traced.run.id, claim)
        return 1
    _print_edges(traced)
    return 0


def _cmd_rank(args: argparse.Namespace) -> int:
    prepared = _pool(args, "A BenchmarkLabel join file is not a rank path.")
    if isinstance(prepared, int):
        return prepared
    result = PairwiseJoinLog().propose(
        prepared,
        code_version=args.code_version,
        recorded_at=_utc_now(),
    )
    if isinstance(result, FailedPairwiseJoin):
        _print_run_failure(
            "FailedPairwiseJoin",
            result.run.id,
            _claim_for_chords(args, prepared),
        )
        return 1
    if _claimed_ppi(args) is not None:
        raise ValueError("A claimed resolution does not emit a join.")
    _print_ranked(
        result,
        physical_join_order(result.joins, (result.run,), result.proposed),
    )
    return 0


def _cmd_recall(args: argparse.Namespace) -> int:
    _require_scale_choice(args)
    _refuse_claimed_calibration(args)
    prepared = _pool(args, "A BenchmarkLabel join file is not a recall path.")
    if isinstance(prepared, int):
        return prepared
    result = PairwiseJoinLog().propose(
        prepared,
        code_version=args.code_version,
        recorded_at=_utc_now(),
    )
    if isinstance(result, FailedPairwiseJoin):
        _print_run_failure("FailedPairwiseJoin", result.run.id)
        return 1
    ordered = physical_join_order(result.joins, (result.run,), result.proposed)
    report = write_join_recall(
        args.benchmarks,
        envelope=result.run.provenance,
        ranked_joins=ordered,
        k=args.k,
        correspondence=_correspondence_map(args.correspondence, prepared),
    )
    _print_record(json.loads(report.read_text(encoding="utf-8")))
    return 0


@dataclass(frozen=True, slots=True)
class _MillimetrePool:
    """Scaled outlines and the chords used to propose joins."""

    chords: tuple[FragmentChords, ...]
    outlines: tuple[FragmentOutline, ...]


@dataclass(frozen=True, slots=True)
class _AssemblyInputs:
    """Joins and millimetre outlines for one assembly command.

    ``joins`` are the pairwise rows. They are not BenchmarkLabel rows.
    """

    joins: PairwiseJoins
    outlines: tuple[FragmentOutline, ...]
    chords: tuple[FragmentChords, ...]


def _cmd_assemble(args: argparse.Namespace) -> int:
    prepared = _assembly_search(
        args, "A BenchmarkLabel join file is not an assembly-search path."
    )
    if isinstance(prepared, int):
        return prepared
    result = prepared[0]
    if isinstance(result, FailedAssemblySearch):
        _print_run_failure("FailedAssemblySearch", result.run.id)
        return 1
    _print_assembly_search(result)
    return 0


def _cmd_assembly_rank(args: argparse.Namespace) -> int:
    prepared = _assembly_search(
        args, "A BenchmarkLabel join file is not an assembly-rank path."
    )
    if isinstance(prepared, int):
        return prepared
    result = prepared[0]
    if isinstance(result, FailedAssemblySearch):
        _print_run_failure("FailedAssemblySearch", result.run.id)
        return 1
    ordered = _ordered_assemblies(result.assemblies, (result.run,), result.proposed)
    _print_record(
        {
            "record": "physical_assembly_order",
            "assemblies": [_assembly_payload(assembly) for assembly in ordered],
            "envelope": _envelope_payload(result.run.provenance),
        }
    )
    return 0


def _ordered_assemblies(
    hypotheses: Sequence[object],
    runs: Sequence[AlgorithmRun],
    events: StatusStream | Sequence[StatusEvent],
) -> tuple[AssemblyContent, ...]:
    """Return the physical assembly order.

    A join in ``hypotheses`` is refused. Rank is not stored on the assembly.
    """
    return physical_assembly_order(hypotheses, runs, events)


def _cmd_placement_error(args: argparse.Namespace) -> int:
    prepared = _assembly_search(
        args, "A BenchmarkLabel join file is not a placement-error path."
    )
    if isinstance(prepared, int):
        return prepared
    completed = _completed_search(prepared)
    if isinstance(completed, int):
        return completed
    result, inputs = completed
    if not isinstance(args.n, int) or isinstance(args.n, bool):
        raise ValueError("N is an integer greater than or equal to 1.")
    report = write_placement_error(
        args.benchmarks,
        envelope=result.run.provenance,
        ranked_assemblies=result.assemblies,
        poses=result.poses,
        polygons={item.fragment.id: item.outline.polygon for item in inputs.outlines},
        n=args.n,
        correspondence=_correspondence_map(args.correspondence, inputs.chords),
    )
    _print_record(json.loads(report.read_text(encoding="utf-8")))
    return 0


def _cmd_join_presence(args: argparse.Namespace) -> int:
    prepared = _assembly_search(
        args, "A BenchmarkLabel join file is not a join-presence path."
    )
    if isinstance(prepared, int):
        return prepared
    completed = _completed_search(prepared)
    if isinstance(completed, int):
        return completed
    result, inputs = completed
    if not isinstance(args.n, int) or isinstance(args.n, bool):
        raise ValueError("N is an integer greater than or equal to 1.")
    report = write_assembly_join_presence(
        args.benchmarks,
        envelope=result.run.provenance,
        fixtures=(
            AssemblyFixture(
                label_file=args.benchmarks / "labels.json",
                assemblies=result.assemblies,
                joins=inputs.joins.joins,
                correspondence=_correspondence_map(args.correspondence, inputs.chords),
            ),
        ),
        n=args.n,
    )
    _print_record(json.loads(report.read_text(encoding="utf-8")))
    return 0


def _assembly_search(
    args: argparse.Namespace,
    refuse_message: str,
) -> tuple[AssemblySearch | FailedAssemblySearch, _AssemblyInputs | None] | int:
    """Search assemblies from the image pool.

    A BenchmarkLabel path is refused before the search. Label rows are not
    passed into ``prw.assembly_search``. A missing page frame, a missing N,
    or a non-millimetre outline fails the search and emits no placement.
    """
    for path, _label in _image_pairs(args.images):
        _refuse_join_label_path(path, refuse_message)
    _require_scale_choice(args)
    _refuse_claimed_calibration(args)
    page = _page_frame(args)
    if args.pixels_per_mm is None or page is None:
        return (_failed_assembly_search(args), None)
    built = _millimetre_pool(args)
    if isinstance(built, int):
        return built
    proposed = PairwiseJoinLog().propose(
        built.chords,
        code_version=args.code_version,
        recorded_at=_utc_now(),
    )
    if isinstance(proposed, FailedPairwiseJoin):
        _print_run_failure("FailedPairwiseJoin", proposed.run.id)
        return 1
    searched = AssemblySearchLog().search(
        proposed.joins,
        proposed.transforms,
        (proposed.run,),
        proposed.proposed,
        built.outlines,
        page[0],
        page[1],
        n=args.n,
        translation_tolerance_mm=args.translation_tolerance_mm,
        rotation_tolerance_radians=args.rotation_tolerance_radians,
        code_version=args.code_version,
        recorded_at=_utc_now(),
    )
    return (searched, _AssemblyInputs(proposed, built.outlines, built.chords))


def _completed_search(
    prepared: tuple[AssemblySearch | FailedAssemblySearch, _AssemblyInputs | None],
) -> tuple[AssemblySearch, _AssemblyInputs] | int:
    result, inputs = prepared
    if isinstance(result, FailedAssemblySearch):
        _print_run_failure("FailedAssemblySearch", result.run.id)
        return 1
    if inputs is None:
        raise ValueError("A completed assembly search cites its outlines.")
    return (result, inputs)


def _failed_assembly_search(args: argparse.Namespace) -> FailedAssemblySearch:
    result = AssemblySearchLog().search(
        (),
        (),
        (),
        (),
        (),
        None,
        None,
        n=args.n,
        translation_tolerance_mm=args.translation_tolerance_mm,
        rotation_tolerance_radians=args.rotation_tolerance_radians,
        code_version=args.code_version,
        recorded_at=_utc_now(),
    )
    if not isinstance(result, FailedAssemblySearch):
        raise ValueError("A missing page frame emits no placement.")
    return result


def _millimetre_pool(args: argparse.Namespace) -> _MillimetrePool | int:
    chords: list[FragmentChords] = []
    outlines: list[FragmentOutline] = []
    for path, label in _image_pairs(args.images):
        presented = _presented_bytes(path)
        segmented = _segment_presented(args, presented, label)
        if not isinstance(segmented, SegmentedOutline):
            _print_failure(segmented, args)
            return 1
        scaled = _apply_scale(segmented, args)
        traced = _trace(scaled.outline, scaled.frame, scaled.run.provenance, args)
        if isinstance(traced, FailedEdgeChord):
            _print_run_failure("FailedEdgeChord", traced.run.id)
            return 1
        fragment = segmented.fragment.confirm()
        chords.append(
            FragmentChords(
                fragment=fragment,
                frame=traced.frame,
                edges=traced.edges,
                envelope=traced.run.provenance,
                observation=scaled.observation,
                transform=scaled.transform,
            )
        )
        outlines.append(_fragment_outline(fragment, scaled))
    return _MillimetrePool(chords=tuple(chords), outlines=tuple(outlines))


def _fragment_outline(fragment: Fragment, scaled: ScaledOutline) -> FragmentOutline:
    return FragmentOutline(
        fragment=fragment,
        frame=scaled.frame,
        outline=scaled.outline,
    )


def _page_frame(args: argparse.Namespace) -> tuple[PageFrame, CoordinateFrame] | None:
    bounds = (
        args.min_width_mm,
        args.max_width_mm,
        args.min_height_mm,
        args.max_height_mm,
    )
    if any(item is None for item in bounds):
        return None
    frame = CoordinateFrame.page_global_mm(
        owner_id=content_id({"kind": "cli-page", "bounds": bounds})
    )
    return (
        PageFrame.create(
            frame,
            min_width_mm=bounds[0],
            max_width_mm=bounds[1],
            min_height_mm=bounds[2],
            max_height_mm=bounds[3],
        ),
        frame,
    )


def _print_assembly_search(result: AssemblySearch) -> None:
    _print_record(
        {
            "record": "AssemblySearch",
            "assemblies": [
                _assembly_payload(assembly) for assembly in result.assemblies
            ],
            "screening": [
                {
                    "hypothesis_id": event.hypothesis_id,
                    "gate": event.gate,
                    "outcome": event.outcome,
                }
                for event in result.screening
            ],
            "envelope": _envelope_payload(result.run.provenance),
        }
    )


def _assembly_payload(assembly: AssemblyContent) -> dict[str, Any]:
    score = next(
        item
        for item in assembly.scores
        if item.channel == "physical" and item.hypothesis_type == "assembly"
    )
    return {
        "id": assembly.id,
        "epistemic_class": assembly.epistemic_class,
        "join_ids": list(assembly.join_ids),
        "placements": [item.fragment_id for item in assembly.placements],
        "score": score.value,
        "channel": score.channel,
    }


def _cmd_agree(args: argparse.Namespace) -> int:
    _refuse_benchmark_label_join(args.benchmarks)
    presented = _presented_bytes(args.path)
    segmented = _segment_presented(args, presented)
    if not isinstance(segmented, SegmentedOutline):
        _print_failure(segmented, args)
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


def _segment_presented(
    args: argparse.Namespace,
    presented: bytes,
    label: str | None = None,
) -> Any:
    stored_label = args.label if label is None else label
    return SegmentationLog().segment(
        presented,
        project_id=pool_project_id(stored_label),
        label=stored_label,
        foreground_threshold=args.foreground_threshold,
        code_version=args.code_version,
        recorded_at=_utc_now(),
        expected_hash=getattr(args, "expected", None),
        enclosed_background_treatment=getattr(
            args, "enclosed_background_treatment", None
        ),
        border_mount_treatment=getattr(args, "border_mount_treatment", None),
    )


def _require_scale_pair(pixels_per_mm: float | None, uncertainty: float | None) -> None:
    if (pixels_per_mm is None) != (uncertainty is None):
        raise ValueError("pixels_per_mm and uncertainty are supplied together.")


def _claimed_ppi(args: argparse.Namespace) -> float | None:
    return getattr(args, "claimed_ppi", None)


def _require_scale_choice(args: argparse.Namespace) -> None:
    claimed = _claimed_ppi(args)
    if claimed is not None and (
        args.pixels_per_mm is not None or args.uncertainty is not None
    ):
        raise ValueError("claimed_resolution_ppi is not a measured pixels_per_mm.")
    _require_scale_pair(args.pixels_per_mm, args.uncertainty)


def _refuse_claimed_calibration(args: argparse.Namespace) -> None:
    if _claimed_ppi(args) is not None:
        raise ValueError("A claimed resolution does not populate calibration.")


def _claim_for_provenance(
    args: argparse.Namespace, provenance: ProvenanceEnvelope
) -> ClaimedResolution | None:
    claimed = _claimed_ppi(args)
    if claimed is None:
        return None
    return record_claimed_resolution(
        claimed,
        source_hashes=provenance.source_hashes,
        code_version=provenance.code_version,
        decoder_name=provenance.decoder_name,
        decoder_version=provenance.decoder_version,
        recorded_at=_utc_now(),
    )


def _claim_for_chords(
    args: argparse.Namespace, chords: Sequence[FragmentChords]
) -> ClaimedResolution | None:
    claimed = _claimed_ppi(args)
    if claimed is None:
        return None
    hashes = tuple(
        sorted({digest for item in chords for digest in item.envelope.source_hashes})
    )
    decoders = {
        (item.envelope.decoder_name, item.envelope.decoder_version) for item in chords
    }
    if len(decoders) == 1:
        decoder_name, decoder_version = next(iter(decoders))
    else:
        decoder_name, decoder_version = ABSENT, ABSENT
    return record_claimed_resolution(
        claimed,
        source_hashes=hashes,
        code_version=args.code_version,
        decoder_name=decoder_name,
        decoder_version=decoder_version,
        recorded_at=_utc_now(),
    )


def _claimed_payload(claim: ClaimedResolution) -> dict[str, Any]:
    return {
        "evidence_description": "claimed resolution",
        "claimed_resolution_ppi": claim.claimed_resolution_ppi,
        "calibration": ABSENT,
        "envelope": _envelope_payload(claim.run.provenance),
    }


def _apply_scale(
    segmented: SegmentedOutline, args: argparse.Namespace
) -> ScaledOutline:
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
    return scaled


def _trace(
    outline: FragmentOutlineRevision,
    frame: CoordinateFrame,
    envelope: ProvenanceEnvelope,
    args: argparse.Namespace,
) -> ChordEdges | FailedEdgeChord:
    return EdgeChordLog().build(
        outline,
        frame,
        envelope,
        minimum_edge_length_mm=args.minimum_edge_length_mm,
        code_version=args.code_version,
        recorded_at=_utc_now(),
    )


def _image_pairs(images: Sequence[Sequence[str]]) -> tuple[tuple[Path, str], ...]:
    """Return each repeated pool flag as a path and its label."""
    if not images:
        raise ValueError("A pool image is one label and one existing path.")
    pairs: list[tuple[Path, str]] = []
    for entry in images:
        if len(entry) != 2 or entry[0] == "" or entry[1] == "":
            raise ValueError("A pool image is one label and one existing path.")
        pairs.append((Path(entry[1]), entry[0]))
    return tuple(pairs)


def _pool(
    args: argparse.Namespace,
    refuse_message: str,
) -> tuple[FragmentChords, ...] | int:
    pairs = _image_pairs(args.images)
    for path, _label in pairs:
        _refuse_join_label_path(path, refuse_message)
    _require_scale_choice(args)
    pool: list[FragmentChords] = []
    for path, label in pairs:
        presented = _presented_bytes(path)
        segmented = _segment_presented(args, presented, label)
        if not isinstance(segmented, SegmentedOutline):
            _print_failure(segmented, args)
            return 1
        contribution = _chords_for(segmented, args)
        if isinstance(contribution, FailedEdgeChord):
            _print_run_failure("FailedEdgeChord", contribution.run.id)
            return 1
        pool.append(contribution)
    return tuple(pool)


def _chords_for(
    segmented: SegmentedOutline,
    args: argparse.Namespace,
) -> FragmentChords | FailedEdgeChord:
    fragment = segmented.fragment.confirm()
    if args.pixels_per_mm is None:
        return FragmentChords(
            fragment=fragment,
            frame=segmented.frame,
            edges=(),
            envelope=segmented.run.provenance,
        )
    scaled = _apply_scale(segmented, args)
    traced = _trace(scaled.outline, scaled.frame, scaled.run.provenance, args)
    if isinstance(traced, FailedEdgeChord):
        return traced
    return FragmentChords(
        fragment=fragment,
        frame=traced.frame,
        edges=traced.edges,
        envelope=traced.run.provenance,
        observation=scaled.observation,
        transform=scaled.transform,
    )


def _correspondence_map(
    pairs: Sequence[str] | None,
    pool: Sequence[FragmentChords],
) -> dict[uuid.UUID, uuid.UUID]:
    by_label = {item.fragment.label: item.fragment.id for item in pool}
    mapped: dict[uuid.UUID, uuid.UUID] = {}
    for pair in pairs or ():
        label, separator, raw = pair.partition("=")
        if separator != "=" or label == "" or raw == "":
            raise ValueError("A correspondence is label=fixture-fragment-id.")
        project_id = by_label.get(label)
        if project_id is None:
            raise ValueError("A correspondence label is one of the fragment labels.")
        if project_id in mapped:
            raise ValueError("A fragment label is given once.")
        try:
            fixture_id = uuid.UUID(raw)
        except ValueError as exc:
            raise ValueError("A fixture fragment id is a UUID.") from exc
        mapped[project_id] = fixture_id
    return mapped


def _print_edges(result: ChordEdges) -> None:
    _print_record(
        {
            "record": "ChordEdges",
            "edges": [
                {
                    "id": edge.id,
                    "epistemic_class": edge.epistemic_class,
                    "producer": edge.producer,
                    "geometry": edge.geometry,
                }
                for edge in result.edges
            ],
            "envelope": _envelope_payload(result.run.provenance),
        }
    )


def _print_ranked(
    result: PairwiseJoins,
    ordered: Sequence[JoinHypothesis],
) -> None:
    _print_record(
        {
            "record": "physical_join_order",
            "joins": [
                {
                    "id": join.id,
                    "epistemic_class": join.epistemic_class,
                    "fragment_a_id": join.fragment_a_id,
                    "fragment_b_id": join.fragment_b_id,
                    "score": join.scores[0].value,
                    "channel": join.scores[0].channel,
                }
                for join in ordered
            ],
            "envelope": _envelope_payload(result.run.provenance),
        }
    )


def _print_run_failure(
    record: str,
    run_id: uuid.UUID,
    claim: ClaimedResolution | None = None,
) -> None:
    payload: dict[str, Any] = {"record": record, "run_id": run_id, "status": "failed"}
    if claim is not None:
        payload["claimed_resolution"] = _claimed_payload(claim)
    _print_record(payload)


def _refuse_join_label_path(path: Path, message: str) -> None:
    if not path.is_file():
        return
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return
    if _contains_join_label(loaded):
        raise ValueError(message)


def _print_outline(
    outline: FragmentOutlineRevision,
    *,
    frame: str,
    envelope: ProvenanceEnvelope,
    claim: ClaimedResolution | None = None,
) -> None:
    payload: dict[str, Any] = {
        "record": "FragmentOutlineRevision",
        "epistemic_class": outline.epistemic_class,
        "producer": outline.producer,
        "frame": frame,
        "polygon": outline.polygon,
        "id": outline.id,
        "envelope": _envelope_payload(envelope),
    }
    if claim is not None:
        payload["claimed_resolution"] = _claimed_payload(claim)
    _print_record(payload)


def _print_failure(result: object, args: argparse.Namespace | None = None) -> None:
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
    if isinstance(result, TiffDecodeFailure):
        _print_record({"record": "TiffDecodeFailure", "kind": result.kind})
        return
    if isinstance(result, FailedSegmentation):
        payload: dict[str, Any] = {
            "record": "FailedSegmentation",
            "kind": result.kind,
            "run_id": result.run.id,
        }
        if args is not None:
            claim = _claim_for_provenance(args, result.run.provenance)
            if claim is not None:
                payload["claimed_resolution"] = _claimed_payload(claim)
        _print_record(payload)
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
    "edge": _cmd_edge,
    "rank": _cmd_rank,
    "recall": _cmd_recall,
    "assemble": _cmd_assemble,
    "assembly-rank": _cmd_assembly_rank,
    "placement-error": _cmd_placement_error,
    "join-presence": _cmd_join_presence,
    "recognize": _cmd_recognize,
}


if __name__ == "__main__":
    raise SystemExit(main())
