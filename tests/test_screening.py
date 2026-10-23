"""In-memory screening events for a gate a hypothesis has already met."""

import dataclasses
import uuid

import pytest

from prw.identity import content_id
from prw.provenance import AssemblyContent
from prw.screening import ScreeningEvent, ScreeningLog


def _hypothesis() -> AssemblyContent:
    return AssemblyContent.create(
        page_frame_id=uuid.uuid4(),
        producer="machine",
        provenance_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
    )


def test_physical_admission_and_exclusion_round_trip() -> None:
    hypothesis = _hypothesis()
    before = hypothesis.content_bytes()
    run_id = uuid.uuid4()
    admitted = ScreeningEvent.create(
        run_id=run_id,
        hypothesis_id=hypothesis.id,
        gate="physical",
        outcome="admitted",
    )
    excluded = ScreeningEvent.create(
        run_id=run_id,
        hypothesis_id=hypothesis.id,
        gate="physical",
        outcome="excluded",
    )
    assert admitted.id != excluded.id
    assert admitted.id.version == 5
    assert admitted.id == content_id(admitted.id_inputs())
    assert excluded.id == content_id([run_id, hypothesis.id, "physical", "excluded"])
    names = {field.name for field in dataclasses.fields(admitted)}
    assert "status" not in names
    assert "epistemic_class" not in names
    assert "score" not in names
    log = ScreeningLog()
    assert log.append(admitted) is admitted
    assert log.append(excluded) is excluded
    assert log.by_id(admitted.id) is admitted
    assert log.by_id(excluded.id) is excluded
    assert log.by_id(admitted.id).outcome == "admitted"
    assert log.by_id(excluded.id).outcome == "excluded"
    assert hypothesis.content_bytes() == before
    assert hypothesis.id == content_id(hypothesis.id_inputs())
    with pytest.raises(KeyError, match="ScreeningEvent"):
        log.by_id(uuid.uuid4())


def test_gate_and_outcome_words_are_closed() -> None:
    run_id = uuid.uuid4()
    hypothesis_id = uuid.uuid4()
    with pytest.raises(ValueError, match="gate"):
        ScreeningEvent.create(
            run_id=run_id,
            hypothesis_id=hypothesis_id,
            gate="ink",
            outcome="admitted",
        )
    with pytest.raises(ValueError, match="outcome"):
        ScreeningEvent.create(
            run_id=run_id,
            hypothesis_id=hypothesis_id,
            gate="physical",
            outcome="accepted",
        )
    for gate in ("language", "human"):
        event = ScreeningEvent.create(
            run_id=run_id,
            hypothesis_id=hypothesis_id,
            gate=gate,
            outcome="excluded",
        )
        assert event.gate == gate
        assert "score" not in {field.name for field in dataclasses.fields(event)}


def test_a_second_append_of_the_same_id_is_refused() -> None:
    hypothesis = _hypothesis()
    before = hypothesis.content_bytes()
    event = ScreeningEvent.create(
        run_id=uuid.uuid4(),
        hypothesis_id=hypothesis.id,
        gate="physical",
        outcome="admitted",
    )
    log = ScreeningLog()
    log.append(event)
    with pytest.raises(ValueError, match="once"):
        log.append(event)
    assert log.rows == (event,)
    assert hypothesis.content_bytes() == before
    with pytest.raises(AttributeError):
        event.outcome = "excluded"  # type: ignore[misc]
