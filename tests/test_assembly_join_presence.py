"""End-to-end join presence at a predeclared N against frozen synthetic joins."""

import inspect
import json
import uuid
from pathlib import Path

from prw.assembly_join_presence import AssemblyFixture, write_assembly_join_presence
from prw.identity import ABSENT, hash_value
from prw.joins import JoinHypothesis
from prw.provenance import AssemblyContent, ProvenanceEnvelope, Score
from prw.synthetic_tear import SyntheticLeaf, generate_synthetic_leaf

_CODE = "test-code"


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


def _leaf(directory: Path, images: Path, seed: int) -> SyntheticLeaf:
    return generate_synthetic_leaf(
        directory,
        images_dir=images,
        missing_fragment_percentage=0.0,
        edge_erosion=0.1,
        rotation=0.2,
        lighting_variation=0.0,
        random_seed=seed,
        code_version=_CODE,
    )


def _join(
    run_id: uuid.UUID,
    provenance_id: uuid.UUID,
    left: uuid.UUID,
    right: uuid.UUID,
) -> JoinHypothesis:
    return JoinHypothesis.create(
        run_id=run_id,
        fragment_a_id=left,
        edge_a_id=uuid.uuid4(),
        fragment_b_id=right,
        edge_b_id=uuid.uuid4(),
        transform_id=uuid.uuid4(),
        scores=(
            Score(
                value=1.0,
                run_id=run_id,
                channel="physical",
                hypothesis_type="join",
            ),
        ),
        provenance_id=provenance_id,
    )


def _assembly(
    envelope: ProvenanceEnvelope, join_ids: tuple[uuid.UUID, ...]
) -> AssemblyContent:
    return AssemblyContent.create(
        page_frame_id=uuid.uuid4(),
        producer="machine",
        join_ids=join_ids,
        provenance_id=envelope.id,
    )


def _file_bytes(directory: Path) -> dict[str, bytes]:
    return {
        path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()
    }


def _fixture_entry(body: dict[str, object], label_file: str) -> dict[str, object]:
    found = [
        item
        for item in body["fixture_list"]
        if isinstance(item, dict) and item["label_file"] == label_file
    ]
    assert len(found) == 1
    entry = found[0]
    assert isinstance(entry, dict)
    return entry


def _join_entry(entry: dict[str, object], label_id: uuid.UUID) -> dict[str, object]:
    join_list = entry["join_list"]
    assert isinstance(join_list, list)
    found = [
        item
        for item in join_list
        if isinstance(item, dict) and item.get("id") == str(label_id)
    ]
    assert len(found) == 1
    recorded = found[0]
    assert isinstance(recorded, dict)
    return recorded


