# Product requirements

- Status: Draft for review
- Phase: P0 (documentation only)
- Glossary: [DATA_MODEL.md](DATA_MODEL.md#glossary)
- Open-question index: [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md)

P0 specifies the product. It does not implement the functional requirements below.

## Problem

Fragmented parchment preserves disconnected pieces of an approximately rectangular writing support and of the text written on it. A scholar needs ranked physical and textual hypotheses, with observed measurements, interpretations, and editorial restoration kept distinct. The workbench exists to present those hypotheses for human validation.

## Users

Three operator roles appear in the workflow. Whether v1 separates them is [Q-PRD-01](#q-prd-01).

- **Scholar.** Compares joins, assemblies, and readings, and records validation decisions. May also author scholarly restoration.
- **Imaging operator.** Captures fragments under the [scan protocol](SCAN_PROTOCOL.md) and imports the files.
- **Benchmark operator.** Runs the headless pipeline on synthetic fixtures and publishes a comparison against the previous benchmark record. See [EVALUATION.md](EVALUATION.md).

## Jobs

- Import local scans and confirm that each source file still matches its recorded checksum.
- Inspect ranked join, assembly, and reading hypotheses, one type and one score channel at a time. Fragments are listed by identification status, not by rank.
- Record accept, reject, or defer on a hypothesis while every alternative remains available.
- Author scholarly restoration that cites the hypotheses it prefers.
- Export an auditable bundle that preserves epistemic class, text status, hashes, and hypothesis labels.

## In-scope workflow

Each step names the epistemic class of what it produces. Classes are defined in the [glossary](DATA_MODEL.md#glossary).

1. **Import.** The operator selects a local folder of lossless TIFF files. Ingest copies the bytes into `originals/` and records the checksum. Those copied bytes are the authoritative source. The pixels and the checksum are observed evidence.
2. **Checksum verification.** A mismatch is an `IntegrityFailure`. It stops use of that file as evidence and does not enter the evidence pool.
3. **Fragment detection.** An outline revision is `interpretation` with `producer: machine`. A later human correction is a new `FragmentOutlineRevision` in class `interpretation` with `producer: human` ([ADR-0013](adr/0013-human-outline-correction.md)).
4. **Text detection.** A `TextLineHypothesis` is `interpretation`: a baseline polyline and a region in `fragment_local_mm`. Order is a separate `TextLineOrder`, a ranked list of alternative sequences. A line has no single order index.
5. **Ranked joins.** Each pairwise join candidate is `hypothesis`, with a `physical` score channel. Rank is inside joins only. Matching admits `catalogued` and `confirmed` fragments by default. A machine rejection appends a `StatusEvent` of `rejected` when the candidate is created. The join row is not rewritten. A human rejection is a `ValidationDecision` that appends `rejected-via-ValidationDecision`.
6. **Top-N page assemblies.** Each assembly is `hypothesis` in the one shared project page frame. It records `unplaced_fragment_ids` for fragments in the search that it did not place, and `join_ids` for the joins it contains. Page geometry follows [ADR-0008](adr/0008-rigid-rectangular-page.md), which is proposed.
7. **Ancient Greek HTR.** Readings are `interpretation` with `producer: machine`. Stored text status is `ocr_inferred`. Stored text is Unicode NFC.
8. **Language scoring.** The `language` score channel annotates hypotheses the physical search already admitted. A `ScreeningEvent` records each gate outcome. The score's class is not a new reading.
9. **Human validation.** A validation decision is a decision record. It points at a hypothesis and leaves competitors in place. Accepting an assembly is blocked when any contained join is rejected. Rejecting a join marks every assembly that contains it `contested`.
10. **Scholarly restoration.** Supplied text lives on the restoration, in class `hypothesis`, with no algorithm run. It references gap regions and existing grapheme ids. The editorial convention is Leiden-style markers. The convention name is stored now, and the marker text is filled at export time. Citations name only hypotheses that are not rejected and not contested.
11. **Export.** The bundle is either an audit export or a metadata-only export, as [ADR-0012](adr/0012-export-types.md) defines. It copies the classes, statuses, hashes, and labels above. It does not collapse them into one transcription. It states whether it contains every hypothesis or a top-N cut of one type and one channel.

## Export

Step 11 of the workflow writes one of the two bundles in [ADR-0012](adr/0012-export-types.md).

## Functional requirements

- **FR-1.** Import a local folder and refuse to treat a failed checksum as usable evidence.
- **FR-2.** Show join, assembly, and reading hypotheses as ranked alternatives inside one type and one channel. Do not rank fragments. Do not show a cross-type total order.
- **FR-3.** Record validation decisions without deleting competing hypotheses. Accepting an assembly is blocked when any contained join is rejected. Rejecting a join marks every containing assembly `contested`. A scholarly restoration cites only hypotheses that are not rejected and not contested.
- **FR-4.** Display text status and epistemic class on every reading.
- **FR-5.** Run detection, search, and HTR off the UI thread, and through the same use cases as the CLI.
- **FR-6.** Export either an audit bundle, with master bytes or rendered composites and recomputable hashes, or a metadata-only bundle labeled non-auditable. Both state hypothesis coverage.

## Non-functional requirements

- **NFR-1.** Default operation is local. A network or cloud call requires explicit implementation approval. See [ADR-0001](adr/0001-local-only-processing.md).
- **NFR-2.** Every derived artifact carries the provenance envelope defined in the [data model](DATA_MODEL.md#provenanceenvelope).
- **NFR-3.** Measurements name one of the three coordinate frames. See [ADR-0002](adr/0002-three-coordinate-frames.md).
- **NFR-4.** Core use cases run headlessly. The Qt shell calls those use cases. See [ADR-0005](adr/0005-qt-shell-and-headless-core.md).
- **NFR-5.** A new runtime dependency is documented with its reason and license before it is added.

## Non-goals

The first product does not claim a recovered original, host cloud collaboration, or publish an edition by itself. Non-Greek HTR, rolls, 3D geometry, and multispectral capture are outside the first product. Multispectral capture is [Q-SCI-18](SCAN_PROTOCOL.md#q-sci-18). Rolls and irregular sheets are [Q-SCI-01](ALGORITHM.md#q-sci-01).

P0 delivers none of FR-1 through FR-6 as software.

## Success criteria

P0 succeeds when the documents in the [roadmap](ROADMAP.md#p0) exist, question IDs match across documents, ADR statuses are explicit, and no application tree exists.

The later product succeeds when a scholar can complete the workflow above on local files, every displayed reading shows text status and epistemic class, and an export lets a reviewer recompute the recorded checksums and see the hypothesis labels. Numeric accuracy targets belong to [EVALUATION.md](EVALUATION.md) and stay unmet until the named benchmarks exist.

## Working assumptions

These assumptions keep the documents coherent. Each one stays open until its question is closed.

- A project is a fragment pool plus one or more hypothesized pages. Multi-manuscript collections are outside the first product. Retires with [Q-PRD-02](#q-prd-02).
- Recto and verso are both captured when both faces exist. How they constrain assembly is undecided. Related: [Q-PRD-03](#q-prd-03).
- The first geometric discussion assumes an approximately rectangular leaf and rigid placements. See [ADR-0008](adr/0008-rigid-rectangular-page.md).
- Physical, HTR, and language scores stay on separate channels until a fusion policy is accepted. See [ADR-0009](adr/0009-separate-score-channels.md).

## Open questions

The index restates these entries and does not close them.

### Q-PRD-01

Are scholar, imaging operator, and benchmark operator separate roles in v1, or one operator?

Separate accounts change the validation record and the export rules for operator names. One shared operator is enough for a single-user desktop tool.

- Options: one local operator with a role label on each action; three distinct local profiles; no role field at all.
- Blocks: role-specific UI in P7. P1 can store a single actor string under the labeled assumption of one local operator.

### Q-PRD-02

Is a project one leaf, one manuscript, or a pool with many hypothesized pages?

The choice fixes the manifest, the fragment pool, and what an assembly is allowed to contain.

- Options: one leaf; one manuscript with many leaves; a pool of fragments and many hypothesized pages, which is the working assumption; a multi-manuscript collection.
- Blocks: closing the project-shape decision. P1 may follow the working assumption only while this question stays open and the assumption stays labeled.

### Q-PRD-03

Do recto and verso constrain the first assembly model?

Face identity changes which outlines may meet and which readings may be scored together.

- Options: capture both faces and ignore face in assembly; capture both faces and forbid joins across opposite faces; model a leaf as a front-and-back pair.
- Blocks: face constraints in P4. Capture of both faces can proceed under the scan protocol.

### Q-PRD-04

Are multi-fragment group scans a supported ingest mode?

Group scans change detection, scale confidence, and the acceptance checklist.

- Options: one fragment per frame only; group scans allowed, recorded as `group_scan` on the source image, and not treated as metrologically equivalent; group scans treated as equivalent to one-fragment frames.
- Blocks: P1 ingest rules for group scans. The provisional protocol flags group scans and does not treat them as metrologically equivalent.

### Q-PRD-05

Which export is required for a scholarly handoff?

Closed by [ADR-0012](adr/0012-export-types.md). An audit export carries master bytes or rendered composites and recomputable hashes. A metadata-only export is labeled non-auditable. Both state whether they contain every hypothesis or a top-N cut of one type and one channel. Leiden-style markers are the editorial convention; the marker text is filled at export time.

- Blocks: nothing further for the export type. P8 remains blocked by the privacy questions.

### Q-PRD-06

Is macOS the only first desktop target?

Qt can target more than one operating system. The first tested platform still has to be chosen.

- Options: macOS only; macOS and Linux; macOS, Linux, and Windows.
- Blocks: P7 packaging claims. Documentation in P0 is platform-neutral.

### Q-PRD-07

What fragment count and page count must a project handle?

Search cost and UI density depend on the bound.

- Options: tens of fragments and one page; low hundreds of fragments and a handful of pages; a larger bound stated with a number before P3.
- Blocks: performance targets for P3 and P4. P0 states no capacity number.

### Q-PRD-08

Is a corrected machine outline observed evidence?

Closed by [ADR-0013](adr/0013-human-outline-correction.md). A human correction is a new `FragmentOutlineRevision` in class `interpretation` with `producer: human`. `run_id` is null. `operator_id` and `session_id` are set. There is no machine envelope. `supersedes_id` cites the machine revision, which stays. Source bytes stay. The correction is not a `FragmentExtent`. Acceptance does not re-type the machine outline. The row is not benchmark ground truth.

- Blocks: nothing for the evidence class of the correction. An accuracy claim against human outlines stays blocked by [Q-SCI-17](EVALUATION.md#q-sci-17).

### Q-PRD-09

Is a working reconstruction a named selection, or only a set of validation decisions?

A named selection can be mistaken for the original page if the UI labels it poorly.

- Options: validation decisions only; a named selection that cites hypothesis ids and keeps its epistemic class as scholarly restoration; a mutable canvas that edits placements in place.
- Blocks: the P7 working-set UI, and any project-format field for a preferred reconstruction.

### Q-PRD-10

Are ruling, pricking, and hair/flesh side in the first product?

These physical features can constrain joins. They also widen capture and the data model.

- Options: out of the first product; recorded as optional observations and unused by search; used as additional `physical` features.
- Blocks: feature work in P2 and P3. The first algorithm contract does not require them. Hair/flesh side as a join constraint is also [Q-SCI-19](ALGORITHM.md#q-sci-19).
