# Task ticket

- Status: Done. [PILOT-11](PILOT-11.md) records the later mount treatment and the third retry. This ticket's second retry is unchanged: one outline per file, each polygon follows the image border, and `prw rank` with `--claimed-ppi 400` is `FailedPairwiseJoin`.
- Phase: Pilot, after the review window

A **yes** on any stop-and-ask field means the ticket waits until an ADR and an explicit decision exist. Open questions are indexed in [OPEN_QUESTIONS.md](../docs/OPEN_QUESTIONS.md). The glossary is in [DATA_MODEL.md](../docs/DATA_MODEL.md#glossary).

## Title

Treat interior enclosed background that contains no 4-interior pixel, record a claimed resolution without writing a calibration, and retry Cleveland Museum of Art Open Access 1999.137.1–3.

## Phase

Pilot. [PILOT-09](PILOT-09.md) recorded the blocked retry. Mount exclusion was not sufficient, and it was not shipped. This ticket ships the treatment and the labeled claim, then retries the three files. It does not close P7.

## Problem

`prw segment` at `--foreground-threshold 1` treats a non-zero black mount as foreground. On these mounted cuttings the enclosed background is exact zero, in thousands of components, the largest 10 or 11 pixels, and the run is `FailedSegmentation` kind `hole`. Those components have no pixel whose four edge neighbors are also in the component. `prw rank` had no labeled way to pass a header ppi. The header value is `claimed_resolution_ppi`. It is not a calibrated scale.

## User or scientific outcome

The operator can pass `--enclosed-background-treatment fill_without_4_interior`. The parameter blob names that rule. Enclosed background that contains the 4-connected radius-1 element still fails as `hole`. The default path, with the flag omitted, is unchanged.

The operator can pass `--claimed-ppi`. The printed record says `claimed resolution`, `calibration` is `absent`, and the blob sets `populates_calibration` to false. The command does not read a TIFF header and does not store `pixels_per_mm`.

On 1999.137.1–3 the treatment returns one outline per file. Each outline is an interpretation of the threshold mask, and each polygon follows the image border because the mount is foreground. `prw rank` with `--claimed-ppi 400` exits 1 with `FailedPairwiseJoin` and prints no joins. The catalogue groups the cuttings. It does not say they are torn mates, and this ticket does not say that either. The recorded run is the second retry in [pilot-cma-1999-137.md](../docs/pilot-cma-1999-137.md). [PILOT-11](PILOT-11.md) is the later ticket. It records `--border-mount-treatment not_above_frame_split` and a third retry that stays `FailedSegmentation` kind `multiple_components`.

## Epistemic-class impact

no. A completed outline stays `interpretation` with producer `machine`. The claimed resolution is not a `CalibrationObservation` and is not epistemic class `observed`. No join was stored. A join, had one been emitted, would have stayed a hypothesis.

## Stop and ask

- Changes a public API: no. Command names and flags stay unfrozen. The new flags are the same kind of unfrozen flag as `--pixels-per-mm`.
- Changes the project format: no
- Changes the privacy policy ([SECURITY_AND_PRIVACY.md](../docs/SECURITY_AND_PRIVACY.md)): no
- Changes evidence semantics (text status, epistemic class, or the meaning of a hypothesis): no

## Schema impact

none.

## Algorithm and benchmark impact

`fragment_outline` stays version `1`. The new parameter is recorded only when the treatment is requested. When it is omitted, the parameter blob is still `foreground_threshold` alone, and the synthetic polygons for that path are unchanged. That default path is not an algorithm change of the previous record, so no benchmark comparison was published. No `BenchmarkLabel` row was added or edited. The leaf files are not under `benchmarks/`.

`claimed_resolution_scale` version `1` records the claim. It does not place a millimetre outline. `pairwise_rigid_join` is unchanged: a missing calibration fails the run and emits no pose.

## New dependencies

none.

## Acceptance criteria

- [x] `--enclosed-background-treatment fill_without_4_interior` fills enclosed background that does not contain a 4-interior pixel, records the rule in the parameter blob, and still fails a component that contains that element. A crack of 20 pixels is filled, so the rule is not an area cap of 11. The omitted flag still fails the synthetic one-pixel hole, and its blob is `{"foreground_threshold": 1}`.
- [x] `--claimed-ppi` records `claimed_resolution_scale` with evidence description `claimed resolution` and `populates_calibration` false. The blob has no `pixels_per_mm`. The frame stays `source_pixels`. The flag together with `--pixels-per-mm` exits 2. `rank` with only the claim exits 1, `FailedPairwiseJoin`, and the object has no `joins` key.
- [x] The 13 November 2026 terms pages and the API records still show CC0 for 1999.137 and for 1999.137.1–3. The three component TIFFs stayed outside Git. The pilot note records the URLs, the access date, the license, and the sha256 of the unchanged bytes.
- [x] `prw verify` succeeds on each file. Without the treatment, `1999.137.1` is still `FailedSegmentation` kind `hole`. With the treatment, each file exits 0 with one outline. Each polygon includes `(0, 0)` and the far corner of the image.
- [x] `prw rank` with the treatment and `--claimed-ppi 400` exits 1 with `FailedPairwiseJoin` and does not print `joins`. The claim's calibration field is `absent`.
- [x] A non-empty `physical_join_order` was not required. None was produced.
- [x] `prw-review` was not opened. There is no join list to smoke.
- [x] The diff contains no image bytes. 1951.314 was not cut. The group TIFF was not downloaded. No further relaxation was added after the outlines turned out to be the frames.

## Tests

Synthetic fixtures only. `tests/test_segment.py` covers the fill, the 20-pixel crack, the plus-shaped hole, the unchanged default blob, and a border inlet that stays open. `tests/test_scale.py` covers the claim envelope. `tests/test_cli.py` covers the printed outline, the mutual exclusion with `--pixels-per-mm`, and a rank that records the claim and prints no joins. No read of `data/`, `scans/`, or `real_data/`. The Cleveland files are not fixtures.

## Provenance effects

A treated outline cites `fragment_outline` version `1`, the source hash, the parameter blob naming `foreground_threshold` and `enclosed_background_treatment`, the `sha256:` parameter hash, `model_hash` `absent`, `code_version`, and the decoder name and version. `random_seed` is omitted. The claim cites `claimed_resolution_scale` version `1` and the same class of envelope fields, with `populates_calibration` false. The failed join run is a separate envelope. Its `run_id` includes `attempt_id` and is not a reproducibility key.

## Non-goals

- Loosening the hole check, the multiple-component check, or the ranker so the list is non-empty.
- An area cap chosen so that 1999.137 passes.
- Treating 400 ppi, or the catalogue size "Each leaf: 17.6 x 9 cm", as a calibrated scale.
- Reading tags 282 or 283 into calibration.
- Cutting 1951.314 or any other whole leaf.
- Stating that the three cuttings are mates, or that a frame outline is a torn edge, or that a failed rank is a reconstruction.
- HTR, a project store, and the rest of P7.
- A new review-window feature.

## Open questions this depends on

[Q-SCI-10](../docs/OPEN_QUESTIONS.md#q-sci-10), [Q-SCI-15](../docs/OPEN_QUESTIONS.md#q-sci-15), and [Q-ENG-01](../docs/OPEN_QUESTIONS.md#q-eng-01) stay open. [Q-ENG-05](../docs/OPEN_QUESTIONS.md#q-eng-05) stays closed.