def test_predeclared_n_counts_each_fixture_and_each_known_join_once(
    tmp_path: Path,
) -> None:
    benchmarks = tmp_path / "benchmarks"
    absent_images = tmp_path / "absent-images"
    present_images = tmp_path / "present-images"
    absent_leaf = _leaf(benchmarks / "absent", absent_images, 7)
    present_leaf = _leaf(benchmarks / "present", present_images, 8)
    assert len(absent_leaf.joins) >= 1
    assert len(present_leaf.joins) >= 4
    absent_labels = (benchmarks / "absent" / "labels.json").read_bytes()
    absent_provenance = (benchmarks / "absent" / "provenance.json").read_bytes()
    present_labels = (benchmarks / "present" / "labels.json").read_bytes()
    present_provenance = (benchmarks / "present" / "provenance.json").read_bytes()
    absent_image_bytes = _file_bytes(absent_images)
    present_image_bytes = _file_bytes(present_images)
    envelope = _envelope()
    run_id = uuid.uuid4()
    known = present_leaf.joins[0]
    later = present_leaf.joins[1]
    unmapped = present_leaf.joins[2]
    known_left = uuid.uuid4()
    known_right = uuid.uuid4()
    later_left = uuid.uuid4()
    later_right = uuid.uuid4()
    partial_left = uuid.uuid4()
    partial_right = uuid.uuid4()
    cited_once = _join(run_id, envelope.id, known_left, known_right)
    cited_again = _join(run_id, envelope.id, known_left, known_right)
    later_join = _join(run_id, envelope.id, later_left, later_right)
    partial_join = _join(run_id, envelope.id, partial_left, partial_right)
    extra_join_id = uuid.uuid4()
    assert extra_join_id not in {
        cited_once.id,
        cited_again.id,
        later_join.id,
        partial_join.id,
    }
    present_fixture = AssemblyFixture(
        label_file=benchmarks / "present" / "labels.json",
        assemblies=(
            _assembly(envelope, (cited_once.id, extra_join_id)),
            _assembly(envelope, (cited_again.id,)),
            _assembly(envelope, (later_join.id, partial_join.id)),
        ),
        joins=(cited_once, cited_again, later_join, partial_join),
        correspondence={
            known_left: known.fragment_ids[0],
            known_right: known.fragment_ids[1],
            later_left: later.fragment_ids[0],
            later_right: later.fragment_ids[1],
            partial_left: unmapped.fragment_ids[0],
        },
    )
    absent_known = absent_leaf.joins[0]
    absent_left = uuid.uuid4()
    absent_right = uuid.uuid4()
    absent_join = _join(run_id, envelope.id, absent_left, absent_right)
    absent_fixture = AssemblyFixture(
        label_file=benchmarks / "absent" / "labels.json",
        assemblies=(_assembly(envelope, (absent_join.id,)),),
        joins=(absent_join,),
        correspondence={absent_left: absent_known.fragment_ids[0]},
    )
    assert absent_right not in absent_fixture.correspondence
    assert partial_right not in present_fixture.correspondence
    first = write_assembly_join_presence(
        benchmarks,
        envelope=envelope,
        fixtures=(absent_fixture, present_fixture),
        n=2,
    )
    first_bytes = first.read_bytes()
    body = json.loads(first_bytes)
    assert body["n"] == 2
    assert body["algorithm_name"] == "rigid_assembly_search"
    assert body["algorithm_version"] == "1"
    assert body["parameter_hash"] == envelope.parameter_hash
    assert body["code_version"] == envelope.code_version
    assert body["model_hash"] == ABSENT
    assert body["random_seed"] == ABSENT
    assert "random_seed" not in envelope.content_mapping()
    assert body["source_hashes"] == list(envelope.source_hashes)
    assert body["reference"] == "frozen kind: join row"
    assert body["metric"] == "assembly_join_presence"
    assert body["does_not_measure"] == "a historical join on real parchment"
    assert body["limiting_questions"] == ["Q-SCI-08", "Q-SCI-15"]
    assert body["presence"] == 1 / 2
    assert [item["label_file"] for item in body["fixture_list"]] == [
        "absent/labels.json",
        "present/labels.json",
    ]
    assert [item["status"] for item in body["fixture_list"]] == ["absent", "present"]
    absent_entry = _fixture_entry(body, "absent/labels.json")
    present_entry = _fixture_entry(body, "present/labels.json")
    assert absent_entry["label_file_hash"] == hash_value(absent_labels)
    assert present_entry["label_file_hash"] == hash_value(present_labels)
    assert str(absent_right) not in {
        item["project_fragment_id"] for item in absent_entry["correspondence"]
    }
    assert str(partial_right) not in {
        item["project_fragment_id"] for item in present_entry["correspondence"]
    }
    assert len(present_entry["join_list"]) == len(present_leaf.joins)
    assert len(absent_entry["join_list"]) == len(absent_leaf.joins)
    present_joins = [
        item for item in present_entry["join_list"] if item["status"] == "present"
    ]
    assert present_joins == [
        item for item in present_entry["join_list"] if item["id"] == str(known.id)
    ]
    assert len(present_joins) == 1
    assert _join_entry(present_entry, later.id)["status"] == "absent"
    assert _join_entry(present_entry, unmapped.id)["status"] == "absent"
    assert all(item["status"] == "absent" for item in absent_entry["join_list"])
    assert body["previous_report"] == ABSENT
    assert body["previous_report_statement"] == (
        "No previous end-to-end join-presence report exists."
    )
    assert "best" not in body
    assert "threshold" not in body
    assert "correct_join" not in body
    assert b"correct_join" not in first_bytes
    assert (benchmarks / "absent" / "labels.json").read_bytes() == absent_labels
    assert (benchmarks / "absent" / "provenance.json").read_bytes() == absent_provenance
    assert (benchmarks / "present" / "labels.json").read_bytes() == present_labels
    assert (
        benchmarks / "present" / "provenance.json"
    ).read_bytes() == present_provenance
    assert _file_bytes(absent_images) == absent_image_bytes
    assert _file_bytes(present_images) == present_image_bytes

    second = write_assembly_join_presence(
        benchmarks,
        envelope=envelope,
        fixtures=(absent_fixture, present_fixture),
        n=3,
    )
    assert first.read_bytes() == first_bytes
    compared = json.loads(second.read_bytes())
    assert compared["n"] == 3
    assert compared["presence"] == 1 / 2
    assert compared["previous_report"] == first.name
    assert compared["previous_report_statement"] == (
        f"The previous end-to-end join-presence report is {first.name}."
    )
    assert compared["previous_fixture_list"] == body["fixture_list"]
    compared_present = _fixture_entry(compared, "present/labels.json")
    assert _join_entry(compared_present, known.id)["status"] == "present"
    assert _join_entry(compared_present, later.id)["status"] == "present"
    assert _join_entry(compared_present, unmapped.id)["status"] == "absent"
    present_statuses = [
        item["status"]
        for item in compared_present["join_list"]
        if item["status"] == "present"
    ]
    assert present_statuses == ["present", "present"]
    assert "best" not in compared
    assert "threshold" not in compared
    assert (benchmarks / "absent" / "labels.json").read_bytes() == absent_labels
    assert (benchmarks / "present" / "labels.json").read_bytes() == present_labels
    assert (benchmarks / "absent" / "provenance.json").read_bytes() == absent_provenance
    assert (
        benchmarks / "present" / "provenance.json"
    ).read_bytes() == present_provenance
    assert _file_bytes(absent_images) == absent_image_bytes
    assert _file_bytes(present_images) == present_image_bytes
    assert sorted(
        path.name for path in (benchmarks / "assembly_join_presence").iterdir()
    ) == [
        "assembly-join-presence-0001.json",
        "assembly-join-presence-0002.json",
    ]


