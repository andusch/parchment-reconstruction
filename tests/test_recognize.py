"""Line recognition without Kraken, torch, or a weight file."""

import importlib.util
import io
import json
import os
import subprocess
import sys
import unicodedata
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from prw.identity import hash_value, require_hash
from prw.ingest import IntegrityFailure, UnsupportedMediaType
from prw.readings import GraphemeHypothesis
from prw.recognize import (
    HTR_INSTALL_MESSAGE,
    HtrGroupMissing,
    LineRecognition,
    LineRecognitionLog,
    PreparedLine,
    grapheme_texts,
    model_hash_for_weights,
    prepare_line_image,
    storage_text,
)
from prw.synthetic_tear import _uncompressed_grayscale_tiff

_ZENODO_MD5 = "e3411a453ce3b9e9efae3f8631d85762"
_RECORDED_AT = "2026-11-14T00:00:00Z"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "prw.cli", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _line_tiff() -> bytes:
    return _uncompressed_grayscale_tiff(2, 2, bytes((0, 1, 2, 3)))


def _prepared() -> PreparedLine:
    prepared = prepare_line_image(_line_tiff())
    assert isinstance(prepared, PreparedLine)
    return prepared


def _store(
    prediction: str,
    *,
    weight_bytes: bytes | None = b"local-weights",
    script: str = "Grek",
    language: str = "grc",
) -> LineRecognition:
    return LineRecognitionLog().store(
        _prepared(),
        weight_bytes=weight_bytes,
        prediction=prediction,
        label="shelf-4",
        script=script,
        language=language,
        code_version="test-code",
        runtime_version="7.1.0",
        recorded_at=_RECORDED_AT,
    )


def test_import_does_not_load_kraken_or_torch() -> None:
    import prw.recognize as recognize

    assert "kraken" not in sys.modules
    assert "torch" not in sys.modules
    source = Path(recognize.__file__).read_text(encoding="utf-8")
    assert "urllib" not in source
    assert "zenodo.org" not in source
    assert "huggingface" not in source
    assert _ZENODO_MD5 not in source
    assert "synthetic_tear" not in source


def test_storage_text_composes_nfd_and_keeps_final_sigma() -> None:
    accented = storage_text("\u03b1\u0301")
    assert accented == "\u03ac"
    assert unicodedata.normalize("NFD", accented) != accented
    final_sigma = storage_text("\u03c2")
    assert final_sigma == "\u03c2"
    assert final_sigma != "\u03c3"
    composed = storage_text("\u03b8\u03b5\u03bf\u0301\u03c2")
    assert composed == "\u03b8\u03b5\u03cc\u03c2"
    assert "\u0301" not in composed
    assert composed.endswith("\u03c2")
    assert storage_text(composed) == composed
    assert grapheme_texts("\u03b1\u0301\u03c2") == ("\u03ac", "\u03c2")


def test_model_hash_is_local_bytes_or_absent() -> None:
    digest = model_hash_for_weights(b"local-weights")
    assert digest == hash_value(b"local-weights")
    assert digest.startswith("sha256:")
    assert model_hash_for_weights(None) == "absent"
    assert digest != _ZENODO_MD5
    with pytest.raises(ValueError, match="sha256:"):
        require_hash(_ZENODO_MD5)


def test_nfd_prediction_is_stored_as_ocr_inferred_interpretation() -> None:
    stored = _store("\u03b1\u0301\u03c2")
    assert stored.reading.epistemic_class == "interpretation"
    assert stored.reading.producer == "machine"
    assert stored.reading.script == "Grek"
    assert stored.reading.language == "grc"
    assert stored.reading.text == "\u03ac\u03c2"
    assert [item.text for item in stored.graphemes] == ["\u03ac", "\u03c2"]
    assert {item.text_status for item in stored.graphemes} == {"ocr_inferred"}
    assert {item.epistemic_class for item in stored.graphemes} == {"interpretation"}
    assert {item.producer for item in stored.graphemes} == {"machine"}
    assert stored.run.provenance.model_hash == hash_value(b"local-weights")
    assert "random_seed" not in stored.run.provenance.content_mapping()
    assert all(event.status == "proposed" for event in stored.proposed)
    blob = json.loads(stored.run.provenance.parameter_blob)
    assert blob["unicode_normalization"] == "NFC"
    assert blob["scored"] is False
    assert blob["model_file"] == "medium.safetensors"
    assert blob["runtime"] == "kraken"
    assert "sha256:" not in stored.run.provenance.parameter_blob


