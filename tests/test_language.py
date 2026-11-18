"""Language scores on hypotheses the physical search already admitted."""

import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from prw.identity import ABSENT, content_id, hash_value
from prw.language import (
    ALGORITHM_NAME,
    ALGORITHM_VERSION,
    SCORE_NAME,
    LanguageGrapheme,
    LanguageHypothesis,
    LanguageReading,
    LanguageRequest,
    LanguageScoreLog,
    LanguageScoreRun,
    PhysicalAdmission,
    SuppliedLetters,
    language_order,
    language_request_from_mapping,
    load_language_input,
    one_hypothesis_request,
    parameter_blob,
)
from prw.provenance import run_id_inputs
from prw.screening import ScreeningEvent

_RECORDED = "2020-01-01T00:00:00Z"
_LATER = "2020-01-01T00:00:01Z"
_ALPHA = "\u03b1"
_BETA = "\u03b2"
_GAMMA = "\u03b3"
_KAPPA_SIGMA = "\u03ba\u03c2"


def _source() -> str:
    return hash_value(b"synthetic-language-source")


def _grapheme(text: str, status: str = "ocr_inferred") -> LanguageGrapheme:
    if status == "human_read" or status == "unclear" or status == "ocr_inferred":
        return LanguageGrapheme(text=text, text_status=status)
    raise AssertionError(status)


def _reading(
    text: str,
    status: str = "ocr_inferred",
    *,
    script: str = "Grek",
    language: str = "grc",
) -> LanguageReading:
    return LanguageReading(
        script=script,
        language=language,
        graphemes=(_grapheme(text, status),),
    )


def _hypothesis(
    hypothesis_id: uuid.UUID,
    readings: tuple[LanguageReading, ...],
    *,
    hypothesis_type: str = "join",
    supplied: tuple[SuppliedLetters, ...] = (),
) -> LanguageHypothesis:
    if hypothesis_type != "join" and hypothesis_type != "assembly":
        raise ValueError("Language scores a join or an assembly.")
    return LanguageHypothesis(
        hypothesis_id=hypothesis_id,
        hypothesis_type=hypothesis_type,
        readings=readings,
        supplied=supplied,
    )


def _request(
    hypotheses: tuple[LanguageHypothesis, ...],
    events: tuple[PhysicalAdmission, ...],
) -> LanguageRequest:
    return LanguageRequest(
        source_hashes=(_source(),),
        physical_events=events,
        hypotheses=hypotheses,
    )


def _admitted(hypothesis_id: uuid.UUID) -> PhysicalAdmission:
    return PhysicalAdmission(
        run_id=uuid.UUID(int=9),
        hypothesis_id=hypothesis_id,
        outcome="admitted",
    )


def _score(
    hypotheses: tuple[LanguageHypothesis, ...],
    events: tuple[PhysicalAdmission, ...],
    *,
    code_version: str = "test-code",
    recorded_at: str = _RECORDED,
) -> tuple[LanguageScoreLog, LanguageScoreRun]:
    log = LanguageScoreLog()
    result = log.score(
        _request(hypotheses, events),
        code_version=code_version,
        recorded_at=recorded_at,
    )
    return log, result


def test_an_admitted_join_receives_one_language_score() -> None:
    hypothesis_id = uuid.UUID(int=3)
    reading = _reading(_ALPHA + _BETA)
    before = reading.graphemes[0].text
    _log, result = _score(
        (_hypothesis(hypothesis_id, (reading,)),),
        (_admitted(hypothesis_id),),
    )
    assert result.run.status == "completed"
    assert result.run.attempt_id is None
    assert result.run.join_ids == ()
    assert result.run.assembly_ids == ()
    assert result.run.reading_ids == ()
    assert result.assemblies == ()
    assert len(result.joins) == 1
    annotation = result.joins[0]
    assert annotation.hypothesis_id == hypothesis_id
    assert annotation.hypothesis_type == "join"
    assert annotation.score.channel == "language"
    assert annotation.score.hypothesis_type == "join"
    assert annotation.score.value == 2
    assert annotation.score.run_id == result.run.id
    assert annotation.score.value > 1
    assert not hasattr(annotation, "rank")
    assert result.screening == (
        ScreeningEvent.create(
            run_id=result.run.id,
            hypothesis_id=hypothesis_id,
            gate="language",
            outcome="admitted",
        ),
    )
    assert result.screening[0].id == content_id(result.screening[0].id_inputs())
    assert reading.graphemes[0].text == before
    envelope = result.run.provenance
    assert envelope.algorithm_name == ALGORITHM_NAME
    assert envelope.algorithm_version == ALGORITHM_VERSION
    assert envelope.model_hash == ABSENT
    assert envelope.random_seed is None
    assert "random_seed" not in envelope.content_mapping()
    assert envelope.decoder_name == ABSENT
    assert envelope.parameter_hash == hash_value(
        envelope.parameter_blob.encode("utf-8")
    )
    assert envelope.parameter_hash.startswith("sha256:")
    assert result.run.id == content_id(run_id_inputs(envelope, "completed", None))
    blob = parameter_blob(result)
    assert blob["score"] == SCORE_NAME
    assert blob["training"] == "none"
    assert blob["calibration"] == "uncalibrated"
    assert blob["generates_graphemes"] is False
    assert blob["creates_joins"] is False
    assert blob["abbreviations_expanded"] is False
    assert blob["hypotheses"][0]["readings"][0]["graphemes"][0]["text"] == before
    for banned in ("weights", "weighted_sum", "fusion", "probability"):
        assert banned not in blob


