# Rank assemblies

Rank assemblies prints the assemblies that the search kept, in the physical channel. On this seed the first and third sorted fragments produce two rows. Scores do not increase down the list. Every row is a hypothesis.

## Sub-features

- `assembly-rank-order` prints `physical_assembly_order` for the seeded pair.
- `assembly-rank-claimed-ppi` rejects `--claimed-ppi`.

## How to get to it (user POV)

- Run `prw assembly-rank` with the same pool, scale, N, tolerance, and page-bound flags as `prw assemble`.
- Pass `--claimed-ppi N` without the measurement pair. The command rejects the claim.

## Driving it with verify-prw

Preconditions:

- Doctor prints `prw-verify doctor ok` for this run.
- `exports` has set `$RUN_ID`, `$CODE`, `$IMAGES`, and `$BENCHMARKS`.
- Bind the first and third fragment paths in sorted file-name order:

```bash
PIECE_A=$(printf '%s\n' "$IMAGES"/fragment-*.tif | sort | sed -n '1p')
PIECE_B=$(printf '%s\n' "$IMAGES"/fragment-*.tif | sort | sed -n '3p')
```

- **Record the label file.** Run `shasum -a 256 "$BENCHMARKS/labels.json"` and keep the digest.
- **Reject a claimed resolution.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature assembly-rank --entry "prw assembly-rank --claimed-ppi" --step claimed-ppi -- assembly-rank --image piece-a "$PIECE_A" --image piece-b "$PIECE_B" --foreground-threshold 1 --code-version "$CODE" --claimed-ppi 400 --minimum-edge-length-mm 6 --n 2 --translation-tolerance-mm 1 --rotation-tolerance-radians 1 --min-width-mm 0 --max-width-mm 1000 --min-height-mm 0 --max-height-mm 1000`. Exit code `2`. stdout is empty. stderr contains `A claimed resolution does not populate calibration.`
- **Rank the kept assemblies.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature assembly-rank --entry "prw assembly-rank two images" --step order -- assembly-rank --image piece-a "$PIECE_A" --image piece-b "$PIECE_B" --foreground-threshold 1 --code-version "$CODE" --pixels-per-mm 10 --uncertainty 0.1 --minimum-edge-length-mm 6 --n 2 --translation-tolerance-mm 1 --rotation-tolerance-radians 1 --min-width-mm 0 --max-width-mm 1000 --min-height-mm 0 --max-height-mm 1000`. Exit code `0`. `record` is `physical_assembly_order`. `assemblies` has two objects. Each `score` is less than or equal to the previous score. Every `epistemic_class` is `hypothesis`. Every `channel` is `physical`. `envelope.algorithm_name` is `rigid_assembly_search`. Stdout does not contain `correct_join`.
- **Label file is unchanged.** `shasum -a 256 "$BENCHMARKS/labels.json"` prints the same digest as the first reading.
- **Proof.** The evidence directory contains `claimed-ppi` and `order`.

## Gotchas

- The command prints the physical order of the assemblies the search kept. It does not read `labels.json` to choose that order.
- `--claimed-ppi` does not populate calibration. Pass it without the measurement pair to see the exit `2` refusal.
- Rank 1 in this list is a hypothesis.
