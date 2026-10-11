# ADR 0003: Evidence classes and ranked hypotheses

- Status: Accepted
- Date: 2026-10-07

## Context

A reconstruction tool can blur what the parchment shows, what a model proposed, and what a scholar supplied. The agent rules forbid labeling an algorithmic result as truth. Rulings R1–R3 and R18 in [R0-01](../reviewed_resolutions/R0-01.md) amend the class names and the grapheme statuses below.

## Decision

Every claim is one of three epistemic classes: `observed`, `interpretation`, or `hypothesis`. `observed` is pixels, calibration, and fragment extent, and is never a reading or a placement. `interpretation` is OCR readings, human letter readings, detected outlines, and detected lines. `hypothesis` is joins, assemblies, placements, and restorations. Algorithms return ranked hypotheses inside one type and one channel. They do not label a join, an assembly, or a reading as the original. Grapheme text status `human_read` is a human letter reading. It is not the epistemic class `observed`.

A reading stores `producer` as `human`, `machine`, or `imported`. The stored grapheme text statuses are `human_read`, `unclear`, and `ocr_inferred`, each in class `interpretation`. `missing` is not a grapheme status. Supplied text lives only on a scholarly restoration, in class `hypothesis`, and is not an algorithm-run output. The name `human_validated` is a validation decision that points at a claim. Acceptance does not re-type the claim. The stored name for HTR output remains `ocr_inferred`.

## Consequences

- User-facing text presents rank, text status, and epistemic class.
- No field is named `truth`, `correct_join`, `original_text`, or unlabeled `confidence`.
- A gap is a `GapRegion` on a page hypothesis. What that region denotes remains [Q-SCI-13](../DATA_MODEL.md#q-sci-13).
- Renaming `ocr_inferred` is an evidence-semantics change and requires stop-and-ask.

## Related

- [DATA_MODEL.md](../DATA_MODEL.md#glossary)
- [Q-SCI-13](../OPEN_QUESTIONS.md#q-sci-13)
- [Q-PRD-08](../OPEN_QUESTIONS.md#q-prd-08), closed by [ADR 0013](0013-human-outline-correction.md)
- [Q-PRD-09](../OPEN_QUESTIONS.md#q-prd-09)
