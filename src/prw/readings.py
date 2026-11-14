"""In-memory reading and grapheme records for machine HTR.

``ReadingHypothesis`` and ``GraphemeHypothesis`` follow
``docs/DATA_MODEL.md``. A machine reading is epistemic class
``interpretation`` with producer ``machine``. Grapheme text status is
``ocr_inferred``. Stored text is Unicode NFC. This module does not strip
accents and does not map final sigma to sigma.

The documented reading id includes grapheme ids, and the documented
grapheme id includes the reading id. Those two sentences cite each other.
The in-memory ids below are computable: the reading id is a UUIDv5 over
the run id and the reading fields other than ``grapheme_ids``, plus the
ordered NFC texts. Each grapheme id is a UUIDv5 over the run id, that
reading id, the zero-based position, and the grapheme content. The
position keeps a repeated letter a distinct row. It is not a line-order
index. No project directory is written.

Inserting a reading or a grapheme appends one ``StatusEvent`` of
``proposed`` in the same write. The row has no status column.
"""

from __future__ import annotations

import unicodedata
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from prw.identity import content_id
from prw.provenance import StatusEvent, StatusStream

type Point = tuple[float, float]


def _require_uuid(value: object, label: str) -> uuid.UUID:
    if not isinstance(value, uuid.UUID):
        raise TypeError(f"{label} is a UUID.")
    return value


def _require_tag(value: object, label: str) -> str:
    if not isinstance(value, str) or value == "" or value != value.strip():
        raise ValueError(f"{label} is a non-empty tag.")
    return value


