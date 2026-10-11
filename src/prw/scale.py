"""Place a source-pixel outline into ``fragment_local_mm`` from a supplied scale.

``fragment_local_mm`` follows ``docs/adr/0011-frame-conventions.md``: ``+x``
right, ``+y`` down, and an origin at the centroid of the establishing
outline. The citation is fixed when the frame is created. A later polygon
is stored in that frame and does not move the origin.

A caller-supplied scale is a supplied measurement, not a scale the
algorithm recovered. ``pixels_per_mm`` and its uncertainty come from the
caller. This module does not read a TIFF header and does not estimate a
target. ``Q-SCI-10`` stays open. Absent scale leaves the outline in
``source_pixels`` and does not invent a millimetre polygon.

The millimetre outline stays epistemic class ``interpretation`` with
producer ``machine``. Calibration stays ``observed``. Supplying a scale
does not make the outline observed.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from prw.frames import CoordinateFrame, polygon_centroid
from prw.identity import content_id
from prw.outlines import FragmentOutlineRevision, OutlineRevisionLog
from prw.provenance import (
    AlgorithmRun,
    ProvenanceEnvelope,
    StatusEvent,
    StatusStream,
    run_id_inputs,
)

ALGORITHM_NAME = "caller_supplied_scale"
ALGORITHM_VERSION = "1"
EVIDENCE_DESCRIPTION = "caller-supplied measurement"
PIXEL_CENTER = (0.5, 0.5)
Producer = Literal["human", "machine"]


def _finite_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{label} is a finite number.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} is a finite number.")
    return number


def _pixels_per_mm(value: object) -> float:
    number = _finite_number(value, "pixels_per_mm")
    if number <= 0:
        raise ValueError("pixels_per_mm is a positive finite number.")
    return number


def _uncertainty(value: object) -> float:
    number = _finite_number(value, "uncertainty")
    if number < 0:
        raise ValueError("uncertainty is zero or a positive finite number.")
    return number


def _require_text(value: str, label: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{label} is required.")
    return value


@dataclass(frozen=True, slots=True)
class CallerScale:
    """A measurement the caller supplied. This is not a recovered scale."""

    pixels_per_mm: float
    uncertainty: float
    producer: Producer

    def __post_init__(self) -> None:
        if self.producer not in {"human", "machine"}:
            raise ValueError("A supplied scale has producer human or machine.")
        object.__setattr__(self, "pixels_per_mm", _pixels_per_mm(self.pixels_per_mm))
        object.__setattr__(self, "uncertainty", _uncertainty(self.uncertainty))


@dataclass(frozen=True, slots=True)
class CalibrationTransform:
    """Uniform scale from ``source_pixels`` into one ``fragment_local_mm`` frame.

    See ``CalibrationTransform`` in ``docs/DATA_MODEL.md``. The epistemic
    class is ``observed``.
    """

    source_image_id: uuid.UUID
    from_frame_id: uuid.UUID
    to_frame_id: uuid.UUID
    rotation_radians: float
    translation_x: float
    translation_y: float
    uniform_scale: float
    producer: Producer
    epistemic_class: Literal["observed"]
    id: uuid.UUID

    @classmethod
    def create(
        cls,
        *,
        source_image_id: uuid.UUID,
        from_frame_id: uuid.UUID,
        to_frame_id: uuid.UUID,
        translation_x: float,
        translation_y: float,
        uniform_scale: float,
        producer: Producer,
    ) -> CalibrationTransform:
        """Build the similarity. Rotation is zero. ``+y`` stays down."""
        fields = {
            "source_image_id": source_image_id,
            "from_frame_id": from_frame_id,
            "to_frame_id": to_frame_id,
            "rotation_radians": 0.0,
            "translation_x": translation_x,
            "translation_y": translation_y,
            "uniform_scale": uniform_scale,
            "producer": producer,
            "epistemic_class": "observed",
        }
        return cls(
            source_image_id=source_image_id,
            from_frame_id=from_frame_id,
            to_frame_id=to_frame_id,
            rotation_radians=0.0,
            translation_x=translation_x,
            translation_y=translation_y,
            uniform_scale=uniform_scale,
            producer=producer,
            epistemic_class="observed",
            id=content_id(fields),
        )

    def content_mapping(self) -> dict[str, object]:
        """Stored fields except ``id``."""
        return {
            "source_image_id": self.source_image_id,
            "from_frame_id": self.from_frame_id,
            "to_frame_id": self.to_frame_id,
            "rotation_radians": self.rotation_radians,
            "translation_x": self.translation_x,
            "translation_y": self.translation_y,
            "uniform_scale": self.uniform_scale,
            "producer": self.producer,
            "epistemic_class": self.epistemic_class,
        }

    def __post_init__(self) -> None:
        if self.epistemic_class != "observed":
            raise ValueError("A calibration transform's epistemic class is observed.")
        if self.rotation_radians != 0.0:
            raise ValueError("A supplied scale does not rotate the outline.")
        if self.id != content_id(self.content_mapping()):
            raise ValueError("CalibrationTransform.id does not match its content.")


@dataclass(frozen=True, slots=True)
class CalibrationObservation:
    """Observed scale for one source image.

    See ``CalibrationObservation`` in ``docs/DATA_MODEL.md``. Producer
    ``human`` omits ``provenance_id``. Producer ``machine`` stores it.
    """

    source_image_id: uuid.UUID
    producer: Producer
    epistemic_class: Literal["observed"]
    pixels_per_mm: float
    uncertainty: float
    evidence_description: str
    frame_id: uuid.UUID
    transform_id: uuid.UUID
    provenance_id: uuid.UUID | None
    id: uuid.UUID

    @classmethod
    def create(
        cls,
        *,
        source_image_id: uuid.UUID,
        producer: Producer,
        pixels_per_mm: float,
        uncertainty: float,
        frame_id: uuid.UUID,
        transform_id: uuid.UUID,
        provenance_id: uuid.UUID | None,
    ) -> CalibrationObservation:
        """Record the caller-supplied measurement. The class is ``observed``."""
        if producer == "human":
            stored_provenance = None
        elif producer == "machine":
            if not isinstance(provenance_id, uuid.UUID):
                raise ValueError("A machine calibration includes provenance_id.")
            stored_provenance = provenance_id
        else:
            raise ValueError("A supplied scale has producer human or machine.")
        observation = cls(
            source_image_id=source_image_id,
            producer=producer,
            epistemic_class="observed",
            pixels_per_mm=pixels_per_mm,
            uncertainty=uncertainty,
            evidence_description=EVIDENCE_DESCRIPTION,
            frame_id=frame_id,
            transform_id=transform_id,
            provenance_id=stored_provenance,
            id=content_id(
                _observation_content(
                    source_image_id=source_image_id,
                    producer=producer,
                    pixels_per_mm=pixels_per_mm,
                    uncertainty=uncertainty,
                    frame_id=frame_id,
                    transform_id=transform_id,
                    provenance_id=stored_provenance,
                )
            ),
        )
        return observation

    def content_mapping(self) -> dict[str, object]:
        """Stored fields except ``id``. Human provenance is absent."""
        return _observation_content(
            source_image_id=self.source_image_id,
            producer=self.producer,
            pixels_per_mm=self.pixels_per_mm,
            uncertainty=self.uncertainty,
            frame_id=self.frame_id,
            transform_id=self.transform_id,
            provenance_id=self.provenance_id,
        )

    def __post_init__(self) -> None:
        if self.epistemic_class != "observed":
            raise ValueError("A calibration observation's epistemic class is observed.")
        if self.evidence_description != EVIDENCE_DESCRIPTION:
            raise ValueError(
                "The evidence is a caller-supplied measurement, "
                "not a scale the algorithm recovered."
            )
        if self.producer == "human" and self.provenance_id is not None:
            raise ValueError("A human calibration omits provenance_id.")
        if self.producer == "machine" and self.provenance_id is None:
            raise ValueError("A machine calibration includes provenance_id.")
        if self.id != content_id(self.content_mapping()):
            raise ValueError("CalibrationObservation.id does not match its content.")


def _observation_content(
    *,
    source_image_id: uuid.UUID,
    producer: Producer,
    pixels_per_mm: float,
    uncertainty: float,
    frame_id: uuid.UUID,
    transform_id: uuid.UUID,
    provenance_id: uuid.UUID | None,
) -> dict[str, object]:
    fields: dict[str, object] = {
        "source_image_id": source_image_id,
        "producer": producer,
        "epistemic_class": "observed",
        "pixels_per_mm": pixels_per_mm,
        "uncertainty": uncertainty,
        "evidence_description": EVIDENCE_DESCRIPTION,
        "frame_id": frame_id,
        "transform_id": transform_id,
    }
    if provenance_id is not None:
        fields["provenance_id"] = provenance_id
    return fields


@dataclass(frozen=True, slots=True)
class UnscaledOutline:
    """The pixel outline, unchanged. No millimetre polygon is stored."""

    outline: FragmentOutlineRevision


@dataclass(frozen=True, slots=True)
class ScaledOutline:
    """A millimetre revision and the observed calibration that placed it."""

    pixel_outline: FragmentOutlineRevision
    outline: FragmentOutlineRevision
    frame: CoordinateFrame
    observation: CalibrationObservation
    transform: CalibrationTransform
    run: AlgorithmRun
    proposed: StatusEvent

    def __post_init__(self) -> None:
        if self.outline.epistemic_class != "interpretation":
            raise ValueError(
                "A millimetre outline's epistemic class is interpretation."
            )
        if self.outline.producer != "machine":
            raise ValueError("A millimetre outline has producer machine.")
        if self.observation.epistemic_class != "observed":
            raise ValueError("Supplying a scale does not re-type the outline.")
        if self.frame.kind != "fragment_local_mm":
            raise ValueError("The scaled outline is in fragment_local_mm.")
        if self.frame.establishing_outline_revision_id != self.outline.id:
            raise ValueError("The establishing citation is this millimetre outline.")
        if self.outline.supersedes_id != self.pixel_outline.id:
            raise ValueError("supersedes_id points at the pixel revision.")
        if polygon_centroid(self.outline.polygon) != self.frame.origin:
            raise ValueError("The local polygon's centroid is the frame origin.")


@dataclass(frozen=True, slots=True)
class LaterLocalOutline:
    """A later polygon in an existing ``fragment_local_mm`` frame."""

    outline: FragmentOutlineRevision
    frame: CoordinateFrame
    proposed: StatusEvent


def _require_pixel_outline(
    outline: FragmentOutlineRevision,
    frame: CoordinateFrame,
) -> None:
    if not isinstance(outline, FragmentOutlineRevision):
        raise TypeError("Scale applies to a FragmentOutlineRevision.")
    if not isinstance(frame, CoordinateFrame):
        raise TypeError("The pixel frame is a CoordinateFrame.")
    if frame.kind != "source_pixels":
        raise ValueError("The pixel outline is in source_pixels.")
    if outline.frame_id != frame.id:
        raise ValueError("The outline cites the source_pixels frame.")
    if outline.epistemic_class != "interpretation" or outline.producer != "machine":
        raise ValueError("The pixel outline is a machine interpretation.")


def _millimetre_polygon(
    polygon: Sequence[tuple[float, float]],
    *,
    pixels_per_mm: float,
    translation_x: float,
    translation_y: float,
) -> tuple[tuple[float, float], ...]:
    offset_x, offset_y = PIXEL_CENTER
    return tuple(
        (
            (x_coord + offset_x) / pixels_per_mm + translation_x,
            (y_coord + offset_y) / pixels_per_mm + translation_y,
        )
        for x_coord, y_coord in polygon
    )


def _establishing_translation(
    polygon: Sequence[tuple[float, float]],
    pixels_per_mm: float,
) -> tuple[float, float]:
    offset_x, offset_y = PIXEL_CENTER
    centers = tuple(
        (x_coord + offset_x, y_coord + offset_y) for x_coord, y_coord in polygon
    )
    centroid_x, centroid_y = polygon_centroid(centers)
    return (-centroid_x / pixels_per_mm, -centroid_y / pixels_per_mm)


def _envelope(
    source_hashes: Sequence[str],
    scale: CallerScale,
    *,
    code_version: str,
    decoder_name: str,
    decoder_version: str,
) -> ProvenanceEnvelope:
    if len(tuple(source_hashes)) < 1:
        raise ValueError("The scale envelope cites the source image hash.")
    return ProvenanceEnvelope.create(
        source_hashes=source_hashes,
        parameters={
            "pixel_center": [PIXEL_CENTER[0], PIXEL_CENTER[1]],
            "pixels_per_mm": scale.pixels_per_mm,
            "uncertainty": scale.uncertainty,
        },
        algorithm_name=ALGORITHM_NAME,
        algorithm_version=ALGORITHM_VERSION,
        code_version=_require_text(code_version, "code_version"),
        decoder_name=_require_text(decoder_name, "decoder_name"),
        decoder_version=_require_text(decoder_version, "decoder_version"),
    )


class ScaleLog:
    """In-memory calibrations and the millimetre outlines they place.

    A repeated completed conversion returns the stored row. The pixel
    revision stays in the log. ``AlgorithmRun`` does not gain ``outline_ids``.
    """

    def __init__(self) -> None:
        self._runs: dict[uuid.UUID, AlgorithmRun] = {}
        self._outlines = OutlineRevisionLog()
        self._status = StatusStream()
        self._scaled: dict[uuid.UUID, ScaledOutline] = {}
        self._later: dict[uuid.UUID, LaterLocalOutline] = {}

    @property
    def outlines(self) -> tuple[FragmentOutlineRevision, ...]:
        return self._outlines.rows

    @property
    def runs(self) -> tuple[AlgorithmRun, ...]:
        return tuple(self._runs.values())

    def apply(
        self,
        pixel_outline: FragmentOutlineRevision,
        pixel_frame: CoordinateFrame,
        scale: CallerScale | None,
        *,
        source_hashes: Sequence[str] = (),
        code_version: str = "",
        decoder_name: str = "",
        decoder_version: str = "",
        recorded_at: str = "",
    ) -> UnscaledOutline | ScaledOutline:
        """Convert ``pixel_outline`` when ``scale`` is supplied.

        ``scale is None`` returns that outline and writes no millimetre
        polygon. The caller supplies ``pixels_per_mm``. This method does
        not read a file.
        """
        _require_pixel_outline(pixel_outline, pixel_frame)
        if scale is None:
            return UnscaledOutline(pixel_outline)
        if not isinstance(scale, CallerScale):
            raise TypeError("Scale is a CallerScale or absent.")
        envelope = _envelope(
            source_hashes,
            scale,
            code_version=code_version,
            decoder_name=decoder_name,
            decoder_version=decoder_version,
        )
        translation_x, translation_y = _establishing_translation(
            pixel_outline.polygon, scale.pixels_per_mm
        )
        local_polygon = _millimetre_polygon(
            pixel_outline.polygon,
            pixels_per_mm=scale.pixels_per_mm,
            translation_x=translation_x,
            translation_y=translation_y,
        )
        run = self._completed_run(envelope, recorded_at)
        outline_id = content_id([run.id, local_polygon])
        stored = self._scaled.get(outline_id)
        if stored is not None:
            return stored
        frame = CoordinateFrame.fragment_local_mm(
            owner_id=pixel_outline.fragment_id,
            establishing_outline_revision_id=outline_id,
            polygon=local_polygon,
        )
        outline = self._millimetre_outline(
            pixel_outline,
            frame_id=frame.id,
            polygon=local_polygon,
            run=run,
            supersedes_id=pixel_outline.id,
        )
        if outline.id != frame.establishing_outline_revision_id:
            raise RuntimeError("The establishing citation is the millimetre outline.")
        transform = CalibrationTransform.create(
            source_image_id=pixel_frame.owner_id,
            from_frame_id=pixel_frame.id,
            to_frame_id=frame.id,
            translation_x=translation_x,
            translation_y=translation_y,
            uniform_scale=scale.pixels_per_mm,
            producer=scale.producer,
        )
        provenance_id = envelope.id if scale.producer == "machine" else None
        observation = CalibrationObservation.create(
            source_image_id=pixel_frame.owner_id,
            producer=scale.producer,
            pixels_per_mm=scale.pixels_per_mm,
            uncertainty=scale.uncertainty,
            frame_id=pixel_frame.id,
            transform_id=transform.id,
            provenance_id=provenance_id,
        )
        self._retain(pixel_outline, recorded_at)
        proposed = self._outlines.insert(
            self._status,
            outline,
            recorded_at=recorded_at,
            actor=str(run.id),
        )
        result = ScaledOutline(
            pixel_outline=pixel_outline,
            outline=outline,
            frame=frame,
            observation=observation,
            transform=transform,
            run=run,
            proposed=proposed,
        )
        self._scaled[outline.id] = result
        return result

    def place_later(
        self,
        pixel_outline: FragmentOutlineRevision,
        established: ScaledOutline,
        *,
        recorded_at: str,
    ) -> LaterLocalOutline:
        """Store another polygon in the establishing frame.

        ``with_later_outline`` keeps the frame id, the establishing
        citation, and the origin.
        """
        if not isinstance(established, ScaledOutline):
            raise TypeError("A later polygon uses an established local frame.")
        if pixel_outline.frame_id != established.pixel_outline.frame_id:
            raise ValueError("The later outline cites the same source_pixels frame.")
        if pixel_outline.epistemic_class != "interpretation":
            raise ValueError("The later outline is a machine interpretation.")
        local_polygon = _millimetre_polygon(
            pixel_outline.polygon,
            pixels_per_mm=established.transform.uniform_scale,
            translation_x=established.transform.translation_x,
            translation_y=established.transform.translation_y,
        )
        outline_id = content_id([established.run.id, local_polygon])
        stored = self._later.get(outline_id)
        if stored is not None:
            return stored
        if outline_id == established.outline.id:
            raise ValueError("A later polygon is a new row.")
        frame = established.frame.with_later_outline(outline_id, local_polygon)
        outline = self._millimetre_outline(
            pixel_outline,
            frame_id=frame.id,
            polygon=local_polygon,
            run=established.run,
            supersedes_id=pixel_outline.id,
        )
        self._retain(pixel_outline, recorded_at)
        proposed = self._outlines.insert(
            self._status,
            outline,
            recorded_at=recorded_at,
            actor=str(established.run.id),
        )
        result = LaterLocalOutline(outline=outline, frame=frame, proposed=proposed)
        self._later[outline.id] = result
        return result

    def _completed_run(
        self, envelope: ProvenanceEnvelope, recorded_at: str
    ) -> AlgorithmRun:
        run_id = content_id(run_id_inputs(envelope, "completed", None))
        stored = self._runs.get(run_id)
        if stored is not None:
            return stored
        run = AlgorithmRun.create(envelope, status="completed", started_at=recorded_at)
        self._runs[run.id] = run
        return run

    def _retain(self, outline: FragmentOutlineRevision, recorded_at: str) -> None:
        try:
            self._outlines.by_id(outline.id)
        except KeyError:
            actor = str(outline.run_id)
            self._outlines.insert(
                self._status,
                outline,
                recorded_at=recorded_at,
                actor=actor,
            )

    def _millimetre_outline(
        self,
        pixel_outline: FragmentOutlineRevision,
        *,
        frame_id: uuid.UUID,
        polygon: Sequence[tuple[float, float]],
        run: AlgorithmRun,
        supersedes_id: uuid.UUID,
    ) -> FragmentOutlineRevision:
        return FragmentOutlineRevision.create(
            fragment_id=pixel_outline.fragment_id,
            frame_id=frame_id,
            polygon=polygon,
            run_id=run.id,
            provenance_id=run.provenance_id,
            supersedes_id=supersedes_id,
        )
