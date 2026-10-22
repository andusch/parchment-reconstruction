# Parchment-workbench CLI verification map

This directory is the maintained source for verifying the headless `prw` CLI. Read this index, then use the matching feature file as the recipe. The desktop Qt shell is not implemented. Do not invent a window to drive.

## Baseline preconditions

- Launch with `.cursor/skills/verify-prw/bin/verify-prw launch` from the repository root.
- Export `PRW_VERIFY_ROOT`, `SCRATCH_BENCHMARKS`, `SCRATCH_IMAGES`, `EVIDENCE`, and `CODE_VERSION` from that output.
- Leave both scratch directories empty until a recipe writes them. Launch does not seed a leaf.
- Run `.cursor/skills/verify-prw/bin/verify-prw doctor` and require `doctor_ok=yes` for this root.
- Never drive a root that this verification run did not launch.
- Never pass a path inside the git checkout, `data/`, `scans/`, or `real_data/`.

## Driving conventions

- Start every recipe from the baseline empty scratch unless its preconditions say a synthetic leaf is already present.
- Treat every command as literal. Keep flags and quoted values unchanged.
- Run CLI actions through `verify-prw drive`. Record writes through `verify-prw observe`.
- A domain failure with exit `1` and a JSON record on stdout is an observation. A traceback is not.
- Restore nothing by editing BenchmarkLabel rows. Cleanup deletes the whole scratch tree.
- Do not remove `$EVIDENCE` during cleanup.

## Proof and skip reporting

- Capture the command, the pane, stdout, stderr, and the exit code.
- For a write, capture `side_effects.txt` and match printed hashes to those file hashes.
- Record the feature id and the step name on every artifact (`--feature`, `--step`).
- Report an unreachable path with the command that was not run and the unmet precondition.
- Do not report a skipped entry point as verified through a different command.

## Feature entry contract

Each feature file starts with an H1 and one paragraph of user-visible behavior, then exactly these H2 sections, in order:

1. `Sub-features`
2. `How to get to it (user POV)`
3. `Driving it with verify-prw`
4. `Gotchas`

## Features

- [Generate a synthetic leaf](./generate.md) writes fixture images, the image manifest, and BenchmarkLabel rows, and refuses a project-shaped destination.
- [Verify a fixture image](./verify.md) hashes a presented TIFF, reports an integrity failure, and names missing fragment files.
- [Segment a fragment](./segment.md) prints a machine outline in source pixels or fragment-local millimetres.
- [Trace chord edges](./edge.md) prints millimetre chord edges, or a failed chord run when scale is omitted.
- [Rank pairwise joins](./rank.md) prints physical-channel join hypotheses for a pool of fixture images.

## Not in this seed

`frame`, `provenance`, `agree`, and `recall` are real `prw` commands. They have no feature file yet. Do not mark them verified by driving one of the five files above.
