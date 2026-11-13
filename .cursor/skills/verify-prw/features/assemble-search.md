# Search assemblies

Search assemblies prints rigid assemblies for two seeded fragments, a predeclared N, two pose tolerances, a minimum edge length, and a page rectangle in millimetres. On this seed the first and third sorted fragments keep two assemblies. A missing N or a missing page rectangle prints `FailedAssemblySearch` and no placement.

## Sub-features

- `assemble-kept` prints `AssemblySearch` with two assemblies.
- `assemble-missing-n` prints `FailedAssemblySearch` when `--n` is omitted.
- `assemble-missing-page` prints `FailedAssemblySearch` when the four page bounds are omitted.
- `assemble-claimed-ppi` rejects `--claimed-ppi`.

## How to get to it (user POV)

- Run `prw assemble --image LABEL PATH --image LABEL PATH --foreground-threshold N --code-version CODE --pixels-per-mm N --uncertainty N --minimum-edge-length-mm N --n N --translation-tolerance-mm N --rotation-tolerance-radians N --min-width-mm N --max-width-mm N --min-height-mm N --max-height-mm N` in a terminal.
- Pass `--claimed-ppi N` without the measurement pair. The command rejects the claim.

## Driving it with verify-prw

Preconditions:

- Doctor prints `prw-verify doctor ok` for this run.
- `exports` has set `$RUN_ID`, `$CODE`, `$IMAGES`, and `$BENCHMARKS`.
- Bind the first and third fragment paths in sorted file-name order. On this seed that pair is the section 2 pair in [Using the workbench](../../../../docs/USAGE.md):

```bash
PIECE_A=$(printf '%s\n' "$IMAGES"/fragment-*.tif | sort | sed -n '1p')
PIECE_B=$(printf '%s\n' "$IMAGES"/fragment-*.tif | sort | sed -n '3p')
```

- **Record the label file.** Run `shasum -a 256 "$BENCHMARKS/labels.json"` and keep the digest.
- **Reject a claimed resolution.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature assemble-search --entry "prw assemble --claimed-ppi" --step claimed-ppi -- assemble --image piece-a "$PIECE_A" --image piece-b "$PIECE_B" --foreground-threshold 1 --code-version "$CODE" --claimed-ppi 400 --minimum-edge-length-mm 6 --n 2 --translation-tolerance-mm 1 --rotation-tolerance-radians 1 --min-width-mm 0 --max-width-mm 1000 --min-height-mm 0 --max-height-mm 1000`. Exit code `2`. stdout is empty. stderr contains `A claimed resolution does not populate calibration.`
- **Search the pair.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature assemble-search --entry "prw assemble two images" --step kept -- assemble --image piece-a "$PIECE_A" --image piece-b "$PIECE_B" --foreground-threshold 1 --code-version "$CODE" --pixels-per-mm 10 --uncertainty 0.1 --minimum-edge-length-mm 6 --n 2 --translation-tolerance-mm 1 --rotation-tolerance-radians 1 --min-width-mm 0 --max-width-mm 1000 --min-height-mm 0 --max-height-mm 1000`. Exit code `0`. `record` is `AssemblySearch`. `assemblies` has two objects. `screening` is non-empty, and each `gate` is `physical`. `envelope.algorithm_name` is `rigid_assembly_search`. Every assembly `epistemic_class` is `hypothesis`. Stdout does not contain `correct_join` or `truth`.
- **Omit N.** Run the search command with `--step missing-n` and without `--n 2`. Exit code `1`. `record` is `FailedAssemblySearch`. `status` is `failed`. The object has no `assemblies` key. Stdout does not contain `placement`.
- **Omit the page bounds.** Run the search command with `--step missing-page` and without `--min-width-mm`, `--max-width-mm`, `--min-height-mm`, and `--max-height-mm`. Exit code `1`. `record` is `FailedAssemblySearch`. `status` is `failed`. The object has no `assemblies` key. Stdout does not contain `placement`.
- **Label file is unchanged.** `shasum -a 256 "$BENCHMARKS/labels.json"` prints the same digest as the first reading.
- **Proof.** The evidence directory contains `claimed-ppi`, `kept`, `missing-n`, and `missing-page`.

## Gotchas

- The pool flag is repeated `--image LABEL PATH`. This recipe uses the first and third sorted files. The first and second sorted files are one raster twice.
- `--claimed-ppi` is passed without `--pixels-per-mm`. The command exits `2` and writes no assembly.
- Omitting `--n`, or omitting the four page-bound flags, prints `FailedAssemblySearch`. That object has no `assemblies` key.
- Assemblies stay hypotheses. The command does not rewrite `labels.json`.
