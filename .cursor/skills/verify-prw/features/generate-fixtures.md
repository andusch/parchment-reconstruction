# Generate a synthetic leaf

Generate a synthetic leaf writes fixture TIFFs, an image manifest, and BenchmarkLabel rows under caller-chosen directories. The same parameters write the same page hash. A destination inside a project-directory name is refused before any file is created.

## Sub-features

- `generate-write` writes the leaf, the manifest, and the benchmark rows.
- `generate-repeat` writes a second leaf with the same page hash.
- `generate-refuse` refuses a destination whose path contains `originals`.

## How to get to it (user POV)

- Run `prw generate --benchmarks DIR --images DIR --missing-fragment-percentage 0 --edge-erosion 0 --rotation 0 --lighting-variation 0 --random-seed 3 --code-version CODE` in a terminal.

## Driving it with verify-prw

Preconditions:

- Doctor prints `prw-verify doctor ok` for this run.
- `exports` has set `$RUN_ID`, `$SCRATCH`, `$CODE`, and `$PAGE`.
- `$SCRATCH/leaf-a` and `$SCRATCH/leaf-b` do not exist.

- **Write a leaf.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature generate-fixtures --entry "prw generate leaf" --step write -- generate --benchmarks "$SCRATCH/leaf-a/benchmarks" --images "$SCRATCH/leaf-a/images" --missing-fragment-percentage 0 --edge-erosion 0 --rotation 0 --lighting-variation 0 --random-seed 3 --code-version "$CODE"`. Exit code `0`. JSON `provenance.random_seed` is `3`, `provenance.algorithm_name` is `synthetic_tear`, and `provenance.parameter_hash` starts with `sha256:`. The `images` array contains an object with `name` `page.tif` and `role` `page`. Stdout does not contain `hypothesis` or `correct_join`.
- **Confirm the files.** `$SCRATCH/leaf-a/benchmarks/labels.json`, `$SCRATCH/leaf-a/benchmarks/provenance.json`, `$SCRATCH/leaf-a/images/image_manifest.json`, and `$SCRATCH/leaf-a/images/page.tif` exist. At least one `fragment-*.tif` exists beside the page. `$SCRATCH/leaf-a/benchmarks/manifest.json` does not exist. `$SCRATCH/leaf-a/originals` does not exist.
- **Confirm the page hash.** `shasum -a 256 "$SCRATCH/leaf-a/images/page.tif"` prints the hex digest inside the stdout `page.tif` `content_hash`, without the `sha256:` prefix.
- **Repeat the leaf.** Run the same command with `--step repeat`, `$SCRATCH/leaf-b/benchmarks`, and `$SCRATCH/leaf-b/images`. Exit code `0`. The `page.tif` `content_hash` equals the first leaf.
- **Refuse a project directory name.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature generate-fixtures --entry "prw generate originals" --step refuse -- generate --benchmarks "$SCRATCH/refused-benchmarks" --images "$SCRATCH/originals/images" --missing-fragment-percentage 0 --edge-erosion 0 --rotation 0 --lighting-variation 0 --random-seed 3 --code-version "$CODE"`. Exit code `2`. stdout is empty. stderr contains `project evidence database`. `$SCRATCH/refused-benchmarks` and `$SCRATCH/originals` do not exist.
- **Seed survives.** Run doctor again. It prints `prw-verify doctor ok`, and `$PAGE` is still a file.
- **Proof.** The evidence directory contains `write`, `repeat`, and `refuse`.

## Gotchas

- A path component `originals`, `observations`, `runs`, `validations`, or `exports` is refused. A parent that already holds `manifest.json` is refused with `That destination is inside a project evidence database.`
- Writing into `$IMAGES` or `$BENCHMARKS` replaces the seeded page. Later verify, segment, and rank recipes then fail doctor or see different bytes. Write under `$SCRATCH`.
- The same seed and parameters reproduce the page hash. This recipe uses random seed `3` so the second leaf can match the first. It does not claim that a different seed matches.
- `labels.json` is the BenchmarkLabel store. Rank refuses that file as an image path. Do not read it to decide whether a generated join is correct.
