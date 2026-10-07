# ADR 0005: Qt shell and headless core

- Status: Accepted
- Date: 2026-10-07

## Context

Scholars need a desktop review surface. Benchmarks and ingest need the same algorithms without a window. Detection, search, and HTR are too slow to run on a UI thread.

## Decision

Qt is the GUI shell. Core use cases are headless and are callable from the CLI and from the shell. Expensive work does not run on the Qt UI thread. The shell loads hypotheses, epistemic class, and text status. It does not implement a second copy of the algorithms.

## Consequences

- A benchmark can run the CLI on synthetic fixtures with no display.
- The UI thread paints, routes input, and shows progress.
- Worker thread versus worker process is not decided. It remains [Q-ENG-06](../ARCHITECTURE.md#q-eng-06).
- The first desktop operating system remains [Q-PRD-06](../PRD.md#q-prd-06). This ADR chooses the toolkit, not the first tested platform.

## Related

- [ARCHITECTURE.md](../ARCHITECTURE.md#layering)
- [Q-ENG-06](../OPEN_QUESTIONS.md#q-eng-06)
- [Q-PRD-06](../OPEN_QUESTIONS.md#q-prd-06)
