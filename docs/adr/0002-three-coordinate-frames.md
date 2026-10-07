# ADR 0002: Three coordinate frames

- Status: Accepted
- Date: 2026-10-07

## Context

A length in pixels is not a length in millimetres, and a millimetre on one fragment is not a millimetre on a hypothesized page. Mixing those spaces produces joins that cannot be audited.

## Decision

The project keeps three coordinate frames distinct:

- `source_pixels` for the immutable image
- `fragment_local_mm` for one fragment
- `page_global_mm` for the one shared project page frame

Every position, length, and polygon names the frame it uses. A transform between frames is an explicit record.

## Consequences

- Code and documents do not store a bare number that could belong to more than one frame.
- A placement is a `RigidTransform`: rotation and translation only. Uniform scale lives on a `CalibrationTransform` for one source image. A free affine is a `DiagnosticRecord`, and it is not a placement.
- Millimetre origin and axis direction are [ADR 0011](0011-frame-conventions.md). [Q-SCI-11](../OPEN_QUESTIONS.md#q-sci-11) and [Q-SCI-12](../OPEN_QUESTIONS.md#q-sci-12) are closed.

## Related

- [DATA_MODEL.md](../DATA_MODEL.md#coordinateframe)
- [ADR 0011](0011-frame-conventions.md)
