"""In-memory provenance envelopes, algorithm runs, and status events.

``ProvenanceEnvelope``, ``AlgorithmRun``, and ``StatusEvent`` follow
``docs/DATA_MODEL.md``. The envelope stores the full parameter blob and its
``sha256:`` digest. A completed run id is the UUIDv5 array in that
introduction. A cancelled or failed run inserts ``attempt_id`` after the
status word. Hypothesis content has no status column. Current status is the
latest ``StatusEvent`` for ``target_id``, under
``docs/adr/0006-append-only-hypotheses.md``.

These records are internal. They are not a stable public API, and they do
not write a project directory.
"""

from __future__ import annotations

import json
import math
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from prw.identity import (
    ABSENT,
    canonical_json,
    canonical_json_bytes,
    content_id,
    hash_value,
    require_hash,
)

RunStatus = Literal["completed", "cancelled", "failed"]
HypothesisStatus = Literal[
    "proposed",
    "rejected",
    "rejected-via-ValidationDecision",
    "contested",
    "invalidated",
]
Producer = Literal["human", "machine", "imported"]
ScoreChannel = Literal["physical", "htr", "language"]
ScoreHypothesisType = Literal["join", "assembly", "reading"]
_INITIAL_STATUSES = frozenset({"proposed", "rejected"})


