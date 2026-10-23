"""Placement error at a predeclared N against frozen synthetic placement labels."""

import inspect
import json
import math
import uuid
from pathlib import Path

from prw.assemblies import placement_pose
from prw.frames import CoordinateFrame
from prw.identity import ABSENT, hash_value
from prw.joins import RigidTransform
from prw.placement_error import write_placement_error
from prw.provenance import AssemblyContent, Placement, ProvenanceEnvelope
from prw.synthetic_tear import generate_synthetic_leaf

_CODE = "test-code"
_SHIFTED = ((2.0, 0.0), (0.0, 2.0))
_MATCHED = ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0))
type Point = tuple[float, float]
type Pose = tuple[float, float, float]


def _envelope() -> ProvenanceEnvelope:
    return ProvenanceEnvelope.create(
        source_hashes=(hash_value(b"fixture-source"),),
        parameters={
            "page_origin": "minimum_corner",
            "score": "join_score_sum_minus_range_penalty",
        },
        algorithm_name="rigid_assembly_search",
        algorithm_version="1",
        code_version=_CODE,
        decoder_name="tiff",
        decoder_version="1",
    )


def _frames() -> tuple[CoordinateFrame, CoordinateFrame]:
    local = CoordinateFrame.fragment_local_mm(
        owner_id=uuid.uuid4(),
        establishing_outline_revision_id=uuid.uuid4(),
        polygon=((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
    )
    page = CoordinateFrame.page_global_mm(owner_id=uuid.uuid4())
    return local, page


def _pose(
    local: CoordinateFrame,
    page: CoordinateFrame,
    envelope: ProvenanceEnvelope,
    rotation: float,
    translation_x: float,
    translation_y: float,
) -> RigidTransform:
    return placement_pose(
        from_frame=local,
        to_frame=page,
        rotation_radians=rotation,
        translation_x=translation_x,
        translation_y=translation_y,
        provenance_id=envelope.id,
    )


def _assembly(
    envelope: ProvenanceEnvelope,
    page_frame_id: uuid.UUID,
    placements: tuple[tuple[uuid.UUID, RigidTransform], ...],
    unplaced: tuple[uuid.UUID, ...] = (),
) -> AssemblyContent:
    return AssemblyContent.create(
        page_frame_id=page_frame_id,
        producer="machine",
        placements=tuple(
            Placement(
                fragment_id=fragment_id,
                outline_revision_id=uuid.uuid4(),
                transform_id=pose.id,
            )
            for fragment_id, pose in placements
        ),
        unplaced_fragment_ids=unplaced,
        provenance_id=envelope.id,
    )


def _apply(vertices: tuple[Point, ...], pose: Pose) -> tuple[Point, ...]:
    rotation, origin_x, origin_y = pose
    cosine = math.cos(rotation)
    sine = math.sin(rotation)
    return tuple(
        (
            x_coord * cosine - y_coord * sine + origin_x,
            x_coord * sine + y_coord * cosine + origin_y,
        )
        for x_coord, y_coord in vertices
    )


def _rmse(vertices: tuple[Point, ...], predicted: Pose, reference: Pose) -> float:
    left = _apply(vertices, predicted)
    right = _apply(vertices, reference)
    total = sum(
        (pred[0] - ref[0]) ** 2 + (pred[1] - ref[1]) ** 2
        for pred, ref in zip(left, right, strict=True)
    )
    return math.sqrt(total / len(vertices))


def _file_bytes(directory: Path) -> dict[str, bytes]:
    return {
        path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()
    }


def _entry(body: dict[str, object], fragment_id: uuid.UUID) -> dict[str, object]:
    found = [
        item
        for item in body["error_list"]
        if isinstance(item, dict) and item["fragment_id"] == str(fragment_id)
    ]
    assert len(found) == 1
    entry = found[0]
    assert isinstance(entry, dict)
    return entry


def test_predeclared_n_lists_vertex_rmse_and_names_the_rest(tmp_path: Path) -> None:
    benchmarks = tmp_path / "benchmarks"
    images = tmp_path / "images"
    leaf = generate_synthetic_leaf(
        benchmarks,
        images_dir=images,
        missing_fragment_percentage=0.0,
        edge_erosion=0.1,
        rotation=0.2,
        lighting_variation=0.0,
        random_seed=7,
        code_version=_CODE,
    )
    assert len(leaf.placements) >= 4
    assert len(leaf.joins) > 0
    labels = (benchmarks / "labels.json").read_bytes()
    provenance = (benchmarks / "provenance.json").read_bytes()
    image_bytes = _file_bytes(images)
    shifted_label = leaf.placements[1]
    matched_label = leaf.placements[0]
    assert (
        shifted_label.rotation_radians,
        shifted_label.translation_x,
        shifted_label.translation_y,
    ) != (0.0, 0.0, 0.0)
    envelope = _envelope()
    local, page = _frames()
    shifted_id = uuid.uuid4()
    matched_id = uuid.uuid4()
    unmatched_id = uuid.uuid4()
    unlabeled_id = uuid.uuid4()
    empty_id = uuid.uuid4()
    unplaced_id = uuid.uuid4()
    held_id = uuid.uuid4()
    shifted_pose = _pose(local, page, envelope, 0.0, 0.0, 0.0)
    matched_pose = _pose(
        local,
        page,
        envelope,
        matched_label.rotation_radians,
        matched_label.translation_x,
        matched_label.translation_y,
    )
    unmatched_pose = _pose(local, page, envelope, 0.1, 1.0, 1.0)
    unlabeled_pose = _pose(local, page, envelope, 0.2, 2.0, 2.0)
    empty_pose = _pose(local, page, envelope, 0.3, 3.0, 3.0)
    held_pose = _pose(
        local,
        page,
        envelope,
        matched_label.rotation_radians,
        matched_label.translation_x,
        matched_label.translation_y,
    )
    worse = _assembly(
        envelope,
        page.id,
        (
            (shifted_id, shifted_pose),
            (matched_id, matched_pose),
            (unmatched_id, unmatched_pose),
            (unlabeled_id, unlabeled_pose),
            (empty_id, empty_pose),
        ),
        (unplaced_id,),
    )
    better = _assembly(envelope, page.id, ((held_id, held_pose),))
    polygons = {
        shifted_id: _SHIFTED,
        matched_id: _MATCHED,
        unmatched_id: ((1.0, 1.0),),
        unlabeled_id: ((1.0, 0.0), (0.0, 1.0)),
        empty_id: (),
        unplaced_id: ((5.0, 5.0), (6.0, 5.0)),
        held_id: _MATCHED,
    }
    missing_fixture = uuid.uuid4()
    correspondence = {
        shifted_id: shifted_label.fragment_id,
        matched_id: matched_label.fragment_id,
        unlabeled_id: missing_fixture,
        empty_id: leaf.placements[2].fragment_id,
        unplaced_id: leaf.placements[3].fragment_id,
        held_id: matched_label.fragment_id,
    }
    assert unmatched_id not in correspondence
    first = write_placement_error(
        benchmarks,
        envelope=envelope,
        ranked_assemblies=(worse, better),
        poses=(
            shifted_pose,
            matched_pose,
            unmatched_pose,
            unlabeled_pose,
            empty_pose,
            held_pose,
        ),
        polygons=polygons,
        n=1,
        correspondence=correspondence,
    )
    first_bytes = first.read_bytes()
    body = json.loads(first_bytes)
    assert body["n"] == 1
    assert body["algorithm_name"] == "rigid_assembly_search"
    assert body["algorithm_version"] == "1"
    assert body["parameter_hash"] == envelope.parameter_hash
    assert body["code_version"] == envelope.code_version
    assert body["model_hash"] == ABSENT
    assert body["random_seed"] == ABSENT
    assert "random_seed" not in envelope.content_mapping()
    assert body["source_hashes"] == list(envelope.source_hashes)
    assert body["page_origin"] == "minimum_corner"
    assert body["freeze_identifier"] == hash_value(labels)
    assert body["freeze_identifier"].startswith("sha256:")
    assert body["reference"] == "frozen kind: placement row"
    assert body["metric"] == "placement_error"
    assert body["unit"] == "root-mean-square error in page millimetres"
    assert body["does_not_measure"] == "warped or shrunken real parchment"
    assert body["error_includes"] == (
        "The error includes the difference between the page-origin rule "
        "minimum_corner and the generator's absolute rotation."
    )
    assert body["limiting_questions"] == ["Q-SCI-03", "Q-SCI-15", "Q-SCI-20"]
    recorded = {
        item["project_fragment_id"]: item["fixture_fragment_id"]
        for item in body["correspondence"]
    }
    assert recorded == {
        str(project): str(fixture) for project, fixture in correspondence.items()
    }
    assert str(unmatched_id) not in recorded
    assert [item["fragment_id"] for item in body["error_list"]] == [
        str(shifted_id),
        str(matched_id),
        str(unmatched_id),
        str(unlabeled_id),
        str(empty_id),
        str(unplaced_id),
    ]
    assert all(item["assembly_id"] == str(worse.id) for item in body["error_list"])
    expected = _rmse(
        _SHIFTED,
        (0.0, 0.0, 0.0),
        (
            shifted_label.rotation_radians,
            shifted_label.translation_x,
            shifted_label.translation_y,
        ),
    )
    shifted = _entry(body, shifted_id)
    matched = _entry(body, matched_id)
    assert shifted["status"] == "scored"
    assert matched["status"] == "scored"
    assert isinstance(shifted["rmse_mm"], float)
    assert math.isclose(shifted["rmse_mm"], expected, rel_tol=1e-12, abs_tol=1e-12)
    assert expected > 1.0
    assert matched["rmse_mm"] == 0.0
    for fragment_id, status in (
        (unmatched_id, "no_correspondence"),
        (unlabeled_id, "no_placement_label"),
        (empty_id, "refused"),
        (unplaced_id, "unplaced"),
    ):
        entry = _entry(body, fragment_id)
        assert entry["status"] == status
        assert "rmse_mm" not in entry
    assert body["unscored_assemblies"] == [
        {"assembly_id": str(better.id), "status": "unscored"}
    ]
    assert str(better.id) not in {item["assembly_id"] for item in body["error_list"]}
    assert str(held_id) not in {item["fragment_id"] for item in body["error_list"]}
    assert body["previous_report"] == ABSENT
    assert body["previous_report_statement"] == (
        "No previous placement-error report exists."
    )
    assert "best" not in body
    assert "threshold" not in body
    assert "correct_join" not in body
    assert b"best" not in first_bytes
    assert b"threshold" not in first_bytes
    assert (benchmarks / "labels.json").read_bytes() == labels
    assert (benchmarks / "provenance.json").read_bytes() == provenance
    assert _file_bytes(images) == image_bytes

    second = write_placement_error(
        benchmarks,
        envelope=envelope,
        ranked_assemblies=(worse, better),
        poses=(
            shifted_pose,
            matched_pose,
            unmatched_pose,
            unlabeled_pose,
            empty_pose,
            held_pose,
        ),
        polygons=polygons,
        n=2,
        correspondence=correspondence,
    )
    assert first.read_bytes() == first_bytes
    compared = json.loads(second.read_bytes())
    assert compared["n"] == 2
    assert compared["previous_report"] == first.name
    assert compared["previous_report_statement"] == (
        f"The previous placement-error report is {first.name}."
    )
    assert compared["previous_error_list"] == body["error_list"]
    assert [item["fragment_id"] for item in compared["error_list"]] == [
        str(shifted_id),
        str(matched_id),
        str(unmatched_id),
        str(unlabeled_id),
        str(empty_id),
        str(unplaced_id),
        str(held_id),
    ]
    assert compared["error_list"][0]["assembly_id"] == str(worse.id)
    assert compared["error_list"][-1]["assembly_id"] == str(better.id)
    assert compared["error_list"][-1]["rmse_mm"] == 0.0
    assert compared["unscored_assemblies"] == []
    assert "best" not in compared
    assert "threshold" not in compared
    assert (benchmarks / "labels.json").read_bytes() == labels
    assert (benchmarks / "provenance.json").read_bytes() == provenance
    assert _file_bytes(images) == image_bytes
    assert sorted(path.name for path in (benchmarks / "placement_error").iterdir()) == [
        "placement-error-0001.json",
        "placement-error-0002.json",
    ]
    assert sorted(path.name for path in benchmarks.iterdir()) == [
        "labels.json",
        "placement_error",
        "provenance.json",
    ]


def test_label_file_with_no_placement_row_writes_no_error(tmp_path: Path) -> None:
    benchmarks = tmp_path / "benchmarks"
    benchmarks.mkdir()
    labels = benchmarks / "labels.json"
    labels.write_text(
        json.dumps(
            [
                {"kind": "page", "id": str(uuid.uuid4())},
                {
                    "kind": "join",
                    "id": str(uuid.uuid4()),
                    "fragment_ids": [str(uuid.uuid4()), str(uuid.uuid4())],
                },
            ]
        ),
        encoding="utf-8",
    )
    before = labels.read_bytes()
    try:
        write_placement_error(
            benchmarks,
            envelope=_envelope(),
            ranked_assemblies=(),
            poses=(),
            polygons={},
            n=1,
            correspondence={},
        )
    except ValueError as exc:
        assert "no placement row" in str(exc)
    else:
        raise AssertionError("A label file with no placement row is refused.")
    assert labels.read_bytes() == before
    assert b"rmse" not in before
    assert not (benchmarks / "placement_error").exists()
    assert not (benchmarks / "provenance.json").exists()


def test_overwriting_labels_json_is_refused(tmp_path: Path) -> None:
    benchmarks = tmp_path / "benchmarks"
    images = tmp_path / "images"
    generate_synthetic_leaf(
        benchmarks,
        images_dir=images,
        missing_fragment_percentage=0.0,
        edge_erosion=0.1,
        rotation=0.2,
        lighting_variation=0.0,
        random_seed=7,
        code_version=_CODE,
    )
    labels = benchmarks / "labels.json"
    before = labels.read_bytes()
    provenance = (benchmarks / "provenance.json").read_bytes()
    try:
        write_placement_error(
            labels,
            envelope=_envelope(),
            ranked_assemblies=(),
            poses=(),
            polygons={},
            n=1,
            correspondence={},
        )
    except ValueError as exc:
        assert "labels.json" in str(exc)
    else:
        raise AssertionError("Overwriting labels.json is refused.")
    assert labels.read_bytes() == before
    assert (benchmarks / "provenance.json").read_bytes() == provenance
    assert not (benchmarks / "placement_error").exists()


def test_n_is_fixed_before_a_label_file_is_read(tmp_path: Path) -> None:
    benchmarks = tmp_path / "benchmarks"
    try:
        write_placement_error(
            benchmarks,
            envelope=_envelope(),
            ranked_assemblies=(),
            poses=(),
            polygons={},
            n=0,
            correspondence={},
        )
    except ValueError as exc:
        assert "N is an integer" in str(exc)
        assert "no placement row" not in str(exc)
    else:
        raise AssertionError("N is an integer greater than or equal to 1.")
    assert not benchmarks.exists()
    assert not (benchmarks / "placement_error").exists()
    assert not (benchmarks / "labels.json").exists()


def test_search_does_not_reference_placement_error() -> None:
    import prw.assembly_search as assembly_search
    import prw.placement_error as placement_error

    search = Path(inspect.getfile(assembly_search)).read_text(encoding="utf-8")
    reporter = Path(inspect.getfile(placement_error)).read_text(encoding="utf-8")
    assert "placement_error" not in search
    assert "prw.assembly_search" not in reporter
    public = [
        name
        for name, value in vars(placement_error).items()
        if inspect.isfunction(value)
        and value.__module__ == placement_error.__name__
        and not name.startswith("_")
    ]
    assert public == ["write_placement_error"]
    defined = [
        name
        for name, value in vars(placement_error).items()
        if inspect.isfunction(value) and value.__module__ == placement_error.__name__
    ]
    assert all(
        "choose" not in name and "best" not in name and "threshold" not in name
        for name in defined
    )
