# ADR 0009: Separate score channels

- Status: Proposed
- Date: 2026-10-07

## Context

Physical fit, HTR, and language evidence can disagree. A single unlabeled score hides which one carried the rank. [Q-SCI-09](../ALGORITHM.md#q-sci-09) asks whether a default sort may fuse the channels, and under which policy.

## Options

1. Store `physical`, `htr`, and `language` separately. Each score carries `score_context` (`run_id`, channel, hypothesis type). Rank is inside one `(run, hypothesis_type, channel)`. A run never ranks mixed types in one order. The scholar can sort by another channel inside one type. No fused value is stored. Scores are incomparable across runs, algorithms, and types. The UI never displays a cross-type total order.
2. Store the three channels and also a declared weighted sum in the parameter blob.
3. Learn a fusion after a separate study, and version that fusion as its own algorithm.

## Decision

Not accepted. The recommendation is option 1 until Q-SCI-09 is closed. Language scoring may annotate only hypotheses the physical search already admitted. It does not create joins. This recommendation is not a fusion policy and does not close Q-SCI-09.

## Consequences

- Presentation fails closed when the run has no declared sort channel, rather than inventing a fused key.
- A later acceptance of option 2 or 3 is an algorithm change and needs a benchmark comparison on the frozen fixture.
- Supplied text stays out of the `language` channel unless [Q-SCI-05](../ALGORITHM.md#q-sci-05) is accepted.
- Scores remain uncalibrated ranking features. They are not stored as probabilities.

## Related

- [Q-SCI-09](../OPEN_QUESTIONS.md#q-sci-09)
- [Q-SCI-05](../OPEN_QUESTIONS.md#q-sci-05)
- [DATA_MODEL.md](../DATA_MODEL.md#score-channels)
