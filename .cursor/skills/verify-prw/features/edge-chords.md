# Trace chord edges

Trace chord edges prints chord edges for one seeded TIFF once a caller-supplied scale is present. Without that scale the command prints `FailedEdgeChord` and no geometry.

## Sub-features

- `edge-millimetres` prints `ChordEdges` for a millimetre outline.
- `edge-pixels` prints `FailedEdgeChord` when the scale pair is omitted.

## How to get to it (user POV)

- Run `prw edge PATH --label LABEL --foreground-threshold N --code-version CODE --pixels-per-mm N --uncertainty N` in a terminal.

## Driving it with verify-prw

Preconditions:

- Doctor prints `prw-verify doctor ok` for this run.
- `exports` has set `$RUN_ID`, `$CODE`, and `$FRAGMENT_A_PATH`.

- **Trace millimetre chords.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature edge-chords --entry "prw edge fragment" --step millimetres -- edge "$FRAGMENT_A_PATH" --label shelf-4 --foreground-threshold 1 --code-version "$CODE" --pixels-per-mm 10 --uncertainty 0.1`. Exit code `0`. `record` is `ChordEdges`. `edges` is non-empty. Each `epistemic_class` is `interpretation`. `envelope.algorithm_name` is `edge_chord`. `envelope.model_hash` is `absent`. The `random_seed` key is absent. Stdout does not contain `correct_join` or `pose`.
- **Omit the scale.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature edge-chords --entry "prw edge fragment without scale" --step pixels -- edge "$FRAGMENT_A_PATH" --label shelf-4 --foreground-threshold 1 --code-version "$CODE"`. Exit code `1`. `record` is `FailedEdgeChord`. `status` is `failed`. The object has no `edges` key. Stdout does not contain `geometry` or `pose`.
- **Proof.** The evidence directory contains `millimetres` and `pixels`.

## Gotchas

- `--pixels-per-mm` and `--uncertainty` are supplied together. The unscaled command is a completed `FailedEdgeChord`, not an empty edge list.
- The printed edges do not include the label `shelf-4`.
