# Segment a fragment

Segment a fragment prints one machine outline for a seeded TIFF. Without a scale the outline is in `source_pixels`. With a caller-supplied scale it is in `fragment_local_mm`. A bad checksum prints `IntegrityFailure` and no polygon.

## Sub-features

- `segment-pixels` prints a `source_pixels` outline.
- `segment-millimetres` prints a `fragment_local_mm` outline for the same file.
- `segment-mismatch` stops on a checksum mismatch.
- `segment-missing` reports a fragment name that is not in the image directory.

## How to get to it (user POV)

- Run `prw segment PATH --label LABEL --foreground-threshold N --code-version CODE` in a terminal.
- Add `--expected sha256:DIGEST` to bind the command to a recorded hash.
- Add `--pixels-per-mm N --uncertainty N` together to scale the outline into millimetres.

## Driving it with verify-prw

Preconditions:

- Doctor prints `prw-verify doctor ok` for this run.
- `exports` has set `$RUN_ID`, `$CODE`, `$IMAGES`, `$FRAGMENT_A_PATH`, and `$FRAGMENT_A_HASH`.

- **Print a pixel outline.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature segment-outline --entry "prw segment fragment" --step pixels -- segment "$FRAGMENT_A_PATH" --label shelf-4 --foreground-threshold 1 --code-version "$CODE" --expected "$FRAGMENT_A_HASH"`. Exit code `0`. The JSON `record` is `FragmentOutlineRevision`, `epistemic_class` is `interpretation`, `producer` is `machine`, and `frame` is `source_pixels`. `polygon` has at least three positions. `envelope.algorithm_name` is `fragment_outline`, `envelope.algorithm_version` is `1`, and `envelope.model_hash` is `absent`. The `random_seed` key is absent. Stdout does not contain `correct_join`.
- **Print a millimetre outline.** Run the same command with `--step millimetres` and these added flags: `--pixels-per-mm 2 --uncertainty 0`. Exit code `0`. `frame` is `fragment_local_mm`. `epistemic_class` is `interpretation`. `producer` is `machine`. `envelope.algorithm_name` is `caller_supplied_scale`.
- **Present a different hash.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature segment-outline --entry "prw segment fragment --expected wrong hash" --step mismatch -- segment "$FRAGMENT_A_PATH" --label shelf-4 --foreground-threshold 1 --code-version "$CODE" --expected "sha256:abababababababababababababababababababababababababababababababab"`. Exit code `1`. The JSON `record` is `IntegrityFailure`. The object has no `polygon` key.
- **Ask for a missing name.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature segment-outline --entry "prw segment missing fragment" --step missing -- segment "$IMAGES/fragment-0.tif" --label shelf-4 --foreground-threshold 1 --code-version "$CODE"`. Exit code `2`. stdout is empty. stderr contains `Fragment files:` and every name on the doctor `fragments` line. stderr does not contain `Traceback`.
- **Proof.** The evidence directory contains `pixels`, `millimetres`, `mismatch`, and `missing`.

## Gotchas

- The printed outline does not include the label `shelf-4`. Assert the record fields, not the label text.
- `--pixels-per-mm` and `--uncertainty` are supplied together. One without the other exits `2` and stderr contains `pixels_per_mm and uncertainty are supplied together.`
- `--foreground-threshold` is an integer from `0` through `255`. These seeded images are segmented at `1`.
- A checksum mismatch prints no polygon. A usage error exits `2` with empty stdout.
