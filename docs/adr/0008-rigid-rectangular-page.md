# ADR 0008: Rigid rectangular page

- Status: Proposed
- Date: 2026-10-07

## Context

The product ranks placements of fragments from an approximately rectangular parchment. Real leaves shrink, cockle, and sometimes come from rolls or irregular sheets. The first search needs a stated geometry so evaluation can say what was assumed. [Q-SCI-01](../ALGORITHM.md#q-sci-01), [Q-SCI-02](../ALGORITHM.md#q-sci-02), and [Q-SCI-03](../ALGORITHM.md#q-sci-03) are open.

## Options

1. Rigid placements in one shared project rectangle. Edges meet. Page width and height are ranges on that frame, not a point size and not a per-assembly frame. Rolls, warps, and anisotropic shrinkage are out of this model. Shrinkage is residual error ([Q-SCI-20](../ALGORITHM.md#q-sci-20)). A rigid rank penalty against those ranges is a known limitation.
2. The same rigid model, but recorded gaps between edges are allowed.
3. A non-rigid warp, with page size known, bounded, or free as a separate choice.
4. A roll or irregular-sheet model in the first algorithm.

## Decision

Not accepted. The recommendation for the first geometric discussion is option 1. It is the working assumption behind the algorithm contract. It is not an accepted scientific model, and it does not close Q-SCI-01, Q-SCI-02, or Q-SCI-03.

## Consequences

- Synthetic tears can test option 1 because the generator follows the same rigid cuts.
- A result on real parchment cannot be reported as confirmation of option 1 while those questions are open.
- Uniform scale lives on a per-image `CalibrationTransform`, as in [ADR 0002](0002-three-coordinate-frames.md). It is not part of a placement.
- Ranking that penalizes a rigid mismatch is a known limitation while shrinkage and cockling stay open.
- Choosing option 3 or 4 later changes the algorithm and requires a benchmark comparison.

## Related

- [Q-SCI-01](../OPEN_QUESTIONS.md#q-sci-01)
- [Q-SCI-02](../OPEN_QUESTIONS.md#q-sci-02)
- [Q-SCI-03](../OPEN_QUESTIONS.md#q-sci-03)
- [Q-SCI-20](../OPEN_QUESTIONS.md#q-sci-20)
- [ALGORITHM.md](../ALGORITHM.md)
