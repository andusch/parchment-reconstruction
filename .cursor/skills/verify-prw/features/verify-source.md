# Verify a source image

Verify a source image hashes a TIFF from the terminal and prints `VerifiedBytes`, an `IntegrityFailure`, or `UnsupportedMediaType`. The TIFF bytes stay as they were.

## Sub-features

- `verify-match` accepts the manifest hash and prints `VerifiedBytes`.
- `verify-repeat` prints that same record again.
- `verify-mismatch` prints `IntegrityFailure` for a different expected hash and leaves the file hash unchanged.
- `verify-unsupported` rejects bytes that are not a TIFF.
- `verify-missing` reports a path that is not in the image directory.

## How to get to it (user POV)

- Run `prw verify PATH` in a terminal.
- Run `prw verify PATH --expected sha256:DIGEST` in a terminal.

## Driving it with verify-prw

Preconditions:

- Doctor prints `prw-verify doctor ok` for this run.
- `exports` has set `$RUN_ID`, `$PAGE`, `$PAGE_HASH`, `$PAGE_BYTES`, `$IMAGES`, and `$SCRATCH`.
- The doctor `fragments` line lists every seeded fragment file name.

- **Match the recorded hash.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature verify-source --entry "prw verify page --expected page_hash" --step matched -- verify "$PAGE" --expected "$PAGE_HASH"`. Exit code `0`. stderr is empty. The JSON `record` is `VerifiedBytes`, `content_hash` equals `$PAGE_HASH`, `byte_length` equals `$PAGE_BYTES`, and `media_type` is `image/tiff`. The stdout text does not contain `hypothesis` or `correct_join`.
- **Read the manifest.** Open `$IMAGES/image_manifest.json`. The `page` entry named `page.tif` has the same `content_hash` and `byte_length` as that `VerifiedBytes` object.
- **Repeat the match.** Run the same command with `--step repeat`. Exit code `0`. `stdout.txt` is byte-for-byte the same as `artifacts/verify-source/$RUN_ID/matched/stdout.txt`.
- **Present a different hash.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature verify-source --entry "prw verify page --expected wrong hash" --step mismatch -- verify "$PAGE" --expected "sha256:abababababababababababababababababababababababababababababababab"`. Exit code `1`. The JSON `record` is `IntegrityFailure`, `presented_hash` equals `$PAGE_HASH`, and `expected_hash` is the supplied digest. The object has no `polygon` key. The stdout text does not contain `hypothesis` or `correct_join`.
- **Hash the file again.** Run the matched command with `--step unchanged`. Exit code `0`. `stdout.txt` matches the matched step. The mismatch did not rewrite the TIFF.
- **Reject a non-TIFF.** Write `not-a-tiff` and a trailing newline to `$SCRATCH/not-a-tiff.txt` with `printf 'not-a-tiff\n' > "$SCRATCH/not-a-tiff.txt"`. Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature verify-source --entry "prw verify non-tiff" --step unsupported -- verify "$SCRATCH/not-a-tiff.txt"`. Exit code `1`. The JSON `record` is `UnsupportedMediaType` and `byte_length` is `11`. Run the same command with `--step unsupported-repeat`. Exit code `1`, and `presented_hash` equals the first unsupported transcript.
- **Ask for a missing name.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature verify-source --entry "prw verify missing fragment" --step missing -- verify "$IMAGES/fragment-0.tif"`. Exit code `2`. stdout is empty. stderr contains that path, the text `Fragment files:`, and every name on the doctor `fragments` line. stderr does not contain `Traceback`.
- **Proof.** The evidence directory for `verify-source` and this run id contains `matched`, `repeat`, `mismatch`, `unchanged`, `unsupported`, `unsupported-repeat`, and `missing`.

## Gotchas

- An `IntegrityFailure` `id` and `timestamp` change on every mismatch. Compare `presented_hash` and `expected_hash`.
- `fragment-0.tif` is not a generated file name. The missing-path error lists the manifest fragment names.
- `UnsupportedMediaType` is exit `1` and is a different record from `IntegrityFailure`.
- Two matching `verify` transcripts are identical. A mismatch transcript is not identical to the next mismatch transcript.
- Passing `$PAGE_HASH` with a fragment path, or a fragment hash with `$PAGE`, is a checksum mismatch.
- The harness refuses `data/`, `scans/`, `real_data/`, and any TIFF path inside the checkout.
