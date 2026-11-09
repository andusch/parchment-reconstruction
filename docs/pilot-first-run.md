# First public-leaf run

- Status: Working note. One operator run of the path in [Public import path](pilot-import-path.md).
- Run: 9 November 2026, checkout `febbabaa105bdc19a06c4d74e28fb2c17d5ee96f` (merge of PR #14). Command names and flags are unfrozen.
- Glossary: [DATA_MODEL.md](DATA_MODEL.md#glossary)

The TIFF stayed outside the clone, at `$HOME/prw-pilot/leaves/shelf-1/image.tif`. On this machine that path was `/home/ubuntu/prw-pilot/leaves/shelf-1/image.tif`. A text sidecar `image.note` sits beside it and is not in Git. [`.gitignore`](../.gitignore) ignores `*.tif` and `*.tiff`. The file was never under `data/`, `scans/`, or `real_data/`.

Every join in a `physical_join_order` is a hypothesis. It is not historical truth. The empty list from this run is the completed result for one pool image. It is not a finding about the object's past.

## Source and license

- **Source.** Cleveland Museum of Art, Open Access images. Object page: <https://clevelandart.org/art/1951.314>. Accession `1951.314`. The page titles the object "Historiated Initial (O) Excised from an Antiphonary: The Donor, Gorus Fucci, Kneels before Christ". That caption stays on the institution's page. This note does not import it as a reading, a language, or a find-site.
- **File.** <https://openaccess-cdn.clevelandart.org/1951.314/1951.314_full.tif>, downloaded 9 November 2026 and left unchanged.
- **Terms read the same day.** [Terms and Conditions](https://www.clevelandart.org/terms-and-conditions) and [Open Access](https://www.clevelandart.org/open-access). The terms page still says Open Access content designated [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/legalcode) may be copied, modified, distributed, or performed, free of charge, for commercial and noncommercial purposes, without prior permission. The Open Access page still says high-resolution images are made available under a CC0 designation. The object-page data and the API record both set `share_license_status` to `CC0`.
- **Attribution.** `absent`. CC0 requires none.
- **Bytes.** `sha256:d2468d256da131d82def5b5a9931c47c85f073808052b028ff1a06e558f5a5bb`, length `53453468`. The API `filesize` field that day was `53463316`. The hash is of the bytes the CDN returned. Those bytes were not edited to match the field.
- **Header claim.** Tags 282 and 283 are the rational `4000000/10000`, and tag 296 is `2` (inch): 400 pixels per inch. `claimed_resolution_ppi` in the sidecar is `400`. `pixels_per_mm` and `uncertainty` are `absent`. The header claim was not passed to the CLI.

The file is classic TIFF, little-endian (`II*\x00`), 4241 by 4199, 8-bit RGB, compression 1 (none), one strip. `prw verify` does not read those tags. Pixel commands reported decoder `lossless_tiff` version `1`.

## Commands

From the checkout root. `CODE` is `git rev-parse HEAD` at the run, `febbabaa105bdc19a06c4d74e28fb2c17d5ee96f`. `LEAF` is `$HOME/prw-pilot/leaves/shelf-1`.

```bash
uv run prw verify "$LEAF/image.tif"
uv run prw verify "$LEAF/image.tif" \
  --expected "sha256:d2468d256da131d82def5b5a9931c47c85f073808052b028ff1a06e558f5a5bb"
```

Both exited `0`. `record` is `VerifiedBytes`. `media_type` is `image/tiff`. `content_hash` is the digest above. `byte_length` is `53453468`. `id` is `effe961b-a1b4-5ced-8954-3ce0ee6ba493`.

```bash
uv run prw segment "$LEAF/image.tif" \
  --label shelf-1 \
  --foreground-threshold 1 \
  --code-version "$CODE" \
  --expected "sha256:d2468d256da131d82def5b5a9931c47c85f073808052b028ff1a06e558f5a5bb"
```

Exit `0`, about 13 seconds. `record` is `FragmentOutlineRevision`. `epistemic_class` is `interpretation`. `producer` is `machine`. `frame` is `source_pixels`. `envelope.algorithm_name` is `fragment_outline`, `algorithm_version` is `1`, `decoder_name` is `lossless_tiff`, `decoder_version` is `1`, `model_hash` is `absent`. The envelope omits `random_seed`. `parameter_blob` is `{"foreground_threshold":1}`. The polygon is `[[0.0,0.0],[4240.0,0.0],[4240.0,4198.0],[0.0,4198.0]]`, the corners of the 4241 by 4199 raster. `--foreground-threshold 1` is the synthetic-leaf integer. On this file it kept the whole raster as one component. This outline is an interpretation of that threshold. It is not a historical edge. No other threshold was selected.

```bash
uv run prw rank \
  --image shelf-1 "$LEAF/image.tif" \
  --foreground-threshold 1 \
  --code-version "$CODE"
```

Exit `0`, about 14 seconds. `record` is `physical_join_order`. `joins` is `[]`. `envelope.algorithm_name` is `pairwise_rigid_join`, `decoder_name` is `lossless_tiff`, `decoder_version` is `1`. The envelope omits `random_seed`. One pool image completes with no joins. `--pixels-per-mm` and `--uncertainty` were omitted because the sidecar has no measurement. A later list with two or more images would still be hypotheses.

```bash
uv run prw assemble \
  --image shelf-1 "$LEAF/image.tif" \
  --foreground-threshold 1 \
  --code-version "$CODE"
```

Exit `1`. `record` is `FailedAssemblySearch`. `status` is `failed`. The object has no `assemblies` key. A completed search needs the scale pair, `--n`, and the page rectangle. The sidecar has no measurement, so none of those were supplied. No placement was emitted.

After these commands the file length and `sha256:d2468d256da131d82def5b5a9931c47c85f073808052b028ff1a06e558f5a5bb` were unchanged. The leaf was not copied into `benchmarks/`. It has no ground-truth label.

## What stays open

[Q-SCI-15](OPEN_QUESTIONS.md#q-sci-15) stays open for every other corpus and for any accuracy claim. [Q-ENG-01](OPEN_QUESTIONS.md#q-eng-01) stays open. This run does not reopen [Q-ENG-05](OPEN_QUESTIONS.md#q-eng-05).
