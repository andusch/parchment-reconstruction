# Task ticket

- Status: Template
- Phase: P0

Copy this file for one implementation ticket. A **yes** on any stop-and-ask field means the ticket waits until an ADR and an explicit decision exist. Open questions are indexed in [OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md). The glossary is in [DATA_MODEL.md](../DATA_MODEL.md#glossary).

## Title

<!-- One sentence. -->

## Phase

<!-- P1 through P8, from ROADMAP.md. -->

## Problem

<!-- What is wrong or missing. -->

## User or scientific outcome

<!-- What a scholar, imaging operator, or benchmark operator can do when this is done. -->

## Epistemic-class impact

<!-- Does this change epistemic class, producer, or scholarly restoration? yes / no. Details: -->

## Stop and ask

Answer each line `yes` or `no`. Any `yes` blocks implementation until a decision exists.

- Changes a public API:
- Changes the project format:
- Changes the privacy policy ([SECURITY_AND_PRIVACY.md](../SECURITY_AND_PRIVACY.md)):
- Changes evidence semantics (text status, epistemic class, or the meaning of a hypothesis):

## Schema impact

<!-- none, or the schema versions and the migration. A stored schema change needs a migration and migration tests. -->

## Algorithm and benchmark impact

<!-- none, or which stage in ALGORITHM.md changes. An algorithm change needs a local comparison against the previous BenchmarkLabel record. Do not edit those labels to pass. -->

## New dependencies

<!-- none, or name, reason, and license for each runtime dependency. Network download requires explicit approval. -->

## Acceptance criteria

- [ ]

## Tests

<!-- Synthetic fixtures only. Do not read data/, scans/, real_data/, TIFF sources, or model weights. -->

## Provenance effects

<!-- Which envelope fields this writes: source hashes, parameter hash, algorithm version, model hash, random seed, code version. -->

## Non-goals

-

## Open questions this depends on

<!-- IDs from OPEN_QUESTIONS.md. If an ID must be closed first, say so. -->
