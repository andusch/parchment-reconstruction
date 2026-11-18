"""Score the ``language`` channel on hypotheses physical search admitted.

Stage 9 in ``docs/ALGORITHM.md``. The implemented algorithm is
``admitted_reading_language`` version ``1``. The parameter blob records
the score ``eligible_nfc_code_point_count``: the number of Unicode code
points in eligible grapheme texts. Texts stay the NFC strings the caller
supplied. This module does not rewrite them, strip accents, or map final
sigma. The count is an uncalibrated ranking feature. It is not a
probability and it is not a language model. No weights are read and no
network call is made. ``model_hash`` is ``absent``. ``random_seed`` is
omitted.

A hypothesis is scored only when a physical ``ScreeningEvent`` for that
id has outcome ``admitted`` and at least one grapheme on a reading that
is not tagged ``nomen-sacrum``, ``abbreviation``, or ``mixed-script`` has
text status ``human_read``, ``unclear``, or ``ocr_inferred``. The
language gate then writes ``admitted`` and one ``language`` score. Every
other offered hypothesis gets ``excluded`` and no score. Empty grapheme
text is eligible and contributes zero. No eligible grapheme means no
score. Supplied letters do not fill that gap and are not stored as
graphemes.

Supplied letters are added to an admitted score only when each block has
a non-empty label and a non-empty treatment. Both are copied into the
parameter blob. A missing label or treatment is refused and writes
nothing. This module does not train on that text.

The score cites the existing join or assembly id. The join row is not
rewritten, and this module does not construct a ``JoinHypothesis``. Rank
is inside one hypothesis type. A request that mixes joins and assemblies
in one order is refused.

These records are internal. They are not a stable public API, and they
do not write a project directory.
"""

from __future__ import annotations

import json
import unicodedata
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from prw.identity import ABSENT, canonical_json, require_hash
from prw.provenance import AlgorithmRun, ProvenanceEnvelope, Score
from prw.screening import ScreeningEvent, ScreeningLog

ALGORITHM_NAME = "admitted_reading_language"
ALGORITHM_VERSION = "1"
SCORE_NAME = "eligible_nfc_code_point_count"
SUPPLIED_RULE = "labeled_addition_on_admitted_eligible_graphemes"
_TEXT_STATUSES = ("human_read", "unclear", "ocr_inferred")
_EXCLUSION_TAGS = frozenset({"nomen-sacrum", "abbreviation", "mixed-script"})
_FORBIDDEN_LABELS = frozenset({*_TEXT_STATUSES, "missing", *_EXCLUSION_TAGS})
_FORBIDDEN_PATH_PARTS = frozenset({"data", "scans", "real_data"})
_REQUEST_KEYS = frozenset({"source_hashes", "physical_events", "hypotheses"})
_EVENT_KEYS = frozenset({"run_id", "hypothesis_id", "outcome"})
_HYPOTHESIS_KEYS = frozenset(
    {"hypothesis_id", "hypothesis_type", "readings", "supplied"}
)
_READING_KEYS = frozenset({"script", "language", "graphemes"})
_GRAPHEME_KEYS = frozenset({"text", "text_status"})
_SUPPLIED_KEYS = frozenset({"text", "label", "treatment"})
type TextStatus = Literal["human_read", "unclear", "ocr_inferred"]
type HypothesisType = Literal["join", "assembly"]
type PhysicalOutcome = Literal["admitted", "excluded"]


def _require_tag(value: object, label: str) -> str:
    if not isinstance(value, str) or value == "" or value != value.strip():
        raise ValueError(f"{label} is a non-empty tag.")
    return value


def _require_nfc(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} is a string stored in Unicode NFC.")
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError(f"{label} is stored in Unicode NFC.")
    return value


def _text_status(value: object) -> TextStatus:
    if value == "human_read" or value == "unclear" or value == "ocr_inferred":
        return value
    raise ValueError("A grapheme text status is human_read, unclear, or ocr_inferred.")


def _hypothesis_type(value: object) -> HypothesisType:
    if value == "join" or value == "assembly":
        return value
    raise ValueError("Language scores a join or an assembly.")


def _physical_outcome(value: object) -> PhysicalOutcome:
    if value == "admitted" or value == "excluded":
        return value
    raise ValueError("A physical outcome is admitted or excluded.")