def test_a_geometry_rejection_is_excluded_and_creates_no_join() -> None:
    hypothesis_id = uuid.UUID(int=4)
    event = PhysicalAdmission(
        run_id=uuid.UUID(int=9),
        hypothesis_id=hypothesis_id,
        outcome="excluded",
    )
    _log, result = _score(
        (_hypothesis(hypothesis_id, (_reading(_ALPHA * 4),)),),
        (event,),
    )
    assert result.joins == ()
    assert result.assemblies == ()
    assert result.run.join_ids == ()
    assert result.screening[0].gate == "language"
    assert result.screening[0].outcome == "excluded"
    assert result.screening[0].hypothesis_id == hypothesis_id
    source = Path(sys.modules["prw.language"].__file__ or "").read_text(
        encoding="utf-8"
    )
    assert "from prw.joins" not in source
    assert "import prw.joins" not in source
    assert "torch" not in source
    assert "kraken" not in source
    assert "benchmarks" not in source


def test_no_eligible_grapheme_writes_no_score_and_does_not_invent_letters() -> None:
    hypothesis_id = uuid.UUID(int=5)
    supplied = SuppliedLetters(
        text=_ALPHA + _BETA + _GAMMA, label="supplied", treatment="labeled_gap"
    )
    _log, result = _score(
        (
            _hypothesis(
                hypothesis_id,
                (LanguageReading(script="Grek", language="grc", graphemes=()),),
                supplied=(supplied,),
            ),
        ),
        (_admitted(hypothesis_id),),
    )
    assert result.joins == ()
    assert result.screening[0].outcome == "excluded"
    blob = parameter_blob(result)
    assert blob["hypotheses"][0]["supplied"][0]["text"] == supplied.text
    assert blob["generates_graphemes"] is False
    assert "text_status" not in blob["hypotheses"][0]["supplied"][0]


def test_an_empty_grapheme_is_eligible_and_scores_zero() -> None:
    hypothesis_id = uuid.UUID(int=6)
    _log, result = _score(
        (_hypothesis(hypothesis_id, (_reading(""),)),),
        (_admitted(hypothesis_id),),
    )
    assert result.joins[0].score.value == 0
    assert result.screening[0].outcome == "admitted"


def test_unseen_and_excluded_physical_gates_write_no_score() -> None:
    admitted_id = uuid.UUID(int=1)
    unseen_id = uuid.UUID(int=2)
    _log, result = _score(
        (
            _hypothesis(unseen_id, (_reading(_ALPHA),)),
            _hypothesis(admitted_id, (_reading(_BETA),)),
        ),
        (_admitted(admitted_id),),
    )
    assert [item.hypothesis_id for item in result.joins] == [admitted_id]
    outcomes = {event.hypothesis_id: event.outcome for event in result.screening}
    assert outcomes[unseen_id] == "excluded"
    assert outcomes[admitted_id] == "admitted"


