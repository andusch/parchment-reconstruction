# Score an outline

Score an outline compares one segmented outline with a polygon you supply and writes a new report under the benchmarks directory. The report leaves `labels.json` unchanged. The polygon you pass is the reference for that report.

## Sub-features

- `agree-report` writes `outline_agreement` for a caller square in `source_pixels`.
- `agree-refuse-label` refuses `labels.json` as the benchmarks path.

## How to get to it (user POV)

- Run `prw agree PATH --benchmarks DIR --reference X,Y --reference X,Y --reference X,Y --frame source_pixels --label LABEL --foreground-threshold N --code-version CODE` in a terminal. Repeat `--reference` once per vertex.

## Driving it with verify-prw

Preconditions:

- Doctor prints `prw-verify doctor ok` for this run.
- `exports` has set `$RUN_ID`, `$CODE`, `$BENCHMARKS`, and `$FRAGMENT_A_PATH`.

- **Record the label file.** Run `shasum -a 256 "$BENCHMARKS/labels.json"` and keep the digest.
- **Score a caller square.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature agree-outline --entry "prw agree caller square" --step report -- agree "$FRAGMENT_A_PATH" --benchmarks "$BENCHMARKS" --reference 0,0 --reference 2,0 --reference 2,2 --reference 0,2 --frame source_pixels --label shelf-4 --foreground-threshold 1 --code-version "$CODE"`. Exit code `0`. `metric` is `outline_agreement`. `algorithm_name` is `fragment_outline`. `frame` is `source_pixels`. `reference` is `generator polygon supplied by the caller`. `previous_report` is `absent`. `previous_report_statement` is `No previous outline-agreement report exists.`. `ious` has one finite number. `reference_polygons` is `[[[0.0,0.0],[2.0,0.0],[2.0,2.0],[0.0,2.0]]]`. `predicted_polygons` has one polygon, and that polygon is not the caller square. Stdout does not contain `correct_join`. The file `$BENCHMARKS/outline_agreement/outline-agreement-0001.json` exists.
- **Label file is unchanged.** `shasum -a 256 "$BENCHMARKS/labels.json"` prints the same digest as the first reading.
- **Pass the label file as the benchmarks path.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature agree-outline --entry "prw agree labels.json" --step refuse-label -- agree "$FRAGMENT_A_PATH" --benchmarks "$BENCHMARKS/labels.json" --reference 0,0 --reference 2,0 --reference 2,2 --reference 0,2 --frame source_pixels --label shelf-4 --foreground-threshold 1 --code-version "$CODE"`. Exit code `2`. stdout is empty. stderr contains `BenchmarkLabel join file`. The label digest is still the first digest. The outline-agreement directory still contains only `outline-agreement-0001.json`.
- **Proof.** The evidence directory contains `report` and `refuse-label`.

## Gotchas

- `generate` does not print a reference polygon. The square `0,0 2,0 2,2 0,2` is the caller reference for this report. It is the polygon recorded in `reference_polygons`.
- `--frame` is `source_pixels` for a segmentation that omitted the scale pair. A different frame exits `2`.
- `labels.json` is the BenchmarkLabel store. Agree refuses that file as `--benchmarks`. Do not open it to judge the IoU.
- The report is a new file under `$BENCHMARKS/outline_agreement/`. Agree does not rewrite `labels.json`.