def test_special_tags_are_stored_and_unscored() -> None:
    stored = _store(
        "\u03ba\u03c2",
        script="mixed",
        language="grc-nomen-sacrum",
    )
    assert stored.reading.script == "mixed"
    assert stored.reading.language == "grc-nomen-sacrum"
    assert stored.reading.text == "\u03ba\u03c2"
    assert stored.reading.text.endswith("\u03c2")
    mapping = stored.reading.content_mapping()
    assert "scores" not in mapping
    assert "htr" not in mapping
    assert "language_score" not in mapping


def test_a_run_without_a_model_records_model_hash_absent() -> None:
    stored = _store("\u03b1", weight_bytes=None)
    assert stored.run.provenance.model_hash == "absent"
    assert stored.reading.epistemic_class == "interpretation"
    assert stored.graphemes[0].text_status == "ocr_inferred"


def test_the_same_completed_inputs_return_the_stored_reading() -> None:
    log = LineRecognitionLog()
    prepared = _prepared()
    kwargs = {
        "weight_bytes": b"local-weights",
        "prediction": "\u03b1\u0301",
        "label": "shelf-4",
        "script": "Grek",
        "language": "grc",
        "code_version": "test-code",
        "runtime_version": "7.1.0",
        "recorded_at": _RECORDED_AT,
    }
    first = log.store(prepared, **kwargs)
    second = log.store(prepared, **kwargs)
    assert second.reading.id == first.reading.id
    assert len(log.runs) == 1


def test_grapheme_storage_rejects_nfd() -> None:
    with pytest.raises(ValueError, match="NFC"):
        GraphemeHypothesis.create(
            reading_id=uuid.uuid4(),
            text="\u03b1\u0301",
            frame_id=uuid.uuid4(),
            ink_region=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
            run_id=uuid.uuid4(),
            position=0,
        )


def test_printed_reading_has_no_score_and_no_join_claim() -> None:
    import prw.cli as cli

    stored = _store("\u03b1\u0301\u03c2")
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        cli._print_recognition(stored)
    payload = json.loads(stdout.getvalue())
    assert payload["record"] == "ReadingHypothesis"
    assert payload["epistemic_class"] == "interpretation"
    assert payload["producer"] == "machine"
    assert payload["text"] == "\u03ac\u03c2"
    assert payload["graphemes"][0]["text_status"] == "ocr_inferred"
    assert "scores" not in payload
    assert "confidence" not in stdout.getvalue()
    assert "probability" not in stdout.getvalue()
    assert "correct_join" not in stdout.getvalue()
    assert payload["envelope"]["model_hash"] == hash_value(b"local-weights")
    assert payload["envelope"]["algorithm_name"] == "greek_line_htr"


def test_cli_rejects_a_missing_weight_path(tmp_path: Path) -> None:
    missing = tmp_path / "no-such" / "medium.safetensors"
    completed = _run(
        "recognize",
        str(tmp_path / "line.tif"),
        "--model",
        str(missing),
        "--label",
        "shelf-4",
        "--code-version",
        "test-code",
    )
    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "medium.safetensors" in completed.stderr
    assert "does not download" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_cli_rejects_a_weight_file_with_another_name(tmp_path: Path) -> None:
    weight = tmp_path / "other.safetensors"
    weight.write_bytes(b"not-weights")
    completed = _run(
        "recognize",
        str(tmp_path / "line.tif"),
        "--model",
        str(weight),
        "--label",
        "shelf-4",
        "--code-version",
        "test-code",
    )
    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "medium.safetensors" in completed.stderr


