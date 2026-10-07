# ADR 0007: Project persistence

- Status: Proposed
- Date: 2026-10-07

## Context

Ingest, hypotheses, decisions, and exports have to live in a project directory the operator controls. The directory layout is the project format. [Q-ENG-01](../ARCHITECTURE.md#q-eng-01) is open. A stored project writes `schema_version: 1` in `manifest.json`. After ingest, the `originals/` copy is the authoritative byte source.

## Options

1. A directory of content-addressed files plus JSON records.
2. A single SQLite database, with original images stored as files beside it.
3. SQLite for records and content-addressed files for originals. The architecture sketches this layout: `manifest.json`, `originals/`, `observations/`, `runs/`, `validations/`, and `exports/`.

Paths must not encode a join, a page, or a reading. Scientific conclusions belong in records.

## Decision

Not accepted. The recommendation is option 3, because originals stay immutable and content-addressed while records stay queryable. The sketch in [ARCHITECTURE.md](../ARCHITECTURE.md#project-directory) is that recommendation. It is not an accepted project format.

## Consequences

- P1 implements a store only after Q-ENG-01 is closed, or keeps the store behind a decision that answers it.
- The stored schema is version `1`. The first change away from that description ships with a migration and migration tests.
- Changing the layout later is a project-format change and requires stop-and-ask.

## Related

- [Q-ENG-01](../OPEN_QUESTIONS.md#q-eng-01)
- [Q-ENG-02](../OPEN_QUESTIONS.md#q-eng-02)
- [ADR 0006](0006-append-only-hypotheses.md)
