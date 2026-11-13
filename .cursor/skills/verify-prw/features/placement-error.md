# Write placement error

Write placement error writes a new placement-error report under the benchmarks directory. The first report on this seed records N `2` and states that no previous placement-error report exists. `labels.json` stays unchanged.

## Sub-features

- `placement-error-report` writes `placement_error` for the seeded pair.
- `placement-error-claimed-ppi` rejects `--claimed-ppi` and writes no report.

## How to get to it (user POV)

- Run `prw placement-error` with the `prw assemble` flags plus `--benchmarks DIR`.
- Pass `--claimed-ppi N` without the measurement pair. The command rejects the claim.

## Driving it with verify-prw

Preconditions:

- Doctor prints `prw-verify doctor ok` for this run.
- `exports` has set `$RUN_ID`, `$CODE`, `$IMAGES`, and `$BENCHMARKS`.
- Bind the first and third fragment paths in sorted file-name order:

```bash
PIECE_A=$(printf '%s\n' "$IMAGES"/fragment-*.tif | sort | sed -n '1p')
PIECE_B=$(printf '%s\n' "$IMAGES"/fragment-*.tif | sort | sed -n '3p')
```

- **Record the label file.** Run `shasum -a 256 "$BENCHMARKS/labels.json"` and `shasum -a 256 "$BENCHMARKS/provenance.json"` and keep both digests.
- **Reject a claimed resolution.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature placement-error --entry "prw placement-error --claimed-ppi" --step claimed-ppi -- placement-error --image piece-a "$PIECE_A" --image piece-b "$PIECE_B" --foreground-threshold 1 --code-version "$CODE" --claimed-ppi 400 --minimum-edge-length-mm 6 --n 2 --translation-tolerance-mm 1 --rotation-tolerance-radians 1 --min-width-mm 0 --max-width-mm 1000 --min-height-mm 0 --max-height-mm 1000 --benchmarks "$BENCHMARKS"`. Exit code `2`. stdout is empty. stderr contains `A claimed resolution does not populate calibration.` `$BENCHMARKS/placement_error` does not exist.
- **Write the report.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature placement-error --entry "prw placement-error two images" --step report -- placement-error --image piece-a "$PIECE_A" --image piece-b "$PIECE_B" --foreground-threshold 1 --code-version "$CODE" --pixels-per-mm 10 --uncertainty 0.1 --minimum-edge-length-mm 6 --n 2 --translation-tolerance-mm 1 --rotation-tolerance-radians 1 --min-width-mm 0 --max-width-mm 1000 --min-height-mm 0 --max-height-mm 1000 --benchmarks "$BENCHMARKS"`. Exit code `0`. `metric` is `placement_error`. `n` is `2`. `reference` is `frozen kind: placement row`. `does_not_measure` is `warped or shrunken real parchment`. `previous_report` is `absent`. `previous_report_statement` is `No previous placement-error report exists.`. `algorithm_name` is `rigid_assembly_search`. Stdout does not contain `correct_join`. The file `$BENCHMARKS/placement_error/placement-error-0001.json` exists.
- **Label files are unchanged.** Both `shasum` readings match the first readings. `$BENCHMARKS/manifest.json` does not exist.
- **Proof.** The evidence directory contains `claimed-ppi` and `report`.

## Gotchas

- The report scores frozen `kind: placement` rows. It does not feed those rows into the search. Do not open `labels.json` to decide whether an error number is small enough.
- `does_not_measure` states the limit: warped or shrunken real parchment is outside this metric.
- `--claimed-ppi` exits `2` before a report file is created. Pass it without the measurement pair.