def _require_nfc(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("Grapheme text is a string stored in Unicode NFC.")
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError("Grapheme text is stored in Unicode NFC.")
    return value


def _polygon(vertices: Sequence[object]) -> tuple[Point, ...]:
    if isinstance(vertices, str | bytes):
        raise TypeError("An ink region is a polygon.")
    points: list[Point] = []
    for vertex in vertices:
        if isinstance(vertex, str | bytes) or not isinstance(vertex, Sequence):
            raise TypeError("An ink-region vertex is an x and a y.")
        if len(vertex) != 2:
            raise ValueError("An ink-region vertex is an x and a y.")
        x_coord, y_coord = vertex
        if isinstance(x_coord, bool) or not isinstance(x_coord, int | float):
            raise TypeError("An ink-region coordinate is a finite number.")
        if isinstance(y_coord, bool) or not isinstance(y_coord, int | float):
            raise TypeError("An ink-region coordinate is a finite number.")
        points.append((float(x_coord), float(y_coord)))
    if len(points) < 3:
        raise ValueError("An ink region has at least three vertices.")
    return tuple(points)


def _reading_identity(
    *,
    anchor_id: uuid.UUID,
    provenance_id: uuid.UUID,
    script: str,
    language: str,
    texts: Sequence[str],
) -> dict[str, Any]:
    return {
        "anchor_id": anchor_id,
        "epistemic_class": "interpretation",
        "language": language,
        "producer": "machine",
        "provenance_id": provenance_id,
        "script": script,
        "texts": list(texts),
    }


def _grapheme_content(
    *,
    text: str,
    frame_id: uuid.UUID,
    ink_region: tuple[Point, ...],
) -> dict[str, Any]:
    return {
        "epistemic_class": "interpretation",
        "ink_region": ink_region,
        "ink_region_frame_id": frame_id,
        "producer": "machine",
        "text": text,
        "text_status": "ocr_inferred",
    }


@dataclass(frozen=True, slots=True)
class GraphemeHypothesis:
    """One machine grapheme. The row has no status column.

    ``text_status`` is ``ocr_inferred``. The epistemic class is
    ``interpretation``. Producer is ``machine``. ``text`` is Unicode NFC.
    ``position`` is the index in the parent reading.
    """

    reading_id: uuid.UUID
    text: str
    text_status: Literal["ocr_inferred"]
    epistemic_class: Literal["interpretation"]
    ink_region_frame_id: uuid.UUID
    ink_region: tuple[Point, ...]
    producer: Literal["machine"]
    run_id: uuid.UUID
    position: int
    id: uuid.UUID

    @classmethod
    def create(
        cls,
        *,
        reading_id: uuid.UUID,
        text: str,
        frame_id: uuid.UUID,
        ink_region: Sequence[object],
        run_id: uuid.UUID,
        position: int,
    ) -> GraphemeHypothesis:
        """Build one ``ocr_inferred`` grapheme. A different status is rejected."""
        stored_reading = _require_uuid(reading_id, "reading_id")
        stored_run = _require_uuid(run_id, "run_id")
        stored_frame = _require_uuid(frame_id, "ink_region_frame_id")
        stored_text = _require_nfc(text)
        stored_region = _polygon(ink_region)
        if isinstance(position, bool) or not isinstance(position, int) or position < 0:
            raise ValueError("A grapheme position is a zero-based index.")
        grapheme_id = content_id(
            [
                stored_run,
                stored_reading,
                position,
                _grapheme_content(
                    text=stored_text,
                    frame_id=stored_frame,
                    ink_region=stored_region,
                ),
            ]
        )
        return cls(
            reading_id=stored_reading,
            text=stored_text,
            text_status="ocr_inferred",
            epistemic_class="interpretation",
            ink_region_frame_id=stored_frame,
            ink_region=stored_region,
            producer="machine",
            run_id=stored_run,
            position=position,
            id=grapheme_id,
        )

    def content_mapping(self) -> dict[str, Any]:
        """Grapheme content. The id inputs are separate from this mapping."""
        return _grapheme_content(
            text=self.text,
            frame_id=self.ink_region_frame_id,
            ink_region=self.ink_region,
        )

    def __post_init__(self) -> None:
        if self.text_status != "ocr_inferred":
            raise ValueError("An HTR grapheme's text status is ocr_inferred.")
        if self.epistemic_class != "interpretation":
            raise ValueError("A grapheme's epistemic class is interpretation.")
        if self.producer != "machine":
            raise ValueError("An HTR grapheme has producer machine.")
        expected = content_id(
            [self.run_id, self.reading_id, self.position, self.content_mapping()]
        )
        if self.id != expected:
            raise ValueError("GraphemeHypothesis.id does not match its content.")


@dataclass(frozen=True, slots=True)
class ReadingHypothesis:
    """One machine reading. The row has no status column.

    The epistemic class is ``interpretation``. Producer is ``machine``.
    ``script`` and ``language`` are the operator's tags. Scores are absent:
    this record does not store an ``htr`` or ``language`` channel.
    """

    run_id: uuid.UUID
    anchor_id: uuid.UUID
    grapheme_ids: tuple[uuid.UUID, ...]
    texts: tuple[str, ...]
    script: str
    language: str
    producer: Literal["machine"]
    epistemic_class: Literal["interpretation"]
    provenance_id: uuid.UUID
    id: uuid.UUID

    @classmethod
    def create(
        cls,
        *,
        run_id: uuid.UUID,
        anchor_id: uuid.UUID,
        texts: Sequence[str],
        grapheme_ids: Sequence[uuid.UUID],
        script: str,
        language: str,
        provenance_id: uuid.UUID,
    ) -> ReadingHypothesis:
        """Build one machine reading. Scores are not stored."""
        stored_run = _require_uuid(run_id, "run_id")
        stored_anchor = _require_uuid(anchor_id, "anchor_id")
        stored_provenance = _require_uuid(provenance_id, "provenance_id")
        stored_script = _require_tag(script, "script")
        stored_language = _require_tag(language, "language")
        stored_texts = tuple(_require_nfc(item) for item in texts)
        stored_ids = tuple(_require_uuid(item, "grapheme_ids") for item in grapheme_ids)
        if len(stored_texts) != len(stored_ids):
            raise ValueError("A reading cites one grapheme id per text.")
        if not stored_texts:
            raise ValueError("A reading cites its graphemes.")
        reading_id = content_id(
            [
                stored_run,
                _reading_identity(
                    anchor_id=stored_anchor,
                    provenance_id=stored_provenance,
                    script=stored_script,
                    language=stored_language,
                    texts=stored_texts,
                ),
            ]
        )
        return cls(
            run_id=stored_run,
            anchor_id=stored_anchor,
            grapheme_ids=stored_ids,
            texts=stored_texts,
            script=stored_script,
            language=stored_language,
            producer="machine",
            epistemic_class="interpretation",
            provenance_id=stored_provenance,
            id=reading_id,
        )

    @property
    def text(self) -> str:
        """Ordered grapheme texts, already stored in Unicode NFC."""
        return "".join(self.texts)

    def content_mapping(self) -> dict[str, Any]:
        """Reading identity. Grapheme ids are stored and are not an id input."""
        return _reading_identity(
            anchor_id=self.anchor_id,
            provenance_id=self.provenance_id,
            script=self.script,
            language=self.language,
            texts=self.texts,
        )

    def __post_init__(self) -> None:
        if self.epistemic_class != "interpretation":
            raise ValueError("A reading's epistemic class is interpretation.")
        if self.producer != "machine":
            raise ValueError("An HTR reading has producer machine.")
        if len(self.texts) != len(self.grapheme_ids) or not self.texts:
            raise ValueError("A reading cites one grapheme id per text.")
        expected = content_id([self.run_id, self.content_mapping()])
        if self.id != expected:
            raise ValueError("ReadingHypothesis.id does not match its content.")


class _HasId(Protocol):
    @property
    def id(self) -> uuid.UUID: ...


class _RowLog[RowT: _HasId]:
    """Append-only rows with one ``proposed`` event in the same write."""

    def __init__(self, record_name: str) -> None:
        self._record_name = record_name
        self._rows: list[RowT] = []

    @property
    def rows(self) -> tuple[RowT, ...]:
        return tuple(self._rows)

    def insert(
        self,
        stream: StatusStream,
        row: RowT,
        *,
        row_id: uuid.UUID,
        recorded_at: str,
        actor: str,
    ) -> StatusEvent:
        """Store ``row`` and append ``proposed`` in the same write."""
        if any(stored.id == row_id for stored in self._rows):
            raise ValueError(
                f"A {self._record_name} is inserted once, with its first status event."
            )
        if stream.current_status(row_id) is not None:
            raise ValueError(
                f"A {self._record_name} is inserted once, with its first status event."
            )
        event = stream.append(
            target_id=row_id,
            status="proposed",
            recorded_at=recorded_at,
            actor=actor,
        )
        self._rows.append(row)
        return event


class ReadingLog:
    """Append-only readings and the graphemes those readings cite."""

    def __init__(self) -> None:
        self._readings: _RowLog[ReadingHypothesis] = _RowLog("reading")
        self._graphemes: _RowLog[GraphemeHypothesis] = _RowLog("grapheme")

    @property
    def readings(self) -> tuple[ReadingHypothesis, ...]:
        return self._readings.rows

    @property
    def graphemes(self) -> tuple[GraphemeHypothesis, ...]:
        return self._graphemes.rows

    def insert(
        self,
        stream: StatusStream,
        reading: ReadingHypothesis,
        graphemes: Sequence[GraphemeHypothesis],
        *,
        recorded_at: str,
        actor: str,
    ) -> tuple[StatusEvent, ...]:
        """Insert the reading and each grapheme, each with ``proposed``."""
        if not isinstance(reading, ReadingHypothesis):
            raise TypeError("insert stores a ReadingHypothesis.")
        stored = tuple(graphemes)
        if tuple(item.id for item in stored) != reading.grapheme_ids:
            raise ValueError("A reading cites the graphemes inserted with it.")
        for item in stored:
            if not isinstance(item, GraphemeHypothesis):
                raise TypeError("insert stores a GraphemeHypothesis.")
            if item.reading_id != reading.id or item.run_id != reading.run_id:
                raise ValueError("A grapheme cites its parent reading and run.")
        events = [
            self._readings.insert(
                stream,
                reading,
                row_id=reading.id,
                recorded_at=recorded_at,
                actor=actor,
            )
        ]
        events.extend(
            self._graphemes.insert(
                stream,
                item,
                row_id=item.id,
                recorded_at=recorded_at,
                actor=actor,
            )
            for item in stored
        )
        return tuple(events)
