# Segment a lossless master

A classic lossless TIFF that is not the synthetic fixture layout prints a machine outline, and two such files can be ranked. The outline is an interpretation. Each join is a hypothesis. The TIFF bytes stay as they were.

## Sub-features

- `segment-master` prints a `source_pixels` outline with decoder `lossless_tiff`.
- `rank-masters` prints `physical_join_order` for two of those files.
- `master-unchanged` shows the segmented file's SHA-256 is the same after the command.

## How to get to it (user POV)

- Write two big-endian uncompressed grayscale TIFFs under the scratch directory. They are not the synthetic fixture layout.
- Run `prw segment PATH --label LABEL --foreground-threshold N --code-version CODE`.
- Run `prw rank` with one `--image LABEL PATH` flag per file and a scale pair.

## Driving it with verify-prw

Preconditions:

- Doctor prints `prw-verify doctor ok` for this run.
- `exports` has set `$RUN_ID`, `$CODE`, and `$SCRATCH`.

- **Write two masters.** Run this program. It writes `$SCRATCH/master-a.tif` and `$SCRATCH/master-b.tif`. Each file is an 8 by 8 big-endian uncompressed 8-bit grayscale TIFF. The image bytes sit before the IFD, so the file is not the synthetic fixture layout.

```bash
SCRATCH="$SCRATCH" uv run python - <<'PY'
import os
import struct
from pathlib import Path

scratch = Path(os.environ["SCRATCH"])

def master(level: int) -> bytes:
    samples = bytes([level]) * 64
    endian = ">"
    tags = {
        256: (4, (8,)),
        257: (4, (8,)),
        258: (3, (8,)),
        259: (3, (1,)),
        262: (3, (1,)),
        273: (4, (8,)),
        277: (3, (1,)),
        278: (4, (8,)),
        279: (4, (64,)),
    }
    entries = []
    for tag in sorted(tags):
        type_code, values = tags[tag]
        code = "I" if type_code == 4 else "H"
        raw = struct.pack(endian + (code * len(values)), *values)
        inline = raw + bytes(4 - len(raw))
        entries.append(struct.pack(endian + "HHI", tag, type_code, 1) + inline)
    ifd_at = 8 + len(samples)
    ifd = struct.pack(endian + "H", len(entries)) + b"".join(entries) + struct.pack(endian + "I", 0)
    header = b"MM\x00*" + struct.pack(endian + "I", ifd_at)
    return header + samples + ifd

(scratch / "master-a.tif").write_bytes(master(200))
(scratch / "master-b.tif").write_bytes(master(180))
PY
```

- **Record the hash.** Run `shasum -a 256 "$SCRATCH/master-a.tif"` and keep the digest.
- **Print an outline.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature segment-lossless-master --entry "prw segment lossless master" --step outline -- segment "$SCRATCH/master-a.tif" --label shelf-1 --foreground-threshold 1 --code-version "$CODE"`. Exit code `0`. stderr is empty. The JSON `record` is `FragmentOutlineRevision`, `epistemic_class` is `interpretation`, `producer` is `machine`, and `frame` is `source_pixels`. `polygon` has at least three positions. `envelope.decoder_name` is `lossless_tiff` and `envelope.decoder_version` is `1`. `envelope.algorithm_name` is `fragment_outline`. The `random_seed` key is absent. Stdout does not contain `UnsupportedFixtureLayout` or `correct_join`.
- **Hash the file again.** `shasum -a 256 "$SCRATCH/master-a.tif"` prints the same digest as the first reading.
- **Rank the two masters.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature segment-lossless-master --entry "prw rank two lossless masters" --step rank -- rank --image shelf-1 "$SCRATCH/master-a.tif" --image shelf-2 "$SCRATCH/master-b.tif" --foreground-threshold 1 --code-version "$CODE" --pixels-per-mm 10 --uncertainty 0.1`. Exit code `0`. stderr is empty. The JSON `record` is `physical_join_order`. `envelope.decoder_name` is `lossless_tiff`. Every `epistemic_class` is `hypothesis`. Every `channel` is `physical`. Stdout does not contain `UnsupportedFixtureLayout` or `correct_join`.
- **Proof.** The evidence directory contains `outline` and `rank`. The two `shasum` readings match.

## Gotchas

- The scratch files are outside the checkout. A TIFF path inside the checkout is refused by the harness.
- `--foreground-threshold 1` matches these solid rectangles. It is not a threshold selected for a photograph.
- `--pixels-per-mm` and `--uncertainty` are supplied together. Rank without them can print `FailedPairwiseJoin`.
- A generated fixture TIFF uses decoder `synthetic_uncompressed_tiff`. Do not put one of those files in the same rank pool as these masters.
- The printed outline does not include the label `shelf-1`.