def test_supplied_letters_need_a_label_and_a_recorded_treatment() -> None:
    with pytest.raises(ValueError, match="explicit restoration label"):
        SuppliedLetters(text=_ALPHA, label="human_read", treatment="labeled_gap")
    with pytest.raises(ValueError, match="explicit restoration label"):
        SuppliedLetters(text=_ALPHA, label="missing", treatment="labeled_gap")
    with pytest.raises(ValueError, match="non-empty"):
        SuppliedLetters(text=_ALPHA, label="", treatment="labeled_gap")
    with pytest.raises(ValueError, match="treatment"):
        SuppliedLetters(text=_ALPHA, label="supplied", treatment="")
    with pytest.raises(ValueError, match="non-empty"):
        SuppliedLetters(text="", label="supplied", treatment="labeled_gap")
    payload = {
        "source_hashes": [_source()],
        "physical_events": [],
        "hypotheses": [
            {
                "hypothesis_id": str(uuid.UUID(int=1)),
                "hypothesis_type": "join",
                "readings": [],
                "supplied": [{"text": _ALPHA, "treatment": "labeled_gap"}],
            }
        ],
    }
    with pytest.raises(ValueError, match="missing label"):
        language_request_from_mapping(payload)


def test_labeled_supplied_letters_are_added_only_with_eligible_graphemes() -> None:
    hypothesis_id = uuid.UUID(int=8)
    supplied = SuppliedLetters(
        text=_GAMMA,
        label="supplied",
        treatment="labeled_gap",
    )
    _log, result = _score(
        (
            _hypothesis(
                hypothesis_id,
                (_reading(_ALPHA),),
                supplied=(supplied,),
            ),
        ),
        (_admitted(hypothesis_id),),
    )
    assert result.joins[0].score.value == 2
    blob = parameter_blob(result)
    stored = blob["hypotheses"][0]["supplied"][0]
    assert stored["label"] == "supplied"
    assert stored["treatment"] == "labeled_gap"
    assert stored["text"] == _GAMMA
    assert blob["supplied_text"] == "labeled_addition_on_admitted_eligible_graphemes"
    bare_id = uuid.UUID(int=11)
    bare = PhysicalAdmission(
        run_id=uuid.UUID(int=9),
        hypothesis_id=bare_id,
        outcome="excluded",
    )
    _log, excluded = _score(
        (_hypothesis(bare_id, (_reading(_ALPHA),), supplied=(supplied,)),),
        (bare,),
    )
    assert excluded.joins == ()
    assert excluded.screening[0].outcome == "excluded"


