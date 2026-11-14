"""Recognize one operator-supplied line image and store an ``ocr_inferred`` reading.

The product-facing runtime is Kraken >= 7.1.0, as
``docs/adr/0010-local-greek-htr-runtime.md`` decides. The weight file is a
local ``medium.safetensors``. This module does not download weights, does
not open a network connection, and does not detect lines. The operator
supplies the line image. Kraken is asked to read that image as one line,
which is the runtime's non-segmentation mode. Character cuts and model
confidences are not stored. A confidence is not a probability and is not
an ``htr`` score. No ``language`` score is written.

Model output is normalized from Unicode NFD to NFC before storage. Storage
does not strip accents and does not normalize final sigma. ``model_hash``
is the ``sha256:`` digest of the local weight bytes when a model is used,
and the token ``absent`` when the run used no model.

Kraken is imported only when a recognition calls it. The ``htr`` dependency
group is not a default group. A missing group raises ``HtrGroupMissing``.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import io
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prw.fixture_tiff import FixtureSamples, read_fixture_tiff
from prw.frames import CoordinateFrame
from prw.identity import ABSENT, content_id, hash_value
from prw.ingest import (
    IntegrityFailure,
    UnsupportedMediaType,
    VerifiedBytes,
    ingest_bytes,
)
from prw.lossless_tiff import DecodedRaster, TiffDecodeFailure, read_lossless_tiff
from prw.outlines import Fragment
from prw.provenance import (
    AlgorithmRun,
    ProvenanceEnvelope,
    StatusEvent,
    StatusStream,
    run_id_inputs,
)
from prw.readings import GraphemeHypothesis, ReadingHypothesis, ReadingLog

ALGORITHM_NAME = "greek_line_htr"
ALGORITHM_VERSION = "1"
WEIGHT_FILE_NAME = "medium.safetensors"
MINIMUM_RUNTIME = "7.1.0"
DEFAULT_SCRIPT = "Grek"
DEFAULT_LANGUAGE = "grc"
HTR_INSTALL_MESSAGE = (
    "The recognizer needs the htr dependency group, which is not installed. "
    "Install it with: uv sync --group htr"
)
_WEIGHT_MESSAGE = (
    "The recognizer reads a local file named medium.safetensors "
    "and does not download weights. Pass that file with --model."
)

type _Raster = FixtureSamples | DecodedRaster


class HtrGroupMissing(ValueError):
    """The optional ``htr`` group is not installed."""


def storage_text(text: str) -> str:
    """Return ``text`` in Unicode NFC.

    NFD input is composed. Accents stay. Final sigma stays final sigma.
    The function does not casefold and does not strip marks.
    """
    if not isinstance(text, str):
        raise TypeError("Recognizer output is text.")
    return unicodedata.normalize("NFC", text)


def grapheme_texts(text: str) -> tuple[str, ...]:
    """Split NFC text into grapheme clusters.

    A cluster is a base character plus any combining marks that remain
    after NFC. An empty prediction is one empty grapheme. Marks are not
    dropped.
    """
    normalized = storage_text(text)
    if normalized == "":
        return ("",)
    clusters: list[str] = []
    current = ""
    for char in normalized:
        if current and unicodedata.combining(char):
            current += char
            continue
        if current:
            clusters.append(current)
        current = char
    clusters.append(current)
    return tuple(clusters)


def model_hash_for_weights(data: bytes | bytearray | None) -> str:
    """Return the provenance ``model_hash`` for local weight bytes.

    ``None`` means the run used no model, and the token is ``absent``.
    Any byte string, including an empty file, is ``sha256:`` plus the
    digest of those bytes. This function does not invent a digest for a
    checksum that was published in another algorithm.
    """
    if data is None:
        return ABSENT
    if not isinstance(data, bytes | bytearray):
        raise TypeError("Model hash reads the local weight bytes.")
    return hash_value(bytes(data))


def require_weight_path(path: Path) -> Path:
    """Return ``path`` when it is an existing ``medium.safetensors`` file."""
    if not isinstance(path, Path):
        raise TypeError("The model path is a local path.")
    if path.name != WEIGHT_FILE_NAME or not path.is_file():
        raise ValueError(_WEIGHT_MESSAGE)
    return path


def require_htr_group() -> str:
    """Return the installed Kraken version.

    Raises:
        HtrGroupMissing: Kraken cannot be imported.
        ValueError: Kraken is installed and older than 7.1.0.
    """
    try:
        version = importlib.metadata.version("kraken")
        importlib.import_module("kraken")
    except (ImportError, importlib.metadata.PackageNotFoundError) as exc:
        raise HtrGroupMissing(HTR_INSTALL_MESSAGE) from exc
    if not _version_at_least(version, (7, 1, 0)):
        raise ValueError(
            f"The recognizer needs Kraken >= 7.1.0. The installed version is {version}."
        )
    return version


def predict_line_text(presented: bytes, model_path: Path) -> str:
    """Return Kraken's text for one line image.

    ``presented`` is the line-image bytes. ``model_path`` is a local
    weight file. Confidences are not returned. This function does not
    download a model and does not segment a page into lines.
    """
    if not isinstance(presented, bytes | bytearray):
        raise TypeError("The recognizer reads caller-supplied line-image bytes.")
    require_weight_path(model_path)
    recognition, containers, configs, images = _htr_modules()
    config = configs.RecognitionInferenceConfig(
        num_line_workers=0,
        padding=16,
        temperature=1.0,
        bidi_reordering=True,
        text_direction="horizontal-tb",
    )
    model = recognition.RecognitionTaskModel.load_model(model_path)
    with images.open(io.BytesIO(bytes(presented))) as image:
        image.load()
        bounds = containers.Segmentation(
            type="bbox",
            text_direction=config.text_direction,
            imagename="operator-line",
            script_detection=False,
            lines=[
                containers.BBoxLine(
                    id="operator-line",
                    bbox=(0, 0, image.width, image.height),
                )
            ],
        )
        records = list(model.predict(im=image, segmentation=bounds, config=config))
    if len(records) != 1:
        raise RuntimeError("The recognizer expected one line prediction.")
    prediction = records[0].prediction
    if not isinstance(prediction, str):
        raise RuntimeError("The recognizer expected text.")
    return prediction


def line_fragment(label: str) -> Fragment:
    """Fragment identity for one operator label.

    The id is a UUIDv5 over this command's project id and the label. The
    command does not write an outline.
    """
    return Fragment.create(project_id=content_id(["cli-recognize", label]), label=label)


def line_rectangle(width: int, height: int) -> tuple[tuple[float, float], ...]:
    """Pixel rectangle of the whole line image.

    The rectangle is the image bounds in ``source_pixels``. It is not a
    character box and not a detected baseline.
    """
    if isinstance(width, bool) or not isinstance(width, int) or width < 1:
        raise ValueError("A line image has a positive width and height.")
    if isinstance(height, bool) or not isinstance(height, int) or height < 1:
        raise ValueError("A line image has a positive width and height.")
    wide = float(width)
    high = float(height)
    return ((0.0, 0.0), (wide, 0.0), (wide, high), (0.0, high))


@dataclass(frozen=True, slots=True)
class PreparedLine:
    """One ingested line image, before a model runs."""

    content_hash: str
    source_id: uuid.UUID
    width: int
    height: int
    decoder_name: str
    decoder_version: str


PrepareResult = (
    IntegrityFailure | UnsupportedMediaType | TiffDecodeFailure | PreparedLine
)


@dataclass(frozen=True, slots=True)
class LineRecognition:
    """One completed line recognition. The reading is an interpretation."""

    run: AlgorithmRun
    reading: ReadingHypothesis
    graphemes: tuple[GraphemeHypothesis, ...]
    frame: CoordinateFrame
    fragment: Fragment
    proposed: tuple[StatusEvent, ...]

    def __post_init__(self) -> None:
        if self.run.status != "completed" or self.run.attempt_id is not None:
            raise ValueError("A completed recognition has no attempt_id.")
        if self.reading.run_id != self.run.id:
            raise ValueError("The reading run_id is the completed run.")
        if self.reading.epistemic_class != "interpretation":
            raise ValueError("A recognition's epistemic class is interpretation.")
        if self.reading.producer != "machine":
            raise ValueError("A recognition has producer machine.")
        if self.run.reading_ids != (self.reading.id,):
            raise ValueError("The run records the reading it produced.")
        if self.run.join_ids or self.run.assembly_ids:
            raise ValueError("A line recognition does not record a join or assembly.")
        if self.run.line_ids or self.run.line_order_ids:
            raise ValueError("A line recognition does not detect a text line.")
        if any(item.text_status != "ocr_inferred" for item in self.graphemes):
            raise ValueError("Stored graphemes are ocr_inferred.")
        if any(item.epistemic_class != "interpretation" for item in self.graphemes):
            raise ValueError("A grapheme's epistemic class is interpretation.")
        if any(item.producer != "machine" for item in self.graphemes):
            raise ValueError("An HTR grapheme has producer machine.")


@dataclass(frozen=True, slots=True)
class FailedLineRecognition:
    """A failed HTR run with no reading.

    ``run.attempt_id`` is set. The run id is not the id a later completed
    run of the same inputs would take.
    """

    run: AlgorithmRun
    detail: str

    def __post_init__(self) -> None:
        if self.run.status != "failed" or self.run.attempt_id is None:
            raise ValueError("A failed recognition stores a failed run and attempt_id.")
        if self.run.reading_ids:
            raise ValueError("A failed recognition stores no reading.")
        if self.detail == "":
            raise ValueError("A failed recognition names the runtime error.")
        completed = content_id(run_id_inputs(self.run.provenance, "completed", None))
        if self.run.id == completed:
            raise ValueError(
                "A failed run id is not the completed id of the same inputs."
            )


def prepare_line_image(
    presented: bytes | bytearray,
    *,
    expected_hash: str | None = None,
) -> PrepareResult:
    """Hash and decode one line image. The bytes are not modified."""
    if not isinstance(presented, bytes | bytearray):
        raise TypeError("The recognizer reads caller-supplied line-image bytes.")
    ingested = ingest_bytes(presented, expected_hash=expected_hash)
    if not isinstance(ingested, VerifiedBytes):
        return ingested
    raster = _read_raster(bytes(presented))
    if isinstance(raster, TiffDecodeFailure):
        return raster
    return PreparedLine(
        content_hash=ingested.content_hash,
        source_id=ingested.id,
        width=raster.width,
        height=raster.height,
        decoder_name=raster.decoder_name,
        decoder_version=raster.decoder_version,
    )


class LineRecognitionLog:
    """In-memory recognition runs and the readings those completed runs inserted."""

    def __init__(self) -> None:
        self._runs: list[AlgorithmRun] = []
        self._completed: dict[uuid.UUID, LineRecognition] = {}
        self._readings = ReadingLog()
        self._status = StatusStream()

    @property
    def runs(self) -> tuple[AlgorithmRun, ...]:
        return tuple(self._runs)

    def store(
        self,
        prepared: PreparedLine,
        *,
        weight_bytes: bytes | bytearray | None,
        prediction: str,
        label: str,
        script: str,
        language: str,
        code_version: str,
        runtime_version: str,
        recorded_at: str,
    ) -> LineRecognition:
        """Store ``prediction`` for one prepared line.

        ``weight_bytes is None`` records ``model_hash`` ``absent``. A byte
        string records the ``sha256:`` digest of those bytes. The same
        completed inputs return the stored reading and do not insert another.
        """
        if not isinstance(prepared, PreparedLine):
            raise TypeError("store reads a prepared line image.")
        envelope = _envelope(
            prepared,
            weight_bytes=weight_bytes,
            script=script,
            language=language,
            code_version=code_version,
            runtime_version=runtime_version,
        )
        normalized = storage_text(prediction)
        completed_id = content_id(run_id_inputs(envelope, "completed", None))
        stored = self._completed.get(completed_id)
        if stored is not None:
            if stored.reading.text != normalized:
                raise ValueError(
                    "A completed recognition of these inputs stored different text."
                )
            return stored
        return self._succeed(
            envelope,
            prepared,
            texts=grapheme_texts(normalized),
            label=label,
            script=script,
            language=language,
            recorded_at=recorded_at,
        )

    def fail(
        self,
        prepared: PreparedLine,
        *,
        weight_bytes: bytes | bytearray | None,
        label: str,
        script: str,
        language: str,
        code_version: str,
        runtime_version: str,
        recorded_at: str,
        detail: str,
    ) -> FailedLineRecognition:
        """Record a failed run. No reading is stored.

        ``label`` is accepted so the caller passes the same request. It is
        not an id input of a run that produced no reading.
        """
        if not isinstance(prepared, PreparedLine):
            raise TypeError("fail reads a prepared line image.")
        if not isinstance(detail, str) or detail == "":
            raise ValueError("A failed recognition names the runtime error.")
        line_fragment(label)
        envelope = _envelope(
            prepared,
            weight_bytes=weight_bytes,
            script=script,
            language=language,
            code_version=code_version,
            runtime_version=runtime_version,
        )
        run = AlgorithmRun.create(envelope, status="failed", started_at=recorded_at)
        self._runs.append(run)
        return FailedLineRecognition(run=run, detail=detail)

    def _succeed(
        self,
        envelope: ProvenanceEnvelope,
        prepared: PreparedLine,
        *,
        texts: tuple[str, ...],
        label: str,
        script: str,
        language: str,
        recorded_at: str,
    ) -> LineRecognition:
        run_id = content_id(run_id_inputs(envelope, "completed", None))
        fragment = line_fragment(label)
        frame = CoordinateFrame.source_pixels(owner_id=prepared.source_id)
        region = line_rectangle(prepared.width, prepared.height)
        reading = ReadingHypothesis.create(
            run_id=run_id,
            anchor_id=fragment.id,
            texts=texts,
            grapheme_ids=_placeholder_ids(len(texts)),
            script=script,
            language=language,
            provenance_id=envelope.id,
        )
        graphemes = tuple(
            GraphemeHypothesis.create(
                reading_id=reading.id,
                text=text,
                frame_id=frame.id,
                ink_region=region,
                run_id=run_id,
                position=index,
            )
            for index, text in enumerate(texts)
        )
        reading = ReadingHypothesis.create(
            run_id=run_id,
            anchor_id=fragment.id,
            texts=texts,
            grapheme_ids=tuple(item.id for item in graphemes),
            script=script,
            language=language,
            provenance_id=envelope.id,
        )
        run = AlgorithmRun.create(
            envelope,
            status="completed",
            started_at=recorded_at,
            reading_ids=(reading.id,),
        )
        if run.id != run_id:
            raise ValueError("The completed run id does not match its inputs.")
        proposed = self._readings.insert(
            self._status,
            reading,
            graphemes,
            recorded_at=recorded_at,
            actor=str(run.id),
        )
        self._runs.append(run)
        result = LineRecognition(
            run=run,
            reading=reading,
            graphemes=graphemes,
            frame=frame,
            fragment=fragment,
            proposed=proposed,
        )
        self._completed[run.id] = result
        return result


def _placeholder_ids(count: int) -> tuple[uuid.UUID, ...]:
    """Temporary ids used only to satisfy the length check before graphemes exist.

    The reading id does not hash grapheme ids. The stored reading is built
    again with the real grapheme ids. These placeholders are not inserted.
    """
    return tuple(uuid.UUID(int=index + 1) for index in range(count))


def _envelope(
    prepared: PreparedLine,
    *,
    weight_bytes: bytes | bytearray | None,
    script: str,
    language: str,
    code_version: str,
    runtime_version: str,
) -> ProvenanceEnvelope:
    if not isinstance(runtime_version, str) or runtime_version == "":
        raise ValueError("runtime_version is required.")
    return ProvenanceEnvelope.create(
        source_hashes=(prepared.content_hash,),
        parameters=_parameters(script, language, runtime_version),
        algorithm_name=ALGORITHM_NAME,
        algorithm_version=ALGORITHM_VERSION,
        code_version=code_version,
        decoder_name=prepared.decoder_name,
        decoder_version=prepared.decoder_version,
        model_hash=model_hash_for_weights(weight_bytes),
    )


def _parameters(script: str, language: str, runtime_version: str) -> dict[str, Any]:
    return {
        "bidi_reordering": True,
        "language": language,
        "line_input": "operator_supplied",
        "minimum_runtime_version": MINIMUM_RUNTIME,
        "model_file": WEIGHT_FILE_NAME,
        "num_line_workers": 0,
        "padding": 16,
        "runtime": "kraken",
        "runtime_version": runtime_version,
        "scored": False,
        "script": script,
        "segmentation": "none",
        "temperature": 1.0,
        "text_direction": "horizontal-tb",
        "unicode_normalization": "NFC",
    }


def _read_raster(presented: bytes) -> _Raster | TiffDecodeFailure:
    fixture = read_fixture_tiff(presented)
    if isinstance(fixture, FixtureSamples):
        return fixture
    return read_lossless_tiff(presented)


def _htr_modules() -> tuple[Any, Any, Any, Any]:
    try:
        recognition: Any = importlib.import_module("kraken.tasks.recognition")
        containers: Any = importlib.import_module("kraken.containers")
        configs: Any = importlib.import_module("kraken.configs")
        images: Any = importlib.import_module("PIL.Image")
    except ImportError as exc:
        raise HtrGroupMissing(HTR_INSTALL_MESSAGE) from exc
    return recognition, containers, configs, images


def _version_at_least(version: str, minimum: tuple[int, int, int]) -> bool:
    parts: list[int] = []
    for piece in version.split("."):
        digits = ""
        for char in piece:
            if not char.isdigit():
                break
            digits += char
        if digits == "":
            break
        parts.append(int(digits))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3]) >= minimum
