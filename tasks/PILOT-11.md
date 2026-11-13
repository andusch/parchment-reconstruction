# Task ticket

- Status: Blocked. The treatment is shipped. The 1999.137 retry stores no outline.
- Phase: Pilot, after the review window

A **yes** on any stop-and-ask field means the ticket waits until an ADR and an explicit decision exist. Open questions are indexed in [OPEN_QUESTIONS.md](../docs/OPEN_QUESTIONS.md). The glossary is in [DATA_MODEL.md](../docs/DATA_MODEL.md#glossary).

## Title

Treat the non-zero mount so an outline can follow the torn cutting rather than the image border, and retry Cleveland Museum of Art Open Access 1999.137.1–3.

## Phase

Pilot. [PILOT-10](PILOT-10.md) is Done. It records one outline per file, each polygon on the image border, and `FailedPairwiseJoin`. This ticket ships a separate mount rule and retries the three files. It does not close P7.

## Problem

With `--foreground-threshold 1` and `--enclosed-background-treatment fill_without_4_interior`, the mount on these cuttings is foreground. It is darker than the cutting and it is not zero, so each polygon follows the image border and includes `(0, 0)` and the far corner. `prw rank` of those outlines with `--claimed-ppi 400` is `FailedPairwiseJoin` and prints no joins. The catalogue groups the cuttings. It does not say they are torn mates.

## User or scientific outcome

The operator can pass `--border-mount-treatment not_above_frame_split`. Samples that are 4-connected to the one-pixel image frame through values at or below that frame's Otsu split are reclassified as background. The split is the maximum luminance of the darker class. A frame of one luminance uses that value. The parameter blob names `border_mount_treatment`. The default path, with the flag omitted, is unchanged. `--enclosed-background-treatment fill_without_4_interior` stays a separate flag. Passing both names both rules, and the mount reclassification runs first. A component that contains a 4-interior pixel still fails as `hole`. A bright speck that stays disconnected still fails as `multiple_components`.

On 1999.137.1–3 the mount rule, and the same rule composed with the fill, each exit 1 with `FailedSegmentation` kind `multiple_components`. No polygon is stored. `prw rank` with those flags and `--claimed-ppi 400` exits 1 with that same segmentation record and prints no joins. The catalogue groups the cuttings. It does not say they are torn mates, and this ticket does not say that either. The recorded run is the third retry in [pilot-cma-1999-137.md](../docs/pilot-cma-1999-137.md).

## Epistemic-class impact

no. A completed outline stays `interpretation` with producer `machine`. This retry stored no outline. No join was stored. A failed segmentation is a failed run. It is not a hypothesis and it is not a historical finding. The claimed resolution is not a `CalibrationObservation`.

## Stop and ask

- Changes a public API: no. Command names and flags stay unfrozen. The new flag is the same kind of unfrozen flag as `--enclosed-background-treatment`.
- Changes the project format: no
- Changes the privacy policy ([SECURITY_AND_PRIVACY.md](../docs/SECURITY_AND_PRIVACY.md)): no
- Changes evidence semantics (text status, epistemic class, or the meaning of a hypothesis): no

## Schema impact

none.

## Algorithm and benchmark impact

`fragment_outline` stays version `1`. The new parameter is recorded only when the mount rule is requested. When it is omitted, the parameter blob is still `foreground_threshold` alone, or that key plus `enclosed_background_treatment` when only the fill is requested. The synthetic polygons for those paths are unchanged. That default path is not an algorithm change of the previous record, so no benchmark comparison was published. No `BenchmarkLabel` row was added or edited. The leaf files are not under `benchmarks/`.

`pairwise_rigid_join` is unchanged. This retry never reached it. The rank command stopped on `FailedSegmentation`.

## New dependencies

none.

## Acceptance criteria

- [x] `--border-mount-treatment not_above_frame_split` reclassifies the border-connected darker side of the frame's Otsu split, records the rule in the parameter blob, and leaves the omitted-flag path unchanged. On a synthetic dark non-zero frame around a lighter interior, the polygon is the interior. It does not include `(0, 0)` or the far corner. A bright contact with the image edge stays in the polygon. An isolated bright speck in the mount still fails as `multiple_components`.
- [x] Composing that rule with `--enclosed-background-treatment fill_without_4_interior` names both rules. Enclosed exact-zero samples that contain no 4-interior pixel are filled. A plus-shaped hole still fails as `hole`. The fill flag alone still leaves the mount in the foreground. Existing fill, crack, plus-shaped hole, default blob, and claimed-ppi tests pass.
- [x] The 13 November 2026 terms pages and the API records still show CC0 for 1999.137 and for 1999.137.1–3. The three component TIFFs stayed outside Git. The pilot note records the URLs, the access date, the license, and the sha256 of the unchanged bytes.
- [x] `prw verify` succeeds on each file. With the mount rule alone, `1999.137.1` is `FailedSegmentation` kind `multiple_components`. With the mount rule and the fill, each file exits 1 with that same kind. The object has no `polygon` key.
- [ ] One torn-edge outline per file. Not produced. The run fails segmentation, so there is no polygon to place on the cutting or on the frame.
- [x] `prw rank` with both flags and `--claimed-ppi 400` exits 1 with `FailedSegmentation` kind `multiple_components` and does not print `joins`. The claim's calibration field is `absent`. `--pixels-per-mm` was not passed.
- [ ] A non-empty `physical_join_order`. Not produced on this retry.
- [ ] A `prw-review` smoke of that list. Not run. There is no join list.
- [x] The diff contains no image bytes. 1951.314 was not cut. The group TIFF was not downloaded. No further relaxation was added after segmentation failed.

## Tests

Synthetic fixtures only. `tests/test_segment.py` covers the frame-split outline, the composition with the fill, the plus-shaped hole, the bright edge contact, the disconnected speck, and the unchanged default blob. `tests/test_cli.py` covers the printed outline, a rank that still has no joins, and a rejected treatment value. No read of `data/`, `scans/`, or `real_data/`. The Cleveland files are not fixtures.

## Provenance effects

A completed outline cites `fragment_outline` version `1`, the source hash, the parameter blob naming `border_mount_treatment` and, when requested, `enclosed_background_treatment`, the `sha256:` parameter hash, `model_hash` `absent`, `code_version`, and the decoder name and version. `random_seed` is omitted. This retry's CLI failure prints no envelope for the segmentation. The rank failure does print the claim. The claim cites `claimed_resolution_scale` version `1` with `populates_calibration` false. Its source hash is `1999.137.1` only, because the pool stops on the first image. The failed segmentation `run_id` includes `attempt_id` and is not a reproducibility key.

## Non-goals

- A further relaxation after `multiple_components`: no area cutoff, no keep-largest rule, and no change to the hole check or the ranker.
- A caller-chosen mount ceiling selected so that 1999.137 passes.
- Treating 400 ppi, or the catalogue size "Each leaf: 17.6 x 9 cm", as a calibrated scale.
- Reading tags 282 or 283 into calibration.
- Cutting 1951.314 or any other whole leaf.
- Stating that the three cuttings are mates, or that a failed segmentation is a torn edge, or that a failed rank is a reconstruction.
- HTR, a project store, and the rest of P7.
- A new review-window feature.

## Open questions this depends on

[Q-SCI-10](../docs/OPEN_QUESTIONS.md#q-sci-10), [Q-SCI-15](../docs/OPEN_QUESTIONS.md#q-sci-15), and [Q-ENG-01](../docs/OPEN_QUESTIONS.md#q-eng-01) stay open. [Q-ENG-05](../docs/OPEN_QUESTIONS.md#q-eng-05) stays closed.
