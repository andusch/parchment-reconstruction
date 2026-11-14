# ADR 0009: Separate score channels

- Status: Accepted
- Date: 2026-10-07

## Context

Physical fit, HTR, and language evidence can disagree. A single unlabeled score hides which one carried the rank. [Q-SCI-09](../ALGORITHM.md#q-sci-09) asks whether a default sort may fuse the channels, and under which policy.

This record was proposed on 2026-10-07. Andu accepted it on 2026-11-15 (Asia/Hong_Kong), in the Elon · Coding chat, after [P5-04](../../tasks/P5-04.md) (PR #28) merged to master. The acceptance closes [Q-SCI-09](../OPEN_QUESTIONS.md#q-sci-09). It does not implement fusion or the language scorer. [P6-01](../../tasks/P6-01.md) records the close-out.

## Options

1. Store `physical`, `htr`, and `language` separately. Each score carries `score_context` (`run_id`, channel, hypothesis type). Rank is inside one `(run, hypothesis_type, channel)`. A run never ranks mixed types in one order. The scholar can sort by another channel inside one type. No fused value is stored. Scores are incomparable across runs, algorithms, and types. The UI never displays a cross-type total order.
2. Store the three channels and also a declared weighted sum in the parameter blob.
3. Learn a fusion after a separate study, and version that fusion as its own algorithm.

## Decision

Option 2. Store `physical`, `htr`, and `language` as separate channels, and also allow a declared weighted sum in the parameter blob as the default sort. This acceptance does not pick weight values and does not write a fused value. Language scoring may annotate only hypotheses the physical search already admitted. It does not create joins. Channels remain separately stored. Scores remain uncalibrated ranking features, not probabilities.

## Consequences

- Until a later ticket implements the declared sum, no fused value is written. Presentation still fails closed when the run has no declared sort, rather than inventing a key. The scholar can still sort by one channel inside one type.
- Accepting option 2 is an algorithm change and needs a benchmark comparison on the frozen fixture when that fusion is implemented. This close-out does not write the comparison and does not pick weights.
- Supplied text may enter the `language` channel only with an explicit label and a recorded treatment ([Q-SCI-05](../ALGORITHM.md#q-sci-05), closed by [P6-01](../../tasks/P6-01.md)). Training on scholarly restoration stays out of scope.
- Scores remain uncalibrated ranking features. They are not stored as probabilities.

## Related

- [Q-SCI-09](../OPEN_QUESTIONS.md#q-sci-09)
- [Q-SCI-05](../OPEN_QUESTIONS.md#q-sci-05)
- [DATA_MODEL.md](../DATA_MODEL.md#score-channels)
- [P6-01](../../tasks/P6-01.md)
