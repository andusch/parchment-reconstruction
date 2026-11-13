# Write join recall

Write join recall writes a new report under the benchmarks directory. It reads `labels.json` only for that comparison. `--k` is the prefix length you declare before the run. On this seed the first-and-third sorted pair reports recall `0.0`, and the doctor-exported pair reports recall `0.25`.

## Sub-features

- `recall-sorted-pair` writes recall `0.0` for the first and third sorted fragment ids.
- `recall-doctor-pair` writes recall `0.25` for the doctor-exported fragment ids and leaves the first report in place.
- `recall-claimed-ppi` rejects `--claimed-ppi` before a report is written.

## How to get to it (user POV)

- Run `prw recall --image LABEL PATH --image LABEL PATH --benchmarks DIR --k N --foreground-threshold N --code-version CODE --pixels-per-mm N --uncertainty N --correspondence LABEL=FIXTURE_ID --correspondence LABEL=FIXTURE_ID` in a terminal.
- Pass `--claimed-ppi N` without the measurement pair. The command rejects the claim.

## Driving it with verify-prw

Preconditions:

- Doctor prints `prw-verify doctor ok` for this run.
- `exports` has set `$RUN_ID`, `$CODE`, `$IMAGES`, `$BENCHMARKS`, `$FRAGMENT_A`, `$FRAGMENT_B`, `$FRAGMENT_A_PATH`, and `$FRAGMENT_B_PATH`.
- The images directory has four `fragment-*.tif` files. Bind the first and third names in sorted order, and the fixture id in each file name:

```bash
SORTED_FIRST=$(printf '%s\n' "$IMAGES"/fragment-*.tif | sort | sed -n '1p')
SORTED_THIRD=$(printf '%s\n' "$IMAGES"/fragment-*.tif | sort | sed -n '3p')
SORTED_FIRST_ID=$(basename "$SORTED_FIRST" .tif)
SORTED_FIRST_ID=${SORTED_FIRST_ID#fragment-}
SORTED_THIRD_ID=$(basename "$SORTED_THIRD" .tif)
SORTED_THIRD_ID=${SORTED_THIRD_ID#fragment-}
DOCTOR_A_ID=$(basename "$FRAGMENT_A" .tif)
DOCTOR_A_ID=${DOCTOR_A_ID#fragment-}
DOCTOR_B_ID=$(basename "$FRAGMENT_B" .tif)
DOCTOR_B_ID=${DOCTOR_B_ID#fragment-}
```

- **Record the label file.** Run `shasum -a 256 "$BENCHMARKS/labels.json"` and `shasum -a 256 "$BENCHMARKS/provenance.json"` and keep both digests.
- **Reject a claimed resolution.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature recall-joins --entry "prw recall --claimed-ppi" --step claimed-ppi -- recall --image piece-a "$SORTED_FIRST" --image piece-b "$SORTED_THIRD" --benchmarks "$BENCHMARKS" --k 1 --foreground-threshold 1 --code-version "$CODE" --claimed-ppi 400`. Exit code `2`. stdout is empty. stderr contains `A claimed resolution does not populate calibration.` `$BENCHMARKS/join_recall` does not exist.
- **Recall the sorted pair.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature recall-joins --entry "prw recall sorted pair" --step sorted-pair -- recall --image piece-a "$SORTED_FIRST" --image piece-b "$SORTED_THIRD" --benchmarks "$BENCHMARKS" --k 1 --foreground-threshold 1 --code-version "$CODE" --pixels-per-mm 10 --uncertainty 0.1 --correspondence "piece-a=$SORTED_FIRST_ID" --correspondence "piece-b=$SORTED_THIRD_ID"`. Exit code `0`. `k` is `1`. `metric` is `join_recall_at_k`. `algorithm_name` is `pairwise_rigid_join`. `recall` is `0.0`. `recall_list` has four entries, and every `status` is `absent`. `reference` is `frozen kind: join row`. `does_not_measure` is `a historical join on real parchment`. `previous_report` is `absent`. `previous_report_statement` is `No previous join-recall report exists.`. Stdout does not contain `correct_join`. The file `$BENCHMARKS/join_recall/join-recall-0001.json` exists.
- **Recall the doctor pair.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature recall-joins --entry "prw recall doctor pair" --step doctor-pair -- recall --image piece-a "$FRAGMENT_A_PATH" --image piece-b "$FRAGMENT_B_PATH" --benchmarks "$BENCHMARKS" --k 1 --foreground-threshold 1 --code-version "$CODE" --pixels-per-mm 10 --uncertainty 0.1 --correspondence "piece-a=$DOCTOR_A_ID" --correspondence "piece-b=$DOCTOR_B_ID"`. Exit code `0`. `k` is `1`. `metric` is `join_recall_at_k`. `recall` is `0.25`. `recall_list` has four entries, three with `status` `absent` and one with `status` `present`. `reference` is `frozen kind: join row`. `does_not_measure` is `a historical join on real parchment`. `previous_report` is `join-recall-0001.json`. The file `$BENCHMARKS/join_recall/join-recall-0002.json` exists. `join-recall-0001.json` is still present.
- **Label files are unchanged.** Both `shasum` readings match the first readings. `$BENCHMARKS/manifest.json` does not exist.
- **Proof.** The evidence directory contains `claimed-ppi`, `sorted-pair`, and `doctor-pair`.

## Gotchas

- The correspondence value is the fixture id in the file name `fragment-<id>.tif`. The flag is `label=fixture-id`, using the same label word passed to `--image`.
- On this seed the first and third sorted ids are not a frozen join, so recall is `0.0`. The doctor export binds `$FRAGMENT_A` and `$FRAGMENT_B` to the first two fragment files in manifest order. A correspondence onto those ids meets one frozen join, so recall is `0.25`. That `0.25` is the measurement for this pool. It is not a historical join.
- `--claimed-ppi` is passed without `--pixels-per-mm`. Together, the message is `claimed_resolution_ppi is not a measured pixels_per_mm.` The calibration refusal is the path in [Using the workbench](../../../../docs/USAGE.md).
- `labels.json` stays byte-identical. Do not open it to decide which pair should have matched.
- A later recall writes the next numbered file and leaves the earlier file in place.
