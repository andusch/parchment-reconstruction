# Risk register

- Status: Draft for review
- Phase: P0
- Glossary: [DATA_MODEL.md](DATA_MODEL.md#glossary)

Each entry is open. P0 mitigations are documentary. Residual risk stays until a later phase implements and checks the control.

## R-01

- **Class.** Product and integrity
- **What can go wrong.** The UI or an export collapses an HTR reading or a join into "the text" or "the reconstruction".
- **Consequence.** A scholar or a later reader treats a hypothesis as the original.
- **Current mitigation.** [ADR-0003](adr/0003-evidence-classes-and-ranked-hypotheses.md), FR-2 and FR-4 in the [PRD](PRD.md), and forbidden field names in the [data model](DATA_MODEL.md#forbidden-fields).
- **Residual status.** Open until P7 and P8 enforce the labels.

## R-02

- **Class.** Scientific
- **What can go wrong.** Scale error propagates into millimetre placements.
- **Consequence.** Joins and assemblies look precise while the millimetre frame is shifted.
- **Current mitigation.** The [scan protocol](SCAN_PROTOCOL.md) requires scale evidence before millimetre claims. The algorithm contract withholds millimetre poses when calibration is missing. Scale error is a separate metric in [EVALUATION.md](EVALUATION.md).
- **Residual status.** Open. The calibration target and the error bound are [Q-SCI-10](SCAN_PROTOCOL.md#q-sci-10).

## R-03

- **Class.** Scientific
- **What can go wrong.** Fused scores hide a contradiction between geometry and language.
- **Consequence.** A sort key prefers a reading that the edges do not support, or hides a sound join with a weak language score.
- **Current mitigation.** [ADR-0009](adr/0009-separate-score-channels.md) recommends separate `physical`, `htr`, and `language` channels. Fusion waits on [Q-SCI-09](ALGORITHM.md#q-sci-09).
- **Residual status.** Open until that question stays closed in favor of separate channels or an explicit policy.

## R-04

- **Class.** Scientific
- **What can go wrong.** Rigid math is applied to shrunken or cockled parchment.
- **Consequence.** A true contact is rejected, or a wrong contact is forced closed.
- **Current mitigation.** [ADR-0008](adr/0008-rigid-rectangular-page.md) is proposed only. Shrinkage and cockling are [Q-SCI-03](ALGORITHM.md#q-sci-03) and [Q-SCI-20](ALGORITHM.md#q-sci-20).
- **Residual status.** Open.

## R-05

- **Class.** Scientific
- **What can go wrong.** Bleed-through is read as text on the wrong face.
- **Consequence.** `ocr_inferred` graphemes record the opposite face as if it were ink on this face.
- **Current mitigation.** The algorithm contract names bleed-through as a known failure mode. Representation is [Q-SCI-06](DATA_MODEL.md#q-sci-06).
- **Residual status.** Open.

## R-06

- **Class.** Scientific
- **What can go wrong.** Fragments from more than one leaf enter one assembly unnoticed.
- **Consequence.** A high-ranked assembly mixes pieces that never shared a page.
- **Current mitigation.** Assemblies are hypotheses. The failure mode is named in [ALGORITHM.md](ALGORITHM.md#known-failure-modes). Project shape is [Q-PRD-02](PRD.md#q-prd-02).
- **Residual status.** Open. No automatic leaf-identity test is specified.

## R-07

- **Class.** Scientific and integrity
- **What can go wrong.** Supplied letters leak into language scoring.
- **Consequence.** Editorial restoration reinforces itself through the `language` channel.
- **Current mitigation.** The language stage excludes `supplied` text unless [Q-SCI-05](ALGORITHM.md#q-sci-05) is accepted.
- **Residual status.** Open until P6 implements that exclusion and a test locks it.

## R-08

- **Class.** Privacy and engineering
- **What can go wrong.** HTR weights are licensed incompatibly, or the runtime calls the network.
- **Consequence.** Redistribution violates a license, or unpublished context leaves the machine.
- **Current mitigation.** [ADR-0010](adr/0010-local-greek-htr-runtime.md) is blocked. No model and no download are approved. [Q-SCI-14](ALGORITHM.md#q-sci-14) and [Q-ENG-03](ARCHITECTURE.md#q-eng-03) stay open.
- **Residual status.** Open.

## R-09

- **Class.** Privacy
- **What can go wrong.** A real scan is committed or loaded into agent context.
- **Consequence.** Unpublished images enter Git history or a transcript.
- **Current mitigation.** [`.gitignore`](../.gitignore) and the forbidden-path rule in [AGENTS.md](../AGENTS.md).
- **Residual status.** Open. Ignore rules do not stop a forced add or an out-of-band copy.

## R-10

- **Class.** Engineering
- **What can go wrong.** A run draws random numbers and does not record the seed.
- **Consequence.** A ranked list cannot be tied back to source hashes and parameters.
- **Current mitigation.** A deterministic algorithm omits `random_seed` and records that absence in the reproducibility key. An algorithm that uses randomness must store the seed. Calling an unseeded random generator is a defect. [ADR-0004](adr/0004-immutable-sources-and-provenance.md).
- **Residual status.** Open until P1 records the envelope in stored runs.

## R-11

- **Class.** Engineering
- **What can go wrong.** Expensive work blocks the Qt thread.
- **Consequence.** The UI stalls during detection, search, or HTR.
- **Current mitigation.** [ADR-0005](adr/0005-qt-shell-and-headless-core.md) and FR-5. Worker thread versus process is [Q-ENG-06](ARCHITECTURE.md#q-eng-06).
- **Residual status.** Open until P7.

## R-12

- **Class.** Integrity
- **What can go wrong.** A schema or evidence-semantics change lands without a migration and a review.
- **Consequence.** Old projects become unreadable, or a status silently changes meaning.
- **Current mitigation.** Agent rules 12 and 14. A stored project uses `schema_version: 1`. Open questions that would change semantics stay indexed until an ADR closes them.
- **Residual status.** Open as a process risk on every later change.

## R-13

- **Class.** Integrity
- **What can go wrong.** Benchmark ground truth is adjusted to make a change look better.
- **Consequence.** Reported improvement is not comparable to the previous record.
- **Current mitigation.** [EVALUATION.md](EVALUATION.md) freezes `BenchmarkLabel` rows before scoring and requires a local comparison under `benchmarks/` on the same fixture. Those labels stay outside the project evidence database. Agent rule 11 forbids altering them to pass checks.
- **Residual status.** Open until the benchmark harness exists and the freeze is testable.

## R-14

- **Class.** Product and scientific
- **What can go wrong.** Top-N contains near-duplicates, so the scholar never sees a real alternative.
- **Consequence.** The ranked list looks diverse and is not.
- **Current mitigation.** No diversity filter runs until [Q-SCI-08](ALGORITHM.md#q-sci-08) defines distinctness. The risk is named so a later filter is predeclared rather than tuned on results.
- **Residual status.** Open.

## R-15

- **Class.** Integrity
- **What can go wrong.** `human_validated` is mistaken for observed fact.
- **Consequence.** An accepted HTR reading or an accepted join is quoted as what the parchment shows.
- **Current mitigation.** The [data model](DATA_MODEL.md#text-status-and-epistemic-class) keeps validation as a decision and keeps the underlying text status and epistemic class.
- **Residual status.** Open until the UI and export show the decision and the class together.
