"""Synthetic outline agreement against caller-supplied generator polygons."""

import inspect
import json
from pathlib import Path

import pytest

from prw.identity import ABSENT, hash_value
from prw.outline_agreement import polygon_iou, write_outline_agreement
from prw.provenance import ProvenanceEnvelope
from prw.segment import ALGORITHM_NAME, ALGORITHM_VERSION
from prw.synthetic_tear import DECODER_NAME, DECODER_VERSION, generate_synthetic_leaf

_SQUARE = ((0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0))
_SHIFT = ((1.0, 0.0), (3.0, 0.0), (3.0, 2.0), (1.0, 2.0))
_ELL = (
    (0.0, 0.0),
    (3.0, 0.0),
    (3.0, 1.0),
    (1.0, 1.0),
    (1.0, 3.0),
    (0.0, 3.0),
)


def _envelope() -> ProvenanceEnvelope:
    return ProvenanceEnvelope.create(
        source_hashes=(hash_value(b"fixture-image"),),
        parameters={"foreground_threshold": 1},
        algorithm_name=ALGORITHM_NAME,
        algorithm_version=ALGORITHM_VERSION,
        code_version="test-code",
        decoder_name=DECODER_NAME,
        decoder_version=DECODER_VERSION,
    )


def test_identical_squares_in_one_frame_have_iou_one() -> None:
    score = polygon_iou(
        _SQUARE,
        _SQUARE,
        predicted_frame="source_pixels",
        reference_frame="source_pixels",
    )
    assert score == 1.0


def test_partial_overlap_lists_the_intersection_ratio() -> None:
    score = polygon_iou(
        _SQUARE,
        _SHIFT,
        predicted_frame="fragment_local_mm",
        reference_frame="fragment_local_mm",
    )
    assert score == pytest.approx(1 / 3)


def test_a_pixel_polygon_paired_with_a_millimetre_polygon_is_refused() -> None:
    with pytest.raises(ValueError, match="one named frame"):
        polygon_iou(
            _SQUARE,
            _SQUARE,
            predicted_frame="source_pixels",
            reference_frame="fragment_local_mm",
        )


def test_reversed_and_concave_polygons_keep_their_area() -> None:
    reversed_square = tuple(reversed(_SQUARE))
    assert (
        polygon_iou(
            reversed_square,
            _SQUARE,
            predicted_frame="page_global_mm",
            reference_frame="page_global_mm",
        )
        == 1.0
    )
    assert (
        polygon_iou(
            _ELL,
            _ELL,
            predicted_frame="source_pixels",
            reference_frame="source_pixels",
        )
        == 1.0
    )


def test_report_lists_every_leaf_iou_and_keeps_labels(tmp_path: Path) -> None:
    benchmarks = tmp_path / "benchmarks"
    leaf = generate_synthetic_leaf(
        benchmarks,
        images_dir=tmp_path / "images",
        missing_fragment_percentage=0.0,
        edge_erosion=0.1,
        rotation=0.2,
        lighting_variation=0.0,
        random_seed=7,
        code_version="test-code",
    )
    labels = (benchmarks / "labels.json").read_bytes()
    provenance = (benchmarks / "provenance.json").read_bytes()
    frame = leaf.fragments[0].frame.kind
    pairs = [
        (fragment.local_polygon, fragment.local_polygon) for fragment in leaf.fragments
    ]
    hashes = tuple(image.content_hash for image in leaf.images)
    envelope = _envelope()
    first = write_outline_agreement(
        benchmarks,
        envelope=envelope,
        frame=frame,
        pairs=pairs,
        fixture_image_hashes=hashes,
    )
    first_bytes = first.read_bytes()
    body = json.loads(first_bytes)
    assert body["algorithm_name"] == "fragment_outline"
    assert body["algorithm_version"] == "1"
    assert body["parameter_hash"] == envelope.parameter_hash
    assert body["code_version"] == envelope.code_version
    assert body["model_hash"] == ABSENT
    assert body["random_seed"] == ABSENT
    assert body["fixture_image_hashes"] == list(hashes)
    assert body["reference"] == "generator polygon supplied by the caller"
    assert body["ious"] == [1.0] * len(leaf.fragments)
    assert len(body["ious"]) == len(pairs)
    assert "best" not in body
    assert "threshold" not in body
    assert body["previous_report"] == ABSENT
    assert body["previous_report_statement"] == (
        "No previous outline-agreement report exists."
    )
    assert body["limiting_questions"] == ["Q-SCI-17"]
    assert (benchmarks / "labels.json").read_bytes() == labels
    assert (benchmarks / "provenance.json").read_bytes() == provenance

    shifted = [(fragment.local_polygon, _SQUARE) for fragment in leaf.fragments]
    second = write_outline_agreement(
        benchmarks,
        envelope=envelope,
        frame=frame,
        pairs=shifted,
        fixture_image_hashes=hashes,
    )
    assert first.read_bytes() == first_bytes
    compared = json.loads(second.read_bytes())
    assert compared["previous_report"] == first.name
    assert compared["previous_ious"] == body["ious"]
    assert compared["ious"] != compared["previous_ious"]
    assert len(compared["ious"]) == len(pairs)
    assert "best" not in compared
    assert (benchmarks / "labels.json").read_bytes() == labels
    assert (benchmarks / "provenance.json").read_bytes() == provenance


def test_segmenter_does_not_reference_the_agreement_report() -> None:
    import prw.segment as segment

    source = Path(inspect.getfile(segment)).read_text(encoding="utf-8")
    assert "outline_agreement" not in source
    assert "outline-agreement" not in source
    assert "labels.json" not in source
