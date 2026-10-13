"""Join recall at a predeclared K against frozen synthetic join labels."""

import inspect
import json
import uuid
from pathlib import Path

from prw.frames import CoordinateFrame
from prw.identity import ABSENT, hash_value
from prw.join_rank import physical_join_order
from prw.join_recall import write_join_recall
from prw.joins import EdgeArc
from prw.outlines import Fragment, FragmentOutlineRevision
from prw.pairwise_join import (
    FragmentChords,
    PairwiseJoinLog,
    PairwiseJoins,
)
from prw.provenance import AlgorithmRun, ProvenanceEnvelope
from prw.scale import CalibrationObservation, CalibrationTransform
from prw.synthetic_tear import generate_synthetic_leaf

_RECORDED = "2020-01-01T00:00:00Z"
_CODE = "test-code"
type Point = tuple[float, float]
type Chord = tuple[Point, Point]


def _edge_envelope(digest: bytes) -> ProvenanceEnvelope:
    return ProvenanceEnvelope.create(
        source_hashes=(hash_value(digest),),
        parameters={"descriptor": "chord", "minimum_edge_length_mm": 0.0},
        algorithm_name="edge_chord",
        algorithm_version="1",
        code_version="edge123",
        decoder_name="tiff",
        decoder_version="1",
    )


def _fragment(project_id: uuid.UUID, label: str) -> Fragment:
    return Fragment.catalogued(project_id=project_id, label=label)


def _span(chord: Chord) -> tuple[Point, ...]:
    start, end = chord
    return (
        start,
        end,
        (start[0] + end[1] - start[1], start[1] + start[0] - end[0]),
    )


def _frame(fragment: Fragment, polygon: tuple[Point, ...]) -> CoordinateFrame:
    return CoordinateFrame.fragment_local_mm(
        owner_id=fragment.id,
        establishing_outline_revision_id=uuid.uuid4(),
        polygon=polygon,
    )


def _edge(
    fragment: Fragment,
    frame: CoordinateFrame,
    envelope: ProvenanceEnvelope,
    chord: Chord,
) -> EdgeArc:
    outline_run = AlgorithmRun.create(
        envelope, status="completed", started_at=_RECORDED
    )
    outline = FragmentOutlineRevision.create(
        fragment_id=fragment.id,
        frame_id=frame.id,
        polygon=(chord[0], chord[1], (chord[0][0], chord[1][1] + 1.0)),
        run_id=outline_run.id,
        provenance_id=envelope.id,
    )
    edge_run = AlgorithmRun.create(envelope, status="completed", started_at=_RECORDED)
    return EdgeArc.create(
        outline_revision_id=outline.id,
        frame=frame,
        geometry=chord,
        run_id=edge_run.id,
        provenance_id=envelope.id,
    )


def _calibration(
    frame: CoordinateFrame,
) -> tuple[CalibrationObservation, CalibrationTransform]:
    source_id = uuid.uuid4()
    pixels = CoordinateFrame.source_pixels(owner_id=source_id)
    transform = CalibrationTransform.create(
        source_image_id=source_id,
        from_frame_id=pixels.id,
        to_frame_id=frame.id,
        translation_x=0.0,
        translation_y=0.0,
        uniform_scale=10.0,
        producer="human",
    )
    observation = CalibrationObservation.create(
        source_image_id=source_id,
        producer="human",
        pixels_per_mm=10.0,
        uncertainty=0.1,
        frame_id=pixels.id,
        transform_id=transform.id,
        provenance_id=None,
    )
    return observation, transform


def _chords(
    fragment: Fragment,
    envelope: ProvenanceEnvelope,
    chord: Chord,
) -> FragmentChords:
    local = _frame(fragment, _span(chord))
    observation, transform = _calibration(local)
    return FragmentChords(
        fragment=fragment,
        frame=local,
        edges=(_edge(fragment, local, envelope, chord),),
        envelope=envelope,
        observation=observation,
        transform=transform,
    )


