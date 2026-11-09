# Task ticket

- Status: Done
- Phase: Pilot, after the P4 CLI

A **yes** on any stop-and-ask field means the ticket waits until an ADR and an explicit decision exist. Open questions are indexed in [OPEN_QUESTIONS.md](../docs/OPEN_QUESTIONS.md). The glossary is in [DATA_MODEL.md](../docs/DATA_MODEL.md#glossary).

## Title

Run verify, segment, and rank on one license-reviewed public TIFF kept outside Git, and record the run.

## Phase

Pilot. The headless commands already exist. [PILOT-03](PILOT-03.md) closed the TIFF-library question.

## Problem

The public-corpus and import-path notes name where a file may live and how to pass it to `prw`. They do not record a real publisher TIFF that has been checksummed, segmented, and ranked.

## User or scientific outcome

An operator can read one worked example: license, object URL, sha256, the commands that ran, and the records those commands printed. The image bytes stay on the machine.

## Epistemic-class impact

no. The note repeats the records the CLI printed. An outline stays `interpretation`. A join stays a hypothesis. The empty join list is not relabeled as a historical finding.

## Stop and ask

- Changes a public API: no
- Changes the project format: no
- Changes the privacy policy ([SECURITY_AND_PRIVACY.md](../docs/SECURITY_AND_PRIVACY.md)): no
- Changes evidence semantics (text status, epistemic class, or the meaning of a hypothesis): no

## Schema impact

none.

## Algorithm and benchmark impact

none. The leaf is not written under `benchmarks/`. No BenchmarkLabel row is added or edited.

## New dependencies

none.

## Acceptance criteria

- [x] One Cleveland Open Access TIFF with `share_license_status` `CC0` is stored outside the checkout and left unchanged.
- [x] `prw verify` succeeds with and without `--expected`. `segment` and `rank` run on that path. `assemble` is recorded with its failure.
- [x] [pilot-first-run.md](../docs/pilot-first-run.md) records the license, the hash, the commands, the decoder name, and that ranked joins are hypotheses.
- [x] The diff contains no image bytes.

## Tests

No new test. The run is an operator transcript on a file the repository does not contain. Existing synthetic tests stay the in-repo check. No read of `data/`, `scans/`, or `real_data/`.

## Provenance effects

The CLI printed the envelopes it already builds. `decoder_name` was `lossless_tiff` and `decoder_version` was `1`. `random_seed` was omitted. This ticket writes no second envelope.

## Non-goals

- Reopening [Q-ENG-05](../docs/OPEN_QUESTIONS.md#q-eng-05).
- Closing [Q-SCI-15](../docs/OPEN_QUESTIONS.md#q-sci-15) or [Q-ENG-01](../docs/OPEN_QUESTIONS.md#q-eng-01).
- HTR, Qt, a project format, and a new TIFF codec.
- Choosing `--foreground-threshold` for a photograph, or turning the 400 ppi header claim into `pixels_per_mm`.
- A find-site, a language, a reading, or an accuracy claim.
- Committing the TIFF or the sidecar.

## Open questions this depends on

[Q-ENG-05](../docs/OPEN_QUESTIONS.md#q-eng-05) stays closed. [Q-SCI-15](../docs/OPEN_QUESTIONS.md#q-sci-15) and [Q-ENG-01](../docs/OPEN_QUESTIONS.md#q-eng-01) stay open.
