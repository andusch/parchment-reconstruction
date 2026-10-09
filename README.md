# Parchment Reconstruction Workbench

Local-first desktop application that ranks physical and textual reconstruction hypotheses for fragmented parchment. A scholar reviews every hypothesis. Algorithmic output remains a hypothesis about the page and the text.

The Python package is `prw` (`src/prw`), distributed as `parchment-workbench`. It has no runtime dependencies. Internal helpers emit canonical JSON, `sha256:` digests, and content-derived UUIDv5 identifiers. In-memory provenance envelopes and an append-only status stream record parameters and negative knowledge. In-memory coordinate frames name kind, origin, and axes. Ingest hashes caller-supplied bytes, accepts TIFF magic, and records a checksum mismatch as an integrity failure. A seeded generator writes synthetic fragment geometry, and its ground truth, only under `benchmarks/`. It also writes uncompressed fixture TIFFs and a SHA-256 image manifest beside that store. Those types are not a stable public API. Checks:

```text
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -m "not slow"
```

## Headless CLI

`python -m prw.cli` calls four use cases: ingest (`prw.ingest`), coordinate frames (`prw.frames`), provenance envelopes (`prw.provenance`), and the synthetic fixture generator (`prw.synthetic_tear`). It does not import Qt. Command names and flags are unfrozen and are not a stable interface. The project format is still [Q-ENG-01](docs/OPEN_QUESTIONS.md#q-eng-01).

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
