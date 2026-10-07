# ADR 0012: Export types

- Status: Accepted
- Date: 2026-10-07

## Context

A scholarly handoff can be audited only when the bundle says what bytes it contains and which hypotheses it kept. [Q-PRD-05](../OPEN_QUESTIONS.md#q-prd-05) asked which export is required. Ruling R24 in [R0-01](../reviewed_resolutions/R0-01.md) decides the types. The editorial convention for supplied text is already Leiden-style markers, with the marker text filled at export time.

## Decision

Two export types exist.

- **Audit.** The bundle includes the master bytes or rendered composites, plus hashes. A reviewer can recompute the checksums. The bundle states whether it contains every hypothesis or a top-N cut, and it names the type and channel of that cut.
- **Metadata-only.** The bundle is explicitly labeled non-auditable. It states the same hypothesis coverage: all hypotheses, or top-N for a named type and channel.

Neither type collapses epistemic class, text status, or hypothesis labels into one transcription.

## Consequences

- Q-PRD-05 is closed.
- P8 still depends on the privacy questions for operator names and access restrictions.
- A metadata-only bundle is not evidence that the bytes were checked.

## Related

- [PRD.md](../PRD.md#export)
- [DATA_MODEL.md](../DATA_MODEL.md#scholarlyrestoration)
- [Q-PRI-02](../SECURITY_AND_PRIVACY.md#q-pri-02)
