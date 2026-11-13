# Write join presence

Write join presence writes a new end-to-end join-presence report under the benchmarks directory. The first report on this seed records N `2` and states that no previous end-to-end join-presence report exists. `labels.json` stays unchanged.

## Sub-features

- `join-presence-report` writes `assembly_join_presence` for the seeded pair.
- `join-presence-claimed-ppi` rejects `--claimed-ppi` and writes no report.

## How to get to it (user POV)

- Run `prw join-presence` with the `prw assemble` flags plus `--benchmarks DIR`.
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
- **Reject a claimed resolution.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature join-presence --entry "prw join-presence --claimed-ppi" --step claimed-ppi -- join-presence --image piece-a "$PIECE_A" --image piece-b "$PIECE_B" --foreground-threshold 1 --code-version "$CODE" --claimed-ppi 400 --minimum-edge-length-mm 6 --n 2 --translation-tolerance-mm 1 --rotation-tolerance-radians 1 --min-width-mm 0 --max-width-mm 1000 --min-height-mm 0 --max-height-mm 1000 --benchmarks "$BENCHMARKS"`. Exit code `2`. stdout is empty. stderr contains `A claimed resolution does not populate calibration.` `$BENCHMARKS/assembly_join_presence` does not exist.
- **Write the report.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature join-presence --entry "prw join-presence two images" --step report -- join-presence --image piece-a "$PIECE_A" --image piece-b "$PIECE_B" --foreground-threshold 1 --code-version "$CODE" --pixels-per-mm 10 --uncertainty 0.1 --minimum-edge-length-mm 6 --n 2 --translation-tolerance-mm 1 --rotation-tolerance-radians 1 --min-width-mm 0 --max-width-mm 1000 --min-height-mm 0 --max-height-mm 1000 --benchmarks "$BENCHMARKS"`. Exit code `0`. `metric` is `assembly_join_presence`. `n` is `2`. `reference` is `frozen kind: join row`. `does_not_measure` is `a historical join on real parchment`. `previous_report` is `absent`. `previous_report_statement` is `No previous end-to-end join-presence report exists.`. `algorithm_name` is `rigid_assembly_search`. `fixture_list` is non-empty. Stdout does not contain `correct_join`. The file `$BENCHMARKS/assembly_join_presence/assembly-join-presence-0001.json` exists.
- **Label files are unchanged.** Both `shasum` readings match the first readings. `$BENCHMARKS/manifest.json` does not exist.
- **Proof.** The evidence directory contains `claimed-ppi` and `report`.

## Gotchas

- The report counts fixtures whose frozen joins appear in the top N assemblies. It does not feed label rows into the search.
- `does_not_measure` states the limit: a historical join on real parchment is outside this metric.
- `--claimed-ppi` exits `2` before a report file is created. Pass it without the measurement pair.
