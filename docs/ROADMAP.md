# Roadmap

- Status: Draft for review
- Phase: P2
- Glossary: [DATA_MODEL.md](DATA_MODEL.md#glossary)

Phases are ordered by dependency. This document sets no dates. From P1 onward, a phase that changes a stored schema includes a migration and migration tests. A phase that changes an algorithm includes a benchmark comparison, as defined in [EVALUATION.md](EVALUATION.md).

Closing a question that touches public APIs, project format, privacy policy, or evidence semantics requires an ADR and an explicit decision. See [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

## P0

**Goal.** Publish the documentation set, the ADRs, the ticket template, and the scoped Cursor rules.

**Exit criteria.**

- The reading order in [README.md](../README.md) resolves.
- These documents exist: [PRD.md](PRD.md), [SCAN_PROTOCOL.md](SCAN_PROTOCOL.md), [ARCHITECTURE.md](ARCHITECTURE.md), [DATA_MODEL.md](DATA_MODEL.md), [ALGORITHM.md](ALGORITHM.md), [EVALUATION.md](EVALUATION.md), [SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md), [RISK_REGISTER.md](RISK_REGISTER.md), this roadmap, and [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).
- [docs/adr/](adr/README.md) contains ADR 0001 through ADR 0012 with the Accepted and Proposed statuses in the ADR index.
- [docs/templates/task-ticket.md](templates/task-ticket.md) exists.
- Six scoped rules exist under `.cursor/rules/`.
- Question IDs in the index match the owning documents.
- No application tree exists: no `src/`, no `pyproject.toml`, no tests, and no model weights.

**Non-goals.** Implementing FR-1 through FR-6, or choosing an HTR model.

**Blocked by.** Nothing further inside P0. Questions closed by an accepted ADR stay closed. The remaining questions in the index stay open on exit.

## P1

**Goal.** Add the package, ingest, checksum verification, coordinate frames, the provenance envelope, a synthetic fixture generator, and a CLI.

**Exit criteria.** A local folder of synthetic files can be ingested, hashed, and rejected on checksum mismatch. A frame record names its kind, origin, and axes. A run writes a provenance envelope. The fixture generator emits the manifest required by [EVALUATION.md](EVALUATION.md). The CLI calls these use cases without Qt.

**Non-goals.** Detector quality claims, join ranking, HTR, and a GUI.

**Blocked by.** [Q-ENG-01](ARCHITECTURE.md#q-eng-01) before a project format is accepted. [Q-ENG-05](ARCHITECTURE.md#q-eng-05) before a TIFF library is chosen. Millimetre origin and axes are [ADR-0011](adr/0011-frame-conventions.md). [Q-PRD-02](PRD.md#q-prd-02) may be followed only as a labeled working assumption.

Packaging ([Q-ENG-02](ARCHITECTURE.md#q-eng-02)) is closed by [P1-01](../tasks/P1-01.md).

## P2

**Goal.** Produce fragment outlines and accept human corrections as new records.

**Exit criteria.** An outline revision is stored as epistemic class `interpretation` and producer `machine`, with provenance. A correction, if the product allows one, does not overwrite the machine outline or the source pixels. Synthetic outline agreement can be computed against generator polygons.

**Non-goals.** An accuracy claim against human outlines, and any use of ruling, pricking, or hair/flesh side.

**Blocked by.** [Q-SCI-17](EVALUATION.md#q-sci-17) for any accuracy claim. [Q-PRD-10](PRD.md#q-prd-10) for those extra physical features.

Tickets: [P2-01](../tasks/P2-01.md) outline records, [P2-02](../tasks/P2-02.md) fixture TIFF samples, [P2-03](../tasks/P2-03.md) one-fragment segmentation, [P2-04](../tasks/P2-04.md) caller-supplied scale, [P2-05](../tasks/P2-05.md) synthetic outline agreement, [P2-06](../tasks/P2-06.md) human correction, and [P2-07](../tasks/P2-07.md) headless CLI. Those tickets are Done. [P2-06](../tasks/P2-06.md) is Done under [ADR-0013](adr/0013-human-outline-correction.md).

## P3

**Goal.** Rank pairwise joins on synthetic tears.

**Exit criteria.** A local benchmark record under `benchmarks/` reports join recall at a predeclared K against the frozen `BenchmarkLabel` store, compared with the previous record when one exists.

**Non-goals.** A claim about historical joins on real parchment. A triple-fragment hypothesis type.

**Blocked by.** [Q-SCI-07](ALGORITHM.md#q-sci-07) only if a triple-fragment type is required. Pairwise joins may proceed under the labeled proposal. [Q-SCI-19](ALGORITHM.md#q-sci-19) blocks using hair and flesh side. [Q-PRD-07](PRD.md#q-prd-07) blocks a capacity or performance target.

Tickets: [P3-01](../tasks/P3-01.md) catalogued fragments, [P3-02](../tasks/P3-02.md) join records, [P3-03](../tasks/P3-03.md) chord edges, [P3-04](../tasks/P3-04.md) pairwise proposals, [P3-05](../tasks/P3-05.md) physical rank, [P3-06](../tasks/P3-06.md) outline invalidation, [P3-07](../tasks/P3-07.md) join recall at K, and [P3-08](../tasks/P3-08.md) headless CLI.

## P4

**Goal.** Search top-N page assemblies on the synthetic fixture.

**Exit criteria.** Assemblies are rigid, non-overlapping placements in a hypothesized rectangle. Placement error and end-to-end join presence are reported at predeclared N. No near-duplicate filter runs unless distinctness has been defined.

**Non-goals.** A scientific claim about real parchment beyond the synthetic fixture. Rolls and non-rigid warps.

**Blocked by.** [Q-SCI-02](ALGORITHM.md#q-sci-02), [Q-SCI-03](ALGORITHM.md#q-sci-03), and [Q-SCI-08](ALGORITHM.md#q-sci-08) for any scientific claim beyond the synthetic fixture. [Q-SCI-01](ALGORITHM.md#q-sci-01) and [Q-SCI-20](ALGORITHM.md#q-sci-20) block claims outside the rigid-leaf proposal. [Q-PRD-03](PRD.md#q-prd-03) blocks face constraints.

Tickets: [P4-01](../tasks/P4-01.md) page placements, [P4-02](../tasks/P4-02.md) screening events, [P4-03](../tasks/P4-03.md) assembly rank, [P4-04](../tasks/P4-04.md) rigid search, [P4-05](../tasks/P4-05.md) placement error, [P4-06](../tasks/P4-06.md) end-to-end join presence, and [P4-07](../tasks/P4-07.md) headless CLI.

## P5

**Goal.** Run local Ancient Greek HTR on line images and store `ocr_inferred` graphemes.

**Exit criteria.** The run records the model hash and uses no network call. Graphemes are stored as `ocr_inferred`. A character error rate is reported only when its Unicode policy was frozen before the run.

**Non-goals.** Renaming `ocr_inferred`. Treating model scores as probabilities. A network fetch of weights.

**Blocked by.** [Q-SCI-04](ALGORITHM.md#q-sci-04), [Q-SCI-14](ALGORITHM.md#q-sci-14), and an approved dependency under [Q-ENG-03](ARCHITECTURE.md#q-eng-03). The Greek storage rules are already recorded; the full ADR is this phase. [Q-SCI-16](EVALUATION.md#q-sci-16) blocks a character-error number. [Q-SCI-06](DATA_MODEL.md#q-sci-06) blocks a show-through representation. [Q-SCI-13](DATA_MODEL.md#q-sci-13) blocks emitting lacunae as a finer status.

## P6

**Goal.** Add the `language` score channel on hypotheses the physical search already admitted.

**Exit criteria.** Supplied text is excluded from scoring unless that inclusion has been accepted. Channels remain separate unless a fusion policy has been accepted. Language-score quality is reported with the metric in [EVALUATION.md](EVALUATION.md), not as character error rate. Calibration uncertainty is propagated into `physical` scores. P0 recorded that requirement and did not implement it.

**Non-goals.** Creating joins from language scores. Training on scholarly restoration.

**Blocked by.** [Q-SCI-05](ALGORITHM.md#q-sci-05) and [Q-SCI-09](ALGORITHM.md#q-sci-09).

## P7

**Goal.** Provide the Qt validation UI on the same use cases as the CLI.

**Exit criteria.** Detection, search, and HTR run off the UI thread. Every reading shows text status and epistemic class. Validation does not delete alternatives. Rank 1 is labeled as a hypothesis.

**Non-goals.** Cloud collaboration and automatic publication.

**Blocked by.** [Q-ENG-06](ARCHITECTURE.md#q-eng-06) for the worker mechanism. [Q-PRD-01](PRD.md#q-prd-01), [Q-PRD-06](PRD.md#q-prd-06), and [Q-PRD-09](PRD.md#q-prd-09) for roles, the first desktop target, and a named working reconstruction. [Q-PRI-01](SECURITY_AND_PRIVACY.md#q-pri-01) for a sync-folder warning. The labeling risks [R-01](RISK_REGISTER.md#r-01), [R-11](RISK_REGISTER.md#r-11), and [R-15](RISK_REGISTER.md#r-15) apply.

## P8

**Goal.** Export a scholarly bundle.

**Exit criteria.** The bundle contains hashes, hypothesis labels, epistemic class, and text status. The scholar can see what left the machine. Operator names follow the closed export rule.

**Non-goals.** Publishing an edition. The editorial convention is already Leiden-style markers, with the marker text filled at export time.

**Blocked by.** [Q-PRI-02](SECURITY_AND_PRIVACY.md#q-pri-02). [Q-PRI-03](SECURITY_AND_PRIVACY.md#q-pri-03) blocks access-restriction behavior. [Q-SCI-13](DATA_MODEL.md#q-sci-13) blocks lacuna markup that depends on the finer status. [Q-SCI-15](EVALUATION.md#q-sci-15) still blocks any claim that the export is historically correct. Export types are [ADR-0012](adr/0012-export-types.md).
