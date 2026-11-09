# ADR 0014: Standard-library lossless TIFF

- Status: Accepted
- Date: 2026-11-09

## Context

Source images are lossless TIFF. [Q-ENG-05](../OPEN_QUESTIONS.md#q-eng-05) asked which TIFF library is allowed, including its license. The options were the Python standard library where it is sufficient, or a documented library chosen with its license. Pixel commands could read only the synthetic uncompressed grayscale layout. A publisher TIFF failed as `UnsupportedFixtureLayout` before any outline existed.

The product rule is unchanged: masters are lossless TIFF, source bytes are immutable, and a header resolution is not `pixels_per_mm`. Epistemic class is unchanged. A detected outline stays `interpretation` with producer `machine`. A join stays a hypothesis.

## Decision

No new runtime dependency. Classic lossless TIFF is read with `struct` and `zlib` from the Python standard library. The license is the Python license already used to run this package.

- Decoder `synthetic_uncompressed_tiff` version `1` remains the reader for the synthetic fixture layout. Provenance for those bytes stays on that name.
- Decoder `lossless_tiff` version `1` reads every other accepted master. `segment`, `edge`, `rank`, `recall`, `assemble`, `assembly-rank`, `placement-error`, and `join-presence` use it when the fixture layout does not match.
- `prw verify` still hashes bytes and checks classic TIFF magic `II*\x00` or `MM\x00*`. It does not decode pixels. BigTIFF magic is `UnsupportedMediaType`.
- Accepted: little- or big-endian classic TIFF; the first full-resolution IFD; strips or tiles; chunky or planar; compression none (including 32771), PackBits, TIFF LZW, and zlib deflate (8 and 32946); predictor none or horizontal at 8 or 16 bits; photometric WhiteIsZero, BlackIsZero, RGB, and palette at 1 or 8 bits; unsigned samples at 1, 8, or 16 bits. Extra samples are dropped. Associated alpha is not un-premultiplied.
- The samples given to the outline algorithm are 8-bit, row-major, and BlackIsZero. 16-bit samples keep the high byte. 1-bit samples expand to 0 or 255. RGB and palette use integer weights `(19595, 38470, 7471)` with rounding bias 32768. That reduction is this decoder. It is not a color measurement, not a reading, and not a calibration.
- Tags 274, 282, and 283 are not applied. Orientation is storage order. A resolution tag is not `pixels_per_mm`.
- A side may be at most 200,000 pixels. The image may be at most 400,000,000 pixels.
- A refusal is `TiffDecodeFailure`. The kind is `not_tiff`, `bigtiff`, `jpeg_compression`, `unsupported_compression`, `unsupported_photometric`, `unsupported_bits`, `oversized`, or `inconsistent`. JPEG compression inside TIFF, including a lossless JPEG mode, is `jpeg_compression`. CCITT, JPEG 2000, WebP, CMYK, and YCbCr are refused. There is no polygon and no epistemic class. The bytes are not modified.
- One rank pool must share one decoder name and version.

## Consequences

- [Q-ENG-05](../OPEN_QUESTIONS.md#q-eng-05) is closed. [PILOT-03](../../tasks/PILOT-03.md) is the implementation.
- A publisher TIFF outside the checkout can be checksummed and, when its layout is accepted, passed to `segment` and `rank`. The outline algorithm can still fail after a successful decode. `--foreground-threshold` stays caller-supplied.
- Fixture provenance does not change, so this decision is not an algorithm change of `fragment_outline` and does not publish a new benchmark comparison. Solver paths still do not read `benchmarks/`.
- No find-site, language, or accuracy claim follows from decoding a real file. [Q-SCI-15](../OPEN_QUESTIONS.md#q-sci-15) stays open for that.
- [Q-ENG-01](../OPEN_QUESTIONS.md#q-eng-01) stays open. The CLI still does not write `originals/` or `manifest.json`.

## Related

- [ADR 0004](0004-immutable-sources-and-provenance.md)
- [DATA_MODEL.md](../DATA_MODEL.md#sourceimage)
- [pilot-import-path.md](../pilot-import-path.md)