def test_single_leaf_is_present_once(tmp_path: Path) -> None:
    benchmarks = tmp_path / "benchmarks"
    images = tmp_path / "images"
    leaf = _leaf(benchmarks, images, 7)
    labels = (benchmarks / "labels.json").read_bytes()
    provenance = (benchmarks / "provenance.json").read_bytes()
    image_bytes = _file_bytes(images)
    envelope = _envelope()
    known = leaf.joins[0]
    left = uuid.uuid4()
    right = uuid.uuid4()
    join = _join(uuid.uuid4(), envelope.id, left, right)
    report = write_assembly_join_presence(
        benchmarks,
        envelope=envelope,
        fixtures=(
            AssemblyFixture(
                label_file=benchmarks / "labels.json",
                assemblies=(_assembly(envelope, (join.id,)),),
                joins=(join,),
                correspondence={
                    left: known.fragment_ids[0],
                    right: known.fragment_ids[1],
                },
            ),
        ),
        n=1,
    )
    body = json.loads(report.read_bytes())
    assert body["n"] == 1
    assert body["presence"] == 1.0
    assert len(body["fixture_list"]) == 1
    assert body["fixture_list"][0]["label_file"] == "labels.json"
    assert body["fixture_list"][0]["status"] == "present"
    assert body["fixture_list"][0]["label_file_hash"] == hash_value(labels)
    present = [
        item
        for item in body["fixture_list"][0]["join_list"]
        if item["status"] == "present"
    ]
    assert len(present) == 1
    assert present[0]["id"] == str(known.id)
    assert len(body["fixture_list"][0]["join_list"]) == len(leaf.joins)
    assert (benchmarks / "labels.json").read_bytes() == labels
    assert (benchmarks / "provenance.json").read_bytes() == provenance
    assert _file_bytes(images) == image_bytes


