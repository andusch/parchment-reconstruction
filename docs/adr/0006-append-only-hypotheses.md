# ADR 0006: Append-only hypotheses

- Status: Accepted
- Date: 2026-10-07

## Context

A scholar will correct outlines, reject joins, and prefer one assembly. If those actions overwrite the machine record, the earlier hypothesis and its provenance disappear. Ranked alternatives are required by [ADR 0003](0003-evidence-classes-and-ranked-hypotheses.md).

## Options

1. Append-only rows. A revision is a new content-derived id with `supersedes_id`. Validation decisions are also append-only, and their ids are random UUIDs. Competitors stay. A human rejection does not rewrite a stored join status.
2. Mutable hypothesis rows. An edit replaces the polygon or the pose in place and keeps a separate log.
3. Snapshot files. Each save writes a full copy of the project state.

## Decision

Hypothesis content rows are immutable. A revision is a new row with a new content-derived id and a `supersedes_id` link. Status is an append-only `StatusEvent` stream. The current status of a hypothesis is derived from the latest event for that id. Inserting a hypothesis appends the first event in the same write, so a live row has a current status. A validation decision appends an event. It does not rewrite the hypothesis row. Rank is not a column on the hypothesis row. A reader derives it from the score and the content-derived id. A row is omitted when it has no score in that channel, when its run is not `completed`, or when its latest status is `invalidated`. A row with no run is not omitted for lack of a run.

## Consequences

- Human correction does not delete the machine outline. The class of that new row is [ADR 0013](0013-human-outline-correction.md), which closes [Q-PRD-08](../OPEN_QUESTIONS.md#q-prd-08).
- An in-place change to `rejected` or `contested` is forbidden. Those words are statuses on the event stream.
- P1 stores hypotheses only with this split between immutable content and the status stream.
- P0 stores nothing.

## Related

- [Q-PRD-08](../OPEN_QUESTIONS.md#q-prd-08), closed by [ADR 0013](0013-human-outline-correction.md)
- [Q-PRD-09](../OPEN_QUESTIONS.md#q-prd-09)
- [Q-ENG-01](../OPEN_QUESTIONS.md#q-eng-01)
