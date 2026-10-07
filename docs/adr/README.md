# Architecture decision records

ADRs record decisions for the Parchment Reconstruction Workbench. The glossary is in [DATA_MODEL.md](../DATA_MODEL.md#glossary). Open questions stay in [OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md).

## Status

- **Accepted.** The decision is in force. It restates a constraint already required by [AGENTS.md](../../AGENTS.md) or [`.gitignore`](../../.gitignore).
- **Proposed.** A direction is recommended. The recommendation is not implementation approval, and the question IDs it names stay open.
- **Superseded.** A later ADR replaces this one. P0 has no superseded records.

## Template

```markdown
# ADR NNNN: Title

- Status: Accepted | Proposed | Superseded
- Date: YYYY-MM-DD

## Context

## Decision

## Consequences

## Related
```

Proposed records include options. Their Decision section states the recommendation and states that the recommendation is not accepted.

Agent rules that are not given their own ADR remain in force from [AGENTS.md](../../AGENTS.md): document every runtime dependency with its reason and license; migrate stored schemas and test the migration; compare benchmarks when an algorithm changes; stop and ask before changing public APIs, project format, privacy policy, or evidence semantics.

## Index

| ADR | Title | Status |
| --- | --- | --- |
| [0001](0001-local-only-processing.md) | Local-only processing | Accepted |
| [0002](0002-three-coordinate-frames.md) | Three coordinate frames | Accepted |
| [0003](0003-evidence-classes-and-ranked-hypotheses.md) | Evidence classes and ranked hypotheses | Accepted |
| [0004](0004-immutable-sources-and-provenance.md) | Immutable sources and provenance | Accepted |
| [0005](0005-qt-shell-and-headless-core.md) | Qt shell and headless core | Accepted |
| [0006](0006-append-only-hypotheses.md) | Append-only hypotheses | Accepted |
| [0007](0007-project-persistence.md) | Project persistence | Proposed |
| [0008](0008-rigid-rectangular-page.md) | Rigid rectangular page | Proposed |
| [0009](0009-separate-score-channels.md) | Separate score channels | Proposed |
| [0010](0010-local-greek-htr-runtime.md) | Local Greek HTR runtime | Proposed, blocked |
| [0011](0011-frame-conventions.md) | Frame conventions | Accepted |
| [0012](0012-export-types.md) | Export types | Accepted |
