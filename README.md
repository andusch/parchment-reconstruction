# Parchment Reconstruction Workbench

Local-first desktop application that ranks physical and textual reconstruction hypotheses for fragmented parchment. A scholar reviews every hypothesis. Algorithmic output remains a hypothesis about the page and the text.

The Python package is `prw` (`src/prw`), distributed as `parchment-workbench`. The headless console has no third-party requirement in `project.dependencies`. The review window uses PySide6-Essentials from the `ui` group ([ADR-0015](docs/adr/0015-thin-review-window.md)). Internal helpers emit canonical JSON, `sha256:` digests, and content-derived UUIDv5 identifiers. In-memory provenance envelopes and an append-only status stream record parameters and negative knowledge. In-memory coordinate frames name kind, origin, and axes. Ingest hashes caller-supplied bytes, accepts classic TIFF magic, and records a checksum mismatch as an integrity failure. Pixel commands read other classic lossless TIFF masters with the standard library ([ADR-0014](docs/adr/0014-stdlib-lossless-tiff.md)). A seeded generator writes synthetic fragment geometry, and its ground truth, only under `benchmarks/`. It also writes uncompressed fixture TIFFs and a SHA-256 image manifest beside that store. Those types are not a stable public API. Checks:

```text
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -m "not slow"
```

## Headless CLI

`python -m prw.cli` calls ingest (`prw.ingest`), coordinate frames (`prw.frames`), provenance envelopes (`prw.provenance`), the synthetic fixture generator (`prw.synthetic_tear`), segmentation (`prw.segment`), caller-supplied scale (`prw.scale`), outline agreement (`prw.outline_agreement`), chord edges (`prw.edge_chord`), pairwise joins (`prw.pairwise_join`, ordered by `prw.join_rank`), join recall (`prw.join_recall`), assembly search (`prw.assembly_search`), assembly rank (`prw.assembly_rank`), placement error (`prw.placement_error`), and end-to-end join presence (`prw.assembly_join_presence`). It does not import Qt. `prw-review` opens the review window on the same join-ranking use cases. Command names and flags are unfrozen and are not a stable interface. The project format is still [Q-ENG-01](docs/OPEN_QUESTIONS.md#q-eng-01).

Processing stays on the local machine. Original source images are immutable and checksum-verified. Real scans never enter Git. See [Security and privacy](docs/SECURITY_AND_PRIVACY.md) and [AGENTS.md](AGENTS.md). A partial license review for three public sources, stored outside this checkout, is [Public-corpus pilot](docs/pilot-public-corpus.md). The directory, checksum, and scale note for one of those files are [Public import path](docs/pilot-import-path.md).

Terms used across these documents are defined once, in the [data model glossary](docs/DATA_MODEL.md#glossary).

## Using the current build

The commands you can run today are the headless `prw` console and the review window `prw-review`. [Using the workbench](docs/USAGE.md) walks them on a synthetic leaf: checksums, outlines, ranked joins, and assembly reports. Command names and flags are unfrozen. The window lists those joins as hypotheses.

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

The numbered list is the P0 reading order. [Public-corpus pilot](docs/pilot-public-corpus.md) sits beside it as a partial answer to [Q-SCI-15](docs/OPEN_QUESTIONS.md#q-sci-15). [Public import path](docs/pilot-import-path.md) is the operator procedure for one file from that set.

Implementation constraints live in [AGENTS.md](AGENTS.md). Later implementation work uses the [task-ticket template](docs/templates/task-ticket.md).