def test_exclusion_tags_are_left_unscored_and_abbreviations_are_not_expanded() -> None:
    kept = uuid.UUID(int=12)
    tagged = uuid.UUID(int=13)
    short = LanguageGrapheme(text=_KAPPA_SIGMA, text_status="ocr_inferred")
    _log, result = _score(
        (
            _hypothesis(kept, (_reading(_ALPHA),)),
            _hypothesis(
                tagged,
                (
                    LanguageReading(
                        script="Grek",
                        language="abbreviation",
                        graphemes=(short,),
                    ),
                    _reading(_BETA),
                ),
            ),
        ),
        (_admitted(kept), _admitted(tagged)),
    )
    by_id = {item.hypothesis_id: item.score.value for item in result.joins}
    assert by_id[kept] == 1
    assert by_id[tagged] == 1
    assert short.text == _KAPPA_SIGMA
    for tag in ("nomen-sacrum", "abbreviation", "mixed-script"):
        only = uuid.UUID(int=20)
        _log, excluded = _score(
            (
                _hypothesis(
                    only,
                    (
                        LanguageReading(
                            script=tag,
                            language="grc",
                            graphemes=(
                                LanguageGrapheme(
                                    text=_ALPHA * 3, text_status="human_read"
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            (_admitted(only),),
        )
        assert excluded.joins == ()
        assert excluded.screening[0].outcome == "excluded"
    with pytest.raises(ValueError, match="one exclusion tag"):
        LanguageReading(
            script="nomen-sacrum",
            language="abbreviation",
            graphemes=(_reading(_ALPHA).graphemes[0],),
        )


def test_human_read_and_unclear_are_eligible_and_other_statuses_are_refused() -> None:
    human_id = uuid.UUID(int=14)
    unclear_id = uuid.UUID(int=15)
    _log, result = _score(
        (
            _hypothesis(human_id, (_reading(_ALPHA, "human_read"),)),
            _hypothesis(unclear_id, (_reading("", "unclear"), _reading(_BETA))),
        ),
        (_admitted(human_id), _admitted(unclear_id)),
    )
    by_id = {item.hypothesis_id: item.score.value for item in result.joins}
    assert by_id[human_id] == 1
    assert by_id[unclear_id] == 1
    with pytest.raises(ValueError, match="text status"):
        LanguageGrapheme(text=_ALPHA, text_status="missing")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="text status"):
        LanguageGrapheme(text=_ALPHA, text_status="supplied")  # type: ignore[arg-type]
    nfd = "\u03b1\u0301"
    assert nfd != "\u03ac"
    with pytest.raises(ValueError, match="Unicode NFC"):
        LanguageGrapheme(text=nfd, text_status="ocr_inferred")


def test_rank_stays_inside_one_hypothesis_type() -> None:
    longer = uuid.UUID(int=2)
    shorter = uuid.UUID(int=30)
    assembly_id = uuid.UUID(int=40)
    _log, result = _score(
        (
            _hypothesis(shorter, (_reading(_ALPHA),)),
            _hypothesis(longer, (_reading(_ALPHA * 3),)),
            _hypothesis(
                assembly_id,
                (_reading(_BETA),),
                hypothesis_type="assembly",
            ),
        ),
        (_admitted(shorter), _admitted(longer), _admitted(assembly_id)),
    )
    assert [item.hypothesis_id for item in result.joins] == [longer, shorter]
    assert [item.hypothesis_id for item in result.assemblies] == [assembly_id]
    tied_left = uuid.UUID(int=1)
    tied_right = uuid.UUID(int=2)
    _log, tied = _score(
        (
            _hypothesis(tied_right, (_reading(_ALPHA),)),
            _hypothesis(tied_left, (_reading(_BETA),)),
        ),
        (_admitted(tied_left), _admitted(tied_right)),
    )
    expected = tuple(sorted((tied_left, tied_right), key=lambda item: item.bytes))
    assert [item.hypothesis_id for item in tied.joins] == list(expected)
    with pytest.raises(ValueError, match="mixed hypothesis types"):
        language_order((*result.joins, *result.assemblies))


def test_a_repeated_run_is_deterministic_and_stores_one_row() -> None:
    hypothesis_id = uuid.UUID(int=16)
    request = _request(
        (_hypothesis(hypothesis_id, (_reading(_ALPHA),)),),
        (_admitted(hypothesis_id),),
    )
    log = LanguageScoreLog()
    first = log.score(request, code_version="test-code", recorded_at=_RECORDED)
    second = log.score(request, code_version="test-code", recorded_at=_LATER)
    assert second is first
    assert second.run.started_at == _RECORDED
    assert len(log.runs) == 1
    assert len(log.screening) == 1
    other = log.score(request, code_version="other-code", recorded_at=_RECORDED)
    assert other.run.id != first.run.id
    assert len(log.runs) == 2
    assert len(log.screening) == 2


def test_conflicting_physical_outcomes_and_duplicate_ids_are_refused() -> None:
    hypothesis_id = uuid.UUID(int=17)
    admitted = _admitted(hypothesis_id)
    excluded = PhysicalAdmission(
        run_id=uuid.UUID(int=8),
        hypothesis_id=hypothesis_id,
        outcome="excluded",
    )
    with pytest.raises(ValueError, match="one physical outcome"):
        _request(
            (_hypothesis(hypothesis_id, (_reading(_ALPHA),)),), (admitted, excluded)
        )
    with pytest.raises(ValueError, match="offered once"):
        _request(
            (
                _hypothesis(hypothesis_id, (_reading(_ALPHA),)),
                _hypothesis(hypothesis_id, (_reading(_BETA),)),
            ),
            (_admitted(hypothesis_id),),
        )
    with pytest.raises(ValueError, match="listed once"):
        _request(
            (_hypothesis(hypothesis_id, (_reading(_ALPHA),)),),
            (admitted, admitted),
        )
    log = LanguageScoreLog()
    assert log.runs == ()
    with pytest.raises(ValueError, match="join or an assembly"):
        LanguageHypothesis(
            hypothesis_id=hypothesis_id,
            hypothesis_type="reading",  # type: ignore[arg-type]
            readings=(_reading(_ALPHA),),
        )


def test_cli_prints_ranked_scores_and_screening(tmp_path: Path) -> None:
    hypothesis_id = uuid.UUID(int=18)
    physical_run = uuid.UUID(int=19)
    payload = {
        "source_hashes": [_source()],
        "physical_events": [
            {
                "run_id": str(physical_run),
                "hypothesis_id": str(hypothesis_id),
                "outcome": "admitted",
            }
        ],
        "hypotheses": [
            {
                "hypothesis_id": str(hypothesis_id),
                "hypothesis_type": "join",
                "readings": [
                    {
                        "script": "Grek",
                        "language": "grc",
                        "graphemes": [
                            {"text": _ALPHA + _BETA, "text_status": "ocr_inferred"}
                        ],
                    }
                ],
                "supplied": [
                    {"text": _GAMMA, "label": "supplied", "treatment": "labeled_gap"}
                ],
            }
        ],
    }
    path = tmp_path / "language.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    completed = _run(
        "language",
        "--input",
        str(path),
        "--code-version",
        "test-code",
        "--recorded-at",
        _RECORDED,
    )
    assert completed.returncode == 0, completed.stderr
    printed = json.loads(completed.stdout)
    assert printed["record"] == "LanguageScores"
    assert printed["status"] == "completed"
    assert printed["joins"][0]["hypothesis_id"] == str(hypothesis_id)
    assert printed["joins"][0]["score"]["channel"] == "language"
    assert printed["joins"][0]["score"]["value"] == 3
    assert "rank" not in printed["joins"][0]
    assert printed["assemblies"] == []
    assert printed["screening"][0]["gate"] == "language"
    assert printed["screening"][0]["outcome"] == "admitted"
    assert printed["envelope"]["algorithm_name"] == ALGORITHM_NAME
    assert printed["envelope"]["model_hash"] == ABSENT
    assert "random_seed" not in printed["envelope"]
    assert "JoinHypothesis" not in completed.stdout
    assert "correct_join" not in completed.stdout
    assert list(tmp_path.iterdir()) == [path]

    flags = _run(
        "language",
        "--code-version",
        "test-code",
        "--recorded-at",
        _RECORDED,
        "--source-hash",
        _source(),
        "--hypothesis-id",
        str(hypothesis_id),
        "--hypothesis-type",
        "join",
        "--physical-run-id",
        str(physical_run),
        "--physical-outcome",
        "excluded",
        "--script",
        "Grek",
        "--language",
        "grc",
        "--grapheme",
        f"{_ALPHA}=ocr_inferred",
    )
    assert flags.returncode == 0, flags.stderr
    excluded = json.loads(flags.stdout)
    assert excluded["joins"] == []
    assert excluded["screening"][0]["outcome"] == "excluded"

    refused = _run(
        "language",
        "--code-version",
        "test-code",
        "--recorded-at",
        _RECORDED,
        "--source-hash",
        _source(),
        "--hypothesis-id",
        str(hypothesis_id),
        "--hypothesis-type",
        "join",
        "--physical-run-id",
        str(physical_run),
        "--physical-outcome",
        "admitted",
        "--script",
        "Grek",
        "--language",
        "grc",
        "--supplied-text",
        _GAMMA,
        "--supplied-label",
        "supplied",
    )
    assert refused.returncode == 2
    assert refused.stdout == ""
    assert "Traceback" not in refused.stderr
    assert "treatment" in refused.stderr


def test_the_loader_refuses_a_corpus_path_a_tiff_and_an_unknown_field(
    tmp_path: Path,
) -> None:
    corpus = tmp_path / "data" / "language.json"
    corpus.parent.mkdir()
    corpus.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="real-corpus"):
        load_language_input(corpus)
    tiff = tmp_path / "line.tif"
    tiff.write_bytes(b"not-a-tiff")
    with pytest.raises(ValueError, match="TIFF"):
        load_language_input(tiff)
    with pytest.raises(ValueError, match="unknown field"):
        language_request_from_mapping(
            {
                "source_hashes": [_source()],
                "physical_events": [],
                "hypotheses": [],
                "generated_letters": _ALPHA,
            }
        )
    request = one_hypothesis_request(
        source_hashes=(_source(),),
        hypothesis_id=uuid.UUID(int=21),
        hypothesis_type="assembly",
        script="Grek",
        language="grc",
        graphemes=((_ALPHA, "ocr_inferred"),),
        physical_run_id=None,
        physical_outcome=None,
        supplied_text=None,
        supplied_label=None,
        supplied_treatment=None,
    )
    result = LanguageScoreLog().score(
        request,
        code_version="test-code",
        recorded_at=_RECORDED,
    )
    assert result.joins == ()
    assert result.assemblies == ()
    assert result.screening[0].outcome == "excluded"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "prw.cli", *args],
        capture_output=True,
        text=True,
        check=False,
    )