def test_label_file_with_no_join_row_writes_no_fraction(tmp_path: Path) -> None:
    benchmarks = tmp_path / "benchmarks"
    benchmarks.mkdir()
    labels = benchmarks / "labels.json"
    labels.write_text(
        json.dumps(
            [
                {"kind": "page", "id": str(uuid.uuid4())},
                {
                    "kind": "placement",
                    "id": str(uuid.uuid4()),
                    "fragment_id": str(uuid.uuid4()),
                },
            ]
        ),
        encoding="utf-8",
    )
    before = labels.read_bytes()
    try:
        write_assembly_join_presence(
            benchmarks,
            envelope=_envelope(),
            fixtures=(
                AssemblyFixture(
                    label_file=labels,
                    assemblies=(),
                    joins=(),
                    correspondence={},
                ),
            ),
            n=1,
        )
    except ValueError as exc:
        assert "no join row" in str(exc)
    else:
        raise AssertionError("A label file with no join row is refused.")
    assert labels.read_bytes() == before
    assert b"presence" not in before
    assert not (benchmarks / "assembly_join_presence").exists()
    assert not (benchmarks / "provenance.json").exists()


def test_overwriting_labels_json_is_refused(tmp_path: Path) -> None:
    benchmarks = tmp_path / "benchmarks"
    images = tmp_path / "images"
    _leaf(benchmarks, images, 7)
    labels = benchmarks / "labels.json"
    before = labels.read_bytes()
    provenance = (benchmarks / "provenance.json").read_bytes()
    try:
        write_assembly_join_presence(
            labels,
            envelope=_envelope(),
            fixtures=(
                AssemblyFixture(
                    label_file=labels,
                    assemblies=(),
                    joins=(),
                    correspondence={},
                ),
            ),
            n=1,
        )
    except ValueError as exc:
        assert "labels.json" in str(exc)
    else:
        raise AssertionError("Overwriting labels.json is refused.")
    assert labels.read_bytes() == before
    assert (benchmarks / "provenance.json").read_bytes() == provenance
    assert not (benchmarks / "assembly_join_presence").exists()


def test_n_is_fixed_before_a_label_file_is_read(tmp_path: Path) -> None:
    benchmarks = tmp_path / "benchmarks"
    try:
        write_assembly_join_presence(
            benchmarks,
            envelope=_envelope(),
            fixtures=(),
            n=0,
        )
    except ValueError as exc:
        assert "N is an integer" in str(exc)
        assert "no join row" not in str(exc)
        assert "no fixture" not in str(exc)
    else:
        raise AssertionError("N is an integer greater than or equal to 1.")
    assert not benchmarks.exists()


def test_caller_list_with_no_fixture_writes_no_fraction(tmp_path: Path) -> None:
    benchmarks = tmp_path / "benchmarks"
    try:
        write_assembly_join_presence(
            benchmarks,
            envelope=_envelope(),
            fixtures=(),
            n=1,
        )
    except ValueError as exc:
        assert "no fixture" in str(exc)
    else:
        raise AssertionError("A caller list with no fixture is refused.")
    assert not benchmarks.exists()
    assert not (benchmarks / "assembly_join_presence").exists()


def test_search_does_not_reference_assembly_join_presence() -> None:
    import prw.assembly_join_presence as assembly_join_presence
    import prw.assembly_search as assembly_search

    search = Path(inspect.getfile(assembly_search)).read_text(encoding="utf-8")
    reporter = Path(inspect.getfile(assembly_join_presence)).read_text(encoding="utf-8")
    assert "assembly_join_presence" not in search
    assert "prw.assembly_search" not in reporter
    public = [
        name
        for name, value in vars(assembly_join_presence).items()
        if inspect.isfunction(value)
        and value.__module__ == assembly_join_presence.__name__
        and not name.startswith("_")
    ]
    assert public == ["write_assembly_join_presence"]
    defined = [
        name
        for name, value in vars(assembly_join_presence).items()
        if inspect.isfunction(value)
        and value.__module__ == assembly_join_presence.__name__
    ]
    assert all(
        "choose" not in name and "best" not in name and "threshold" not in name
        for name in defined
    )