def _ranked(
    fragments: tuple[Fragment, Fragment, Fragment],
) -> tuple[tuple[object, ...], ProvenanceEnvelope]:
    edge_envelope = _edge_envelope(b"source-a")
    long_a: Chord = ((0.0, 0.0), (4.0, 0.0))
    long_b: Chord = ((1.0, 2.0), (5.0, 2.0))
    short: Chord = ((0.0, 0.0), (1.0, 0.0))
    proposed = PairwiseJoinLog().propose(
        (
            _chords(fragments[0], edge_envelope, long_a),
            _chords(fragments[1], edge_envelope, long_b),
            _chords(fragments[2], edge_envelope, short),
        ),
        code_version=_CODE,
        recorded_at=_RECORDED,
    )
    assert isinstance(proposed, PairwiseJoins)
    ranked = physical_join_order(proposed.joins, (proposed.run,), proposed.proposed)
    return ranked, proposed.run.provenance


def _file_bytes(directory: Path) -> dict[str, bytes]:
    return {
        path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()
    }


def test_predeclared_k_lists_every_known_join_and_counts_a_pair_once(
    tmp_path: Path,
) -> None:
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
    labels = (benchmarks / "labels.json").read_bytes()
    provenance = (benchmarks / "provenance.json").read_bytes()
    image_bytes = _file_bytes(images)
    project_id = uuid.uuid4()
    fragment_a = _fragment(project_id, "piece-a")
    fragment_b = _fragment(project_id, "piece-b")
    fragment_c = _fragment(project_id, "piece-c")
    ranked, envelope = _ranked((fragment_a, fragment_b, fragment_c))
    assert len(ranked) == 6
    assert len(leaf.joins) == 4
    known = leaf.joins[0]
    fixture_a, fixture_b = known.fragment_ids
    correspondence = {
        fragment_a.id: fixture_a,
        fragment_c.id: fixture_b,
    }
    assert fragment_b.id not in correspondence
    first = write_join_recall(
        benchmarks,
        envelope=envelope,
        ranked_joins=ranked,
        k=6,
        correspondence=correspondence,
    )
    first_bytes = first.read_bytes()
    body = json.loads(first_bytes)
    assert body["k"] == 6
    assert body["algorithm_name"] == "pairwise_rigid_join"
    assert body["algorithm_version"] == "1"
    assert body["parameter_hash"] == envelope.parameter_hash
    assert body["code_version"] == envelope.code_version
    assert body["model_hash"] == ABSENT
    assert body["random_seed"] == ABSENT
    assert "random_seed" not in envelope.content_mapping()
    assert body["source_hashes"] == list(envelope.source_hashes)
    assert body["label_file_hash"] == hash_value(labels)
    assert body["reference"] == "frozen kind: join row"
    assert body["does_not_measure"] == "a historical join on real parchment"
    assert body["limiting_questions"] == ["Q-SCI-15"]
    assert body["recall"] == 1 / len(leaf.joins)
    assert len(body["recall_list"]) == len(leaf.joins)
    shared = [
        join
        for join in ranked[: body["k"]]
        if {join.fragment_a_id, join.fragment_b_id} == {fragment_a.id, fragment_c.id}
    ]
    assert len(shared) == 2
    assert any(
        fragment_b.id in {join.fragment_a_id, join.fragment_b_id}
        for join in ranked[: body["k"]]
    )
    recorded = {
        item["project_fragment_id"]: item["fixture_fragment_id"]
        for item in body["correspondence"]
    }
    assert recorded == {
        str(fragment_a.id): str(fixture_a),
        str(fragment_c.id): str(fixture_b),
    }
    assert str(fragment_b.id) not in recorded
    for label in leaf.joins:
        entry = next(
            item for item in body["recall_list"] if item["id"] == str(label.id)
        )
        expected = "present" if label.id == known.id else "absent"
        assert entry["status"] == expected
        assert set(entry["fragment_ids"]) == {str(item) for item in label.fragment_ids}
    assert body["previous_report"] == ABSENT
    assert body["previous_report_statement"] == (
        "No previous join-recall report exists."
    )
    assert "best" not in body
    assert "threshold" not in body
    assert "correct_join" not in body
    assert (benchmarks / "labels.json").read_bytes() == labels
    assert (benchmarks / "provenance.json").read_bytes() == provenance

    second = write_join_recall(
        benchmarks,
        envelope=envelope,
        ranked_joins=ranked,
        k=1,
        correspondence=correspondence,
    )
    assert first.read_bytes() == first_bytes
    compared = json.loads(second.read_bytes())
    assert compared["k"] == 1
    assert compared["recall"] == 0
    assert compared["previous_report"] == first.name
    assert compared["previous_report_statement"] == (
        f"The previous join-recall report is {first.name}."
    )
    assert compared["previous_recall_list"] == body["recall_list"]
    assert all(item["status"] == "absent" for item in compared["recall_list"])
    assert fragment_b.id in {ranked[0].fragment_a_id, ranked[0].fragment_b_id}
    assert any(
        {join.fragment_a_id, join.fragment_b_id} == {fragment_a.id, fragment_c.id}
        for join in ranked[1:]
    )
    assert "best" not in compared
    assert "threshold" not in compared
    assert (benchmarks / "labels.json").read_bytes() == labels
    assert (benchmarks / "provenance.json").read_bytes() == provenance
    assert _file_bytes(images) == image_bytes
    assert sorted(path.name for path in (benchmarks / "join_recall").iterdir()) == [
        "join-recall-0001.json",
        "join-recall-0002.json",
    ]


