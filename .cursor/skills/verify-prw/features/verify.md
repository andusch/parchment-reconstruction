# Verify a fixture image

Verify hashes one presented TIFF and prints `VerifiedBytes` or an `IntegrityFailure`. A path that is not a file exits with an error on stderr. When the sibling `image_manifest.json` lists fragment files, that error names them. The TIFF bytes stay as they were.

## Sub-features

- `verify-match` prints `VerifiedBytes` for the manifest hash, and for a call with no `--expected`.
- `verify-mismatch` prints `IntegrityFailure` and exits `1` when `--expected` differs. It does not rewrite the file.
- `verify-missing` exits `2` and lists the fragment file names from the sibling image manifest.

## How to get to it (user POV)

- Run `python -m prw.cli verify <path>`.
- Run `python -m prw.cli verify <path> --expected <sha256:digest>`.

## Driving it with verify-prw

Preconditions:

- `verify-prw doctor` printed `doctor_ok=yes` for this root.
- [Generate a synthetic leaf](./generate.md) has already completed `generate-write` in this scratch. `$SCRATCH_IMAGES/page.tif` and `$SCRATCH_IMAGES/image_manifest.json` exist. If they do not, stop and report that unmet precondition. Do not invent image bytes.

- **Read the manifest hash.** Take the `page` entry from the image manifest. Run `uv run python -c 'import json,sys; from pathlib import Path; images=json.loads(Path(sys.argv[1]).read_text())["images"]; print(next(item["content_hash"] for item in images if item["name"]=="page.tif"))' "$SCRATCH_IMAGES/image_manifest.json"`. The printed line starts with `sha256:`. Independently, `sha256sum "$SCRATCH_IMAGES/page.tif"` prints the same hex after that prefix. Save the full `sha256:` value as `PAGE_HASH`.
- **Match the manifest.** Check the page against that hash. Run `.cursor/skills/verify-prw/bin/verify-prw drive --feature verify --step match -- verify "$SCRATCH_IMAGES/page.tif" --expected "$PAGE_HASH"`. Exit code `0`. Stdout is JSON with `record` `VerifiedBytes`, `content_hash` equal to `PAGE_HASH`, and `media_type` present. Stdout does not contain `hypothesis` or `correct_join`. Stderr is empty.
- **Hash without an expected value.** Run `.cursor/skills/verify-prw/bin/verify-prw drive --feature verify --step bare -- verify "$SCRATCH_IMAGES/page.tif"`. Exit code `0`. `content_hash` is still `PAGE_HASH`.
- **Confirm the file was not rewritten.** Run `sha256sum "$SCRATCH_IMAGES/page.tif"` again. The hex still matches `PAGE_HASH`.
- **Mismatch.** Ask for a digest the file does not have. Run `.cursor/skills/verify-prw/bin/verify-prw drive --feature verify --step mismatch -- verify "$SCRATCH_IMAGES/page.tif" --expected "sha256:abababababababababababababababababababababababababababababababab"`. Exit code `1`. Stdout is JSON with `record` `IntegrityFailure`, `expected_hash` equal to that argument, and `presented_hash` equal to `PAGE_HASH`. Stdout does not contain `hypothesis`, `correct_join`, or `polygon`. `sha256sum` of `page.tif` is still `PAGE_HASH`.
- **Missing path.** Ask for a file the manifest does not have. Run `.cursor/skills/verify-prw/bin/verify-prw drive --feature verify --step missing -- verify "$SCRATCH_IMAGES/not-a-page.tif"`. Exit code `2`. Stdout is empty. Stderr contains the missing path, `Fragment files:`, and every `fragment-*.tif` name listed in `image_manifest.json`. Stderr does not contain `Traceback`.

## Gotchas

- Exit `1` still prints JSON on stdout. Exit `2` prints nothing on stdout.
- Read the expected hash from `image_manifest.json` or from the generate stdout. Do not open `labels.json`. Verify does not consult the BenchmarkLabel store.
- A checksum mismatch must leave the TIFF unchanged. Compare `sha256sum` before and after.
- `not-a-page.tif` is a missing path beside a real manifest. A missing path whose parent has no manifest says the path is not a fixture image and does not include `Fragment files:`.
- The harness rejects a TIFF path inside the git checkout. Keep the file under `$SCRATCH_IMAGES`.
