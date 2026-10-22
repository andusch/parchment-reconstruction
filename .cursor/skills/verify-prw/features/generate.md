# Generate a synthetic leaf

Generate writes one seeded synthetic leaf: uncompressed fixture TIFFs, an image manifest of `sha256:` digests, and BenchmarkLabel rows under the benchmarks directory. The printed record is the provenance envelope and the image list. It does not claim a real manuscript joined.

## Sub-features

- `generate-write` writes the leaf under the caller-supplied benchmarks and images directories.
- `generate-provenance` prints the parameter blob, its `sha256:` parameter hash, and the random seed.
- `generate-refuse-project` refuses a destination that is inside a project evidence database.

## How to get to it (user POV)

- Run `python -m prw.cli generate` with `--benchmarks`, `--images`, `--missing-fragment-percentage`, `--edge-erosion`, `--rotation`, `--lighting-variation`, `--random-seed`, and `--code-version`.

## Driving it with verify-prw

Preconditions:

- `verify-prw doctor` printed `doctor_ok=yes` for this root.
- `$SCRATCH_BENCHMARKS` and `$SCRATCH_IMAGES` exist, are empty, and are the paths doctor printed.
- `$CODE_VERSION` is the short git SHA launch recorded.

- **Write the leaf.** Run the generator into the empty scratch directories. Run `.cursor/skills/verify-prw/bin/verify-prw drive --feature generate --step write-leaf -- generate --benchmarks "$SCRATCH_BENCHMARKS" --images "$SCRATCH_IMAGES" --missing-fragment-percentage 0 --edge-erosion 0 --rotation 0.2 --lighting-variation 0.4 --random-seed 7 --code-version "$CODE_VERSION"`. Exit code `0`. Stdout is one JSON object whose `provenance.random_seed` is `7`, whose `provenance.parameter_hash` starts with `sha256:`, and whose `provenance.parameter_blob` contains `lighting_variation`. Stdout does not contain `correct_join` or `hypothesis`. Stderr is empty.
- **Confirm stored files.** Read the scratch tree back. Run `.cursor/skills/verify-prw/bin/verify-prw observe --feature generate --step write-leaf`. `side_effects.txt` lists `benchmarks/labels.json`, `benchmarks/provenance.json`, `images/image_manifest.json`, `images/page.tif`, and one `images/fragment-*.tif` for every fragment entry in the printed `images` list. With these parameters that list has `page.tif` and four fragment images. Each printed `content_hash` equals `sha256:` plus the `sha256` of that file in `side_effects.txt`, and each printed `byte_length` equals that file's `size`. `manifest_json=absent`. `originals=absent`. No file sits outside `benchmarks/` and `images/`.
- **Refuse a project directory name.** Create a disposable destination whose path contains `originals`. Run `mkdir -p "$PRW_VERIFY_ROOT/scratch/originals"` and `.cursor/skills/verify-prw/bin/verify-prw drive --feature generate --step refuse-originals -- generate --benchmarks "$PRW_VERIFY_ROOT/scratch/originals" --images "$SCRATCH_IMAGES" --missing-fragment-percentage 0 --edge-erosion 0 --rotation 0 --lighting-variation 0 --random-seed 1 --code-version "$CODE_VERSION"`. Exit code `2`. Stdout is empty. Stderr contains `project evidence database`. `images/page.tif` is unchanged from the write-leaf hashes.
- **Refuse a parent manifest.** Point generate at a directory whose parent already holds `manifest.json`. Run `mkdir -p "$PRW_VERIFY_ROOT/scratch/probe/child"`, `printf '%s\n' '{}' > "$PRW_VERIFY_ROOT/scratch/probe/manifest.json"`, and `.cursor/skills/verify-prw/bin/verify-prw drive --feature generate --step refuse-manifest -- generate --benchmarks "$PRW_VERIFY_ROOT/scratch/probe/child" --images "$PRW_VERIFY_ROOT/scratch/probe/child" --missing-fragment-percentage 0 --edge-erosion 0 --rotation 0 --lighting-variation 0 --random-seed 1 --code-version "$CODE_VERSION"`. Exit code `2`. Stdout is empty. Stderr contains `project evidence database`. The write-leaf `benchmarks/labels.json` hash is unchanged.

## Gotchas

- The same seed and parameters reproduce the same TIFF bytes. A second generate into a non-empty images directory overwrites those files. Prove `generate-write` from an empty scratch.
- This harness keeps benchmarks and images in sibling directories. The CLI also accepts one directory for both. Do not retarget the recipe at the git checkout to make that point.
- Path parts `originals`, `observations`, `runs`, `validations`, and `exports` are refused. A parent `manifest.json` is refused. Both refusals exit `2` with an empty stdout.
- Generate writes TIFF files under scratch. Evidence keeps names and hashes only. Do not commit the TIFFs or `labels.json`.
- Stdout is canonical JSON. There is no human-readable summary after it.
- `generate-refuse-project` is unreachable until the driver creates the disposable probe directories under this run's scratch. If those directories were not created, report that unmet precondition. Do not point the refusal at the checkout, and do not treat the successful write as the refusal proof.
