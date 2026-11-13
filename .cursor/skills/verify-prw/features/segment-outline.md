# Segment a fragment

Segment a fragment prints one machine outline for a seeded TIFF. Without a scale the outline is in `source_pixels`. With a caller-supplied scale it is in `fragment_local_mm`. A bad checksum prints `IntegrityFailure` and no polygon.

## Sub-features

- `segment-pixels` prints a `source_pixels` outline.
- `segment-millimetres` prints a `fragment_local_mm` outline for the same file.
- `segment-claimed-ppi` records a claimed resolution and leaves the outline in `source_pixels`.
- `segment-claimed-with-scale` refuses `--claimed-ppi` together with a measurement flag.
- `segment-enclosed-background` names `fill_without_4_interior` in the parameter blob.
- `segment-mismatch` stops on a checksum mismatch.
- `segment-missing` reports a fragment name that is not in the image directory.

## How to get to it (user POV)

- Run `prw segment PATH --label LABEL --foreground-threshold N --code-version CODE` in a terminal.
- Add `--expected sha256:DIGEST` to bind the command to a recorded hash.
- Add `--pixels-per-mm N --uncertainty N` together to scale the outline into millimetres.
- Add `--claimed-ppi N` to record a claimed resolution. Omit the measurement pair.
- Add `--enclosed-background-treatment fill_without_4_interior` to name that fill rule. Omit the flag to leave the hole check unchanged.

## Driving it with verify-prw

Preconditions:

- Doctor prints `prw-verify doctor ok` for this run.
- `exports` has set `$RUN_ID`, `$CODE`, `$IMAGES`, `$FRAGMENT_A_PATH`, and `$FRAGMENT_A_HASH`.

- **Print a pixel outline.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature segment-outline --entry "prw segment fragment" --step pixels -- segment "$FRAGMENT_A_PATH" --label shelf-4 --foreground-threshold 1 --code-version "$CODE" --expected "$FRAGMENT_A_HASH"`. Exit code `0`. The JSON `record` is `FragmentOutlineRevision`, `epistemic_class` is `interpretation`, `producer` is `machine`, and `frame` is `source_pixels`. `polygon` has at least three positions. `envelope.algorithm_name` is `fragment_outline`, `envelope.algorithm_version` is `1`, and `envelope.model_hash` is `absent`. `envelope.parameter_blob` is `{"foreground_threshold":1}`. The `random_seed` key is absent. The object has no `claimed_resolution` key. Stdout does not contain `correct_join`.
- **Print a millimetre outline.** Run the same command with `--step millimetres` and these added flags: `--pixels-per-mm 2 --uncertainty 0`. Exit code `0`. `frame` is `fragment_local_mm`. `epistemic_class` is `interpretation`. `producer` is `machine`. `envelope.algorithm_name` is `caller_supplied_scale`.
- **Present a different hash.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature segment-outline --entry "prw segment fragment --expected wrong hash" --step mismatch -- segment "$FRAGMENT_A_PATH" --label shelf-4 --foreground-threshold 1 --code-version "$CODE" --expected "sha256:abababababababababababababababababababababababababababababababab"`. Exit code `1`. The JSON `record` is `IntegrityFailure`. The object has no `polygon` key.
- **Ask for a missing name.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature segment-outline --entry "prw segment missing fragment" --step missing -- segment "$IMAGES/fragment-0.tif" --label shelf-4 --foreground-threshold 1 --code-version "$CODE"`. Exit code `2`. stdout is empty. stderr contains `Fragment files:` and every name on the doctor `fragments` line. stderr does not contain `Traceback`.
- **Record a claimed resolution.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature segment-outline --entry "prw segment fragment --claimed-ppi" --step claimed-ppi -- segment "$FRAGMENT_A_PATH" --label shelf-4 --foreground-threshold 1 --code-version "$CODE" --expected "$FRAGMENT_A_HASH" --claimed-ppi 400`. Exit code `0`. `frame` is `source_pixels`. `epistemic_class` is `interpretation`. `producer` is `machine`. `envelope.algorithm_name` is `fragment_outline`. `claimed_resolution.evidence_description` is `claimed resolution`. `claimed_resolution.claimed_resolution_ppi` is `400.0`. `claimed_resolution.calibration` is `absent`. `claimed_resolution.envelope.algorithm_name` is `claimed_resolution_scale`. The claim's `parameter_blob` is `{"claimed_resolution_ppi":400.0,"evidence_description":"claimed resolution","populates_calibration":false}`. Stdout does not contain `pixels_per_mm`. The `polygon` equals the pixels step polygon.
- **Pass the claim with a measurement.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature segment-outline --entry "prw segment fragment --claimed-ppi --pixels-per-mm" --step claimed-with-scale -- segment "$FRAGMENT_A_PATH" --label shelf-4 --foreground-threshold 1 --code-version "$CODE" --claimed-ppi 400 --pixels-per-mm 10 --uncertainty 0.1`. Exit code `2`. stdout is empty. stderr contains `claimed_resolution_ppi is not a measured pixels_per_mm.`
- **Name the enclosed-background treatment.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature segment-outline --entry "prw segment fragment --enclosed-background-treatment" --step enclosed-background -- segment "$FRAGMENT_A_PATH" --label shelf-4 --foreground-threshold 1 --enclosed-background-treatment fill_without_4_interior --code-version "$CODE" --expected "$FRAGMENT_A_HASH"`. Exit code `0`. `frame` is `source_pixels`. `epistemic_class` is `interpretation`. `producer` is `machine`. `envelope.algorithm_name` is `fragment_outline`. `envelope.parameter_blob` is `{"enclosed_background_treatment":"fill_without_4_interior","foreground_threshold":1}`. The `polygon` equals the pixels step polygon.
- **Proof.** The evidence directory contains `pixels`, `millimetres`, `mismatch`, `missing`, `claimed-ppi`, `claimed-with-scale`, and `enclosed-background`.

## Gotchas

- The printed outline does not include the label `shelf-4`. Assert the record fields, not the label text.
- `--pixels-per-mm` and `--uncertainty` are supplied together. One without the other exits `2` and stderr contains `pixels_per_mm and uncertainty are supplied together.`
- `--claimed-ppi 400` records a claim. `calibration` stays `absent`. The number is not a measured `pixels_per_mm`, and the command does not read a TIFF resolution tag. Passing it with either measurement flag exits `2`.
- `--enclosed-background-treatment fill_without_4_interior` fills enclosed background that contains no 4-interior pixel. On this seed the polygon matches the untreated outline. Omit the flag and the blob stays `{"foreground_threshold":1}`. A component that does contain that element still fails as `hole`.
- `--foreground-threshold` is an integer from `0` through `255`. These seeded images are segmented at `1`.
- A checksum mismatch prints no polygon. A usage error exits `2` with empty stdout.
