# Mission

Build a local-first, expert-in-the-loop desktop application that ranks
physical and textual reconstruction hypotheses for fragmented parchment.

# Non-negotiable rules

1. Original source images are immutable and checksum-verified.
2. Keep source pixels, fragment-local millimetres, and page-global
   millimetres as explicit coordinate systems.
3. Epistemic class is exactly one of `observed`, `interpretation`, or
   `hypothesis`. A reading is `interpretation` plus `producer` (`human`,
   `machine`, or `imported`). Acceptance writes a validation decision and
   does not re-type the reading. `missing` is not a grapheme status.
   Supplied text lives only on a scholarly restoration.
4. Return ranked hypotheses; never label an algorithmic result as truth.
5. No network or cloud call without explicit implementation approval.
6. Every derived artifact records source hashes, the full parameter blob
   and its SHA-256, algorithm name and version, model hash, code version,
   and decoder name and version. `random_seed` is recorded when the
   algorithm used randomness and omitted when the algorithm is
   deterministic. Hash-only parameters are not acceptable. Hash fields
   include the `sha256:` algorithm identifier.
7. Expensive work must not run on the Qt UI thread.
8. Core algorithms must be usable headlessly by both CLI and GUI.
9. Do not add a runtime dependency without documenting the reason and license.
10. Do not add placeholders, fake results, silent exception handling, or
    TODO-only implementations.
11. Do not weaken tests or alter benchmark ground truth to pass CI.
12. Every schema change requires a migration and migration tests.
13. Every algorithm change requires a benchmark comparison against the
    previous local record. Benchmark labels live in the BenchmarkLabel
    store under `benchmarks/`, outside the project evidence database.
    That store is the only place a ground-truth label is allowed.
    Solver code paths never read it.
14. Stop and ask before changing public APIs, project format, privacy policy,
    or scientific evidence semantics.

# Package

The scaffold lives at `src/prw` (distribution `parchment-workbench`). The four
checks below are in force. Do not invent results. The document set and the
glossary live under `docs/`. Start with [docs/DATA_MODEL.md](docs/DATA_MODEL.md).

# Stop and ask

If a task needs a change to public APIs, project format, privacy policy, or
evidence semantics, stop and ask. Open questions are indexed in
[docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md). Closing one of those questions
when it touches the surfaces in rule 14 requires an ADR and an explicit decision.

# Forbidden paths

Never read or commit `data/`, `scans/`, `real_data/`, TIFF sources, or model
weights. Tests, when they exist, use synthetic fixtures.

# Required checks

- uv run ruff check .
- uv run ruff format --check .
- uv run mypy src
- uv run pytest -m "not slow"
