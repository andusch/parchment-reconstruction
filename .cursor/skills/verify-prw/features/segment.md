# Segment a fragment

Segment reads one fixture TIFF and prints a `FragmentOutlineRevision`. Without a scale the frame is `source_pixels`. With a caller-supplied scale the frame is `fragment_local_mm`. The outline is an interpretation produced by the machine. A checksum mismatch prints `IntegrityFailure` and no polygon.

## Sub-features

- `segment-pixels` prints a source-pixel outline for a manifest hash.
- `segment-scale` prints a fragment-local millimetre outline when pixels per millimetre and uncertainty are both supplied.
- `segment-mismatch` prints `IntegrityFailure` and exits `1` when `--expected` does not match the file.
- `segment-scale-pair` exits `2` when only one of the two scale flags is present.

## How to get to it (user POV)

- Run `python -m prw.cli segment <path> --label <label> --foreground-threshold <int> --code-version <version>`.
- Add `--expected <sha256:digest>` to bind the hash.
- Add `--pixels-per-mm <float> --uncertainty <float>` together to scale the outline.

## Driving it with verify-prw

Preconditions:

- `verify-prw doctor` printed `doctor_ok=yes` for this root.
- [Generate a synthetic leaf](./generate.md) has completed `generate-write` in this scratch. If `$SCRATCH_IMAGES/image_manifest.json` has no fragment entry, stop and report that unmet precondition.

- **Choose the fragment.** Take the first fragment name from the manifest. Run `uv run python -c 'import json,sys; from pathlib import Path; images=json.loads(Path(sys.argv[1]).read_text())["images"]; item=next(image for image in images if image["role"]=="fragment"); print(item["name"]); print(item["content_hash"])' "$SCRATCH_IMAGES/image_manifest.json"`. Save the name as `FRAGMENT_NAME` and the hash as `FRAGMENT_HASH`. The file `$SCRATCH_IMAGES/$FRAGMENT_NAME` exists, and `sha256sum` of it matches `FRAGMENT_HASH`.
- **Pixel outline.** Segment in source pixels. Run `.cursor/skills/verify-prw/bin/verify-prw drive --feature segment --step pixels -- segment "$SCRATCH_IMAGES/$FRAGMENT_NAME" --label shelf-4 --foreground-threshold 1 --code-version "$CODE_VERSION" --expected "$FRAGMENT_HASH"`. Exit code `0`. Stdout is JSON with `record` `FragmentOutlineRevision`, `epistemic_class` `interpretation`, `producer` `machine`, `frame` `source_pixels`, and a `polygon` of at least three points. `envelope.algorithm_name` is `fragment_outline`, `envelope.algorithm_version` is `1`, `envelope.model_hash` is `absent`, and `envelope.source_hashes` is a one-item list of `FRAGMENT_HASH`. `random_seed` is absent. Stdout does not contain `correct_join`. Stderr is empty.
- **Millimetre outline.** Supply a scale. Run `.cursor/skills/verify-prw/bin/verify-prw drive --feature segment --step scale -- segment "$SCRATCH_IMAGES/$FRAGMENT_NAME" --label shelf-4 --foreground-threshold 1 --code-version "$CODE_VERSION" --expected "$FRAGMENT_HASH" --pixels-per-mm 2 --uncertainty 0`. Exit code `0`. `frame` is `fragment_local_mm`, `epistemic_class` is `interpretation`, `producer` is `machine`, and `envelope.algorithm_name` is `caller_supplied_scale`.
- **Checksum mismatch.** Run `.cursor/skills/verify-prw/bin/verify-prw drive --feature segment --step mismatch -- segment "$SCRATCH_IMAGES/$FRAGMENT_NAME" --label shelf-4 --foreground-threshold 1 --code-version "$CODE_VERSION" --expected "sha256:abababababababababababababababababababababababababababababababab"`. Exit code `1`. `record` is `IntegrityFailure`. Stdout does not contain `polygon`. `sha256sum` of the fragment file is still `FRAGMENT_HASH`.
- **Half a scale.** Run `.cursor/skills/verify-prw/bin/verify-prw drive --feature segment --step half-scale -- segment "$SCRATCH_IMAGES/$FRAGMENT_NAME" --label shelf-4 --foreground-threshold 1 --code-version "$CODE_VERSION" --pixels-per-mm 2`. Exit code `2`. Stdout is empty. Stderr contains `pixels_per_mm and uncertainty are supplied together`.

## Gotchas

- `--pixels-per-mm` and `--uncertainty` are supplied together or not at all. One without the other is exit `2`, not a scaled outline.
- For the synthetic leaf in [generate](./generate.md), `--foreground-threshold 1` keeps the painted samples. The flag is an integer from 0 through 255.
- The pixel outline's frame is `source_pixels`. The scaled outline's frame is `fragment_local_mm`. Do not accept a result that labels either outline `observed` or `hypothesis`.
- Segmentation of a fixture does not use a random seed. `random_seed` stays out of the envelope.
- `--label` is the caller's opaque label. The recipe uses `shelf-4`.
- A mismatch must not rewrite the TIFF. Compare `sha256sum` afterward.
