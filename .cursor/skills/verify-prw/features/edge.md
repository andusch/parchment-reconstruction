# Trace chord edges

Edge segments one fixture image and prints chord edges. With a caller-supplied scale the record is `ChordEdges` in millimetres and each edge is an interpretation. Without a scale the run fails as `FailedEdgeChord` and prints no geometry.

## Sub-features

- `edge-mm` prints millimetre chords when pixels per millimetre and uncertainty are both supplied.
- `edge-pixels` exits `1` with `FailedEdgeChord` when the outline stays in source pixels.
- `edge-scale-pair` exits `2` when only one of the two scale flags is present.

## How to get to it (user POV)

- Run `python -m prw.cli edge <path> --label <label> --foreground-threshold <int> --code-version <version> --pixels-per-mm <float> --uncertainty <float>`.
- Omit the scale pair to see the pixel-frame failure.

## Driving it with verify-prw

Preconditions:

- `verify-prw doctor` printed `doctor_ok=yes` for this root.
- [Generate a synthetic leaf](./generate.md) has completed `generate-write` in this scratch. If no `fragment-*.tif` is in `$SCRATCH_IMAGES`, stop and report that unmet precondition.

- **Choose the fragment.** Use the same manifest selection as [segment](./segment.md). Save `FRAGMENT_NAME`. The file is `$SCRATCH_IMAGES/$FRAGMENT_NAME`.
- **Millimetre chords.** Run `.cursor/skills/verify-prw/bin/verify-prw drive --feature edge --step millimetre -- edge "$SCRATCH_IMAGES/$FRAGMENT_NAME" --label shelf-4 --foreground-threshold 1 --code-version "$CODE_VERSION" --pixels-per-mm 10 --uncertainty 0.1`. Exit code `0`. Stdout is JSON with `record` `ChordEdges` and a non-empty `edges` list. Every edge has `epistemic_class` `interpretation`. `envelope.algorithm_name` is `edge_chord`, `envelope.model_hash` is `absent`, and `random_seed` is absent. Stdout does not contain `correct_join` or `pose`. Stderr is empty.
- **Pixel frame.** Run `.cursor/skills/verify-prw/bin/verify-prw drive --feature edge --step pixels -- edge "$SCRATCH_IMAGES/$FRAGMENT_NAME" --label shelf-4 --foreground-threshold 1 --code-version "$CODE_VERSION"`. Exit code `1`. Stdout is JSON with `record` `FailedEdgeChord`, `status` `failed`, and a `run_id`. Stdout does not contain `geometry`, `pose`, or `translation`.
- **Half a scale.** Run `.cursor/skills/verify-prw/bin/verify-prw drive --feature edge --step half-scale -- edge "$SCRATCH_IMAGES/$FRAGMENT_NAME" --label shelf-4 --foreground-threshold 1 --code-version "$CODE_VERSION" --uncertainty 0.1`. Exit code `2`. Stdout is empty. Stderr contains `pixels_per_mm and uncertainty are supplied together`.

## Gotchas

- Omitting the scale is a successful observation of `FailedEdgeChord`, not a broken install. Exit `1` with that record is the expected pixel-frame result.
- Edges are interpretations. They are not joins and they do not carry a pose.
- `--minimum-edge-length-mm` defaults to `0`. Leave it unset in this recipe.
- The scale flags are a pair, same as segment. Supplying one of them is exit `2`.
