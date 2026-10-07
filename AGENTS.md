# Mission

Build a local-first, expert-in-the-loop desktop application that ranks
physical and textual reconstruction hypotheses for fragmented parchment.

# Non-negotiable rules

1. Original source images are immutable and checksum-verified.
2. Keep source pixels, fragment-local millimetres, and page-global
   millimetres as explicit coordinate systems.
3. Distinguish observed, OCR-inferred, unclear, missing, supplied, and
   human-validated text.
4. Return ranked hypotheses; never label an algorithmic result as truth.
5. No network or cloud call without explicit implementation approval.
6. Every derived artifact records source hashes, parameters, algorithm
   version, model hash, and random seed.
7. Expensive work must not run on the Qt UI thread.
8. Core algorithms must be usable headlessly by both CLI and GUI.
9. Do not add a runtime dependency without documenting the reason and license.
10. Do not add placeholders, fake results, silent exception handling, or
    TODO-only implementations.
11. Do not weaken tests or alter benchmark ground truth to pass CI.
12. Every schema change requires a migration and migration tests.
13. Every algorithm change requires a benchmark comparison.
14. Stop and ask before changing public APIs, project format, privacy policy,
    or scientific evidence semantics.

# Required checks

- uv run ruff check .
- uv run ruff format --check .
- uv run mypy src
- uv run pytest -m "not slow"
