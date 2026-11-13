# Cleveland 1999.137 retry

- Status: Working note. The third retry is blocked. Segmentation fails and stores no outline.
- First run: 13 November 2026, checkout `6f64d082be2de162876c4447a1d457bf08165bde` (merge of PR #18). That run is the section [First retry](#first-retry).
- Second run: 13 November 2026, code version `77c4ff9dd48ff2f0e6639437b8a60e774d98e093`. That run is the section [Second retry](#second-retry).
- Third run: 13 November 2026, code version `ce08a426236413031e14eccc5a341b58a27dbafe`. That run is the section [Third retry](#third-retry).
- Glossary: [DATA_MODEL.md](DATA_MODEL.md#glossary)

The three TIFFs stayed outside the clone, under `$HOME/prw-pilot/1999.137/`. On this machine that directory was `/home/ubuntu/prw-pilot/1999.137`. Text sidecars sit beside the files and are not in Git. [`.gitignore`](../.gitignore) ignores `*.tif` and `*.tiff`. The files were never under `data/`, `scans/`, or `real_data/`.

The Cleveland catalogue groups these three cuttings under accession `1999.137`. The object-page text read on this day does not say they are torn mates, and it does not say that an edge of one meets an edge of another. This note does not treat them as mates. It does not treat a join as a reconstruction. No join was emitted.

[1951.314](pilot-first-run.md) was not opened. The group file `1999.137_full.tif` was not downloaded, and no whole leaf was cut to make a pool.

## Third retry

Code version passed to every pixel command: `ce08a426236413031e14eccc5a341b58a27dbafe`. That commit names `--border-mount-treatment not_above_frame_split`. The bytes, the license check, and the header claim are the same records as the [source table](#source-and-license). On this day the terms pages were read again, and the API records for `1999.137` and `1999.137.1`–`1999.137.3` still set `share_license_status` to `CC0`. `sha256sum` of the three files matched the table before the commands and again after them. The files were not edited.

`CODE` below is `ce08a426236413031e14eccc5a341b58a27dbafe`. `LEAF` is `$HOME/prw-pilot/1999.137`.

`prw verify` was run again on each file. Each exited `0`. `record` is `VerifiedBytes`. The ids are the same three ids as the first retry.

The mount rule reclassifies, as background, each sample that is 4-connected to the one-pixel image frame through samples at or below that frame's Otsu split. The split is the maximum luminance of the darker class of the frame. A frame of one luminance uses that value. Samples above the split stop the flood. The rule is not a caller-chosen ceiling. It runs only when the flag is passed. `--enclosed-background-treatment fill_without_4_interior` is a separate flag. When both are passed, the mount reclassification runs first and the parameter blob names both rules. On a failed segmentation the CLI does not print that blob.

One control, with the mount rule and without the fill, on `1999.137.1` only:

```bash
uv run prw segment "$LEAF/1999.137.1_full.tif" \
  --label 1999.137.1 \
  --foreground-threshold 1 \
  --border-mount-treatment not_above_frame_split \
  --code-version "$CODE"
```

Exit `1`. `record` is `FailedSegmentation`. `kind` is `multiple_components`. The object has no `polygon` key. The printed `run_id` includes a random `attempt_id` and is not copied here.

The composition on each file:

```bash
uv run prw segment "$LEAF/1999.137.1_full.tif" \
  --label 1999.137.1 \
  --foreground-threshold 1 \
  --border-mount-treatment not_above_frame_split \
  --enclosed-background-treatment fill_without_4_interior \
  --code-version "$CODE"
uv run prw segment "$LEAF/1999.137.2_full.tif" \
  --label 1999.137.2 \
  --foreground-threshold 1 \
  --border-mount-treatment not_above_frame_split \
  --enclosed-background-treatment fill_without_4_interior \
  --code-version "$CODE"
uv run prw segment "$LEAF/1999.137.3_full.tif" \
  --label 1999.137.3 \
  --foreground-threshold 1 \
  --border-mount-treatment not_above_frame_split \
  --enclosed-background-treatment fill_without_4_interior \
  --code-version "$CODE"
```

Each exited `1`. `record` is `FailedSegmentation`. `kind` is `multiple_components`. The object has no `polygon` key and no `parameter_blob` key. The component check is reported before the hole check, so this record does not say whether an enclosed background remained. No outline was stored. This retry has no polygon to compare with `(0, 0)` or with the far corner of the image. It does not describe a torn edge, and it does not describe a frame outline.

```bash
uv run prw rank \
  --image 1999.137.1 "$LEAF/1999.137.1_full.tif" \
  --image 1999.137.2 "$LEAF/1999.137.2_full.tif" \
  --image 1999.137.3 "$LEAF/1999.137.3_full.tif" \
  --foreground-threshold 1 \
  --border-mount-treatment not_above_frame_split \
  --enclosed-background-treatment fill_without_4_interior \
  --claimed-ppi 400 \
  --code-version "$CODE"
```

Exit `1`. `record` is `FailedSegmentation`. `kind` is `multiple_components`. The object has no `joins` key and no `polygon` key. The pool command stops on the first image. Each file, segmented alone, fails the same way. `claimed_resolution.evidence_description` is `claimed resolution`. `claimed_resolution.claimed_resolution_ppi` is `400.0`. `claimed_resolution.calibration` is `absent`. The claim envelope's algorithm is `claimed_resolution_scale` version `1`. Its parameter blob is `{"claimed_resolution_ppi":400.0,"evidence_description":"claimed resolution","populates_calibration":false}`. `parameter_hash` is `sha256:c99a1b862f72a5654cd0f8bea5f7a4e65e3a336bdd0064a2c83978f34c93b366`. `model_hash` is `absent`. `random_seed` is omitted. The claim id is `ee4cf79b-3a54-5fbf-a3bc-e8458c3a6418`. Its source hash is the digest of `1999.137.1` only, because the pool stops before the other two files. `pixels_per_mm` was not printed. `--pixels-per-mm` was not passed. The catalogue size "Each leaf: 17.6 x 9 cm" was not passed. The TIFF header was not read into the claim. The failed segmentation `run_id` includes a random `attempt_id` and is not copied here.

`prw-review` was not opened. There is no join list to smoke.

No further rule was added after this result. The component check, the hole check, and the ranker were not loosened. No join hypothesis was invented. The catalogue groups these cuttings. This retry does not say they are torn mates.

## Second retry

Code version passed to every pixel command: `77c4ff9dd48ff2f0e6639437b8a60e774d98e093`. The bytes, the license check, and the header claim are the same records as the [source table](#source-and-license). On this day the terms pages were read again, and the API records for `1999.137` and `1999.137.1`–`1999.137.3` still set `share_license_status` to `CC0`. `sha256sum` of the three files matched the table before the commands and again after them. The files were not edited.

`CODE` below is `77c4ff9dd48ff2f0e6639437b8a60e774d98e093`. `LEAF` is `$HOME/prw-pilot/1999.137`.

`prw verify` was run again on each file. Each exited `0`. `record` is `VerifiedBytes`. The ids are the same three ids as the first retry.

One control, without the new treatment, on `1999.137.1` only:

```bash
uv run prw segment "$LEAF/1999.137.1_full.tif" \
  --label 1999.137.1 \
  --foreground-threshold 1 \
  --code-version "$CODE"
```

Exit `1`. `record` is `FailedSegmentation`. `kind` is `hole`. The object has no `polygon` key. The printed `run_id` includes a random `attempt_id` and is not copied here.

The treatment on each file:

```bash
uv run prw segment "$LEAF/1999.137.1_full.tif" \
  --label 1999.137.1 \
  --foreground-threshold 1 \
  --enclosed-background-treatment fill_without_4_interior \
  --code-version "$CODE"
uv run prw segment "$LEAF/1999.137.2_full.tif" \
  --label 1999.137.2 \
  --foreground-threshold 1 \
  --enclosed-background-treatment fill_without_4_interior \
  --code-version "$CODE"
uv run prw segment "$LEAF/1999.137.3_full.tif" \
  --label 1999.137.3 \
  --foreground-threshold 1 \
  --enclosed-background-treatment fill_without_4_interior \
  --code-version "$CODE"
```

Each exited `0`. `record` is `FragmentOutlineRevision`. `epistemic_class` is `interpretation`. `producer` is `machine`. `frame` is `source_pixels`. `envelope.algorithm_name` is `fragment_outline`. `envelope.algorithm_version` is `1`. `envelope.model_hash` is `absent`. The envelope omits `random_seed`. `envelope.decoder_name` is `lossless_tiff` and `envelope.decoder_version` is `1`. The parameter blob on each file is:

```json
{"enclosed_background_treatment":"fill_without_4_interior","foreground_threshold":1}
```

`parameter_hash` is `sha256:8cc20c79e705c5e12f88807f543dc64f3aa12d64314393c6da29dd2a4e23d0cd`.

The rule fills an enclosed 4-connected background component when that component does not contain a pixel together with its four edge neighbors. On these files the enclosed zeros measured in the first retry are of that shape, including the largest components of 10 and 11 pixels. The hole check then passes. The outer boundary is the boundary of the threshold-1 mask. The mount is darker than the cutting and is not zero, so the mount stays foreground. Each polygon meets the image border. It is an interpretation of that mask. It is the border of the frame, with one-pixel steps where a border sample is background. It is not a torn edge of the cutting.

| Accession | Pixels | Vertices | Outline id | Corners in the polygon |
| --- | --- | --- | --- | --- |
| `1999.137.1` | 1252 by 2048 | 13 | `b826be94-07bc-5d52-81f1-9cd77fa3ceff` | `(0, 0)` and `(1251, 2047)` |
| `1999.137.2` | 1838 by 1536 | 58 | `497bd93b-ce9a-529b-a97c-e8f03cdb3bf2` | `(0, 0)` and `(1837, 1535)` |
| `1999.137.3` | 1536 by 1701 | 225 | `a73a98a3-31da-5cc3-8dd1-18269f8328fe` | `(0, 0)` and `(1535, 1700)` |

The thirteen vertices of `1999.137.1` are `(0, 0)`, `(177, 0)`, `(178, 1)`, `(179, 0)`, `(1045, 0)`, `(1046, 1)`, `(1047, 0)`, `(1251, 0)`, `(1251, 981)`, `(1250, 982)`, `(1251, 983)`, `(1251, 2047)`, `(0, 2047)`. The other two polygons are the same kind of border walk. Their vertex lists stay in the command stdout and are not copied here.

```bash
uv run prw rank \
  --image 1999.137.1 "$LEAF/1999.137.1_full.tif" \
  --image 1999.137.2 "$LEAF/1999.137.2_full.tif" \
  --image 1999.137.3 "$LEAF/1999.137.3_full.tif" \
  --foreground-threshold 1 \
  --enclosed-background-treatment fill_without_4_interior \
  --claimed-ppi 400 \
  --code-version "$CODE"
```

Exit `1`. `record` is `FailedPairwiseJoin`. `status` is `failed`. The object has no `joins` key. `claimed_resolution.evidence_description` is `claimed resolution`. `claimed_resolution.claimed_resolution_ppi` is `400.0`. `claimed_resolution.calibration` is `absent`. The claim envelope's algorithm is `claimed_resolution_scale` version `1`. Its parameter blob is `{"claimed_resolution_ppi":400.0,"evidence_description":"claimed resolution","populates_calibration":false}`. `model_hash` is `absent`. `random_seed` is omitted. The claim id is `f2626055-8328-58cd-aad0-58f680178d2e`. Its three source hashes are the table digests. `pixels_per_mm` was not printed. `--pixels-per-mm` was not passed. The catalogue size "Each leaf: 17.6 x 9 cm" was not passed. The TIFF header was not read into the claim. The failed join `run_id` includes a random `attempt_id` and is not copied here.

`prw-review` was not opened. There is no join list to smoke.

No further rule was added after this result. The outlines are the frames. A mount-exclusion pass was not stacked on the treatment. The ranker, the hole check, and the multiple-component check were not loosened. No join hypothesis was invented. The catalogue groups these cuttings. This retry does not say they are torn mates.

## Source and license

- **Source.** Cleveland Museum of Art, Open Access images. Group page: <https://clevelandart.org/art/1999.137>. The page titles the group "Three Cuttings from a Missal". Component pages: <https://clevelandart.org/art/1999.137.1>, <https://clevelandart.org/art/1999.137.2>, <https://clevelandart.org/art/1999.137.3>. Those titles and the page's descriptive text stay on the institution's pages. This note does not import them as a reading, a language, or a find-site.
- **Files.** Downloaded 13 November 2026 and left unchanged.
  - <https://openaccess-cdn.clevelandart.org/1999.137.1/1999.137.1_full.tif>
  - <https://openaccess-cdn.clevelandart.org/1999.137.2/1999.137.2_full.tif>
  - <https://openaccess-cdn.clevelandart.org/1999.137.3/1999.137.3_full.tif>
- **Terms read the same day.** [Terms and Conditions](https://www.clevelandart.org/terms-and-conditions) and [Open Access](https://www.clevelandart.org/open-access). The terms page still says Open Access content designated [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/legalcode) may be copied, modified, distributed, or performed, free of charge, for commercial and noncommercial purposes, without prior permission. The Open Access page still says high-resolution images are made available under a CC0 designation. The group page's embedded record, and each component's API record, set `share_license_status` to `CC0`.
- **Attribution.** `absent`. CC0 requires none.
- **Bytes.** The hash is of the bytes the CDN returned. The API `filesize` field that day was 3308 bytes smaller on each component. Those bytes were not edited to match the field.

| Accession | Pixels | Bytes | `content_hash` | API `filesize` |
| --- | --- | --- | --- | --- |
| `1999.137.1` | 1252 by 2048 | `7698512` | `sha256:3c0c3957e6c62447f5909141210f78f099bd743a116b5f63a9b6a2de263cc62d` | `7695204` |
| `1999.137.2` | 1838 by 1536 | `8476064` | `sha256:cabdb870d68409e9d060e8ce7265cc294121d3b8b17bd03dc937cc1a3b3c8cba` | `8472756` |
| `1999.137.3` | 1536 by 1701 | `7844424` | `sha256:3f9f6a99a7e83f3df7934129010040b6323b30043b70c1fbd5c1b09180dd4351` | `7841116` |

`prw verify` ids were `ce4c02c3-7d7a-559d-a9b9-8f5750beadfd`, `f3097b91-92dc-5cfa-92d8-c23d9354647e`, and `1f062ad6-3b3e-5894-9f93-179e49ef958b`.

- **Header claim.** On each file, tags 282 and 283 are the rational `838860800/2097152`, which is 400. Tag 296 is absent. The TIFF default unit when that tag is absent is the inch, so the header claim is 400 pixels per inch. `claimed_resolution_ppi` in the sidecars is `400`. `pixels_per_mm` and `uncertainty` are `absent`. `prw` does not read those tags. The first retry did not pass the claim. The second retry passed `400` only as `--claimed-ppi`. The component records also state a size, "Each leaf: 17.6 x 9 cm". That sentence was not passed to the CLI.

Each file is classic TIFF, little-endian (`II*\x00`), 8-bit RGB, compression 1 (none). `prw verify` does not read those tags. Pixel commands got past decode. The first retry's failure below is `FailedSegmentation`, which is the record after a raster exists.

## First retry

## Commands

From the checkout root. `CODE` is `git rev-parse HEAD` at the run, `6f64d082be2de162876c4447a1d457bf08165bde`. `LEAF` is `$HOME/prw-pilot/1999.137`.

```bash
uv run prw verify "$LEAF/1999.137.1_full.tif"
uv run prw verify "$LEAF/1999.137.2_full.tif"
uv run prw verify "$LEAF/1999.137.3_full.tif"
```

Each exited `0`. `record` is `VerifiedBytes`. `media_type` is `image/tiff`. The digests and lengths are the table above.

```bash
uv run prw segment "$LEAF/1999.137.1_full.tif" \
  --label 1999.137.1 \
  --foreground-threshold 1 \
  --code-version "$CODE"
uv run prw segment "$LEAF/1999.137.2_full.tif" \
  --label 1999.137.2 \
  --foreground-threshold 1 \
  --code-version "$CODE"
uv run prw segment "$LEAF/1999.137.3_full.tif" \
  --label 1999.137.3 \
  --foreground-threshold 1 \
  --code-version "$CODE"
```

Each exited `1`. `record` is `FailedSegmentation`. `kind` is `hole`. The object has no `polygon` key. `--foreground-threshold 1` is the synthetic-leaf integer. A failed run id includes a random `attempt_id`, so the printed `run_id` is not a reproducibility key and is not copied here.

```bash
uv run prw rank \
  --image 1999.137.1 "$LEAF/1999.137.1_full.tif" \
  --image 1999.137.2 "$LEAF/1999.137.2_full.tif" \
  --image 1999.137.3 "$LEAF/1999.137.3_full.tif" \
  --foreground-threshold 1 \
  --code-version "$CODE"
```

Exit `1`. `record` is `FailedSegmentation`. `kind` is `hole`. The object has no `joins` key. The pool command stops on the first image. Each file, segmented alone, fails the same way, so the stop is not special to `1999.137.1`. `--pixels-per-mm` and `--uncertainty` were omitted. The 400 ppi header claim was not supplied as a scale.

`prw-review` was not opened. There is no hypothesis list to smoke.

After these commands the three lengths and the three digests above were unchanged. The files were not copied into `benchmarks/`. They have no ground-truth label.

## Why this is a hole

At threshold 1 a sample of 1 or more is foreground. The mount is darker than the cutting and is not pure black, so those mount samples are foreground. The enclosed background is exact zero.

An operator count of the decoded 8-bit luminance, using the same 4-connected rule as `fragment_outline` version `1`, found only small enclosed background components. Every one of them is mean luminance 0.

| Accession | Enclosed components | Enclosed pixels | Largest component | Components of 4 pixels or fewer |
| --- | --- | --- | --- | --- |
| `1999.137.1` | 4008 | 5427 | 10 | 3971 |
| `1999.137.2` | 11407 | 14754 | 10 | 11373 |
| `1999.137.3` | 12936 | 16901 | 11 | 12872 |

Border-pixel medians are 24, 30, and 26. Most exact-zero samples sit in a brighter neighborhood than that mount median. In a 12-pixel radius, the neighborhood-mean counts for zero samples are:

| Accession | 0–31 | 32–63 | 64–95 | 96–127 | 128–159 | 160–191 |
| --- | --- | --- | --- | --- | --- | --- |
| `1999.137.1` | 193 | 598 | 2520 | 1747 | 370 | 2 |
| `1999.137.2` | 277 | 4136 | 7288 | 2442 | 555 | 74 |
| `1999.137.3` | 1206 | 4441 | 8118 | 3007 | 204 | 1 |

The zeros that fail the hole check are inside the cutting, not only in the darkest mount. Removing the border-connected dark mount from the mask, and leaving the hole check as it is, does not leave one component and does not clear the enclosed zeros. That count was made outside `prw`, at ceilings 32, 48, 64, 80, and 96. None of those ceilings produced a single component without an enclosed background. It was not added to `prw`.

The same three files were segmented at thresholds 16, 32, 48, 64, 96, and 128. Each of those runs is `FailedSegmentation` kind `multiple_components`. No threshold in that set printed an outline. Those runs were measurements. They were not adopted as a selected threshold, and they were not a change to the checker.

The hole check, the multiple-component check, and the ranker were left as they are. Filling the zero samples, or keeping only the largest component, would be a relaxation of those checks. That was not done. No join hypothesis was invented.

## What was not added

This paragraph is the first retry. `prw rank` on that checkout required a scale before it could emit a millimetre join, and that checkout had no labeled claimed-resolution flag. The first retry never reached that step. Adding the flag, or passing `400 / 25.4` through `--pixels-per-mm`, would not have created an outline on that checkout. Passing the header claim through `--pixels-per-mm` would have recorded it as a caller-supplied measurement. That was not done. [Q-SCI-10](OPEN_QUESTIONS.md#q-sci-10) stays open. A file-header resolution does not populate calibration. The [second retry](#second-retry) later added the labeled claim and still left calibration absent.

No algorithm version changed. No benchmark comparison was published. No `BenchmarkLabel` row was added or edited.

## What stays open

The second retry's outlines are interpretations of the threshold mask, and they follow the image border. The rank list is empty. The third retry requested the frame-split mount rule, with the enclosed-background fill named on the same command. Each segmentation is `FailedSegmentation` kind `multiple_components`. No outline was stored, and no join was stored. [Q-SCI-15](OPEN_QUESTIONS.md#q-sci-15) stays open for every other corpus and for any accuracy claim. [Q-ENG-01](OPEN_QUESTIONS.md#q-eng-01) stays open. [Q-SCI-10](OPEN_QUESTIONS.md#q-sci-10) stays open. A synthetic pool whose rank list has join hypotheses is [Multi-fragment pool](pilot-multi-fragment-pool.md). Those rows stay hypotheses. One earlier Cleveland file, segmented at this same threshold, is [First public-leaf run](pilot-first-run.md).
