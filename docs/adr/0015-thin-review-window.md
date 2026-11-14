# ADR 0015: Thin review window

- Status: Accepted
- Date: 2026-11-09

## Context

[ADR 0005](0005-qt-shell-and-headless-core.md) chooses Qt as the shell and requires expensive work off the UI thread. It does not choose a Python binding, and it leaves worker thread versus worker process as [Q-ENG-06](../OPEN_QUESTIONS.md#q-eng-06). A person still needs to see ranked join hypotheses, not only CLI JSON. Full P7 also waits on roles ([Q-PRD-01](../OPEN_QUESTIONS.md#q-prd-01)), the first desktop target ([Q-PRD-06](../OPEN_QUESTIONS.md#q-prd-06)), a named reconstruction ([Q-PRD-09](../OPEN_QUESTIONS.md#q-prd-09)), a project store ([Q-ENG-01](../OPEN_QUESTIONS.md#q-eng-01)), and a sync-folder warning ([Q-PRI-01](../OPEN_QUESTIONS.md#q-pri-01)).

## Options

1. PySide6-Essentials for a thin window. The import name is PySide6. The binding is LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only. Rank runs on a Qt thread. The session stays in memory. The Essentials build omits Qt WebEngine.
2. PyQt6. Its GPL terms sit beside an MIT workbench only with a separate commercial license.
3. The standard-library Tk shell. No new dependency, and a later replacement by the Qt shell from ADR 0005.
4. Text only. No placement sketch.

## Decision

Option 1. This is the Pilot-05 slice. It does not close the questions above.

- The review window uses PySide6-Essentials. The import name is PySide6. The reason is ADR 0005. The license of the binding is LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only. Shiboken6 is the required transitive package and uses that same license. It is the CPython binding runtime. The workbench stays MIT. Qt is not vendored. WebEngine is not installed.
- PySide6-Essentials is the `ui` dependency group. `uv` installs that group by default so the checks can import the window. `project.dependencies` stays empty. The headless `prw` console does not import PySide6.
- `prw-review` opens the window. The command is unfrozen and is not a stable interface.
- One rank runs on a `QThread` and calls `load_ranked_joins`, which calls the same segment, scale, chord, pairwise-join, and `physical_join_order` use cases as `prw rank`. The UI thread paints and routes input. A second rank waits. Closing the window waits for the current rank. There is no cancellation and no worker process. [Q-ENG-06](../OPEN_QUESTIONS.md#q-eng-06) stays open.
- The actor string is `local-operator`. The window does not ask for a person's name. [Q-PRD-01](../OPEN_QUESTIONS.md#q-prd-01) stays open.
- There is no packaging claim and no chosen desktop target. [Q-PRD-06](../OPEN_QUESTIONS.md#q-prd-06) stays open.
- A decision is `accept`, `reject`, or `defer`. Reject also appends `rejected-via-ValidationDecision`. Accept and defer do not change status. No decision rewrites the join, drops another join, or changes epistemic class. There is no named reconstruction. [Q-PRD-09](../OPEN_QUESTIONS.md#q-prd-09) stays open.
- The session is in memory. The window does not write `manifest.json` or `originals/`. [Q-ENG-01](../OPEN_QUESTIONS.md#q-eng-01) stays open.
- The window does not detect a sync folder. [Q-PRI-01](../OPEN_QUESTIONS.md#q-pri-01) stays open.
- The sketch draws outline polygons in `fragment_local_mm`. It does not draw source pixels. Rank 1 and every other row are labeled hypothesis.

## Consequences

- An operator with the `ui` group can load a synthetic multi-fragment pool and read ranked joins as hypotheses.
- P7 still owes readings, assemblies, HTR, process isolation, roles, a desktop target, a named reconstruction, and the sync-folder warning.
- CI installs the default groups, `dev` and `ui`, including PySide6-Essentials. It does not install the `htr` group.

## Related

- [ADR 0005](0005-qt-shell-and-headless-core.md)
- [ADR 0006](0006-append-only-hypotheses.md)
- [PILOT-05](../../tasks/PILOT-05.md)
