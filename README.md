# Parchment Reconstruction Workbench

Local-first desktop application that ranks physical and textual reconstruction hypotheses for fragmented parchment. A scholar reviews every hypothesis. Algorithmic output remains a hypothesis about the page and the text.

The Python package is `prw` (`src/prw`), distributed as `parchment-workbench`. It has no runtime dependencies. Internal helpers emit canonical JSON, `sha256:` digests, and content-derived UUIDv5 identifiers. Those helpers are not a stable public API. Checks:

```text
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -m "not slow"
```

Processing stays on the local machine. Original source images are immutable and checksum-verified. Real scans never enter Git. See [Security and privacy](docs/SECURITY_AND_PRIVACY.md) and [AGENTS.md](AGENTS.md).

Terms used across these documents are defined once, in the [data model glossary](docs/DATA_MODEL.md#glossary).

## Reading order

1. [Product requirements](docs/PRD.md)
2. [Scan protocol](docs/SCAN_PROTOCOL.md)
3. [Architecture](docs/ARCHITECTURE.md)
4. [Data model](docs/DATA_MODEL.md)
5. [Algorithms](docs/ALGORITHM.md)
6. [Evaluation](docs/EVALUATION.md)
7. [Security and privacy](docs/SECURITY_AND_PRIVACY.md)
8. [Risk register](docs/RISK_REGISTER.md)
9. [Roadmap](docs/ROADMAP.md)
10. [Open questions](docs/OPEN_QUESTIONS.md)
11. [Architecture decision records](docs/adr/README.md)

Implementation constraints live in [AGENTS.md](AGENTS.md). Later implementation work uses the [task-ticket template](docs/templates/task-ticket.md).
