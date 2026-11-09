# Task ticket

- Status: Done
- Phase: P7 slice

A **yes** on any stop-and-ask field means the ticket waits until an ADR and an explicit decision exist. Open questions are indexed in [OPEN_QUESTIONS.md](../docs/OPEN_QUESTIONS.md). The glossary is in [DATA_MODEL.md](../docs/DATA_MODEL.md#glossary).

## Title

Show ranked join hypotheses in a thin review window.

## Phase

A slice of P7. Full P7 stays open.

## Problem

`prw rank` prints join hypotheses as JSON. A reviewer cannot see the two outlines, the proposed pose, or record a decision without leaving the terminal. Pilot-04's public leaf is one fragment, so its rank list is empty. A window still has to work on a synthetic multi-fragment pool.

## User or scientific outcome

An operator launches the window, loads two or more synthetic fragment images, and sees every ranked join labeled as a hypothesis. Reject, keep, and defer append a decision. The other joins stay on screen. The sketch is a pose in fragment-local millimetres, not a page and not a historical join.

## Epistemic-class impact

no. A join stays `hypothesis`. An outline stays `interpretation`. Accept does not re-type the join.

## Stop and ask

- Changes a public API: no. `prw-review` is unfrozen, as the other commands are. [ADR-0015](../docs/adr/0015-thin-review-window.md) records it.
- Changes the project format: no
- Changes the privacy policy ([SECURITY_AND_PRIVACY.md](../docs/SECURITY_AND_PRIVACY.md)): no. The window does not ask for a person's name.
- Changes evidence semantics (text status, epistemic class, or the meaning of a hypothesis): no

## Schema impact

none. The session is in memory. No `manifest.json` and no migration.

## Algorithm and benchmark impact

none. Rank is `physical_join_order`. The window does not read `benchmarks/`.

## New dependencies

PySide6-Essentials, imported as PySide6, LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only, in the `ui` dependency group. Reason: [ADR-0005](../docs/adr/0005-qt-shell-and-headless-core.md) already chose Qt, and [ADR-0015](../docs/adr/0015-thin-review-window.md) chooses this binding. Essentials omits Qt WebEngine. The headless console does not import it. Installing the group downloads the binding. That download is the operator's package install, not a call from a rank or a review session.

## Acceptance criteria

- [x] The window loads a synthetic multi-fragment pool through the existing segment, scale, chord, and pairwise-join use cases, then shows `physical_join_order`.
- [x] Rank 1 and every other row are labeled hypothesis. The banner says rank is not a historical join.
- [x] Reject appends `rejected-via-ValidationDecision` and leaves every join id in the list. Accept and defer do not change epistemic class or status, and they do not drop a row.
- [x] The placement sketch uses `fragment_local_mm` and does not draw source pixels.
- [x] Rank runs on a Qt thread. One rank at a time. No cancellation. [Q-ENG-06](../docs/OPEN_QUESTIONS.md#q-eng-06) stays open.
- [x] A BenchmarkLabel join file is refused and is not passed to the proposer.

## Tests

`tests/test_review.py` checks the lines, the decision log, the sketch, the label-file refusal, and that the join ids match `prw rank`. `tests/test_review_window.py` drives the window on the offscreen Qt platform in a child process. The parent process does not import Qt, so the headless CLI import check still sees a process that has not loaded PySide6.

## Provenance effects

none beyond the envelopes the existing use cases already write. The window does not invent a second envelope. `random_seed` stays omitted. The actor on a decision is the token `local-operator`.

## Non-goals

HTR, language scores, cloud sync, scholarly export, a project store, roles, a named reconstruction, assembly review, reading review, and a worker process.

## Open questions this depends on

[Q-ENG-06](../docs/OPEN_QUESTIONS.md#q-eng-06), [Q-PRD-01](../docs/OPEN_QUESTIONS.md#q-prd-01), [Q-PRD-06](../docs/OPEN_QUESTIONS.md#q-prd-06), [Q-PRD-09](../docs/OPEN_QUESTIONS.md#q-prd-09), [Q-ENG-01](../docs/OPEN_QUESTIONS.md#q-eng-01), and [Q-PRI-01](../docs/OPEN_QUESTIONS.md#q-pri-01) stay open. The assumptions used here are in [ADR-0015](../docs/adr/0015-thin-review-window.md).
