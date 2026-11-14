"""Character error rate on synthetic text and the frozen line fixture.

These tests do not read ``data/``, ``scans/``, ``real_data/``, a real-corpus
TIFF, or model weights. The live recognize path is skipped unless the
``htr`` group is installed and ``PRW_HTR_WEIGHTS`` names a local
``medium.safetensors``.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest

import prw.recognize
from prw.character_error import (
    comparison_text,
    edit_distance,
    exclusion_tag,
    write_character_error,
)
from prw.fixture_tiff import FixtureSamples, read_fixture_tiff, write_fixture_tiff
from prw.identity import hash_value
from prw.provenance import ProvenanceEnvelope
from prw.synthetic_line import (
    FROZEN_LINES,
    generate_synthetic_lines,
    read_synthetic_line,
    reader_envelope,
)

_EXACT = "\u03bb\u03bf\u03b3\u03bf\u03c2"
_ACCENTED = "\u03bb\u03cc\u03b3\u03bf\u03c2"
_MEDIAL = "\u03bb\u03bf\u03b3\u03bf\u03c3"
_XI = "\u03bb\u03bf\u03b3\u03bf\u03be"
_AS_WRITTEN = "\u03ba\u03c2"
_EXPANDED = "\u03ba\u03cd\u03c1\u03b9\u03bf\u03c2"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "prw.cli", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_comparison_strips_accents_and_final_sigma_without_rewriting_storage() -> None:
    stored = _ACCENTED
    assert unicodedata.normalize("NFC", stored) == stored
    assert comparison_text(stored) == _MEDIAL
    assert comparison_text("\u03c2") == "\u03c3"
    assert comparison_text("\u03cc") == "\u03bf"
    assert stored == _ACCENTED
    assert "\u03cc" in stored
    assert stored.endswith("\u03c2")


def test_comparison_refuses_nfd_storage() -> None:
    nfd = unicodedata.normalize("NFD", "\u03cc")
    assert nfd != "\u03cc"
    with pytest.raises(ValueError, match="Unicode NFC"):
        comparison_text(nfd)


def test_edit_distance_counts_insert_delete_and_substitute() -> None:
    assert edit_distance("\u03b1", "\u03b1") == 0
    assert edit_distance("\u03b1\u03b2", "\u03b1") == 1
    assert edit_distance("\u03b1", "\u03b1\u03b2") == 1
    assert edit_distance("\u03b1", "\u03b2") == 1
    assert edit_distance(_MEDIAL, _XI) == 1


def test_abbreviations_are_not_expanded() -> None:
    assert comparison_text(_AS_WRITTEN) != comparison_text(_EXPANDED)
    assert edit_distance(comparison_text(_AS_WRITTEN), comparison_text(_EXPANDED)) > 0
    assert exclusion_tag("Grek", "grc") is None
    assert exclusion_tag("nomen-sacrum", "grc") == "nomen-sacrum"
    assert exclusion_tag("Grek", "abbreviation") == "abbreviation"
    assert exclusion_tag("mixed-script", "grc") == "mixed-script"
    assert exclusion_tag("nomen-sacrum", "nomen-sacrum") == "nomen-sacrum"
    with pytest.raises(ValueError, match="one exclusion tag"):
        exclusion_tag("nomen-sacrum", "abbreviation")


def test_fixture_tiff_round_trip() -> None:
    payload = write_fixture_tiff(2, 2, bytes((0x03, 0x03, 0xBB, 0xBF)))
    raster = read_fixture_tiff(payload)
    assert isinstance(raster, FixtureSamples)
    assert raster.width == 2
    assert raster.height == 2
    assert raster.samples == bytes((0x03, 0x03, 0xBB, 0xBF))


def test_slot_reader_returns_the_painted_nfc_text() -> None:
    payload = write_fixture_tiff(len(_ACCENTED), 2, _rows(_ACCENTED))
    assert read_synthetic_line(payload) == _ACCENTED


def test_frozen_fixture_report_is_one_over_twenty_two(tmp_path: Path) -> None:
    benchmarks, images = _fixture(tmp_path)
    labels_before = (benchmarks / "labels.json").read_bytes()
    provenance_before = (benchmarks / "provenance.json").read_bytes()
    image_before = (images / "line-accent.tif").read_bytes()
    first = _score(benchmarks, images, "test-code")
    second = _score(benchmarks, images, "test-code")
    report = json.loads(first.read_text(encoding="utf-8"))
    assert report["metric"] == "character_error_rate"
    assert report["algorithm_name"] == "synthetic_line_slots"
    assert report["algorithm_version"] == "1"
    assert report["model_hash"] == "absent"
    assert report["random_seed"] == "absent"
    assert report["abbreviations_expanded"] is False
    assert report["storage"] == "nfc"
    assert report["claim"] == "synthetic-fixture result"
    assert report["edit_distance"] == 1
    assert report["reference_length"] == 22
    assert report["character_error_rate"] == 1 / 22
    assert report["scored_line_count"] == 5
    assert report["unscored_line_count"] == 3
    assert report["freeze_identifier"] == hash_value(labels_before)
    assert report["parameter_hash"] == hash_value(
        report["parameter_blob"].encode("utf-8")
    )
    assert "random_seed" not in json.loads(report["parameter_blob"])
    assert report["does_not_measure"] == (
        "Ancient Greek handwriting, scholarly acceptability, "
        "or the PP-OCRv6 medium model card"
    )
    assert report["model_card_figures"] == (
        "citations only; not this synthetic-fixture result"
    )
    assert report["limiting_questions"] == ["Q-SCI-06", "Q-SCI-13", "Q-SCI-15"]
    assert report["previous_report"] == "absent"
    assert "7.21" not in first.read_text(encoding="utf-8")
    assert "44.03" not in first.read_text(encoding="utf-8")
    assert "correct_join" not in first.read_text(encoding="utf-8")
    by_name = {item["image_name"]: item for item in report["line_list"]}
    accent = by_name["line-accent.tif"]
    assert accent["status"] == "scored"
    assert accent["reference_text"] == _ACCENTED
    assert accent["hypothesis_text"] == _EXACT
    assert accent["reference_comparison"] == _MEDIAL
    assert accent["hypothesis_comparison"] == _MEDIAL
    assert accent["edit_distance"] == 0
    final = by_name["line-final-sigma.tif"]
    assert final["reference_text"] == _MEDIAL
    assert final["hypothesis_text"] == _EXACT
    assert final["reference_comparison"] == final["hypothesis_comparison"] == _MEDIAL
    substituted = by_name["line-substitution.tif"]
    assert substituted["edit_distance"] == 1
    assert substituted["reference_length"] == 5
    assert substituted["character_error_rate"] == 1 / 5
    as_written = by_name["line-as-written.tif"]
    assert as_written["reference_text"] == as_written["hypothesis_text"] == _AS_WRITTEN
    assert as_written["exclusion"] == "absent"
    assert as_written["edit_distance"] == 0
    for name, tag in (
        ("line-nomen-sacrum.tif", "nomen-sacrum"),
        ("line-abbreviation.tif", "abbreviation"),
        ("line-mixed-script.tif", "mixed-script"),
    ):
        row = by_name[name]
        assert row["status"] == "unscored"
        assert row["exclusion"] == tag
        assert row["character_error_rate"] == "absent"
        assert "edit_distance" not in row
    abbreviated = by_name["line-abbreviation.tif"]
    assert abbreviated["reference_text"] == _AS_WRITTEN
    assert abbreviated["hypothesis_text"] == _EXPANDED
    later = json.loads(second.read_text(encoding="utf-8"))
    assert later["previous_report"] == first.name
    assert later["previous_line_list"] == report["line_list"]
    assert (benchmarks / "labels.json").read_bytes() == labels_before
    assert (benchmarks / "provenance.json").read_bytes() == provenance_before
    assert (images / "line-accent.tif").read_bytes() == image_before
    assert not (benchmarks / "manifest.json").exists()
    assert not (tmp_path / "originals").exists()
    provenance = json.loads(provenance_before)
    assert provenance["algorithm_name"] == "synthetic_line_fixture"
    assert "random_seed" not in provenance


def test_cli_writes_the_synthetic_report(tmp_path: Path) -> None:
    benchmarks = tmp_path / "benchmarks"
    images = tmp_path / "images"
    generated = _run(
        "character-error",
        "--generate-fixture",
        "--benchmarks",
        str(benchmarks),
        "--images",
        str(images),
        "--code-version",
        "test-code",
    )
    assert generated.returncode == 0, generated.stderr
    payload = json.loads(generated.stdout)
    assert payload["provenance"]["algorithm_name"] == "synthetic_line_fixture"
    assert "random_seed" not in payload["provenance"]
    labels = (benchmarks / "labels.json").read_bytes()
    scored = _run(
        "character-error",
        "--benchmarks",
        str(benchmarks),
        "--images",
        str(images),
        "--code-version",
        "test-code",
    )
    assert scored.returncode == 0, scored.stderr
    report = json.loads(scored.stdout)
    assert report["edit_distance"] == 1
    assert report["reference_length"] == 22
    assert report["character_error_rate"] == 1 / 22
    assert (benchmarks / "character_error" / "character-error-0001.json").is_file()
    assert (benchmarks / "labels.json").read_bytes() == labels
    again = _run(
        "character-error",
        "--generate-fixture",
        "--benchmarks",
        str(benchmarks),
        "--images",
        str(images),
        "--code-version",
        "test-code",
    )
    assert again.returncode == 2
    assert "written once" in again.stderr


def test_model_flag_does_not_download_or_score_without_weights(tmp_path: Path) -> None:
    benchmarks, images = _fixture(tmp_path)
    missing = _run(
        "character-error",
        "--benchmarks",
        str(benchmarks),
        "--images",
        str(images),
        "--code-version",
        "test-code",
        "--model",
        str(tmp_path / "medium.safetensors"),
    )
    assert missing.returncode == 2
    assert missing.stdout == ""
    assert "does not download weights" in missing.stderr
    assert not (benchmarks / "character_error").exists()
    if importlib.util.find_spec("kraken") is not None:
        return
    weight = tmp_path / "medium.safetensors"
    weight.write_bytes(b"not-a-model")
    refused = _run(
        "character-error",
        "--benchmarks",
        str(benchmarks),
        "--images",
        str(images),
        "--code-version",
        "test-code",
        "--model",
        str(weight),
    )
    assert refused.returncode == 2
    assert refused.stdout == ""
    assert "uv sync --group htr" in refused.stderr
    assert not (benchmarks / "character_error").exists()


def test_live_recognize_path_requires_local_weights(tmp_path: Path) -> None:
    weights = os.environ.get("PRW_HTR_WEIGHTS")
    if importlib.util.find_spec("kraken") is None or not weights:
        pytest.skip("The htr group and PRW_HTR_WEIGHTS are required.")
    model = Path(weights)
    if model.name != "medium.safetensors" or not model.is_file():
        pytest.skip("PRW_HTR_WEIGHTS is not a local medium.safetensors.")
    benchmarks, images = _fixture(tmp_path)
    scored = _run(
        "character-error",
        "--benchmarks",
        str(benchmarks),
        "--images",
        str(images),
        "--code-version",
        "test-code",
        "--model",
        str(model),
    )
    assert scored.returncode == 0, scored.stderr
    report = json.loads(scored.stdout)
    assert report["algorithm_name"] == "greek_line_htr"
    assert report["model_hash"] == hash_value(model.read_bytes())
    assert report["claim"] == "synthetic-fixture result"
    assert "7.21" not in scored.stdout
    assert "44.03" not in scored.stdout


def test_modules_do_not_import_kraken() -> None:
    for module in (
        sys.modules["prw.character_error"],
        sys.modules["prw.synthetic_line"],
        prw.recognize,
    ):
        source = Path(module.__file__ or "").read_text(encoding="utf-8")
        assert "import kraken" not in source
        assert "import torch" not in source
        assert "urllib" not in source


def test_project_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="project evidence database"):
        generate_synthetic_lines(
            tmp_path / "originals",
            images_dir=tmp_path / "images",
            code_version="test-code",
        )


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    benchmarks = tmp_path / "benchmarks"
    images = tmp_path / "images"
    generate_synthetic_lines(benchmarks, images_dir=images, code_version="test-code")
    return benchmarks, images


def _score(benchmarks: Path, images: Path, code_version: str) -> Path:
    manifest = json.loads((images / "image_manifest.json").read_text(encoding="utf-8"))
    hypotheses: dict[str, str] = {}
    hashes: list[str] = []
    for entry in manifest["images"]:
        payload = (images / entry["name"]).read_bytes()
        hypotheses[entry["name"]] = read_synthetic_line(payload)
        hashes.append(hash_value(payload))
    envelope = reader_envelope(source_hashes=hashes, code_version=code_version)
    return write_character_error(
        benchmarks,
        images_dir=images,
        envelope=envelope,
        hypotheses=hypotheses,
    )


def _rows(text: str) -> bytes:
    high = bytes(ord(char) >> 8 for char in text)
    low = bytes(ord(char) & 0xFF for char in text)
    return high + low


def test_frozen_lines_stay_nfc() -> None:
    assert len(FROZEN_LINES) == 8
    for spec in FROZEN_LINES:
        assert unicodedata.normalize("NFC", spec.reference_text) == spec.reference_text
        assert unicodedata.normalize("NFC", spec.painted_text) == spec.painted_text


def test_htr_envelope_is_accepted_without_a_model_file(tmp_path: Path) -> None:
    benchmarks, images = _fixture(tmp_path)
    manifest = json.loads((images / "image_manifest.json").read_text(encoding="utf-8"))
    hypotheses = {entry["name"]: _EXACT for entry in manifest["images"]}
    hashes = [entry["content_hash"] for entry in manifest["images"]]
    envelope = ProvenanceEnvelope.create(
        source_hashes=hashes,
        parameters={"reader": "greek_line_htr", "model_file": "medium.safetensors"},
        algorithm_name="greek_line_htr",
        algorithm_version="1",
        code_version="test-code",
        decoder_name="synthetic_uncompressed_tiff",
        decoder_version="1",
        model_hash="sha256:" + "ab" * 32,
    )
    path = write_character_error(
        benchmarks,
        images_dir=images,
        envelope=envelope,
        hypotheses=hypotheses,
    )
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["algorithm_name"] == "greek_line_htr"
    assert report["model_hash"] == "sha256:" + "ab" * 32
    assert report["random_seed"] == "absent"
    assert report["claim"] == "synthetic-fixture result"