def _require_utc(value: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError("A timestamp is UTC ISO-8601.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("A timestamp is UTC ISO-8601.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("A timestamp is UTC ISO-8601.")
    return value


def _require_source_hash(value: str) -> str:
    checked = require_hash(value)
    if checked == ABSENT:
        raise ValueError("A source hash is a sha256: digest.")
    return checked


def _require_parameter_blob(blob: str, parameter_hash: str) -> None:
    try:
        parsed = json.loads(blob)
    except json.JSONDecodeError as exc:
        raise ValueError("parameter_blob is canonical JSON.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("parameter_blob is a JSON object.")
    if canonical_json(parsed) != blob:
        raise ValueError("parameter_blob is canonical JSON.")
    if parameter_hash != hash_value(blob.encode("utf-8")):
        raise ValueError("parameter_hash does not match parameter_blob.")


def _require_text(value: str, label: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{label} is required.")
    return value


def _hypothesis_content(
    *,
    page_frame_id: uuid.UUID,
    join_ids: tuple[uuid.UUID, ...],
    placements: tuple[Placement, ...],
    unplaced_fragment_ids: tuple[uuid.UUID, ...],
    producer: Producer,
    scores: tuple[Score, ...],
    provenance_id: uuid.UUID | None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "page_frame_id": page_frame_id,
        "join_ids": join_ids,
        "placements": [
            {
                "fragment_id": item.fragment_id,
                "outline_revision_id": item.outline_revision_id,
                "transform_id": item.transform_id,
            }
            for item in placements
        ],
        "unplaced_fragment_ids": unplaced_fragment_ids,
        "producer": producer,
        "epistemic_class": "hypothesis",
        "scores": [
            {
                "value": item.value,
                "run_id": item.run_id,
                "channel": item.channel,
                "hypothesis_type": item.hypothesis_type,
            }
            for item in scores
        ],
    }
    if provenance_id is not None:
        fields["provenance_id"] = provenance_id
    return fields


def _uuid_tuple(values: Sequence[uuid.UUID], label: str) -> tuple[uuid.UUID, ...]:
    items: list[uuid.UUID] = []
    for value in values:
        if not isinstance(value, uuid.UUID):
            raise TypeError(f"{label} entries are UUIDs.")
        items.append(value)
    return tuple(items)


@dataclass(frozen=True, slots=True)
class ProvenanceEnvelope:
    """Full parameter record for one derived artifact.

    ``random_seed`` is a JSON integer when the algorithm used randomness and
    is omitted when the algorithm is deterministic. ``model_hash`` is always
    present: a ``sha256:`` digest, or ``absent`` when the run used no model.
    """

    source_hashes: tuple[str, ...]
    parameter_blob: str
    parameter_hash: str
    algorithm_name: str
    algorithm_version: str
    model_hash: str
    code_version: str
    decoder_name: str
    decoder_version: str
    random_seed: int | None
    id: uuid.UUID

    @classmethod
    def create(
        cls,
        *,
        source_hashes: Sequence[str],
        parameters: Mapping[str, Any],
        algorithm_name: str,
        algorithm_version: str,
        code_version: str,
        decoder_name: str,
        decoder_version: str,
        model_hash: str | None = None,
        random_seed: int | None = None,
    ) -> ProvenanceEnvelope:
        """Build an envelope whose id is the UUIDv5 of its canonical content."""
        if isinstance(random_seed, bool) or (
            random_seed is not None and not isinstance(random_seed, int)
        ):
            raise TypeError(
                "random_seed is a JSON integer when the algorithm used randomness."
            )
        blob_bytes = canonical_json_bytes(dict(parameters))
        stored_model = ABSENT if model_hash is None else require_hash(model_hash)
        hashes = tuple(_require_source_hash(item) for item in source_hashes)
        fields: dict[str, Any] = {
            "source_hashes": hashes,
            "parameter_blob": blob_bytes.decode("utf-8"),
            "parameter_hash": hash_value(blob_bytes),
            "algorithm_name": _require_text(algorithm_name, "algorithm_name"),
            "algorithm_version": _require_text(algorithm_version, "algorithm_version"),
            "model_hash": stored_model,
            "code_version": _require_text(code_version, "code_version"),
            "decoder_name": _require_text(decoder_name, "decoder_name"),
            "decoder_version": _require_text(decoder_version, "decoder_version"),
        }
        if random_seed is not None:
            fields["random_seed"] = random_seed
        return cls(
            source_hashes=fields["source_hashes"],
            parameter_blob=fields["parameter_blob"],
            parameter_hash=fields["parameter_hash"],
            algorithm_name=fields["algorithm_name"],
            algorithm_version=fields["algorithm_version"],
            model_hash=fields["model_hash"],
            code_version=fields["code_version"],
            decoder_name=fields["decoder_name"],
            decoder_version=fields["decoder_version"],
            random_seed=random_seed,
            id=content_id(fields),
        )

    def content_mapping(self) -> dict[str, Any]:
        """Stored fields except ``id``. ``random_seed`` is absent when omitted."""
        fields: dict[str, Any] = {
            "source_hashes": self.source_hashes,
            "parameter_blob": self.parameter_blob,
            "parameter_hash": self.parameter_hash,
            "algorithm_name": self.algorithm_name,
            "algorithm_version": self.algorithm_version,
            "model_hash": self.model_hash,
            "code_version": self.code_version,
            "decoder_name": self.decoder_name,
            "decoder_version": self.decoder_version,
        }
        if self.random_seed is not None:
            fields["random_seed"] = self.random_seed
        return fields

    def __post_init__(self) -> None:
        if self.id != content_id(self.content_mapping()):
            raise ValueError("ProvenanceEnvelope.id does not match its content.")
        require_hash(self.model_hash)
        _require_parameter_blob(self.parameter_blob, self.parameter_hash)


def run_id_inputs(
    envelope: ProvenanceEnvelope,
    status: RunStatus,
    attempt_id: uuid.UUID | None,
) -> list[Any]:
    """Return the data-model array for an ``AlgorithmRun`` id.

    Timestamps are not included. A completed run has no ``attempt_id``. A
    cancelled or failed run inserts ``attempt_id`` after the status word.
    Source hashes are sorted lexicographically. The last element is the seed
    or the token ``absent``.
    """
    seed: int | str = ABSENT if envelope.random_seed is None else envelope.random_seed
    tail: list[Any] = [
        envelope.algorithm_name,
        envelope.algorithm_version,
        envelope.code_version,
        envelope.parameter_hash,
        envelope.model_hash,
        *sorted(envelope.source_hashes),
        seed,
    ]
    if status == "completed":
        if attempt_id is not None:
            raise ValueError("A completed run has no attempt_id.")
        return [status, *tail]
    if status in {"cancelled", "failed"}:
        if attempt_id is None:
            raise ValueError("A cancelled or failed run includes attempt_id.")
        return [status, attempt_id, *tail]
    raise ValueError("Run status is completed, cancelled, or failed.")


@dataclass(frozen=True, slots=True)
class AlgorithmRun:
    """One execution grouping. Status is written once and is not rewritten."""

    provenance: ProvenanceEnvelope
    join_ids: tuple[uuid.UUID, ...]
    assembly_ids: tuple[uuid.UUID, ...]
    reading_ids: tuple[uuid.UUID, ...]
    line_ids: tuple[uuid.UUID, ...]
    line_order_ids: tuple[uuid.UUID, ...]
    status: RunStatus
    started_at: str
    attempt_id: uuid.UUID | None
    id: uuid.UUID

    @classmethod
    def create(
        cls,
        provenance: ProvenanceEnvelope,
        *,
        status: RunStatus,
        started_at: str,
        attempt_id: uuid.UUID | None = None,
        join_ids: Sequence[uuid.UUID] = (),
        assembly_ids: Sequence[uuid.UUID] = (),
        reading_ids: Sequence[uuid.UUID] = (),
        line_ids: Sequence[uuid.UUID] = (),
        line_order_ids: Sequence[uuid.UUID] = (),
    ) -> AlgorithmRun:
        """Build a run. A non-completed run receives a random ``attempt_id``."""
        _require_utc(started_at)
        if status == "completed":
            if attempt_id is not None:
                raise ValueError("A completed run has no attempt_id.")
        elif attempt_id is None:
            attempt_id = uuid.uuid4()
        elif not isinstance(attempt_id, uuid.UUID):
            raise TypeError("attempt_id is a UUID.")
        return cls(
            provenance=provenance,
            join_ids=_uuid_tuple(join_ids, "join_ids"),
            assembly_ids=_uuid_tuple(assembly_ids, "assembly_ids"),
            reading_ids=_uuid_tuple(reading_ids, "reading_ids"),
            line_ids=_uuid_tuple(line_ids, "line_ids"),
            line_order_ids=_uuid_tuple(line_order_ids, "line_order_ids"),
            status=status,
            started_at=started_at,
            attempt_id=attempt_id,
            id=content_id(run_id_inputs(provenance, status, attempt_id)),
        )

    @property
    def provenance_id(self) -> uuid.UUID:
        """Envelope id stored on the run."""
        return self.provenance.id

    def __post_init__(self) -> None:
        _require_utc(self.started_at)
        expected = content_id(
            run_id_inputs(self.provenance, self.status, self.attempt_id)
        )
        if self.id != expected:
            raise ValueError(
                "AlgorithmRun.id does not match its inputs. Status is not rewritten."
            )


@dataclass(frozen=True, slots=True)
class Placement:
    """One placed fragment. This ticket does not search placements."""

    fragment_id: uuid.UUID
    outline_revision_id: uuid.UUID
    transform_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class Score:
    """One channel value. Rank is derived later and is not stored here."""

    value: int | float
    run_id: uuid.UUID
    channel: ScoreChannel
    hypothesis_type: ScoreHypothesisType

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int | float):
            raise TypeError("A score value is a number.")
        if isinstance(self.value, float) and not math.isfinite(self.value):
            raise ValueError("A score value is a finite number.")
        if self.channel not in {"physical", "htr", "language"}:
            raise ValueError("A score channel is physical, htr, or language.")
        if self.hypothesis_type not in {"join", "assembly", "reading"}:
            raise ValueError("A score hypothesis type is join, assembly, or reading.")


@dataclass(frozen=True, slots=True)
class AssemblyContent:
    """Assembly-shaped hypothesis content. There is no status field.

    The epistemic class is ``hypothesis``. The id is a UUIDv5 over the run id
    and the hypothesis content when ``run_id`` is set, and over the row
    content otherwise. See ``AssemblyHypothesis`` in ``docs/DATA_MODEL.md``.
    """

    page_frame_id: uuid.UUID
    join_ids: tuple[uuid.UUID, ...]
    placements: tuple[Placement, ...]
    unplaced_fragment_ids: tuple[uuid.UUID, ...]
    producer: Producer
    scores: tuple[Score, ...]
    provenance_id: uuid.UUID | None
    run_id: uuid.UUID | None
    epistemic_class: Literal["hypothesis"]
    id: uuid.UUID

    @classmethod
    def create(
        cls,
        *,
        page_frame_id: uuid.UUID,
        producer: Producer,
        unplaced_fragment_ids: Sequence[uuid.UUID] = (),
        join_ids: Sequence[uuid.UUID] = (),
        placements: Sequence[Placement] = (),
        scores: Sequence[Score] = (),
        provenance_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
    ) -> AssemblyContent:
        """Build immutable assembly content and its content-derived id."""
        if producer not in {"human", "machine", "imported"}:
            raise ValueError("producer is human, machine, or imported.")
        content_placements = tuple(placements)
        for placement in content_placements:
            if not isinstance(placement, Placement):
                raise TypeError("placements entries are Placement records.")
        content_scores = tuple(scores)
        for score in content_scores:
            if not isinstance(score, Score):
                raise TypeError("scores entries are Score records.")
        stored_joins = _uuid_tuple(join_ids, "join_ids")
        stored_unplaced = _uuid_tuple(unplaced_fragment_ids, "unplaced_fragment_ids")
        content = _hypothesis_content(
            page_frame_id=page_frame_id,
            join_ids=stored_joins,
            placements=content_placements,
            unplaced_fragment_ids=stored_unplaced,
            producer=producer,
            scores=content_scores,
            provenance_id=provenance_id,
        )
        name: dict[str, Any] | list[Any] = (
            content if run_id is None else [run_id, content]
        )
        return cls(
            page_frame_id=page_frame_id,
            join_ids=stored_joins,
            placements=content_placements,
            unplaced_fragment_ids=stored_unplaced,
            producer=producer,
            scores=content_scores,
            provenance_id=provenance_id,
            run_id=run_id,
            epistemic_class="hypothesis",
            id=content_id(name),
        )

    def content_mapping(self) -> dict[str, Any]:
        """Hypothesis content. ``id`` and ``run_id`` are not in this object."""
        return _hypothesis_content(
            page_frame_id=self.page_frame_id,
            join_ids=self.join_ids,
            placements=self.placements,
            unplaced_fragment_ids=self.unplaced_fragment_ids,
            producer=self.producer,
            scores=self.scores,
            provenance_id=self.provenance_id,
        )

    def id_inputs(self) -> dict[str, Any] | list[Any]:
        """Name used for the content-derived id."""
        content = self.content_mapping()
        if self.run_id is None:
            return content
        return [self.run_id, content]

    def content_bytes(self) -> bytes:
        """Canonical bytes of the hypothesis content."""
        return canonical_json_bytes(self.content_mapping())

    def __post_init__(self) -> None:
        if self.epistemic_class != "hypothesis":
            raise ValueError("An assembly's epistemic class is hypothesis.")
        if self.id != content_id(self.id_inputs()):
            raise ValueError("AssemblyContent.id does not match its content.")


@dataclass(frozen=True, slots=True)
class StatusEvent:
    """One append-only status record. The id is a random UUID."""

    id: uuid.UUID
    target_id: uuid.UUID
    status: HypothesisStatus
    recorded_at: str
    actor: str

    def __post_init__(self) -> None:
        if self.status not in {
            "proposed",
            "rejected",
            "rejected-via-ValidationDecision",
            "contested",
            "invalidated",
        }:
            raise ValueError(
                "Status is proposed, rejected, rejected-via-ValidationDecision, "
                "contested, or invalidated."
            )
        _require_utc(self.recorded_at)
        _require_text(self.actor, "actor")
        if self.id.version != 4:
            raise ValueError("A status event id is a random UUID.")


class StatusStream:
    """Append-only ``StatusEvent`` log. Hypothesis rows are not updated."""

    def __init__(self) -> None:
        self._events: list[StatusEvent] = []

    @property
    def events(self) -> tuple[StatusEvent, ...]:
        return tuple(self._events)

    def current_status(self, target_id: uuid.UUID) -> HypothesisStatus | None:
        """Return the status on the latest event for ``target_id``."""
        found = [event.status for event in self._events if event.target_id == target_id]
        if not found:
            return None
        return found[-1]

    def append(
        self,
        *,
        target_id: uuid.UUID,
        status: HypothesisStatus,
        recorded_at: str,
        actor: str,
    ) -> StatusEvent:
        """Append an event.

        The first event for a target is ``proposed`` or ``rejected``.
        """
        if self.current_status(target_id) is None and status not in _INITIAL_STATUSES:
            raise ValueError(
                "The first status event is proposed, or rejected "
                "for a machine rejection."
            )
        event = StatusEvent(
            id=uuid.uuid4(),
            target_id=target_id,
            status=status,
            recorded_at=recorded_at,
            actor=actor,
        )
        self._events.append(event)
        return event


def insert_hypothesis(
    stream: StatusStream,
    hypothesis: AssemblyContent,
    *,
    recorded_at: str,
    actor: str,
    machine_rejection: bool = False,
) -> StatusEvent:
    """Insert a hypothesis and its first event in the same write.

    The event is ``proposed``, or ``rejected`` when this write is a machine
    rejection. The hypothesis object is not modified.
    """
    if stream.current_status(hypothesis.id) is not None:
        raise ValueError("A hypothesis is inserted once, with its first status event.")
    if machine_rejection and hypothesis.producer != "machine":
        raise ValueError("A machine rejection requires producer machine.")
    initial: HypothesisStatus = "rejected" if machine_rejection else "proposed"
    return stream.append(
        target_id=hypothesis.id,
        status=initial,
        recorded_at=recorded_at,
        actor=actor,
    )
