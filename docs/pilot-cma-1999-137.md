# Cleveland 1999.137 retry

- Status: Working note. The retry produced no join list.
- Run: 13 November 2026, checkout `6f64d082be2de162876c4447a1d457bf08165bde` (merge of PR #18). Command names and flags are unfrozen.
- Glossary: [DATA_MODEL.md](DATA_MODEL.md#glossary)

The three TIFFs stayed outside the clone, under `$HOME/prw-pilot/1999.137/`. On this machine that directory was `/home/ubuntu/prw-pilot/1999.137`. Text sidecars sit beside the files and are not in Git. [`.gitignore`](../.gitignore) ignores `*.tif` and `*.tiff`. The files were never under `data/`, `scans/`, or `real_data/`.

The Cleveland catalogue groups these three cuttings under accession `1999.137`. The object-page text read on this day does not say they are torn mates, and it does not say that an edge of one meets an edge of another. This note does not treat them as mates. It does not treat a join as a reconstruction. No join was emitted.

[1951.314](pilot-first-run.md) was not opened. The group file `1999.137_full.tif` was not downloaded, and no whole leaf was cut to make a pool.

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

- **Header claim.** On each file, tags 282 and 283 are the rational `838860800/2097152`, which is 400. Tag 296 is absent. The TIFF default unit when that tag is absent is the inch, so the header claim is 400 pixels per inch. `claimed_resolution_ppi` in the sidecars is `400`. `pixels_per_mm` and `uncertainty` are `absent`. The header claim was not passed to the CLI. The component records also state a size, "Each leaf: 17.6 x 9 cm". That sentence was not passed to the CLI.

Each file is classic TIFF, little-endian (`II*\x00`), 8-bit RGB, compression 1 (none). `prw verify` does not read those tags. Pixel commands got past decode: the failure below is `FailedSegmentation`, which is the record after a raster exists.

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

`prw rank` still requires a scale before it can emit a millimetre join, and it still has no labeled claimed-resolution flag. This retry never reached that step. Adding the flag, or passing `400 / 25.4` through `--pixels-per-mm`, would not create an outline. Passing the header claim through `--pixels-per-mm` would record it as a caller-supplied measurement. That was not done. [Q-SCI-10](OPEN_QUESTIONS.md#q-sci-10) stays open. A file-header resolution still does not populate calibration.

No algorithm version changed. No benchmark comparison was published. No `BenchmarkLabel` row was added or edited.

## What stays open

[Q-SCI-15](OPEN_QUESTIONS.md#q-sci-15) stays open for every other corpus and for any accuracy claim. [Q-ENG-01](OPEN_QUESTIONS.md#q-eng-01) stays open. [Q-SCI-10](OPEN_QUESTIONS.md#q-sci-10) stays open. A synthetic pool whose rank list has join hypotheses is [Multi-fragment pool](pilot-multi-fragment-pool.md). Those rows stay hypotheses. One earlier Cleveland file, segmented at this same threshold, is [First public-leaf run](pilot-first-run.md).