def _uuid(value: object, label: str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{label} is a UUID.")
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ValueError(f"{label} is a UUID.") from exc


def _source_hashes(values: Sequence[object]) -> tuple[str, ...]:
    if isinstance(values, str | bytes):
        raise ValueError("source_hashes is a sequence of sha256: digests.")
    if len(values) < 1:
        raise ValueError("A language score cites at least one source hash.")
    stored: list[str] = []
    for item in values:
        if not isinstance(item, str):
            raise ValueError("A source hash is a sha256: digest.")
        checked = require_hash(item)
        if checked == ABSENT:
            raise ValueError("A source hash is a sha256: digest.")
        stored.append(checked)
    unique = tuple(sorted(set(stored)))
    if len(unique) != len(stored):
        raise ValueError("A source hash is listed once.")
    return unique


def _exclusion(script: str, language: str) -> str | None:
    found: list[str] = []
    if script in _EXCLUSION_TAGS:
        found.append(script)
    if language in _EXCLUSION_TAGS and language not in found:
        found.append(language)
    if len(found) > 1:
        raise ValueError("A reading has one exclusion tag.")
    if not found:
        return None
    return found[0]


def _supplied_label(value: object) -> str:
    label = _require_tag(value, "A supplied-text label")
    if label in _FORBIDDEN_LABELS:
        raise ValueError(
            "A supplied-text label is an explicit restoration label, "
            "not a grapheme text status."
        )
    return label


def _mapping_keys(
    value: object,
    *,
    required: frozenset[str],
    optional: frozenset[str],
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} is a JSON object.")
    extra = set(value) - required - optional
    missing = required - set(value)
    if missing:
        name = sorted(missing)[0]
        raise ValueError(f"{label} is missing {name}.")
    if extra:
        name = sorted(extra)[0]
        raise ValueError(f"{label} has an unknown field {name}.")
    return value


def _object_list(value: object, label: str) -> list[object]:
    if isinstance(value, str | bytes) or not isinstance(value, Sequence):
        raise ValueError(f"{label} is a list.")
    return list(value)


@dataclass(frozen=True, slots=True)
class LanguageGrapheme:
    """One offered grapheme. The text is stored and is not rewritten."""

    text: str
    text_status: TextStatus

    def __post_init__(self) -> None:
        _require_nfc(self.text, "Grapheme text")
        _text_status(self.text_status)


@dataclass(frozen=True, slots=True)
class LanguageReading:
    """Readings that sit on one join or assembly.

    ``script`` and ``language`` are the operator's tags. A tag of
    ``nomen-sacrum``, ``abbreviation``, or ``mixed-script`` leaves the
    reading unscored. Two different exclusion tags on one reading are
    refused. Abbreviations are not expanded.
    """

    script: str
    language: str
    graphemes: tuple[LanguageGrapheme, ...]

    def __post_init__(self) -> None:
        _exclusion(
            _require_tag(self.script, "script"),
            _require_tag(self.language, "language"),
        )
        if isinstance(self.graphemes, str | bytes):
            raise TypeError("graphemes is a sequence of graphemes.")
        for item in self.graphemes:
            if not isinstance(item, LanguageGrapheme):
                raise TypeError("graphemes entries are LanguageGrapheme records.")


@dataclass(frozen=True, slots=True)
class SuppliedLetters:
    """Restoration letters. They are not a grapheme and not a text status."""

    text: str
    label: str
    treatment: str

    def __post_init__(self) -> None:
        text = _require_nfc(self.text, "Supplied letters")
        if text == "":
            raise ValueError("Supplied letters are a non-empty NFC string.")
        _supplied_label(self.label)
        _require_tag(self.treatment, "A supplied-text treatment")


@dataclass(frozen=True, slots=True)
class PhysicalAdmission:
    """One physical-gate outcome the language stage consults.

    The language stage does not create this event. It reads the outcome
    the physical search already recorded.
    """

    run_id: uuid.UUID
    hypothesis_id: uuid.UUID
    outcome: PhysicalOutcome

    def __post_init__(self) -> None:
        _uuid(self.run_id, "run_id")
        _uuid(self.hypothesis_id, "hypothesis_id")
        _physical_outcome(self.outcome)


@dataclass(frozen=True, slots=True)
class LanguageHypothesis:
    """One join or assembly, the readings that sit on it, and any supply."""

    hypothesis_id: uuid.UUID
    hypothesis_type: HypothesisType
    readings: tuple[LanguageReading, ...]
    supplied: tuple[SuppliedLetters, ...] = ()

    def __post_init__(self) -> None:
        _uuid(self.hypothesis_id, "hypothesis_id")
        _hypothesis_type(self.hypothesis_type)
        if isinstance(self.readings, str | bytes):
            raise TypeError("readings is a sequence of readings.")
        for reading in self.readings:
            if not isinstance(reading, LanguageReading):
                raise TypeError("readings entries are LanguageReading records.")
        if isinstance(self.supplied, str | bytes):
            raise TypeError("supplied is a sequence of supplied-letter blocks.")
        for block in self.supplied:
            if not isinstance(block, SuppliedLetters):
                raise TypeError("supplied entries are SuppliedLetters records.")


@dataclass(frozen=True, slots=True)
class LanguageRequest:
    """The inputs of one language-scoring run. Timestamps are not included."""

    source_hashes: tuple[str, ...]
    physical_events: tuple[PhysicalAdmission, ...]
    hypotheses: tuple[LanguageHypothesis, ...]

    def __post_init__(self) -> None:
        if self.source_hashes != _source_hashes(self.source_hashes):
            raise ValueError("Source hashes are sorted, unique sha256: digests.")
        if isinstance(self.physical_events, str | bytes):
            raise TypeError("physical_events is a sequence of physical admissions.")
        if isinstance(self.hypotheses, str | bytes):
            raise TypeError("hypotheses is a sequence of language hypotheses.")
        seen_events: set[tuple[uuid.UUID, uuid.UUID, str]] = set()
        outcomes: dict[uuid.UUID, str] = {}
        for event in self.physical_events:
            if not isinstance(event, PhysicalAdmission):
                raise TypeError(
                    "physical_events entries are PhysicalAdmission records."
                )
            identity = (event.run_id, event.hypothesis_id, event.outcome)
            if identity in seen_events:
                raise ValueError("A physical admission is listed once.")
            seen_events.add(identity)
            previous = outcomes.get(event.hypothesis_id)
            if previous is not None and previous != event.outcome:
                raise ValueError("A hypothesis has one physical outcome.")
            outcomes[event.hypothesis_id] = event.outcome
        seen_ids: set[uuid.UUID] = set()
        for item in self.hypotheses:
            if not isinstance(item, LanguageHypothesis):
                raise TypeError("hypotheses entries are LanguageHypothesis records.")
            if item.hypothesis_id in seen_ids:
                raise ValueError("A hypothesis is offered once.")
            seen_ids.add(item.hypothesis_id)


@dataclass(frozen=True, slots=True)
class LanguageAnnotation:
    """A ``language`` score citing a hypothesis the physical gate admitted."""

    hypothesis_id: uuid.UUID
    hypothesis_type: HypothesisType
    score: Score

    def __post_init__(self) -> None:
        _uuid(self.hypothesis_id, "hypothesis_id")
        _hypothesis_type(self.hypothesis_type)
        if not isinstance(self.score, Score):
            raise TypeError("A language annotation cites a Score.")
        if self.score.channel != "language":
            raise ValueError("The language channel is language.")
        if self.score.hypothesis_type != self.hypothesis_type:
            raise ValueError("The score hypothesis type matches the annotation.")
        if isinstance(self.score.value, bool) or not isinstance(self.score.value, int):
            raise TypeError("A language score is a code-point count.")
        if self.score.value < 0:
            raise ValueError("A language score is a code-point count.")


def language_order(
    annotations: Sequence[LanguageAnnotation],
) -> tuple[LanguageAnnotation, ...]:
    """Rank one hypothesis type by the language channel.

    A higher score comes first. Equal scores are ordered by the hypothesis
    id, ascending bytewise. Joins and assemblies are not placed in one
    order. Rank is not stored on the annotation.
    """
    if isinstance(annotations, str | bytes):
        raise TypeError("Language rank orders annotations.")
    stored = tuple(annotations)
    for item in stored:
        if not isinstance(item, LanguageAnnotation):
            raise TypeError("Language rank orders annotations.")
    kinds = {item.hypothesis_type for item in stored}
    if len(kinds) > 1:
        raise ValueError("A language run does not rank mixed hypothesis types.")
    return tuple(
        sorted(stored, key=lambda item: (-item.score.value, item.hypothesis_id.bytes))
    )


@dataclass(frozen=True, slots=True)
class LanguageScoreRun:
    """One completed language-scoring run.

    ``joins`` and ``assemblies`` are separate rank lists. A hypothesis
    that was excluded is absent from both and present in ``screening``.
    ``run`` lists no join, assembly, or reading id: this stage does not
    create those rows.
    """

    run: AlgorithmRun
    joins: tuple[LanguageAnnotation, ...]
    assemblies: tuple[LanguageAnnotation, ...]
    screening: tuple[ScreeningEvent, ...]

    def __post_init__(self) -> None:
        if self.run.status != "completed" or self.run.attempt_id is not None:
            raise ValueError("A completed language run has no attempt_id.")
        provenance = self.run.provenance
        if provenance.algorithm_name != ALGORITHM_NAME:
            raise ValueError("The language algorithm is admitted_reading_language.")
        if provenance.algorithm_version != ALGORITHM_VERSION:
            raise ValueError("The language algorithm version is 1.")
        if provenance.model_hash != ABSENT or provenance.random_seed is not None:
            raise ValueError("Language scoring omits a model and a random seed.")
        if "random_seed" in provenance.content_mapping():
            raise ValueError("Language scoring omits random_seed.")
        parameters = json.loads(provenance.parameter_blob)
        if not isinstance(parameters, dict):
            raise ValueError("The language parameter blob is a JSON object.")
        if parameters.get("score") != SCORE_NAME:
            raise ValueError("The parameter blob names eligible_nfc_code_point_count.")
        if parameters.get("training") != "none":
            raise ValueError("Language scoring does not train.")
        if parameters.get("generates_graphemes") is not False:
            raise ValueError("Language scoring does not generate graphemes.")
        if parameters.get("creates_joins") is not False:
            raise ValueError("Language scoring does not create a join.")
        for banned in ("weights", "weighted_sum", "fusion", "probability"):
            if banned in parameters:
                raise ValueError("Language scoring does not store a fused key.")
        if (
            self.run.join_ids
            or self.run.assembly_ids
            or self.run.reading_ids
            or self.run.line_ids
            or self.run.line_order_ids
        ):
            raise ValueError(
                "Language scoring does not create a join, assembly, or reading."
            )
        if self.joins != language_order(self.joins):
            raise ValueError("Joins are ranked inside the language channel.")
        if self.assemblies != language_order(self.assemblies):
            raise ValueError("Assemblies are ranked inside the language channel.")
        if any(item.hypothesis_type != "join" for item in self.joins):
            raise ValueError("The join list scores joins.")
        if any(item.hypothesis_type != "assembly" for item in self.assemblies):
            raise ValueError("The assembly list scores assemblies.")
        annotations = (*self.joins, *self.assemblies)
        scored = {item.hypothesis_id for item in annotations}
        if len(scored) != len(annotations):
            raise ValueError("A hypothesis receives one language score.")
        admitted: set[uuid.UUID] = set()
        excluded: set[uuid.UUID] = set()
        for event in self.screening:
            if event.gate != "language" or event.run_id != self.run.id:
                raise ValueError("Screening events are the language gate of this run.")
            if event.outcome == "admitted":
                admitted.add(event.hypothesis_id)
            else:
                excluded.add(event.hypothesis_id)
        if admitted != scored:
            raise ValueError(
                "A language score is written only for an admitted hypothesis."
            )
        if excluded & scored:
            raise ValueError("An excluded hypothesis has no language score.")
        if len(self.screening) != len(
            {event.hypothesis_id for event in self.screening}
        ):
            raise ValueError("The language gate records one outcome per hypothesis.")
        ordered = tuple(
            sorted(self.screening, key=lambda event: event.hypothesis_id.bytes)
        )
        if self.screening != ordered:
            raise ValueError("Screening events are stored in hypothesis-id order.")


def _parameters(request: LanguageRequest) -> dict[str, Any]:
    events = sorted(
        request.physical_events,
        key=lambda event: (str(event.hypothesis_id), str(event.run_id), event.outcome),
    )
    hypotheses = sorted(request.hypotheses, key=lambda item: str(item.hypothesis_id))
    return {
        "abbreviations_expanded": False,
        "calibration": "uncalibrated",
        "creates_joins": False,
        "eligible_text_status": list(_TEXT_STATUSES),
        "exclusion_tags": sorted(_EXCLUSION_TAGS),
        "generates_graphemes": False,
        "hypotheses": [_hypothesis_parameter(item) for item in hypotheses],
        "physical_events": [
            {
                "hypothesis_id": str(event.hypothesis_id),
                "outcome": event.outcome,
                "run_id": str(event.run_id),
            }
            for event in events
        ],
        "score": SCORE_NAME,
        "supplied_text": SUPPLIED_RULE,
        "training": "none",
        "unit": "nfc_code_point",
    }


def _hypothesis_parameter(item: LanguageHypothesis) -> dict[str, Any]:
    stored: dict[str, Any] = {
        "hypothesis_id": str(item.hypothesis_id),
        "hypothesis_type": item.hypothesis_type,
        "readings": [
            {
                "graphemes": [
                    {"text": grapheme.text, "text_status": grapheme.text_status}
                    for grapheme in reading.graphemes
                ],
                "language": reading.language,
                "script": reading.script,
            }
            for reading in item.readings
        ],
    }
    if item.supplied:
        stored["supplied"] = [
            {"label": block.label, "text": block.text, "treatment": block.treatment}
            for block in item.supplied
        ]
    return stored


def _eligible_count(item: LanguageHypothesis) -> int | None:
    """Return the code-point count, or None when no grapheme is eligible."""
    found = False
    count = 0
    for reading in item.readings:
        if _exclusion(reading.script, reading.language) is not None:
            continue
        for grapheme in reading.graphemes:
            found = True
            count += len(grapheme.text)
    if not found:
        return None
    return count


def _admission(item: LanguageHypothesis, events: Sequence[PhysicalAdmission]) -> str:
    outcomes = {
        event.outcome for event in events if event.hypothesis_id == item.hypothesis_id
    }
    if not outcomes:
        return "unseen"
    if len(outcomes) != 1:
        raise ValueError("A hypothesis has one physical outcome.")
    return next(iter(outcomes))


def _envelope(request: LanguageRequest, *, code_version: str) -> ProvenanceEnvelope:
    if not isinstance(code_version, str) or code_version == "":
        raise ValueError("code_version is required.")
    return ProvenanceEnvelope.create(
        source_hashes=request.source_hashes,
        parameters=_parameters(request),
        algorithm_name=ALGORITHM_NAME,
        algorithm_version=ALGORITHM_VERSION,
        code_version=code_version,
        decoder_name=ABSENT,
        decoder_version=ABSENT,
    )


class LanguageScoreLog:
    """In-memory language scores and the screening events of those runs.

    A repeated completed run returns the stored scores. The log does not
    rewrite a join and does not read a benchmark label.
    """

    def __init__(self) -> None:
        self._runs: list[AlgorithmRun] = []
        self._completed: dict[uuid.UUID, LanguageScoreRun] = {}
        self._screening = ScreeningLog()

    @property
    def runs(self) -> tuple[AlgorithmRun, ...]:
        return tuple(self._runs)

    @property
    def screening(self) -> tuple[ScreeningEvent, ...]:
        return self._screening.rows

    def score(
        self,
        request: LanguageRequest,
        *,
        code_version: str,
        recorded_at: str,
    ) -> LanguageScoreRun:
        """Score ``request`` and record one language-gate event per hypothesis.

        Malformed requests are refused by ``LanguageRequest`` before this
        method stores a run. A hypothesis the physical gate did not admit,
        and a hypothesis with no eligible grapheme, are excluded. Neither
        case writes a language score or a grapheme.
        """
        if not isinstance(request, LanguageRequest):
            raise TypeError("score reads a LanguageRequest.")
        envelope = _envelope(request, code_version=code_version)
        completed = AlgorithmRun.create(
            envelope,
            status="completed",
            started_at=recorded_at,
        )
        stored = self._completed.get(completed.id)
        if stored is not None:
            return stored
        joins: list[LanguageAnnotation] = []
        assemblies: list[LanguageAnnotation] = []
        events: list[ScreeningEvent] = []
        for item in request.hypotheses:
            outcome, annotation = _gate_one(item, request.physical_events, completed)
            events.append(
                ScreeningEvent.create(
                    run_id=completed.id,
                    hypothesis_id=item.hypothesis_id,
                    gate="language",
                    outcome=outcome,
                )
            )
            if annotation is None:
                continue
            if annotation.hypothesis_type == "join":
                joins.append(annotation)
            else:
                assemblies.append(annotation)
        result = LanguageScoreRun(
            run=completed,
            joins=language_order(joins),
            assemblies=language_order(assemblies),
            screening=tuple(
                sorted(events, key=lambda event: event.hypothesis_id.bytes)
            ),
        )
        for event in result.screening:
            self._screening.append(event)
        self._runs.append(result.run)
        self._completed[result.run.id] = result
        return result


def _gate_one(
    item: LanguageHypothesis,
    events: Sequence[PhysicalAdmission],
    run: AlgorithmRun,
) -> tuple[PhysicalOutcome, LanguageAnnotation | None]:
    if _admission(item, events) != "admitted":
        return "excluded", None
    count = _eligible_count(item)
    if count is None:
        return "excluded", None
    for block in item.supplied:
        count += len(block.text)
    annotation = LanguageAnnotation(
        hypothesis_id=item.hypothesis_id,
        hypothesis_type=item.hypothesis_type,
        score=Score(
            value=count,
            run_id=run.id,
            channel="language",
            hypothesis_type=item.hypothesis_type,
        ),
    )
    return "admitted", annotation


def language_request_from_mapping(payload: object) -> LanguageRequest:
    """Build a request from the unfrozen JSON object. Unknown fields are refused."""
    mapping = _mapping_keys(
        payload,
        required=_REQUEST_KEYS,
        optional=frozenset(),
        label="The language input",
    )
    hashes = _object_list(mapping["source_hashes"], "source_hashes")
    event_rows = _object_list(mapping["physical_events"], "physical_events")
    hypothesis_rows = _object_list(mapping["hypotheses"], "hypotheses")
    return LanguageRequest(
        source_hashes=_source_hashes(hashes),
        physical_events=tuple(_event_from_mapping(row) for row in event_rows),
        hypotheses=tuple(_hypothesis_from_mapping(row) for row in hypothesis_rows),
    )


def _event_from_mapping(value: object) -> PhysicalAdmission:
    mapping = _mapping_keys(
        value,
        required=_EVENT_KEYS,
        optional=frozenset(),
        label="A physical event",
    )
    return PhysicalAdmission(
        run_id=_uuid(mapping["run_id"], "run_id"),
        hypothesis_id=_uuid(mapping["hypothesis_id"], "hypothesis_id"),
        outcome=_physical_outcome(mapping["outcome"]),
    )


def _hypothesis_from_mapping(value: object) -> LanguageHypothesis:
    mapping = _mapping_keys(
        value,
        required=_HYPOTHESIS_KEYS - {"supplied"},
        optional=frozenset({"supplied"}),
        label="A hypothesis",
    )
    readings = _object_list(mapping["readings"], "readings")
    supplied_rows = mapping.get("supplied", ())
    supplied = _object_list(supplied_rows, "supplied")
    return LanguageHypothesis(
        hypothesis_id=_uuid(mapping["hypothesis_id"], "hypothesis_id"),
        hypothesis_type=_hypothesis_type(mapping["hypothesis_type"]),
        readings=tuple(_reading_from_mapping(row) for row in readings),
        supplied=tuple(_supplied_from_mapping(row) for row in supplied),
    )


def _reading_from_mapping(value: object) -> LanguageReading:
    mapping = _mapping_keys(
        value,
        required=_READING_KEYS,
        optional=frozenset(),
        label="A reading",
    )
    graphemes = _object_list(mapping["graphemes"], "graphemes")
    return LanguageReading(
        script=_require_tag(mapping["script"], "script"),
        language=_require_tag(mapping["language"], "language"),
        graphemes=tuple(_grapheme_from_mapping(row) for row in graphemes),
    )


def _grapheme_from_mapping(value: object) -> LanguageGrapheme:
    mapping = _mapping_keys(
        value,
        required=_GRAPHEME_KEYS,
        optional=frozenset(),
        label="A grapheme",
    )
    return LanguageGrapheme(
        text=_require_nfc(mapping["text"], "Grapheme text"),
        text_status=_text_status(mapping["text_status"]),
    )


def _supplied_from_mapping(value: object) -> SuppliedLetters:
    mapping = _mapping_keys(
        value,
        required=_SUPPLIED_KEYS,
        optional=frozenset(),
        label="Supplied letters",
    )
    return SuppliedLetters(
        text=_require_nfc(mapping["text"], "Supplied letters"),
        label=_supplied_label(mapping["label"]),
        treatment=_require_tag(mapping["treatment"], "A supplied-text treatment"),
    )


def load_language_input(path: Path) -> LanguageRequest:
    """Read one JSON request. A corpus path or a TIFF is refused."""
    if not isinstance(path, Path):
        raise TypeError("The language input is a path.")
    if any(part in _FORBIDDEN_PATH_PARTS for part in path.parts):
        raise ValueError("Language scoring does not read a real-corpus path.")
    if path.suffix.lower() in {".tif", ".tiff"}:
        raise ValueError("Language scoring does not read a TIFF.")
    if not path.is_file():
        raise ValueError("The language input is a JSON file.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("The language input is a JSON object.") from exc
    return language_request_from_mapping(payload)


def one_hypothesis_request(
    *,
    source_hashes: Sequence[str],
    hypothesis_id: uuid.UUID,
    hypothesis_type: str,
    script: str,
    language: str,
    graphemes: Sequence[tuple[str, str]],
    physical_run_id: uuid.UUID | None,
    physical_outcome: str | None,
    supplied_text: str | None,
    supplied_label: str | None,
    supplied_treatment: str | None,
) -> LanguageRequest:
    """Build a one-hypothesis request from unfrozen CLI flags."""
    if (physical_run_id is None) != (physical_outcome is None):
        raise ValueError("A physical outcome and its run id are supplied together.")
    supplied_fields = (supplied_text, supplied_label, supplied_treatment)
    if any(item is not None for item in supplied_fields) and any(
        item is None for item in supplied_fields
    ):
        raise ValueError(
            "Supplied letters require text, an explicit label, and a treatment."
        )
    events: tuple[PhysicalAdmission, ...] = ()
    if physical_run_id is not None and physical_outcome is not None:
        events = (
            PhysicalAdmission(
                run_id=physical_run_id,
                hypothesis_id=hypothesis_id,
                outcome=_physical_outcome(physical_outcome),
            ),
        )
    supplied: tuple[SuppliedLetters, ...] = ()
    if (
        supplied_text is not None
        and supplied_label is not None
        and supplied_treatment is not None
    ):
        supplied = (
            SuppliedLetters(
                text=supplied_text,
                label=supplied_label,
                treatment=supplied_treatment,
            ),
        )
    reading_graphemes = tuple(
        LanguageGrapheme(text=text, text_status=_text_status(status))
        for text, status in graphemes
    )
    return LanguageRequest(
        source_hashes=_source_hashes(list(source_hashes)),
        physical_events=events,
        hypotheses=(
            LanguageHypothesis(
                hypothesis_id=hypothesis_id,
                hypothesis_type=_hypothesis_type(hypothesis_type),
                readings=(
                    LanguageReading(
                        script=script,
                        language=language,
                        graphemes=reading_graphemes,
                    ),
                ),
                supplied=supplied,
            ),
        ),
    )


def parameter_blob(run: LanguageScoreRun) -> dict[str, Any]:
    """Return the parsed parameter blob. The hash covers this object."""
    parsed = json.loads(run.run.provenance.parameter_blob)
    if not isinstance(parsed, dict):
        raise ValueError("The language parameter blob is a JSON object.")
    if canonical_json(parsed) != run.run.provenance.parameter_blob:
        raise ValueError("parameter_blob is canonical JSON.")
    return parsed
