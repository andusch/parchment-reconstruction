# Report character error

Report character error writes a frozen synthetic line fixture under scratch, then a character-error report beside that fixture's labels. The first report states that no previous character-error report exists. The seeded leaf's `labels.json` stays unchanged. The command does not download weights.

## Sub-features

- `character-error-fixture` writes the frozen line images and BenchmarkLabel rows.
- `character-error-report` writes `character_error_rate` for that fixture.
- `character-error-missing-model` rejects a missing `medium.safetensors` and writes no report.

## How to get to it (user POV)

- Run `prw character-error --generate-fixture` with a benchmarks directory and an images directory.
- Run `prw character-error` again without `--generate-fixture` to score that fixture.
- Pass `--model` pointing at a path that is not a local `medium.safetensors`. The command rejects it.

## Driving it with verify-prw

Preconditions:

- Doctor prints `prw-verify doctor ok` for this run.
- `exports` has set `$RUN_ID`, `$CODE`, `$SCRATCH`, and `$BENCHMARKS`.
- The line fixture uses `$SCRATCH/lines/benchmarks` and `$SCRATCH/lines/images`. It does not use the seeded `$BENCHMARKS`.

- **Record the seeded label file.** Run `shasum -a 256 "$BENCHMARKS/labels.json"` and keep the digest.
- **Write the fixture.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature character-error --entry "prw character-error --generate-fixture" --step fixture -- character-error --generate-fixture --benchmarks "$SCRATCH/lines/benchmarks" --images "$SCRATCH/lines/images" --code-version "$CODE"`. Exit code `0`. `provenance.algorithm_name` is `synthetic_line_fixture`. The provenance object has no `random_seed` key. `$SCRATCH/lines/benchmarks/labels.json` exists. `$SCRATCH/lines/benchmarks/manifest.json` does not exist. `$SCRATCH/lines/images/line-exact.tif` exists.
- **Record the line label file.** Run `shasum -a 256 "$SCRATCH/lines/benchmarks/labels.json"` and keep the digest.
- **Write the report.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature character-error --entry "prw character-error synthetic lines" --step report -- character-error --benchmarks "$SCRATCH/lines/benchmarks" --images "$SCRATCH/lines/images" --code-version "$CODE"`. Exit code `0`. `metric` is `character_error_rate`. `algorithm_name` is `synthetic_line_slots`. `model_hash` is `absent`. `random_seed` is `absent`. `claim` is `synthetic-fixture result`. `edit_distance` is `1`. `reference_length` is `22`. `scored_line_count` is `5`. `unscored_line_count` is `3`. `abbreviations_expanded` is false. `previous_report` is `absent`. `previous_report_statement` is `No previous character-error report exists.`. `does_not_measure` is `Ancient Greek handwriting, scholarly acceptability, or the PP-OCRv6 medium model card`. Stdout does not contain `7.21`, `44.03`, or `correct_join`. The file `$SCRATCH/lines/benchmarks/character_error/character-error-0001.json` exists.
- **Label files are unchanged.** The line-fixture `shasum` matches the reading taken after the fixture step. The seeded `$BENCHMARKS/labels.json` digest matches the first reading.
- **Reject a missing model.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature character-error --entry "prw character-error --model missing" --step missing-model -- character-error --benchmarks "$SCRATCH/lines/benchmarks" --images "$SCRATCH/lines/images" --code-version "$CODE" --model "$SCRATCH/lines/medium.safetensors"`. Exit code `2`. stdout is empty. stderr contains `does not download weights`. `$SCRATCH/lines/benchmarks/character_error/character-error-0002.json` does not exist.
- **Proof.** The evidence directory contains `fixture`, `report`, and `missing-model`.

## Gotchas

- The report scores frozen `kind: line` rows. It does not feed those rows into `recognize`. Do not open `labels.json` to decide whether the rate is small enough.
- `does_not_measure` states the limit: this number is not Ancient Greek handwriting and not the model card.
- `--model` without a local `medium.safetensors` exits `2` before another report file is created. The command does not download weights.
- The fixture directory is under `$SCRATCH`. Scoring the seeded leaf's `labels.json` is a different store and is not this feature.