def test_cli_missing_htr_group(tmp_path: Path) -> None:
    if importlib.util.find_spec("kraken") is not None:
        pytest.skip("The htr group is installed, so the missing-group path is patched.")
    weight = tmp_path / "medium.safetensors"
    weight.write_bytes(b"not-weights")
    image = tmp_path / "line.tif"
    image.write_bytes(_line_tiff())
    completed = _run(
        "recognize",
        str(image),
        "--model",
        str(weight),
        "--label",
        "shelf-4",
        "--code-version",
        "test-code",
    )
    assert completed.returncode == 2
    assert completed.stdout == ""
    assert HTR_INSTALL_MESSAGE in completed.stderr
    assert "Traceback" not in completed.stderr


def test_cli_missing_group_message_is_actionable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import prw.cli as cli

    weight = tmp_path / "medium.safetensors"
    weight.write_bytes(b"not-weights")
    image = tmp_path / "line.tif"
    image.write_bytes(_line_tiff())

    def missing() -> str:
        raise HtrGroupMissing(HTR_INSTALL_MESSAGE)

    monkeypatch.setattr(cli, "require_htr_group", missing)
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        status = cli.main(
            [
                "recognize",
                str(image),
                "--model",
                str(weight),
                "--label",
                "shelf-4",
                "--code-version",
                "test-code",
            ]
        )
    assert status == 2
    assert stdout.getvalue() == ""
    assert HTR_INSTALL_MESSAGE in stderr.getvalue()


def test_cli_rejects_a_non_tiff_before_prediction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import prw.cli as cli

    weight = tmp_path / "medium.safetensors"
    weight.write_bytes(b"not-weights")
    image = tmp_path / "line.txt"
    image.write_bytes(b"not-a-tiff\n")
    monkeypatch.setattr(cli, "require_htr_group", lambda: "7.1.0")

    def unexpected(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("A non-TIFF line image does not call the recognizer.")

    monkeypatch.setattr(cli, "predict_line_text", unexpected)
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        status = cli.main(
            [
                "recognize",
                str(image),
                "--model",
                str(weight),
                "--label",
                "shelf-4",
                "--code-version",
                "test-code",
            ]
        )
    assert status == 1
    payload = json.loads(stdout.getvalue())
    assert payload["record"] == "UnsupportedMediaType"
    assert "reading" not in payload


def test_checksum_mismatch_stores_no_reading() -> None:
    payload = _line_tiff()
    result = prepare_line_image(payload, expected_hash="sha256:" + "ab" * 32)
    assert isinstance(result, IntegrityFailure)
    assert not isinstance(result, UnsupportedMediaType)


def test_htr_group_is_optional_in_pyproject() -> None:
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "dependencies = []" in text
    assert 'default-groups = ["dev", "ui"]' in text
    assert "kraken>=7.1.0" in text
    assert "htr" in text


def _live_weight_path() -> str | None:
    raw = os.environ.get("PRW_HTR_WEIGHTS", "")
    if raw == "":
        return None
    path = Path(raw)
    if path.name != "medium.safetensors" or not path.is_file():
        return None
    if importlib.util.find_spec("kraken") is None:
        return None
    return str(path)


@pytest.mark.skipif(
    _live_weight_path() is None,
    reason=(
        "Live recognition needs the htr group and PRW_HTR_WEIGHTS pointing "
        "at a local medium.safetensors. This test does not fetch weights."
    ),
)
def test_live_recognizer_when_local_weights_are_present(tmp_path: Path) -> None:
    weight = _live_weight_path()
    assert weight is not None
    image = tmp_path / "line.tif"
    image.write_bytes(_line_tiff())
    completed = _run(
        "recognize",
        str(image),
        "--model",
        weight,
        "--label",
        "shelf-4",
        "--code-version",
        "test-code",
        "--script",
        "Grek",
        "--language",
        "grc",
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["record"] == "ReadingHypothesis"
    assert payload["epistemic_class"] == "interpretation"
    assert payload["producer"] == "machine"
    assert payload["graphemes"]
    assert {item["text_status"] for item in payload["graphemes"]} == {"ocr_inferred"}
    assert payload["envelope"]["model_hash"] == hash_value(Path(weight).read_bytes())
    assert "character_error_rate" not in payload
    assert "confidence" not in completed.stdout
    assert unicodedata.normalize("NFC", payload["text"]) == payload["text"]
