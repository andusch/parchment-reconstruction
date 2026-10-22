# Rank joins

Rank joins prints pairwise join hypotheses in `physical` score order. The command reads fixture TIFFs. It leaves the BenchmarkLabel file unchanged and does not print a ground-truth join.

## Sub-features

- `rank-order` prints `physical_join_order` for two seeded fragments.
- `rank-unscaled` fails when the scale pair is omitted.
- `rank-refuse-label` refuses `labels.json` as an image path.
- `rank-missing` reports a fragment name that is not in the image directory.

## How to get to it (user POV)

- Run `prw rank --image LABEL PATH --image LABEL PATH --foreground-threshold N --code-version CODE --pixels-per-mm N --uncertainty N` in a terminal. Repeat `--image` once per fragment.

## Driving it with verify-prw

Preconditions:

- Doctor prints `prw-verify doctor ok` for this run.
- `exports` has set `$RUN_ID`, `$CODE`, `$IMAGES`, `$BENCHMARKS`, `$FRAGMENT_A_PATH`, and `$FRAGMENT_B_PATH`.
- `$FRAGMENT_A_PATH` and `$FRAGMENT_B_PATH` are different files.

- **Record the label file.** Run `shasum -a 256 "$BENCHMARKS/labels.json"` and keep the digest.
- **Rank two fragments.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature rank-joins --entry "prw rank two images" --step order -- rank --image piece-a "$FRAGMENT_A_PATH" --image piece-b "$FRAGMENT_B_PATH" --foreground-threshold 1 --code-version "$CODE" --pixels-per-mm 10 --uncertainty 0.1`. Exit code `0`. The JSON `record` is `physical_join_order`. `joins` is non-empty. Each `score` is less than or equal to the previous score. Every `epistemic_class` is `hypothesis`. Every `channel` is `physical`. `envelope.algorithm_name` is `pairwise_rigid_join`. The `random_seed` key is absent. Stdout does not contain `correct_join` or `pose`.
- **Label file is unchanged.** `shasum -a 256 "$BENCHMARKS/labels.json"` prints the same digest as the first reading.
- **Omit the scale.** Run the rank command with `--step unscaled` and without `--pixels-per-mm` and `--uncertainty`. Exit code `1`. The JSON `record` is `FailedPairwiseJoin` and `status` is `failed`. The object has no `joins` key.
- **Pass the label file as an image.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature rank-joins --entry "prw rank labels.json" --step refuse-label -- rank --image piece-a "$BENCHMARKS/labels.json" --foreground-threshold 1 --code-version "$CODE" --pixels-per-mm 10 --uncertainty 0.1`. Exit code `2`. stdout is empty. stderr contains `BenchmarkLabel join file`. The label digest is still the first digest.
- **Ask for a missing name.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature rank-joins --entry "prw rank missing image" --step missing -- rank --image piece-a "$IMAGES/fragment-0.tif" --image piece-b "$FRAGMENT_B_PATH" --foreground-threshold 1 --code-version "$CODE" --pixels-per-mm 10 --uncertainty 0.1`. Exit code `2`. stdout is empty. stderr contains `Fragment files:` and every name on the doctor `fragments` line. stderr does not contain `Traceback`.
- **Proof.** The evidence directory contains `order`, `unscaled`, `refuse-label`, and `missing`.

## Gotchas

- The pool flag is repeated `--image LABEL PATH`. A positional path exits `2` and names `--image` as required.
- Omitting the scale pair prints `FailedPairwiseJoin`. That is a completed failure record, not an empty ranking.
- `labels.json` contains join rows. Rank refuses it. Do not open it to judge whether the printed order is the correct join.
- Rank does not rewrite `labels.json`. The `shasum` before and after is the observation that it stayed put.
- Scores are ordered inside the `physical` channel. The command does not print a cross-type order.
