# Recognize a line

Recognize a line reads one operator-supplied line image with a local `medium.safetensors` file. The checks below refuse a missing weight path and a missing `htr` group. They do not download weights and they do not print a reading.

## Sub-features

- `recognize-missing-weight` rejects a model path that is not a local `medium.safetensors` file.
- `recognize-missing-group` rejects the command when the `htr` group is not installed.

## How to get to it (user POV)

- Run `prw recognize LINE --model PATH --label LABEL --code-version CODE` in a terminal.
- Install the optional group with `uv sync --group htr` before a run that has a local weight file. This feature does not install it and does not fetch weights.

## Driving it with verify-prw

Preconditions:

- Doctor prints `prw-verify doctor ok` for this run.
- `exports` has set `$RUN_ID`, `$CODE`, and `$SCRATCH`.
- The `htr` group is not installed. A checkout that has Kraken installed does not show the missing-group refusal.

- **Reject a missing weight.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature recognize-line --entry "prw recognize missing weight" --step missing-weight -- recognize "$SCRATCH/line.tif" --model "$SCRATCH/no-such/medium.safetensors" --label shelf-4 --code-version "$CODE"`. Exit code `2`. stdout is empty. stderr contains `does not download weights`. stderr contains `medium.safetensors`.
- **Reject a missing group.** Write the bytes `not-weights` to `$SCRATCH/medium.safetensors`. Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature recognize-line --entry "prw recognize missing htr group" --step missing-group -- recognize "$SCRATCH/line.tif" --model "$SCRATCH/medium.safetensors" --label shelf-4 --code-version "$CODE"`. Exit code `2`. stdout is empty. stderr contains `uv sync --group htr`. The line image does not need to exist. The command checks the group after it finds the weight file and before it reads the image. A checkout with Kraken installed continues to the missing image instead of this refusal.
- **Proof.** The evidence directory contains `missing-weight` and `missing-group`. Neither transcript downloads a weight file.

## Gotchas

- The weight file stays outside Git and outside this instance. Do not fetch `medium.safetensors` to make the command succeed.
- A successful recognition needs both the `htr` group and a local `medium.safetensors`. This feature does not drive that success.
- The command does not find lines on a page. The image, when one is supplied, is already one line.
- `$CODE` is the doctor export. A dirty worktree does not change that SHA.
