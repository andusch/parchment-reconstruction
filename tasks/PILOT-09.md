# Task ticket

- Status: Blocked
- Phase: Pilot, after the review window

A **yes** on any stop-and-ask field means the ticket waits until an ADR and an explicit decision exist. Open questions are indexed in [OPEN_QUESTIONS.md](../docs/OPEN_QUESTIONS.md). The glossary is in [DATA_MODEL.md](../docs/DATA_MODEL.md#glossary).

## Title

Retry ranking on Cleveland Museum of Art Open Access 1999.137.1–3 after mount-aware segmentation and a labeled claimed-ppi scale.

## Phase

Pilot. [PILOT-04](PILOT-04.md) recorded one Cleveland leaf. [PILOT-06](PILOT-06.md) recorded a synthetic pool with join hypotheses. This ticket does not close P7.

## Problem

`prw segment` at `--foreground-threshold 1` treats a non-zero black mount as foreground. On a mounted cutting that mask encloses exact-zero samples, and the run is `FailedSegmentation` kind `hole`. `prw rank` also has no labeled way to pass a header ppi. The header value is `claimed_resolution_ppi`. It is not a calibrated scale.

## User or scientific outcome

The three CC0 cuttings were checksummed and passed to `segment` and `rank`. Each segmentation is `FailedSegmentation` kind `hole`. The pool command prints no joins. The catalogue groups the cuttings. It does not say they are torn mates, and this ticket does not say that either. The recorded run is [pilot-cma-1999-137.md](../docs/pilot-cma-1999-137.md).

## Epistemic-class impact

no. No outline was stored. No join was stored. A hole failure is a failed run. It is not a hypothesis and it is not a historical finding.

## Stop and ask

- Changes a public API: no. No flag was added.
- Changes the project format: no
- Changes the privacy policy ([SECURITY_AND_PRIVACY.md](../docs/SECURITY_AND_PRIVACY.md)): no
- Changes evidence semantics (text status, epistemic class, or the meaning of a hypothesis): no

## Schema impact

none.

## Algorithm and benchmark impact

none shipped. `fragment_outline` stays version `1`. The hole check and the ranker were not changed. No `BenchmarkLabel` row was added or edited. The leaf files are not under `benchmarks/`.

An operator count, outside `prw`, removed border-connected samples at or below ceilings 32, 48, 64, 80, and 96 and still found more than one component and still found enclosed zeros. That count is in the pilot note. It was not committed as an algorithm, because it does not yield one outline and the next step would be a hole-check or component-check relaxation.

## New dependencies

none.

## Acceptance criteria

- [x] The 13 November 2026 terms pages and the object records still show CC0 for 1999.137 and for 1999.137.1–3. The three component TIFFs are outside Git. The pilot note records the URLs, the access date, the license, and the sha256 of the unchanged bytes.
- [x] `prw verify` succeeds on each file. `prw segment` at `--foreground-threshold 1` exits 1 with `FailedSegmentation` kind `hole` on each file. `prw rank` on the three files exits 1 with that same record and does not print `joins`.
- [ ] Mount-aware segmentation that returns one outline on these files, with the synthetic threshold-1 path unchanged. Not shipped. The mount is not the whole of the enclosed zeros, and the hole check was not relaxed.
- [ ] A labeled claimed-ppi scale whose provenance says the scale is claimed resolution. Not shipped. There is no outline to scale, and 400 ppi was not passed through `--pixels-per-mm`.
- [ ] A non-empty `physical_join_order`. Not produced.
- [ ] A `prw-review` smoke of that list. Not run.
- [x] The diff contains no image bytes. 1951.314 was not cut. The group TIFF was not downloaded.

## Tests

No new product test. The run is an operator transcript on files the repository does not contain. Existing synthetic tests stay the in-repo check. No read of `data/`, `scans/`, or `real_data/`.

## Provenance effects

`verify` printed `VerifiedBytes`. `segment` and `rank` printed a failed segmentation and no envelope of a completed outline or a completed join. `random_seed` was not involved. The 400 ppi header claim is in the sidecar and in the pilot note. It is not a calibration observation.

## Non-goals

- Loosening the hole check, the multiple-component check, or the ranker so the list is non-empty.
- Treating 400 ppi, or the catalogue size "Each leaf: 17.6 x 9 cm", as a calibrated scale.
- Cutting 1951.314 or any other whole leaf.
- Stating that the three cuttings are mates, or that a failed segmentation is a reconstruction.
- HTR, a project store, and the rest of P7.
- A new review-window feature.

## Open questions this depends on

[Q-SCI-10](../docs/OPEN_QUESTIONS.md#q-sci-10), [Q-SCI-15](../docs/OPEN_QUESTIONS.md#q-sci-15), and [Q-ENG-01](../docs/OPEN_QUESTIONS.md#q-eng-01) stay open. [Q-ENG-05](../docs/OPEN_QUESTIONS.md#q-eng-05) stays closed.
