# Parchment workbench verification map

This directory is the maintained source for verifying the user-facing behavior of the parchment-workbench CLI. Read this index before driving the app, then use the matching feature file as the recipe.

## Baseline preconditions

- The checkout root is the parchment-reconstruction repository, and `uv` is on `PATH`.
- Launch with `uv run python .cursor/skills/verify-prw/verify_prw.py launch`.
- Require the line `prw-verify ready <run-id>` before exporting variables or driving a feature.
- The instance is `$TMPDIR/prw-verify/<run-id>/`. It is outside the checkout. Its seed is one synthetic leaf: missing-fragment percentage `0`, edge erosion `0`, rotation `0`, lighting variation `0`, random seed `3`, and `code-version` equal to `git rev-parse HEAD` at launch.
- Export doctor fields with `eval "$(uv run python .cursor/skills/verify-prw/verify_prw.py exports --run RUN_ID)"`.
- Run `doctor --run "$RUN_ID"` and require `prw-verify doctor ok`, version `0.0.0`, and a `commands` line of `agree,assemble,assembly-rank,edge,frame,generate,join-presence,placement-error,provenance,rank,recall,segment,verify`.
- Drive only the instance this launch created. A second run id is a second instance. The same run id refuses a concurrent drive.
- There is no Qt shell, port, account, or project database. Do not open `data/`, `scans/`, `real_data/`, or a TIFF inside the checkout.
- `frame`, `agree`, `edge`, and `recall` are implemented commands and have no feature file. Do not report them as verified.

## Driving conventions

- Start every recipe from the seeded baseline unless its preconditions say otherwise.
- Treat every flag as literal. Substitute only the exported doctor variables, and keep those substitutions quoted.
- Run the CLI through `verify_prw.py run`. The helper exits with the CLI status. A non-zero status is the observation when the recipe says so.
- Parse stdout as one JSON object. Assert fields. A missing key is an assertion about the parsed object.
- A journey that writes a second leaf uses `$SCRATCH` and leaves `$IMAGES` and `$BENCHMARKS` in place.
- Restore nothing by editing the seed. Cleanup removes the instance. Do not remove proof artifacts during cleanup.

## Proof and skip reporting

- Capture the command, stdout, stderr, and exit code for each step.
- A checksum or ranking proof includes a second view of the bytes or of the label file the command must leave unchanged.
- Record the feature id and entry point. `meta.txt` stores both.
- Report an unreachable path with the attempted command and the unmet precondition.
- Do not report a skipped entry point as verified through a different command.

## Feature entry contract

Each feature file starts with an H1 title and one paragraph describing the user-visible behavior. It then uses exactly four H2 sections in this order.

1. `Sub-features` lists short IDs with one line for each behavior.
2. `How to get to it (user POV)` lists every user entry point.
3. `Driving it with verify-prw` starts with `Preconditions:` and uses labeled bullets that pair each user action with an exact command and observable result.
4. `Gotchas` lists traps that can waste or invalidate a verification run.

Keep implementation details out of the map. Name only user paths, stable handles, required state, commands, and observable proof.

## Features

- [Verify a source image](./verify-source.md) covers a matching checksum, a mismatch, a non-TIFF, and a missing path.
- [Generate a synthetic leaf](./generate-fixtures.md) covers writing a leaf, repeating it, and refusing a project-directory destination.
- [Segment a fragment](./segment-outline.md) covers a pixel outline, a millimetre outline, a checksum failure, and a missing path.
- [Rank joins](./rank-joins.md) covers physical order, a missing scale, a BenchmarkLabel path, and a missing image.
- [Record provenance](./provenance-envelope.md) covers a deterministic envelope, a seeded envelope, and a rejected parameter.
