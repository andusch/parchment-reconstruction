# Record provenance

Record provenance prints one provenance envelope. A deterministic call omits `random_seed`. The same arguments print the same envelope, including its id.

## Sub-features

- `provenance-deterministic` omits `random_seed` and repeats exactly.
- `provenance-seeded` records `random_seed` `7`.
- `provenance-bad-parameter` rejects a parameter value that is not JSON.

## How to get to it (user POV)

- Run `prw provenance --algorithm-name NAME --algorithm-version VERSION --code-version CODE --parameter NAME=JSON` in a terminal.
- Add `--random-seed N` when the algorithm used randomness.

## Driving it with verify-prw

Preconditions:

- Doctor prints `prw-verify doctor ok` for this run.
- `exports` has set `$RUN_ID` and `$CODE`.

- **Print a deterministic envelope.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature provenance-envelope --entry "prw provenance deterministic" --step deterministic -- provenance --algorithm-name demo --algorithm-version 1 --code-version "$CODE" --parameter edge_erosion=0.25`. Exit code `0`. The `random_seed` key is absent. `parameter_hash` starts with `sha256:`. The parsed `parameter_blob` is `{"edge_erosion": 0.25}`. `model_hash`, `decoder_name`, and `decoder_version` are `absent`. `source_hashes` is `[]`. `code_version` equals `$CODE`.
- **Repeat it.** Run the same command with `--step deterministic-repeat`. Exit code `0`. `stdout.txt` is byte-for-byte the same as the deterministic step, including `id`.
- **Record a seed.** Run the deterministic command with `--step seeded` and `--random-seed 7`. Exit code `0`. `random_seed` is `7`. stdout differs from the deterministic transcript.
- **Send a non-JSON parameter.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature provenance-envelope --entry "prw provenance bad parameter" --step bad-parameter -- provenance --algorithm-name demo --algorithm-version 1 --code-version "$CODE" --parameter edge_erosion=quarter`. Exit code `2`. stdout is empty. stderr contains `A parameter value is JSON.`
- **Proof.** The evidence directory contains `deterministic`, `deterministic-repeat`, `seeded`, and `bad-parameter`.

## Gotchas

- Omit `--random-seed` for a deterministic envelope. The key is absent. It is not present with a null value.
- `--parameter` takes one `name=json` argument. `edge_erosion=0.25` is a JSON number. `edge_erosion="0.25"` is a JSON string. `edge_erosion=quarter` is rejected.
- A repeated deterministic call matches the whole stdout. Compare the files rather than a single field.
- `code_version` is the string passed on the command line. Use `$CODE` so the envelope cites this checkout's HEAD. A dirty worktree does not change that SHA.
