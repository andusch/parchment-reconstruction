# Rank pairwise joins

Rank segments a pool of fixture images and prints pairwise joins in physical-score order. Each join is a hypothesis on the `physical` channel. The command takes a repeated `--image LABEL PATH` pair. It does not read the BenchmarkLabel store. A join-label file passed as an image is refused.

## Sub-features

- `rank-order` prints `physical_join_order` for two scaled fragment images, highest score first.
- `rank-no-scale` exits `1` with `FailedPairwiseJoin` when the scale pair is omitted.
- `rank-flag` exits `2` when the pool is passed as bare paths and `--label` instead of `--image`.
- `rank-refuse-label` exits `2` when an image path is the BenchmarkLabel `labels.json`, and does not change that file.
- `rank-missing` exits `2` when one pool path is absent and names the fragment files in the sibling manifest.

## How to get to it (user POV)

- Run `python -m prw.cli rank --image <label> <path> --image <label> <path> --foreground-threshold <int> --code-version <version> --pixels-per-mm <float> --uncertainty <float>`.
- Repeat `--image` once per fragment. The label and the path are the two arguments of that flag.

## Driving it with verify-prw

Preconditions:

- `verify-prw doctor` printed `doctor_ok=yes` for this root.
- [Generate a synthetic leaf](./generate.md) has completed `generate-write` with `--missing-fragment-percentage 0`, so at least three `fragment-*.tif` files are in `$SCRATCH_IMAGES`. If fewer than three exist, stop and report that unmet precondition.
- Save `LABELS_HASH` from `sha256sum "$SCRATCH_BENCHMARKS/labels.json"` before any rank command. Rank must not change it.

- **Choose two fragments.** Sort the fragment file names and take the first and the third. Run `uv run python -c 'import sys; from pathlib import Path; names=sorted(path.name for path in Path(sys.argv[1]).glob("fragment-*.tif")); print(names[0]); print(names[2])' "$SCRATCH_IMAGES"`. Save them as `FRAGMENT_A` and `FRAGMENT_B`.
- **Physical order.** Run `.cursor/skills/verify-prw/bin/verify-prw drive --feature rank --step order -- rank --image piece-a "$SCRATCH_IMAGES/$FRAGMENT_A" --image piece-b "$SCRATCH_IMAGES/$FRAGMENT_B" --foreground-threshold 1 --code-version "$CODE_VERSION" --pixels-per-mm 10 --uncertainty 0.1`. Exit code `0`. Stdout is JSON with `record` `physical_join_order` and a non-empty `joins` list. The `score` values are sorted highest first. Every join has `epistemic_class` `hypothesis` and `channel` `physical`. `envelope.algorithm_name` is `pairwise_rigid_join`. Stdout does not contain `correct_join` or `pose`. Stderr is empty. `sha256sum` of `labels.json` is still `LABELS_HASH`.
- **No scale.** Run `.cursor/skills/verify-prw/bin/verify-prw drive --feature rank --step no-scale -- rank --image piece-a "$SCRATCH_IMAGES/$FRAGMENT_A" --image piece-b "$SCRATCH_IMAGES/$FRAGMENT_B" --foreground-threshold 1 --code-version "$CODE_VERSION"`. Exit code `1`. `record` is `FailedPairwiseJoin` and `status` is `failed`. Stdout does not contain `joins`, `pose`, or `translation`. `labels.json` is still `LABELS_HASH`.
- **Wrong pool flag.** Run `.cursor/skills/verify-prw/bin/verify-prw drive --feature rank --step bad-flag -- rank "$SCRATCH_IMAGES/$FRAGMENT_A" --label piece-a "$SCRATCH_IMAGES/$FRAGMENT_B" --label piece-b --foreground-threshold 1 --code-version "$CODE_VERSION" --pixels-per-mm 10 --uncertainty 0.1`. Exit code `2`. Stdout is empty. Stderr contains `the following arguments are required: --image` and does not contain `Traceback`. `labels.json` is still `LABELS_HASH`.
- **Refuse a join label.** Run `.cursor/skills/verify-prw/bin/verify-prw drive --feature rank --step refuse-label -- rank --image piece-a "$SCRATCH_BENCHMARKS/labels.json" --foreground-threshold 1 --code-version "$CODE_VERSION" --pixels-per-mm 10 --uncertainty 0.1`. Exit code `2`. Stdout is empty. Stderr contains `BenchmarkLabel join file`. `sha256sum` of `labels.json` is still `LABELS_HASH`.
- **Missing image.** Run `.cursor/skills/verify-prw/bin/verify-prw drive --feature rank --step missing -- rank --image piece-a "$SCRATCH_IMAGES/fragment-0.tif" --image piece-b "$SCRATCH_IMAGES/$FRAGMENT_B" --foreground-threshold 1 --code-version "$CODE_VERSION" --pixels-per-mm 10 --uncertainty 0.1`. Exit code `2`. Stdout is empty. Stderr contains `fragment-0.tif`, `Fragment files:`, and each real `fragment-*.tif` name, and does not contain `Traceback`. `labels.json` is still `LABELS_HASH`.

## Gotchas

- A pool image is one `--image LABEL PATH` pair, repeated. A bare path plus `--label` does not parse. The error asks for `--image`.
- Without the scale pair, pairwise join fails. Exit `1` and `FailedPairwiseJoin` are the expected observation.
- `labels.json` is ground truth written by generate. Rank must not be given that file as an image, and a refusal must not change its bytes. Do not edit it to make a later score look right.
- `fragment-0.tif` is not a generated name. Generated names look like `fragment-<uuid>.tif`. The missing-path check depends on that absent name beside a real manifest.
- Joins are hypotheses on the `physical` channel. The record must not contain `correct_join` or `pose`.
- `rank-missing` assumes `fragment-0.tif` was not produced. If a future generator uses that exact name, the missing-path step needs a different absent name. Do not delete a real fragment to force the check.
