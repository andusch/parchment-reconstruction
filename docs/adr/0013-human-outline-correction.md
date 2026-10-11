# ADR 0013: Human outline correction

- Status: Accepted
- Date: 2026-10-11

## Context

A scholar tracing a visible edge may be recording what they see, or revising the detector's reading of that edge. [Q-PRD-08](../OPEN_QUESTIONS.md#q-prd-08) asked which class the new row has. [ADR 0003](0003-evidence-classes-and-ranked-hypotheses.md) already places detected outlines in `interpretation`. [ADR 0006](0006-append-only-hypotheses.md) forbids deleting the machine outline. A `FragmentExtent` is observed extent bound to source bytes, and a detector polygon is not that row.

## Decision

A human correction of a machine outline is a new `FragmentOutlineRevision`.

- `epistemic_class` is `interpretation`. `producer` is `human`. `run_id` is null. `operator_id` and `session_id` are set. There is no machine envelope.
- `supersedes_id` cites the machine revision. That revision stays. Source bytes stay.
- The correction is not a `FragmentExtent`. Acceptance does not re-type the machine outline.
- The row is not benchmark ground truth. [Q-SCI-17](../OPEN_QUESTIONS.md#q-sci-17) stays open.

## Consequences

- [Q-PRD-08](../OPEN_QUESTIONS.md#q-prd-08) is closed.
- [P2-06](../../tasks/P2-06.md) may store that in-memory row. It stores no `FragmentExtent` for the correction.
- An accuracy claim against human outlines remains blocked by [Q-SCI-17](../OPEN_QUESTIONS.md#q-sci-17).

## Related

- [ADR 0003](0003-evidence-classes-and-ranked-hypotheses.md)
- [ADR 0006](0006-append-only-hypotheses.md)
- [DATA_MODEL.md](../DATA_MODEL.md#fragmentoutlinerevision)
- [Q-SCI-17](../OPEN_QUESTIONS.md#q-sci-17)
