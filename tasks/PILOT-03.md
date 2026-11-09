# Task ticket

- Status: Done
- Phase: P1

A **yes** on any stop-and-ask field means the ticket waits until an ADR and an explicit decision exist. Open questions are indexed in [OPEN_QUESTIONS.md](../docs/OPEN_QUESTIONS.md). The glossary is in [DATA_MODEL.md](../docs/DATA_MODEL.md#glossary).

## Title

Read classic lossless TIFF masters that are not the synthetic fixture layout.

## Phase

P1, unblocking the public-image pilot. The outline and rank commands already exist.

## Problem

`prw verify` checksums a publisher TIFF. `segment` and `rank` then return `UnsupportedFixtureLayout` because the file is not the synthetic uncompressed grayscale layout. [Q-ENG-05](../docs/OPEN_QUESTIONS.md#q-eng-05) asked which TIFF library is allowed.

## User or scientific outcome

An operator can checksum a license-reviewed TIFF kept outside Git and pass it to `segment` and `rank` when its layout is one this decoder accepts. A refusal names the layout problem. It is not an outline and not a join. No manuscript image is committed.

## Epistemic-class impact

no. A decoded raster is input to the existing outline algorithm. The outline stays `interpretation` with producer `machine`. A join stays a hypothesis. Grayscale reduction is decoder provenance, not a reading and not a calibration. Header resolution is not `pixels_per_mm`.

## Stop and ask

- Changes a public API: no. Command names stay unfrozen. [ADR-0014](../docs/adr/0014-stdlib-lossless-tiff.md) records the decoder and the `TiffDecodeFailure` record.
- Changes the project format: no
- Changes the privacy policy ([SECURITY_AND_PRIVACY.md](../docs/SECURITY_AND_PRIVACY.md)): no
- Changes evidence semantics (text status, epistemic class, or the meaning of a hypothesis): no

## Schema impact

none. No project database is written.

## Algorithm and benchmark impact

none for `fragment_outline` on the synthetic fixture. Those bytes still use decoder `synthetic_uncompressed_tiff` version `1`, and the trace is unchanged, so no benchmark comparison is published. The new decoder does not read `benchmarks/`.

## New dependencies

none. `struct` and `zlib` are in the Python standard library. Reason and license are in [ADR-0014](../docs/adr/0014-stdlib-lossless-tiff.md).

## Acceptance criteria

- [x] A classic lossless TIFF that is not the fixture layout decodes to 8-bit grayscale without `UnsupportedFixtureLayout`.
- [x] `segment` and `rank` use that raster. Fixture files still record `synthetic_uncompressed_tiff` version `1`.
- [x] JPEG-in-TIFF, other non-lossless or unsupported layouts, and oversized images return `TiffDecodeFailure` and no polygon.
- [x] `verify` still hashes classic TIFF magic and does not decode pixels.
- [x] Tests build tiny synthetic TIFFs in memory. No publisher image is committed.
- [x] Q-ENG-05, the ADR, the roadmap, and the import-path note match this behavior.

## Tests

Synthetic bytes only. Cover uncompressed big-endian grayscale, RGB luminance, palette, WhiteIsZero, 1-bit, 16-bit, predictor, strips, tiles, planar, PackBits, deflate, LZW, a skipped thumbnail, an ignored resolution tag, and each refusal kind. One CLI `segment` and one CLI `rank` use files under `tmp_path`.

## Provenance effects

`decoder_name` and `decoder_version` are `lossless_tiff` and `1` when the fixture layout does not match, and the fixture pair otherwise. `random_seed` stays omitted. Source hashes, the parameter blob, algorithm name and version, model hash, and code version are unchanged in role.

## Non-goals

- HTR, Qt, and a project format.
- A find-site, a language, a reading, or an accuracy claim on a real manuscript.
- BigTIFF, JPEG, JPEG 2000, CCITT, CMYK, and YCbCr.
- Applying orientation, ICC profiles, or transfer curves.
- Choosing `--foreground-threshold` for a photograph.

## Open questions this depends on

[Q-ENG-05](../docs/OPEN_QUESTIONS.md#q-eng-05) is closed here. [Q-ENG-01](../docs/OPEN_QUESTIONS.md#q-eng-01) and [Q-SCI-15](../docs/OPEN_QUESTIONS.md#q-sci-15) stay open.
