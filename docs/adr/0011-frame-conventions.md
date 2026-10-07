# ADR 0011: Frame conventions

- Status: Accepted
- Date: 2026-10-07

## Context

Joins and overlays disagree when each implementation picks its own origin and y axis. [ADR 0002](0002-three-coordinate-frames.md) keeps the three frames distinct and does not by itself fix the axes. Ruling R15 in [R0-01](../reviewed_resolutions/R0-01.md) decides the millimetre convention. One shared project page frame, from ruling R13, needs the same handedness so assemblies are comparable.

## Decision

`source_pixels` has its origin at the top-left pixel, `+x` to the right, `+y` down, in pixels.

`fragment_local_mm` uses the same axes, in millimetres. Its origin is the centroid of one polygon: the `FragmentOutlineRevision` cited by `CoordinateFrame.establishing_outline_revision_id`. That citation is the mask. It is not a `FragmentExtent`. The citation is fixed when the frame is created. Superseding the outline does not move the origin and does not change the citation. Later edge geometry is expressed in that same frame. The `+y` down axis matches the image convention and prevents sign bugs.

`page_global_mm` uses the same axes, in millimetres. Its origin is the corner with the smallest x and the smallest y, and that corner is coordinate (0, 0). Width and height on `PageFrame` are ranges measured from that origin. They are not a point size, and they do not move the origin.

Each stored frame repeats this origin and these axes. That repetition is redundancy, so a reader can see the convention on the row. It is not a second choice of origin or axes.

Transforms are not stored on frames. A placement is a `RigidTransform`. A per-image similarity is a `CalibrationTransform`.

## Consequences

- [Q-SCI-11](../OPEN_QUESTIONS.md#q-sci-11) and [Q-SCI-12](../OPEN_QUESTIONS.md#q-sci-12) are closed.
- The synthetic generator writes coordinates and ground-truth transforms in this convention.
- Code does not inherit a hidden axis default.

## Related

- [ADR 0002](0002-three-coordinate-frames.md)
- [DATA_MODEL.md](../DATA_MODEL.md#coordinateframe)
- [DATA_MODEL.md](../DATA_MODEL.md#pageframe)