def test_label_file_with_no_join_row_writes_no_recall(tmp_path: Path) -> None:
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
    envelope = ProvenanceEnvelope.create(
        source_hashes=(hash_value(b"fixture"),),
        parameters={"score": "negative_absolute_length_difference"},
        algorithm_name="pairwise_rigid_join",
        algorithm_version="1",
        code_version=_CODE,
        decoder_name="tiff",
        decoder_version="1",
    )
    try:
        write_join_recall(
            benchmarks,
            envelope=envelope,
            ranked_joins=(),
            k=1,
            correspondence={},
        )
    except ValueError as exc:
        assert "no join row" in str(exc)
    else:
        raise AssertionError("A label file with no join row is refused.")
    assert labels.read_bytes() == before
    assert b"recall" not in before
    assert not (benchmarks / "join_recall").exists()
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
    envelope = ProvenanceEnvelope.create(
        source_hashes=(hash_value(b"fixture"),),
        parameters={"score": "negative_absolute_length_difference"},
        algorithm_name="pairwise_rigid_join",
        algorithm_version="1",
        code_version=_CODE,
        decoder_name="tiff",
        decoder_version="1",
    )
    try:
        write_join_recall(
            labels,
            envelope=envelope,
            ranked_joins=(),
            k=1,
            correspondence={},
        )
    except ValueError as exc:
        assert "labels.json" in str(exc)
    else:
        raise AssertionError("Overwriting labels.json is refused.")
    assert labels.read_bytes() == before
    assert (benchmarks / "provenance.json").read_bytes() == provenance
    assert not (benchmarks / "join_recall").exists()


def test_k_is_fixed_before_a_label_file_is_read(tmp_path: Path) -> None:
    benchmarks = tmp_path / "benchmarks"
    benchmarks.mkdir()
    envelope = ProvenanceEnvelope.create(
        source_hashes=(hash_value(b"fixture"),),
        parameters={"score": "negative_absolute_length_difference"},
        algorithm_name="pairwise_rigid_join",
        algorithm_version="1",
        code_version=_CODE,
        decoder_name="tiff",
        decoder_version="1",
    )
    try:
        write_join_recall(
            benchmarks,
            envelope=envelope,
            ranked_joins=(),
            k=0,
            correspondence={},
        )
    except ValueError as exc:
        assert "K is an integer" in str(exc)
        assert "no join row" not in str(exc)
    else:
        raise AssertionError("K is an integer greater than or equal to 1.")
    assert not (benchmarks / "join_recall").exists()
    assert not (benchmarks / "labels.json").exists()


def test_proposer_does_not_reference_the_label_path() -> None:
    import prw.join_recall as join_recall
    import prw.pairwise_join as pairwise_join

    source = Path(inspect.getfile(pairwise_join)).read_text(encoding="utf-8")
    assert "labels.json" not in source
    assert "join_recall" not in source
    public = [
        name
        for name, value in vars(join_recall).items()
        if inspect.isfunction(value)
        and value.__module__ == join_recall.__name__
        and not name.startswith("_")
    ]
    assert public == ["write_join_recall"]
